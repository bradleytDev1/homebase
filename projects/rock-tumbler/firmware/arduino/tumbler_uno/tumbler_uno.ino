/* ===========================================================================
 * tumbler_uno.ino -- Rock tumbler controller for Arduino Uno / Nano / Pro Mini
 *
 * WHY THIS EXISTS
 *   The Pico/TMC2209 version in ../../main.py leans on the TMC2209's internal
 *   step generator (VACTUAL): write a velocity, walk away. Classic drivers --
 *   A4988, DRV8825, TB6600 -- have no such thing. They want STEP pulses.
 *
 *   The good news is that STEP/DIR is a universal interface. This one sketch
 *   drives any of them, and an ATmega328 has its own equivalent of VACTUAL
 *   hiding in the datasheet: Timer1 in CTC mode with hardware pin toggle.
 *   Configure three registers and the silicon emits a rock-steady square wave
 *   on pin 9 forever, with the CPU completely uninvolved. Same architectural
 *   win, different chip.
 *
 * THE TRAP THIS AVOIDS
 *   The obvious approach is AccelStepper in a loop. Don't. On a 16 MHz AVR it
 *   tops out around 4,000 steps/s because runSpeed() does floating-point work
 *   every pulse. This machine needs ~8,960 steps/s at 1/16 microstepping. You
 *   would get a barrel that runs at half speed, stutters, and gets slower
 *   whenever the serial port is busy. Timer1 is both faster and simpler.
 *
 * WIRING (Uno / Nano)
 *   D9  -> driver STEP    (MUST be D9: it is OC1A, the hardware toggle output)
 *   D8  -> driver DIR
 *   D7  -> driver ENABLE  (active low on A4988/DRV8825)
 *   D2  <- hall sensor or reed switch  (INT0; magnet on the barrel end cap)
 *   Driver logic 5V from the Arduino, motor supply separate, GROUNDS COMMON.
 *
 *   A4988/DRV8825: set microstep mode pins for 1/16 (MS1/MS2/MS3 all high on
 *   an A4988). Set the current trimpot LOW -- see the README for the Vref
 *   formulas. Factory-default Vref will cook both driver and motor over a
 *   six-week run, and you need about a quarter of it.
 *
 *   TB6600: opto-isolated, so tie PUL+/DIR+/EN+ to 5V and drive PUL-/DIR-/EN-
 *   from the Arduino pins (the pins sink the opto current). Current is set by
 *   DIP switches; choose the lowest setting your motor will start on.
 *
 * TWO BUGS THIS SKETCH IS WRITTEN AROUND
 *   1. millis() rolls over at 49.7 days. A four-stage campaign runs far longer
 *      than that, and a single stage at 42 days comes uncomfortably close. All
 *      timing here uses the rollover-safe idiom (uint32_t)(now - then) >= gap,
 *      which is correct across the wrap. Comparing timestamps directly is not.
 *   2. float on AVR is 32-bit: 24 bits of mantissa, so integers above ~16.7
 *      million stop being exact. Accumulating microsteps in a float would
 *      silently stop counting after half an hour. All dose arithmetic here is
 *      integer; floats appear only in one-off setup maths and in ratios.
 * ===========================================================================
 */

#include <avr/eeprom.h>
#include <avr/interrupt.h>

/* --- PINS ---------------------------------------------------------------- */
const uint8_t PIN_STEP = 9;     /* OC1A -- do not move this one */
const uint8_t PIN_DIR  = 8;
const uint8_t PIN_EN   = 7;     /* active low */
const uint8_t PIN_HALL = 2;     /* INT0 */

/* --- MACHINE (from tools/tumbler_calc.py) -------------------------------- */
const float    BARREL_OD_MM = 112.0;   /* outside dia: what touches the rollers */
const float    ROLLER_OD_MM = 40.0;    /* outside dia including the tyre        */
const float    GEAR_RATIO   = 1.0;     /* motor revs per roller rev             */
const uint16_t FULL_STEPS   = 200;     /* 1.8 degree motor                      */
const uint8_t  MICROSTEPS   = 16;      /* must match the driver's mode pins     */

/* Barrel speed, in tenths of an rpm, kept integer so the dose maths below
 * never touches a float. 602 = 60.2 rpm = 45% of critical for a 100 mm barrel. */
const uint16_t TARGET_RPM_X10 = 602;

/* --- BEHAVIOUR ----------------------------------------------------------- */
const uint16_t RAMP_MS        = 8000;  /* soft start duration                  */
const uint8_t  RAMP_STEPS     = 40;
const uint32_t REVERSE_SEC    = 6UL * 3600UL;  /* flip direction this often; 0 = never */
const uint8_t  SLIP_FAULT_PCT = 40;    /* stop above this much slip            */
const uint8_t  SLIP_WARN_PCT  = 15;
const uint8_t  MAGNETS_PER_REV = 1;
const uint16_t HALL_DEBOUNCE_MS = 50;  /* reed switches bounce; hall sensors do not */
const uint32_t SAVE_EVERY_REVS  = 500;
const uint32_t REPORT_EVERY_SEC = 60;

/* Stage doses in barrel revolutions. At 60 rpm, 600k revolutions is about a
 * week -- but revolutions, not days, are what abrasive wear actually tracks. */
const uint8_t  N_STAGES = 4;
const uint32_t STAGE_REVS[N_STAGES] = { 600000UL, 600000UL, 600000UL, 600000UL };
const char* const STAGE_NAME[N_STAGES] = {
  "1 coarse  60/90 SiC",
  "2 medium  120/220 SiC",
  "3 pre-polish 500 SiC",
  "4 polish  cerium oxide"
};

/* ===========================================================================
 * TIMER1 -- hardware step generation
 *
 * CTC mode with COM1A0 set toggles OC1A (pin D9) on every compare match, so
 * the output frequency is
 *
 *     f = F_CPU / (2 * N * (1 + OCR1A))          N = prescaler
 *
 * With N = 1 that covers 122 Hz to 8 MHz, which swallows our 7-22 kHz working
 * range whole. Each rising edge is one microstep. The CPU does nothing.
 * ===========================================================================
 */

/* ---------------------------------------------------------------------------
 * ocr_for_hz -- OCR1A value that produces the requested step frequency.
 *   Inputs:  hz (float) -- desired step rate, Hz. Values outside the timer's
 *                          range are clamped rather than wrapping.
 *   Returns: uint16_t   -- value to load into OCR1A.
 * ------------------------------------------------------------------------ */
uint16_t ocr_for_hz(float hz) {
  if (hz < 1.0) hz = 1.0;
  float v = ((float)F_CPU / (2.0 * hz)) - 1.0;
  if (v < 1.0)     v = 1.0;
  if (v > 65535.0) v = 65535.0;
  return (uint16_t)(v + 0.5);
}

/* ---------------------------------------------------------------------------
 * hz_for_ocr -- the frequency a given OCR1A actually produces.
 *   Quantisation matters: we trim the machine against measured revolutions, so
 *   it helps to know what we really asked for rather than what we wanted.
 *   Inputs:  ocr (uint16_t) -- register value.
 *   Returns: float          -- realised step rate, Hz.
 * ------------------------------------------------------------------------ */
float hz_for_ocr(uint16_t ocr) {
  return (float)F_CPU / (2.0 * ((float)ocr + 1.0));
}

/* ---------------------------------------------------------------------------
 * timer1_begin -- put Timer1 into CTC toggle mode, stopped.
 *   Inputs:  none.  Returns: void.
 * ------------------------------------------------------------------------ */
void timer1_begin(void) {
  uint8_t s = SREG;
  cli();
  TCCR1A = 0;
  TCCR1B = 0;
  TCNT1  = 0;
  TCCR1A |= (1 << COM1A0);   /* toggle OC1A on compare match */
  TCCR1B |= (1 << WGM12);    /* CTC, TOP = OCR1A             */
  OCR1A   = 65535;           /* start as slow as possible    */
  SREG = s;
}

/* ---------------------------------------------------------------------------
 * timer1_set_hz -- change the step frequency while running.
 *
 *   Gotcha worth the four extra lines: in CTC mode, writing an OCR1A value
 *   BELOW the current TCNT1 means the compare match is missed, and the counter
 *   runs all the way to 0xFFFF before wrapping -- a 4 ms hole in the step
 *   train. During a soft-start ramp that is a visible stutter. Resetting TCNT1
 *   when we lower the target closes it.
 *
 *   Inputs:  hz (float) -- desired step rate, Hz.
 *   Returns: uint16_t   -- the OCR1A value written.
 * ------------------------------------------------------------------------ */
uint16_t timer1_set_hz(float hz) {
  uint16_t o = ocr_for_hz(hz);
  uint8_t s = SREG;
  cli();                       /* OCR1A is 16-bit: the two byte writes must
                                * not be split by an interrupt */
  OCR1A = o;
  if (TCNT1 > o) TCNT1 = 0;
  SREG = s;
  return o;
}

/* ---------------------------------------------------------------------------
 * timer1_run / timer1_halt -- start and stop the pulse train.
 *   Inputs:  none.  Returns: void.
 * ------------------------------------------------------------------------ */
void timer1_run(void)  { TCCR1B |= (1 << CS10); }                 /* presc. 1 */
void timer1_halt(void) { TCCR1B &= ~((1 << CS12) | (1 << CS11) | (1 << CS10)); }

/* ---------------------------------------------------------------------------
 * step_hz_for_rpm -- barrel rpm to microstep frequency.
 *   Friction drive preserves surface speed, so the roller turns faster than
 *   the barrel by the diameter ratio; the belt then scales motor to roller.
 *   Inputs:  rpm_x10 (uint16_t) -- barrel speed in tenths of an rpm.
 *   Returns: float              -- microsteps per second.
 * ------------------------------------------------------------------------ */
float step_hz_for_rpm(uint16_t rpm_x10) {
  float barrel_rpm = rpm_x10 / 10.0;
  float roller_rpm = barrel_rpm * BARREL_OD_MM / ROLLER_OD_MM;
  float motor_rpm  = roller_rpm * GEAR_RATIO;
  return motor_rpm * (float)FULL_STEPS * (float)MICROSTEPS / 60.0;
}

/* ===========================================================================
 * ODOMETER -- persistent revolution count in EEPROM
 *
 * The dose lives here, so it has to survive power cuts. Two wrinkles:
 *   - EEPROM endures ~100,000 writes per cell. Saving every 500 revolutions is
 *     ~4,800 writes per four-stage campaign, which would wear a fixed location
 *     out in about twenty campaigns. A 32-slot ring spreads that to hundreds.
 *   - A power cut mid-write corrupts one slot, so every record carries a
 *     checksum and boot picks the newest slot that still verifies.
 * ===========================================================================
 */

const uint8_t  RING_SLOTS = 32;
const uint16_t RING_BASE  = 0;

typedef struct __attribute__((packed)) {
  uint8_t  stage;
  uint32_t pulses;
  uint16_t seq;
  uint8_t  sum;
} Record;   /* 8 bytes */

volatile uint32_t g_pulses   = 0;    /* written by the ISR */
volatile uint32_t g_lastHall = 0;

uint8_t  g_stage    = 0;
uint16_t g_seq      = 0;
uint8_t  g_slot     = 0;
uint32_t g_lastSave = 0;

/* ---------------------------------------------------------------------------
 * rec_sum -- checksum over a record's payload.
 *   Inputs:  r (const Record*) -- record to summarise.
 *   Returns: uint8_t           -- checksum byte (never 0xFF, so an erased
 *            EEPROM cell full of 0xFF can never masquerade as valid).
 * ------------------------------------------------------------------------ */
uint8_t rec_sum(const Record* r) {
  uint8_t s = 0x5A;
  s ^= r->stage;
  s ^= (uint8_t)(r->pulses);
  s ^= (uint8_t)(r->pulses >> 8);
  s ^= (uint8_t)(r->pulses >> 16);
  s ^= (uint8_t)(r->pulses >> 24);
  s ^= (uint8_t)(r->seq);
  s ^= (uint8_t)(r->seq >> 8);
  return (s == 0xFF) ? 0xFE : s;
}

/* ---------------------------------------------------------------------------
 * odo_load -- scan the ring and restore the newest valid record.
 *   Sequence numbers are compared as signed differences so the comparison
 *   stays correct when seq wraps past 65535.
 *   Inputs:  none.
 *   Returns: void. Sets g_stage, g_pulses, g_seq, g_slot.
 * ------------------------------------------------------------------------ */
void odo_load(void) {
  Record r;
  bool found = false;
  uint16_t best = 0;
  uint8_t  bestSlot = 0;
  Record   bestRec;

  for (uint8_t i = 0; i < RING_SLOTS; i++) {
    eeprom_read_block(&r, (const void*)(RING_BASE + i * sizeof(Record)), sizeof(Record));
    if (r.sum != rec_sum(&r)) continue;
    if (!found || (int16_t)(r.seq - best) > 0) {
      found = true; best = r.seq; bestSlot = i; bestRec = r;
    }
  }

  if (found) {
    g_stage = bestRec.stage;
    g_pulses = bestRec.pulses;
    g_seq = bestRec.seq;
    g_slot = bestSlot;
  } else {
    g_stage = 0; g_pulses = 0; g_seq = 0; g_slot = 0;
  }
  g_lastSave = g_pulses;
}

/* ---------------------------------------------------------------------------
 * odo_pulses -- raw magnet-pass count, read atomically.
 *   The ISR writes g_pulses as a 32-bit value, which the AVR cannot read in
 *   one instruction; without the guard, a read that straddles an increment can
 *   return a value that was never true.
 *   Inputs:  none.
 *   Returns: uint32_t -- pulses this stage.
 * ------------------------------------------------------------------------ */
uint32_t odo_pulses(void) {
  uint32_t p;
  uint8_t s = SREG; cli();
  p = g_pulses;
  SREG = s;
  return p;
}

/* ---------------------------------------------------------------------------
 * odo_save -- write the current dose into the next ring slot.
 *   Inputs:  none.
 *   Returns: void.
 * ------------------------------------------------------------------------ */
void odo_save(void) {
  Record r;
  r.pulses = odo_pulses();
  r.stage = g_stage;
  r.seq   = ++g_seq;
  r.sum   = rec_sum(&r);
  g_slot  = (uint8_t)((g_slot + 1) % RING_SLOTS);
  eeprom_update_block(&r, (void*)(RING_BASE + g_slot * sizeof(Record)), sizeof(Record));
  g_lastSave = r.pulses;
}

/* ---------------------------------------------------------------------------
 * odo_revs -- measured barrel revolutions this stage.
 *   Inputs:  none.
 *   Returns: uint32_t -- revolutions (pulses divided by magnets fitted).
 * ------------------------------------------------------------------------ */
uint32_t odo_revs(void) {
  return odo_pulses() / (MAGNETS_PER_REV < 1 ? 1 : MAGNETS_PER_REV);
}

/* ---------------------------------------------------------------------------
 * hall_isr -- one magnet pass. Debounced, allocation-free, no Serial.
 *   Inputs:  none (interrupt context).
 *   Returns: void.
 * ------------------------------------------------------------------------ */
void hall_isr(void) {
  uint32_t now = millis();
  if ((uint32_t)(now - g_lastHall) < HALL_DEBOUNCE_MS) return;
  g_lastHall = now;
  g_pulses++;
}

/* ===========================================================================
 * CONTROL
 * ===========================================================================
 */

int8_t   g_dir       = 1;
bool     g_running   = false;
uint32_t g_runSec    = 0;     /* seconds actually spent turning, integer */
uint32_t g_tPrevSec  = 0;
uint32_t g_tReverse  = 0;
uint32_t g_tReport   = 0;
float    g_stepHz    = 0;

/* ---------------------------------------------------------------------------
 * expected_revs -- barrel revolutions the machine believes it commanded.
 *
 *   Pure integer: revs = runSec * rpm_x10 / 600. A stage is about 600,000
 *   seconds, so the product peaks near 3.6e8 and never threatens a uint32.
 *   Done in float, this would have quietly stopped counting after half an hour.
 *
 *   Inputs:  none.
 *   Returns: uint32_t -- expected revolutions.
 * ------------------------------------------------------------------------ */
uint32_t expected_revs(void) {
  return (g_runSec * (uint32_t)TARGET_RPM_X10) / 600UL;
}

/* ---------------------------------------------------------------------------
 * slip_pct -- percentage of commanded rotation the barrel did not deliver.
 *
 *   0 means perfect traction. A slow climb over days means grit or water on
 *   the tyres. A jump toward 100 means the barrel has stopped while the motor
 *   spins on -- the failure that otherwise wastes a week of grinding unseen.
 *
 *   Inputs:  none.
 *   Returns: uint8_t -- 0..100, and 0 until there is enough data to judge.
 * ------------------------------------------------------------------------ */
uint8_t slip_pct(void) {
  uint32_t exp = expected_revs();
  if (exp < 10UL) return 0;
  uint32_t got = odo_revs();
  if (got >= exp) return 0;
  return (uint8_t)(((exp - got) * 100UL) / exp);
}

/* ---------------------------------------------------------------------------
 * ramp_to -- soft start, ramping the step frequency up from rest.
 *
 *   Slamming a full, sloshing barrel from zero to speed breaks traction; a
 *   barrel that slips every start wears a flat band into the tyres.
 *
 *   Inputs:  target_hz (float) -- final step rate, Hz.
 *   Returns: void.
 * ------------------------------------------------------------------------ */
void ramp_to(float target_hz) {
  timer1_set_hz(target_hz * 0.1);
  timer1_run();
  for (uint8_t i = 1; i <= RAMP_STEPS; i++) {
    float f = target_hz * (0.1 + 0.9 * ((float)i / (float)RAMP_STEPS));
    timer1_set_hz(f);
    delay(RAMP_MS / RAMP_STEPS);
  }
  timer1_set_hz(target_hz);
  g_running = true;
}

/* ---------------------------------------------------------------------------
 * start_motion -- energise the driver and ramp up in the current direction.
 *   Inputs:  none.  Returns: void.
 * ------------------------------------------------------------------------ */
void start_motion(void) {
  digitalWrite(PIN_DIR, g_dir > 0 ? HIGH : LOW);
  digitalWrite(PIN_EN, LOW);          /* active low */
  delayMicroseconds(10);              /* DIR setup, far beyond any driver's need */
  ramp_to(g_stepHz);
}

/* ---------------------------------------------------------------------------
 * stop_motion -- halt the pulse train, leaving the driver energised.
 *   Inputs:  none.  Returns: void.
 * ------------------------------------------------------------------------ */
void stop_motion(void) {
  timer1_halt();
  g_running = false;
}

/* ---------------------------------------------------------------------------
 * reverse_motion -- flip direction through a controlled stop.
 *   Reversing every few hours stops the load packing into one channel and
 *   wears the tyres and barrel evenly. No hobby tumbler with a shaded-pole
 *   motor can do this at all.
 *   Inputs:  none.  Returns: void.
 * ------------------------------------------------------------------------ */
void reverse_motion(void) {
  stop_motion();
  delay(2000);
  g_dir = -g_dir;
  start_motion();
  g_tReverse = millis();
}

/* ---------------------------------------------------------------------------
 * fault_stop -- stop everything and de-energise, then latch.
 *   Inputs:  msg (const char*) -- what went wrong.
 *   Returns: void. Does not return to normal operation.
 * ------------------------------------------------------------------------ */
void fault_stop(const char* msg) {
  stop_motion();
  digitalWrite(PIN_EN, HIGH);      /* drop the coils: no heat, no torque */
  odo_save();
  Serial.print(F("FAULT: "));
  Serial.println(msg);
  for (;;) { delay(1000); }
}

/* ---------------------------------------------------------------------------
 * report -- one status line.
 *   Inputs:  none.  Returns: void.
 * ------------------------------------------------------------------------ */
void report(void) {
  uint32_t got = odo_revs();
  uint32_t tgt = (g_stage < N_STAGES) ? STAGE_REVS[g_stage] : 0;
  Serial.print(STAGE_NAME[g_stage < N_STAGES ? g_stage : N_STAGES - 1]);
  Serial.print(F("  "));
  Serial.print(got);
  Serial.print('/');
  Serial.print(tgt);
  Serial.print(F(" rev  "));
  Serial.print(tgt ? (uint8_t)((got * 100UL) / tgt) : 100);
  Serial.print(F("%  dir "));
  Serial.print(g_dir > 0 ? '+' : '-');
  Serial.print(F("  slip "));
  Serial.print(slip_pct());
  Serial.println('%');
}

/* ---------------------------------------------------------------------------
 * setup -- bring up pins, timer, odometer and motion.
 *   Inputs:  none.  Returns: void.
 * ------------------------------------------------------------------------ */
void setup(void) {
  Serial.begin(115200);

  pinMode(PIN_STEP, OUTPUT);       /* OC1A only drives the pin if it is an output */
  pinMode(PIN_DIR, OUTPUT);
  pinMode(PIN_EN, OUTPUT);
  digitalWrite(PIN_EN, HIGH);      /* stay de-energised until we are ready */
  pinMode(PIN_HALL, INPUT_PULLUP);

  timer1_begin();
  odo_load();

  g_stepHz = step_hz_for_rpm(TARGET_RPM_X10);
  uint16_t ocr = ocr_for_hz(g_stepHz);

  Serial.println(F("\n--- rock tumbler ---"));
  Serial.print(F("stage      : "));
  Serial.println(STAGE_NAME[g_stage < N_STAGES ? g_stage : N_STAGES - 1]);
  Serial.print(F("resuming at: "));
  Serial.print(odo_revs());
  Serial.println(F(" revolutions"));
  Serial.print(F("step rate  : "));
  Serial.print(g_stepHz);
  Serial.print(F(" Hz  (OCR1A="));
  Serial.print(ocr);
  Serial.print(F(" -> "));
  Serial.print(hz_for_ocr(ocr));
  Serial.println(F(" Hz actual)"));

  if (g_stage >= N_STAGES) {
    Serial.println(F("all stages complete -- reset the EEPROM to start a new batch"));
    for (;;) { delay(1000); }
  }

  attachInterrupt(digitalPinToInterrupt(PIN_HALL), hall_isr, FALLING);

  uint32_t now = millis();
  g_tPrevSec = now;
  g_tReverse = now;
  g_tReport  = now;
  start_motion();
}

/* ---------------------------------------------------------------------------
 * loop -- supervise. Every comparison below uses the rollover-safe idiom,
 *         because this machine is expected to outlive millis()' 49.7 days.
 *   Inputs:  none.  Returns: void.
 * ------------------------------------------------------------------------ */
void loop(void) {
  uint32_t now = millis();

  /* Integrate running time in whole seconds. */
  if ((uint32_t)(now - g_tPrevSec) >= 1000UL) {
    g_tPrevSec += 1000UL;
    if (g_running) g_runSec++;
  }

  /* Persist the dose periodically. Both sides are in pulses; g_lastSave is
   * the pulse count at the last write, so the subtraction stays in one unit. */
  if ((odo_pulses() - g_lastSave) >=
      SAVE_EVERY_REVS * (uint32_t)(MAGNETS_PER_REV < 1 ? 1 : MAGNETS_PER_REV)) {
    odo_save();
  }

  /* Slip watchdog. */
  uint8_t slip = slip_pct();
  if (slip >= SLIP_FAULT_PCT) {
    fault_stop("barrel not turning -- check traction, magnet and sensor");
  }

  /* Scheduled reversal. */
  if (REVERSE_SEC && (uint32_t)(now - g_tReverse) >= REVERSE_SEC * 1000UL) {
    reverse_motion();
    Serial.print(F("reversed -> "));
    Serial.println(g_dir > 0 ? '+' : '-');
  }

  /* Stage complete? Stop and wait for a human with a hose. */
  if (odo_revs() >= STAGE_REVS[g_stage]) {
    stop_motion();
    digitalWrite(PIN_EN, HIGH);
    g_stage++;
    g_pulses = 0;
    odo_save();
    Serial.println(F("\nstage complete."));
    Serial.println(F("wash everything -- stones, barrel, lid, hands -- then reset."));
    Serial.println(F("one grain of coarse grit in the polish stage ruins the batch."));
    for (;;) { delay(1000); }
  }

  /* Status line. */
  if ((uint32_t)(now - g_tReport) >= REPORT_EVERY_SEC * 1000UL) {
    g_tReport = now;
    report();
    if (slip >= SLIP_WARN_PCT) {
      Serial.println(F("  warning: traction falling off -- grit on the tyres?"));
    }
  }
}
