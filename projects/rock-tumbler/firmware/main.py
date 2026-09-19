"""
main.py -- Tumbler controller for a Raspberry Pi Pico + TMC2209.

THE IDEA WORTH THE TROUBLE
    Commercial tumblers give you a switch. You get a machine that knows what
    it has done.

    Abrasive wear follows Archard's law: the volume of material removed is
    proportional to load times SLIDING DISTANCE, divided by hardness.

        V = K * W * L / H

    Sliding distance, on this machine, is barrel revolutions. Not hours --
    revolutions. That distinction is the whole argument for a stepper drive.
    "Seven days" is a proxy for the real dose, and a poor one: it silently
    assumes your barrel speed, your charge and your power supply were all
    identical to the person who wrote the instructions. Counting revolutions
    measures the dose directly. Run the coarse stage to 600,000 revolutions
    and you can change barrel size, change speed, lose a night to a power cut,
    and still land in the same place.

    So this firmware counts, persists the count across reboots, and reports
    stage progress as a fraction of a revolution target.

WHAT ELSE IT DOES THAT A SWITCH CANNOT
    * Soft start. Ramps up over several seconds so a full barrel does not
      break traction and sit there polishing a flat spot onto the tyres.
    * Scheduled reversal. Flips direction every few hours. The load stops
      packing into a preferred channel, and tyre and barrel wear evenly.
      No commercial hobby tumbler does this.
    * Closed-loop slip detection. A magnet on the barrel and a hall sensor on
      the frame let the controller compare the revolutions it COMMANDED with
      the revolutions that actually happened. Wet grit on a tyre shows up as
      a rising slip fraction days before you would notice by eye.
    * Fault latch. Over-temperature or an open motor coil stops the machine
      rather than cooking a printed bracket unattended.

WIRING (Pico)
    GP0  -> 1k resistor -> TMC2209 PDN_UART      (also tie PDN_UART to GP1)
    GP1  <- TMC2209 PDN_UART                     (single wire, half duplex)
    GP2  -> TMC2209 EN                           (active low)
    GP3  <- hall sensor / reed switch            (magnet on the barrel end cap)
    Driver VM from a 24 V supply; Pico from USB or a separate 5 V regulator.
    Common ground between Pico and driver. Do not skip the common ground.

Run `python3 main.py --selftest` on a desktop to exercise the control logic
with a simulated driver and barrel.
"""

import sys

try:
    from machine import Pin, UART
    import utime as time
    ON_DEVICE = True
except ImportError:                     # desktop, for tests
    import time
    ON_DEVICE = False

from tmc2209 import TMC2209


# ===========================================================================
# CONFIGURATION -- paste the numbers from tools/tumbler_calc.py here
# ===========================================================================
BARREL_OD_MM    = 112.0     # barrel OUTSIDE diameter (what touches the rollers)
ROLLER_OD_MM    = 40.0      # roller OUTSIDE diameter including tyre
GEAR_RATIO      = 1.0       # motor revolutions per roller revolution
FULL_STEPS      = 200       # 1.8 degree motor
MICROSTEPS      = 16

TARGET_BARREL_RPM = 60.0    # from the calculator: 45% of critical for a 100 mm ID
RUN_CURRENT       = 8       # IRUN 0..31. Low. See tmc2209.begin() for why.
HOLD_CURRENT      = 8

RAMP_SECONDS      = 8.0     # soft start
REVERSE_HOURS     = 6.0     # flip direction this often; 0 disables
SLIP_WARN         = 0.15    # warn above 15% slip
SLIP_FAULT        = 0.40    # stop above 40% -- something is jammed
MAGNETS_PER_REV   = 1       # magnets on the barrel end cap

STATE_FILE        = "tumbler_state.txt"
SAVE_EVERY_REVS   = 500     # persist the odometer this often

# Stage targets in barrel revolutions. At 60 rpm, 600 krev is about seven days.
# Adjust to taste; the point is that these are doses, not durations.
STAGES = [
    ("1 coarse grind  60/90 SiC",   600_000),
    ("2 medium grind  120/220 SiC", 600_000),
    ("3 pre-polish    500 SiC",     600_000),
    ("4 polish        cerium oxide", 600_000),
]


# ---------------------------------------------------------------------------
def barrel_rpm_to_usteps(barrel_rpm, barrel_od=BARREL_OD_MM, roller_od=ROLLER_OD_MM,
                         gear=GEAR_RATIO, full_steps=FULL_STEPS,
                         microsteps=MICROSTEPS):
    """
    Convert a desired barrel speed into the microstep rate the driver needs.

    Friction drive preserves surface speed, so the roller turns faster than the
    barrel by the diameter ratio; the belt (if any) then scales motor to roller.

    Inputs:
        barrel_rpm (float) -- desired barrel speed, RPM.
        barrel_od  (float) -- barrel outside diameter, mm.
        roller_od  (float) -- roller outside diameter, mm.
        gear       (float) -- motor revs per roller rev.
        full_steps (int)   -- motor full steps per revolution.
        microsteps (int)   -- driver microstep setting.
    Returns:
        float -- microsteps per second.
    """
    roller_rpm = barrel_rpm * barrel_od / roller_od
    motor_rpm = roller_rpm * gear
    return motor_rpm * full_steps * microsteps / 60.0


# ---------------------------------------------------------------------------
def usteps_to_barrel_revs(usteps, barrel_od=BARREL_OD_MM, roller_od=ROLLER_OD_MM,
                          gear=GEAR_RATIO, full_steps=FULL_STEPS,
                          microsteps=MICROSTEPS):
    """
    Inverse: how many barrel revolutions a number of microsteps should have
    produced, assuming no slip. Comparing this with the measured count is the
    whole of the slip detector.

    Inputs:  as barrel_rpm_to_usteps, plus usteps (float) -- microsteps issued.
    Returns: float -- expected barrel revolutions.
    """
    motor_revs = usteps / (full_steps * microsteps)
    roller_revs = motor_revs / gear
    return roller_revs * roller_od / barrel_od


# ===========================================================================
# CLASS: Odometer
#   Counts barrel revolutions from a hall sensor and survives power loss.
# ===========================================================================
class Odometer:
    """
    Persistent revolution counter. The dose, in Archard's sense, lives here.
    """

    def __init__(self, path=STATE_FILE, magnets_per_rev=MAGNETS_PER_REV):
        """
        Inputs:
            path            (str) -- file to persist the count into.
            magnets_per_rev (int) -- magnets fitted to the barrel end cap.
        Returns: None.
        """
        self.path = path
        self.magnets = max(1, magnets_per_rev)
        self.pulses = 0
        self.stage = 0
        self._last_saved = 0
        self.load()

    def load(self):
        """
        Restore the odometer from flash. A missing or corrupt file simply
        starts from zero rather than refusing to run.
        Inputs: none. Returns: None.
        """
        try:
            with open(self.path) as f:
                parts = f.read().strip().split(",")
                self.stage = int(parts[0])
                self.pulses = int(parts[1])
                self._last_saved = self.pulses
        except (OSError, ValueError, IndexError):
            self.stage, self.pulses, self._last_saved = 0, 0, 0

    def save(self):
        """
        Persist the odometer. Called every SAVE_EVERY_REVS revolutions -- often
        enough that a power cut costs minutes, rarely enough not to wear flash.
        Inputs: none. Returns: None.
        """
        try:
            with open(self.path, "w") as f:
                f.write("{},{}".format(self.stage, self.pulses))
            self._last_saved = self.pulses
        except OSError:
            pass

    def tick(self):
        """
        Record one hall-sensor pulse. Safe to call from an interrupt handler:
        it does no allocation and touches no file.
        Inputs: none. Returns: None.
        """
        self.pulses += 1

    @property
    def revs(self):
        """
        Inputs:  none.
        Returns: float -- measured barrel revolutions this stage.
        """
        return self.pulses / self.magnets

    def maybe_save(self):
        """
        Persist if enough revolutions have accumulated since the last write.
        Inputs: none. Returns: bool -- True if a save happened.
        """
        if (self.pulses - self._last_saved) >= SAVE_EVERY_REVS * self.magnets:
            self.save()
            return True
        return False

    def next_stage(self):
        """
        Advance to the next grit stage and zero the dose counter.
        Inputs: none. Returns: int -- the new stage index.
        """
        self.stage += 1
        self.pulses = 0
        self.save()
        return self.stage


# ===========================================================================
# CLASS: Tumbler
#   The control loop: ramp, run, reverse, watch for slip and faults.
# ===========================================================================
class Tumbler:
    """
    Ties the driver, the odometer and the stage schedule together.
    """

    def __init__(self, driver, odometer, target_rpm=TARGET_BARREL_RPM,
                 clock=None):
        """
        Inputs:
            driver     (TMC2209) -- configured driver instance.
            odometer   (Odometer)-- revolution counter.
            target_rpm (float)   -- desired barrel speed.
            clock      (callable)-- returns monotonic seconds; defaults to
                                    time.time. Injected so tests can run a
                                    six-week campaign in a millisecond.
        Returns: None.
        """
        self.drv = driver
        self.odo = odometer
        self.target_rpm = target_rpm
        self.clock = clock or time.time
        self.direction = 1
        self.usteps_issued = 0.0
        self.running = False
        self.fault = None
        self._t_last = self.clock()
        self._t_reverse = self.clock()

    # -- motion ------------------------------------------------------------
    def target_usteps(self):
        """
        Inputs:  none.
        Returns: float -- signed microstep rate for the current direction.
        """
        return barrel_rpm_to_usteps(self.target_rpm) * self.direction

    def start(self, ramp_s=RAMP_SECONDS, steps=20, sleep=None):
        """
        Soft start. Ramping matters here: slamming a full, sloshing barrel from
        rest to speed breaks traction between tyre and barrel, and a barrel
        that slips at every start wears a band into the tyre.

        Inputs:
            ramp_s (float)   -- ramp duration, seconds.
            steps  (int)     -- number of velocity increments.
            sleep  (callable)-- sleep function; injected for tests.
        Returns: None.
        """
        sleep = sleep or time.sleep
        final = self.target_usteps()
        for i in range(1, steps + 1):
            self.drv.set_velocity(final * i / steps)
            sleep(ramp_s / steps)
        self.running = True
        self._t_last = self.clock()
        self._t_reverse = self.clock()

    def reverse(self, sleep=None):
        """
        Flip direction through a controlled stop, so the load settles instead
        of being snapped the other way.

        Inputs:  sleep (callable) -- sleep function; injected for tests.
        Returns: int -- the new direction, +1 or -1.
        """
        sleep = sleep or time.sleep
        self.drv.stop()
        sleep(2.0)
        self.direction = -self.direction
        self.start(sleep=sleep)
        self._t_reverse = self.clock()
        return self.direction

    def stop(self):
        """
        Stop the barrel and leave the driver energised but idle.
        Inputs: none. Returns: None.
        """
        self.drv.stop()
        self.running = False

    # -- supervision -------------------------------------------------------
    def accumulate(self, now=None):
        """
        Integrate commanded microsteps since the last call. This is the
        open-loop expectation that the measured count is compared against.

        Inputs:  now (float) -- current time; defaults to self.clock().
        Returns: float -- microsteps added.
        """
        now = self.clock() if now is None else now
        dt = now - self._t_last
        self._t_last = now
        if not self.running or dt <= 0:
            return 0.0
        added = abs(self.target_usteps()) * dt
        self.usteps_issued += added
        return added

    def slip(self):
        """
        Fraction of commanded rotation that the barrel failed to deliver.

        0.0 means perfect traction. Rising slip over days means grit or water
        on the tyres; a sudden jump to 1.0 means the barrel has stopped
        turning while the motor happily spins on -- the failure mode that
        otherwise wastes a week of grinding.

        Inputs:  none.
        Returns: float -- slip fraction, 0.0 to 1.0 (0.0 before enough data).
        """
        expected = usteps_to_barrel_revs(self.usteps_issued)
        if expected < 10.0:
            return 0.0
        measured = self.odo.revs
        return max(0.0, min(1.0, 1.0 - measured / expected))

    def check_faults(self):
        """
        Poll the driver and the slip detector for reasons to shut down.

        Inputs:  none.
        Returns: str | None -- a fault description, or None if healthy.
        """
        s = self.drv.status()
        if s is not None:
            if s["ot"]:
                return "driver over-temperature shutdown"
            if s["s2ga"] or s["s2gb"]:
                return "motor coil shorted to ground"
            if s["ola"] or s["olb"]:
                return "motor coil open -- check the connector"
        if self.slip() >= SLIP_FAULT:
            return "barrel not turning: slip {:.0%}".format(self.slip())
        return None

    def due_to_reverse(self, now=None):
        """
        Inputs:  now (float) -- current time; defaults to self.clock().
        Returns: bool -- True if the reversal interval has elapsed.
        """
        if REVERSE_HOURS <= 0:
            return False
        now = self.clock() if now is None else now
        return (now - self._t_reverse) >= REVERSE_HOURS * 3600.0

    def stage_progress(self):
        """
        Inputs:  none.
        Returns: tuple (name, revs_done, revs_target, fraction). Fraction is
                 clamped to 1.0; name is "done" once the schedule is exhausted.
        """
        if self.odo.stage >= len(STAGES):
            return ("done", self.odo.revs, 0, 1.0)
        name, target = STAGES[self.odo.stage]
        return (name, self.odo.revs, target, min(1.0, self.odo.revs / target))

    def report(self):
        """
        One line of status, suitable for a serial log or a small OLED.
        Inputs:  none.
        Returns: str.
        """
        name, done, target, frac = self.stage_progress()
        return ("{:<28s} {:>9.0f}/{:<9d} rev  {:>5.1f}%  "
                "dir {:+d}  slip {:>4.0%}").format(
                    name, done, target, frac * 100.0, self.direction, self.slip())


# ---------------------------------------------------------------------------
def build_hardware():
    """
    Construct the on-device objects. Kept separate so the control logic above
    stays importable and testable on a desktop.

    Inputs:  none.
    Returns: tuple (Tumbler, Odometer).
    """
    uart = UART(0, baudrate=115200, tx=Pin(0), rx=Pin(1), timeout=100)
    en = Pin(2, Pin.OUT, value=1)
    drv = TMC2209(uart, slave=0, enable_pin=en)
    drv.begin(run_current=RUN_CURRENT, hold_current=HOLD_CURRENT,
              microsteps=MICROSTEPS, stealth=True)

    odo = Odometer()
    hall = Pin(3, Pin.IN, Pin.PULL_UP)
    hall.irq(trigger=Pin.IRQ_FALLING, handler=lambda p: odo.tick())

    return Tumbler(drv, odo), odo


# ---------------------------------------------------------------------------
def run():
    """
    Main loop. Runs the current stage to its revolution target, then stops and
    waits for you to clean the barrel and advance the stage.

    Deliberately does NOT auto-advance: between stages every last grain of the
    previous grit has to be washed off the stones, the barrel and your hands.
    A single grain of 60 grit carried into the polish stage will scratch every
    stone in the batch, and the machine has no way to know whether you did it.

    Inputs:  none.
    Returns: None. Runs until a fault or stage completion.
    """
    tumbler, odo = build_hardware()

    if not tumbler.drv.comms_ok():
        print("FAULT: no response from TMC2209 -- check PDN_UART wiring")
        return

    name, done, target, _ = tumbler.stage_progress()
    print("stage: {}   resuming at {:.0f} of {} revolutions".format(name, done, target))
    tumbler.start()

    last_print = 0
    while True:
        tumbler.accumulate()
        odo.maybe_save()

        fault = tumbler.check_faults()
        if fault:
            tumbler.stop()
            tumbler.drv.disable()
            odo.save()
            print("FAULT: " + fault)
            return

        if tumbler.due_to_reverse():
            tumbler.reverse()
            print("reversed -> {:+d}".format(tumbler.direction))

        _, done, target, frac = tumbler.stage_progress()
        if target and done >= target:
            tumbler.stop()
            odo.save()
            print("\nstage complete: {:.0f} revolutions".format(done))
            print("wash everything -- stones, barrel, lid, hands -- then advance.")
            return

        now = time.time()
        if now - last_print >= 60:
            print(tumbler.report())
            last_print = now
        time.sleep(1)


# ---------------------------------------------------------------------------
def _selftest():
    """
    Exercise the control logic against a simulated driver and barrel, including
    a simulated six-week campaign, without any hardware.

    Inputs:  none.
    Returns: bool -- True if all checks pass. Prints each result.
    """
    ok = True

    def check(name, cond, detail=""):
        nonlocal ok
        ok &= bool(cond)
        print(f"  [{'ok' if cond else 'FAIL'}] {name} {detail}")

    class FakeDriver:
        """Records velocities instead of writing them to silicon."""
        def __init__(self):
            self.v = 0.0
            self.history = []
            self.flags = dict(raw=0, otpw=False, ot=False, s2ga=False,
                              s2gb=False, ola=False, olb=False,
                              current=8, stealth=True)

        def set_velocity(self, u):
            self.v = u
            self.history.append(u)
            return int(u)

        def stop(self):
            self.v = 0.0
            self.history.append(0.0)

        def disable(self):
            self.stop()

        def status(self):
            return self.flags

    # -- speed maths --------------------------------------------------------
    u = barrel_rpm_to_usteps(60.0)
    # 60 rpm barrel * 112/40 = 168 rpm motor * 3200 usteps/rev / 60 s
    check("60 rpm barrel -> 8960 usteps/s", abs(u - 8960.0) < 1.0, f"{u:.1f}")
    r = usteps_to_barrel_revs(u * 60.0)
    check("usteps round-trip to 60 revs in 60 s", abs(r - 60.0) < 1e-9, f"{r:.4f}")

    # -- odometer -----------------------------------------------------------
    import os
    tmp = "/tmp/_tumbler_test_state.txt"
    if os.path.exists(tmp):
        os.remove(tmp)
    odo = Odometer(path=tmp, magnets_per_rev=2)
    for _ in range(400):
        odo.tick()
    check("2 magnets per rev halves the count", odo.revs == 200.0, f"{odo.revs}")
    odo.save()
    odo2 = Odometer(path=tmp, magnets_per_rev=2)
    check("odometer survives a reboot", odo2.revs == 200.0, f"{odo2.revs}")
    odo2.next_stage()
    check("advancing a stage zeroes the dose",
          odo2.stage == 1 and odo2.revs == 0.0)

    # -- controlled clock ---------------------------------------------------
    t = {"now": 0.0}
    fake = FakeDriver()
    odo3 = Odometer(path=tmp + ".2", magnets_per_rev=1)
    odo3.pulses, odo3.stage = 0, 0
    tum = Tumbler(fake, odo3, target_rpm=60.0, clock=lambda: t["now"])

    tum.start(ramp_s=0.0, steps=10, sleep=lambda s: None)
    ramp = [abs(v) for v in fake.history]
    check("soft start ramps monotonically upward",
          all(ramp[i] <= ramp[i + 1] for i in range(len(ramp) - 1)))
    check("ramp ends at full speed", abs(ramp[-1] - 8960.0) < 1.0, f"{ramp[-1]:.0f}")

    # -- perfect traction: measured matches commanded, slip stays zero ------
    t["now"] = 60.0
    tum.accumulate()
    for _ in range(60):                       # 60 revs in 60 s at 60 rpm
        odo3.tick()
    check("no slip under perfect traction", tum.slip() < 0.01, f"{tum.slip():.3f}")

    # -- a slipping barrel must be detected --------------------------------
    t["now"] = 120.0
    tum.accumulate()                          # commanded another 60 revs
    for _ in range(30):                       # but only 30 happened
        odo3.tick()
    s = tum.slip()
    check("50% under-rotation reads as 25% cumulative slip",
          0.24 < s < 0.26, f"{s:.3f}")
    check("slip below the fault threshold does not stop the run",
          tum.check_faults() is None)

    # -- a fully stalled barrel must fault ---------------------------------
    t["now"] = 600.0
    tum.accumulate()                          # lots more commanded, none measured
    check("stalled barrel raises a fault",
          tum.check_faults() is not None, f"slip {tum.slip():.2f}")

    # -- driver faults ------------------------------------------------------
    fake.flags["ola"] = True
    tum2 = Tumbler(fake, Odometer(path=tmp + ".3"), clock=lambda: t["now"])
    check("open coil raises a fault", "open" in (tum2.check_faults() or ""))
    fake.flags["ola"] = False
    fake.flags["ot"] = True
    check("over-temperature raises a fault",
          "temperature" in (tum2.check_faults() or ""))
    fake.flags["ot"] = False

    # -- reversal scheduling ------------------------------------------------
    t["now"] = 0.0
    fake3 = FakeDriver()
    odo4 = Odometer(path=tmp + ".4")
    odo4.pulses, odo4.stage = 0, 0
    tum3 = Tumbler(fake3, odo4, clock=lambda: t["now"])
    tum3.start(ramp_s=0.0, steps=2, sleep=lambda s: None)
    check("not due to reverse immediately", not tum3.due_to_reverse())
    t["now"] = REVERSE_HOURS * 3600.0 + 1
    check("due to reverse after the interval", tum3.due_to_reverse())
    d = tum3.reverse(sleep=lambda s: None)
    check("reversal flips direction", d == -1, f"{d}")
    check("reversed velocity is negative", fake3.v < 0, f"{fake3.v:.0f}")
    check("reversal resets the timer", not tum3.due_to_reverse())

    # -- a simulated campaign: does the dose model reach the target on time? -
    t["now"] = 0.0
    fake4 = FakeDriver()
    odo5 = Odometer(path=tmp + ".5")
    odo5.pulses, odo5.stage = 0, 0
    tum4 = Tumbler(fake4, odo5, target_rpm=60.0, clock=lambda: t["now"])
    tum4.start(ramp_s=0.0, steps=2, sleep=lambda s: None)
    target = STAGES[0][1]
    hours = 0
    while odo5.revs < target and hours < 24 * 60:
        hours += 1
        t["now"] = hours * 3600.0
        tum4.accumulate()
        for _ in range(60 * 60):              # one hour of perfect rotation
            odo5.tick()
    days = hours / 24.0
    check("600 krev at 60 rpm completes in about 7 days",
          6.5 < days < 7.5, f"{days:.2f} days")
    _, _, _, frac = tum4.stage_progress()
    check("progress reports complete", frac >= 1.0, f"{frac:.2f}")

    for f in (tmp, tmp + ".2", tmp + ".3", tmp + ".4", tmp + ".5"):
        if os.path.exists(f):
            os.remove(f)

    print(f"\n  {'ALL CHECKS PASSED' if ok else 'SOMETHING IS WRONG'}")
    return ok


if __name__ == "__main__":
    if "--selftest" in sys.argv or not ON_DEVICE:
        print("\n  TUMBLER CONTROL LOGIC SELF TEST\n")
        sys.exit(0 if _selftest() else 1)
    run()
