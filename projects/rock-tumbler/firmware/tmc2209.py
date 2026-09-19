"""
tmc2209.py -- Minimal single-wire UART driver for the Trinamic TMC2209.

WHY THIS CHIP, FOR THIS MACHINE
    A rock tumbler runs continuously for four to six weeks in a room you also
    live in. Two TMC2209 features decide the project:

    1. StealthChop. The driver commutates with a quiet voltage-mode PWM instead
       of chopping current audibly. A tumbler built this way is quieter than
       the rocks inside it -- which is the entire difference between a machine
       you keep running and one you unplug after three days.

    2. VACTUAL (register 0x22). The chip contains its own step generator. Write
       a velocity and it spins by itself, indefinitely, with no STEP pulses
       from the microcontroller at all. No timer interrupt, no jitter, no CPU
       load, and a speed change is one register write. For a machine whose
       whole job is "hold one speed for six weeks", nothing else comes close.

PROTOCOL
    Single-wire half-duplex UART. Tie the driver's PDN_UART pin to the MCU TX
    through a 1k resistor and to MCU RX directly; the driver echoes its own
    bytes, so reads must skip the echo.

    Write datagram (8 bytes):  0x05, slave, reg|0x80, d3, d2, d1, d0, crc
    Read request  (4 bytes):   0x05, slave, reg,      crc
    Read reply    (8 bytes):   0x05, 0xFF,  reg,      d3, d2, d1, d0, crc
    Data is big-endian. CRC is 8-bit, polynomial x^8+x^2+x+1, fed LSB-first.

REFERENCE
    Trinamic / Analog Devices TMC2209 datasheet rev 1.09, sections 5 (UART)
    and 6 (register map).

This module imports `machine` lazily so the protocol logic can be unit tested
on desktop CPython -- run `python3 tmc2209.py` to self-test.
"""

# --- Register addresses ----------------------------------------------------
REG_GCONF       = 0x00
REG_IFCNT       = 0x02
REG_IOIN        = 0x06
REG_IHOLD_IRUN  = 0x10
REG_TPOWERDOWN  = 0x11
REG_TSTEP       = 0x12
REG_VACTUAL     = 0x22
REG_CHOPCONF    = 0x6C
REG_DRV_STATUS  = 0x6F

SYNC = 0x05

# MRES field (CHOPCONF bits 24..27) -> microsteps per full step.
MRES = {256: 0, 128: 1, 64: 2, 32: 3, 16: 4, 8: 5, 4: 6, 2: 7, 1: 8}

# CHOPCONF starting point: TOFF=3 (driver enabled), HSTRT=5, interpolation on.
CHOPCONF_BASE = 0x10000053

F_CLK_INTERNAL = 12_000_000     # nominal internal oscillator, Hz


# ---------------------------------------------------------------------------
def crc8(data):
    """
    Trinamic UART checksum: CRC-8, polynomial 0x07, data fed least-significant
    bit first, initial value zero.

    Inputs:
        data (bytes | bytearray | list[int]) -- the datagram bytes preceding
            the checksum (3 bytes for a read request, 7 for a write).
    Returns:
        int -- the checksum byte, 0..255.
    """
    crc = 0
    for byte in data:
        b = byte
        for _ in range(8):
            if (crc >> 7) ^ (b & 0x01):
                crc = ((crc << 1) ^ 0x07) & 0xFF
            else:
                crc = (crc << 1) & 0xFF
            b >>= 1
    return crc


# ---------------------------------------------------------------------------
def build_write(slave, reg, value):
    """
    Assemble an 8-byte register-write datagram.

    Inputs:
        slave (int) -- driver address 0..3, set by the MS1/MS2 pins.
        reg   (int) -- register address, 0..0x7F.
        value (int) -- 32-bit value; negatives are encoded two's complement.
    Returns:
        bytes -- the complete datagram including checksum.
    """
    v = value & 0xFFFFFFFF
    d = bytearray([SYNC, slave & 0xFF, (reg & 0x7F) | 0x80,
                   (v >> 24) & 0xFF, (v >> 16) & 0xFF,
                   (v >> 8) & 0xFF, v & 0xFF])
    d.append(crc8(d))
    return bytes(d)


# ---------------------------------------------------------------------------
def build_read(slave, reg):
    """
    Assemble a 4-byte register-read request datagram.

    Inputs:
        slave (int) -- driver address 0..3.
        reg   (int) -- register address, 0..0x7F.
    Returns:
        bytes -- the complete request including checksum.
    """
    d = bytearray([SYNC, slave & 0xFF, reg & 0x7F])
    d.append(crc8(d))
    return bytes(d)


# ---------------------------------------------------------------------------
def velocity_to_vactual(usteps_per_sec, f_clk=F_CLK_INTERNAL):
    """
    Convert a microstep rate into a VACTUAL register value.

    One velocity LSB equals f_CLK / 2^24 microsteps per second, so:
        VACTUAL = usteps_per_sec * 2^24 / f_CLK

    Inputs:
        usteps_per_sec (float) -- desired rate; negative reverses direction.
        f_clk          (int)   -- driver clock in Hz.
    Returns:
        int -- clamped to the signed 24-bit register range.
    """
    v = int(round(usteps_per_sec * (1 << 24) / f_clk))
    lim = (1 << 23) - 1
    return max(-lim, min(lim, v))


# ---------------------------------------------------------------------------
def vactual_to_velocity(vactual, f_clk=F_CLK_INTERNAL):
    """
    Inverse of velocity_to_vactual -- what a given register value will actually
    produce. Useful for reporting the quantised speed you really got.

    Inputs:
        vactual (int) -- register value.
        f_clk   (int) -- driver clock in Hz.
    Returns:
        float -- microsteps per second.
    """
    return vactual * f_clk / (1 << 24)


# ---------------------------------------------------------------------------
class TMC2209:
    """
    A single TMC2209 on a single-wire UART.

    Construct with an already-configured UART object exposing MicroPython's
    read()/write()/any() interface. Everything here is deliberately blocking
    and unhurried; this machine changes speed a few times a month.
    """

    def __init__(self, uart, slave=0, enable_pin=None, f_clk=F_CLK_INTERNAL):
        """
        Inputs:
            uart       -- UART object (MicroPython machine.UART or a stub).
            slave (int)-- driver address 0..3.
            enable_pin -- optional output Pin driving /EN; active low.
            f_clk (int)-- driver clock in Hz; trim this after calibration.
        Returns: None.
        """
        self.uart = uart
        self.slave = slave
        self.en = enable_pin
        self.f_clk = f_clk
        self._chopconf = CHOPCONF_BASE
        self.microsteps = 16

    # -- transport ----------------------------------------------------------
    def write_reg(self, reg, value):
        """
        Write one register.

        Inputs:  reg (int) register address; value (int) 32-bit payload.
        Returns: None.
        """
        self.uart.write(build_write(self.slave, reg, value))
        # The driver echoes our own bytes back on the shared wire; drain them
        # so they do not contaminate the next read.
        self._drain()

    def read_reg(self, reg):
        """
        Read one register.

        Inputs:  reg (int) -- register address.
        Returns: int | None -- the 32-bit value, or None if the reply was
                 missing or failed its checksum.
        """
        self._drain()
        self.uart.write(build_read(self.slave, reg))
        # 4 echoed request bytes + 8 reply bytes.
        buf = self.uart.read(12)
        if not buf or len(buf) < 12:
            return None
        reply = buf[4:12]
        if reply[0] != SYNC or crc8(reply[:7]) != reply[7]:
            return None
        return (reply[3] << 24) | (reply[4] << 16) | (reply[5] << 8) | reply[6]

    def _drain(self):
        """
        Discard any pending bytes on the shared wire (echoes, stale replies).
        Inputs: none. Returns: None.
        """
        try:
            while self.uart.any():
                self.uart.read(self.uart.any())
        except AttributeError:
            pass

    # -- configuration ------------------------------------------------------
    def begin(self, run_current=8, hold_current=8, microsteps=16,
              stealth=True, invert=False):
        """
        Bring the driver up in the configuration this machine wants.

        Note on current: set it LOW. The torque demand here is single-digit
        newton-centimetres against a NEMA 17's forty-plus, and a stepper draws
        its full set current whether it is loaded or not, twenty-four hours a
        day, for six weeks. Every unnecessary amp becomes heat in a printed
        bracket. Start at run_current=8 (about a quarter scale) and only raise
        it if the barrel visibly stalls under a full charge.

        Inputs:
            run_current  (int)  -- IRUN, 0..31 current scale while moving.
            hold_current (int)  -- IHOLD, 0..31 current scale while stopped.
            microsteps   (int)  -- 1,2,4,8,16,32,64,128,256.
            stealth      (bool) -- True for silent StealthChop (what you want).
            invert       (bool) -- flip the motor's sense of "forward".
        Returns: None.
        """
        if self.en is not None:
            self.en.value(0)                      # /EN is active low
        gconf = 0
        gconf |= (1 << 6)                         # pdn_disable: UART owns the pin
        gconf |= (1 << 7)                         # microsteps from register, not pins
        if not stealth:
            gconf |= (1 << 2)                     # en_spreadCycle
        if invert:
            gconf |= (1 << 3)                     # shaft: reverse direction
        self.write_reg(REG_GCONF, gconf)
        self.set_current(run_current, hold_current)
        self.write_reg(REG_TPOWERDOWN, 20)
        self.set_microsteps(microsteps)

    def set_current(self, run, hold, hold_delay=6):
        """
        Set IHOLD_IRUN.

        Inputs:
            run        (int) -- IRUN 0..31.
            hold       (int) -- IHOLD 0..31.
            hold_delay (int) -- IHOLDDELAY 0..15, power-down ramp.
        Returns: None.
        """
        run = max(0, min(31, run))
        hold = max(0, min(31, hold))
        self.write_reg(REG_IHOLD_IRUN,
                       hold | (run << 8) | ((hold_delay & 0x0F) << 16))

    def set_microsteps(self, n):
        """
        Set microstep resolution, with MicroPlyer interpolation left on so the
        driver smooths whatever we ask for up to 256 internally.

        Inputs:  n (int) -- one of 1,2,4,8,16,32,64,128,256.
        Returns: None.
        Raises:  ValueError on an unsupported value.
        """
        if n not in MRES:
            raise ValueError("microsteps must be a power of two, 1..256")
        self.microsteps = n
        self._chopconf = (CHOPCONF_BASE & ~(0x0F << 24)) | (MRES[n] << 24) | (1 << 28)
        self.write_reg(REG_CHOPCONF, self._chopconf)

    # -- motion -------------------------------------------------------------
    def set_velocity(self, usteps_per_sec):
        """
        Spin at a constant velocity using the driver's internal step generator.
        Sign sets direction; zero stops and hands control back to the STEP pin.

        Inputs:  usteps_per_sec (float) -- microstep rate, signed.
        Returns: int -- the VACTUAL value actually written.
        """
        v = velocity_to_vactual(usteps_per_sec, self.f_clk)
        self.write_reg(REG_VACTUAL, v)
        return v

    def stop(self):
        """
        Stop the internal step generator.
        Inputs: none. Returns: None.
        """
        self.write_reg(REG_VACTUAL, 0)

    def disable(self):
        """
        Stop and drop current entirely -- the safe state for a fault or for
        the end of a run.
        Inputs: none. Returns: None.
        """
        self.stop()
        if self.en is not None:
            self.en.value(1)

    # -- diagnostics --------------------------------------------------------
    def status(self):
        """
        Decode DRV_STATUS into the handful of flags worth acting on.

        For an unattended six-week run these are the smoke detector. `ot` and
        `otpw` mean the driver is cooking; `ola`/`olb` usually mean a motor
        wire has vibrated loose, which on this machine is an inevitability
        rather than a possibility.

        Inputs:  none.
        Returns: dict of flags plus the raw word, or None if the read failed.
        """
        raw = self.read_reg(REG_DRV_STATUS)
        if raw is None:
            return None
        return {
            "raw": raw,
            "otpw": bool(raw & (1 << 0)),        # over-temperature pre-warning
            "ot": bool(raw & (1 << 1)),          # over-temperature shutdown
            "s2ga": bool(raw & (1 << 2)),        # short to ground, coil A
            "s2gb": bool(raw & (1 << 3)),        # short to ground, coil B
            "ola": bool(raw & (1 << 6)),         # open load, coil A
            "olb": bool(raw & (1 << 7)),         # open load, coil B
            "current": (raw >> 16) & 0x1F,       # actual current scale
            "stealth": bool(raw & (1 << 30)),
        }

    def comms_ok(self):
        """
        Confirm the driver is actually listening. IFCNT increments on every
        successful write, so two reads either side of a write must differ.

        Inputs:  none.
        Returns: bool -- True if the driver acknowledged a write.
        """
        a = self.read_reg(REG_IFCNT)
        if a is None:
            return False
        self.write_reg(REG_TPOWERDOWN, 20)
        b = self.read_reg(REG_IFCNT)
        return b is not None and b != a


# ---------------------------------------------------------------------------
def _selftest():
    """
    Verify the protocol layer without hardware.

    Inputs:  none.
    Returns: bool -- True if all checks pass. Prints each result.
    """
    ok = True

    def check(name, cond, detail=""):
        nonlocal ok
        ok &= bool(cond)
        print(f"  [{'ok' if cond else 'FAIL'}] {name} {detail}")

    # 1. Cross-check the CRC against an independently written implementation:
    #    feeding bits LSB-first is identical to reversing each byte and feeding
    #    MSB-first. Two different routines agreeing is worth more than one
    #    routine looking correct.
    def crc8_reference(data):
        crc = 0
        for byte in data:
            rev = int('{:08b}'.format(byte)[::-1], 2)
            for i in range(7, -1, -1):
                bit = (rev >> i) & 1
                if (crc >> 7) ^ bit:
                    crc = ((crc << 1) ^ 0x07) & 0xFF
                else:
                    crc = (crc << 1) & 0xFF
        return crc

    vectors = [b'\x05\x00\x00', b'\x05\x00\x6c', bytes(range(7)), b'\xff\xff\xff\xff']
    agree = all(crc8(v) == crc8_reference(v) for v in vectors)
    check("crc8 agrees with independent implementation", agree)
    print(f"        read request GCONF@0 = {build_read(0, REG_GCONF).hex(' ')}")

    # 2. Datagram shapes must match the datasheet exactly.
    w = build_write(0, REG_VACTUAL, 20104)
    check("write datagram is 8 bytes", len(w) == 8, f"got {len(w)}")
    check("write sets the register MSB", w[2] == (REG_VACTUAL | 0x80), hex(w[2]))
    check("write checksum verifies", crc8(w[:7]) == w[7])
    r = build_read(0, REG_DRV_STATUS)
    check("read request is 4 bytes", len(r) == 4, f"got {len(r)}")
    check("read leaves the register MSB clear", r[2] == REG_DRV_STATUS, hex(r[2]))

    # 3. Big-endian payload packing.
    w2 = build_write(1, REG_IHOLD_IRUN, 0x12345678)
    check("payload is big-endian", w2[3:7] == b'\x12\x34\x56\x78', w2[3:7].hex())

    # 4. Negative velocity must encode as two's complement -- this is how the
    #    machine reverses direction, so getting it wrong means a tumbler that
    #    only ever turns one way.
    wn = build_write(0, REG_VACTUAL, -20104)
    packed = (wn[3] << 24) | (wn[4] << 16) | (wn[5] << 8) | wn[6]
    check("negative velocity is two's complement",
          packed == (-20104 & 0xFFFFFFFF), hex(packed))

    # 5. VACTUAL round-trips, and reversal is exactly symmetric.
    v = velocity_to_vactual(8987.0)
    back = vactual_to_velocity(v)
    check("VACTUAL round-trip within 1 ustep/s", abs(back - 8987.0) < 1.0,
          f"{v} -> {back:.1f}")
    check("reversal is symmetric", velocity_to_vactual(-8987.0) == -v)

    # 6. Clamping at the signed 24-bit boundary.
    check("velocity clamps to 24-bit signed",
          velocity_to_vactual(1e9) == (1 << 23) - 1)

    # 7. Microstep encoding lands in CHOPCONF bits 24..27 with interpolation on.
    t = TMC2209(uart=None)
    t.uart = type("Stub", (), {"write": lambda s, b: None,
                               "read": lambda s, n: None,
                               "any": lambda s: 0})()
    t.set_microsteps(16)
    check("MRES field for 1/16 is 4", (t._chopconf >> 24) & 0x0F == 4)
    check("interpolation enabled", bool(t._chopconf & (1 << 28)))
    t.set_microsteps(256)
    check("MRES field for 1/256 is 0", (t._chopconf >> 24) & 0x0F == 0)

    print(f"\n  {'ALL CHECKS PASSED' if ok else 'SOMETHING IS WRONG'}")
    return ok


if __name__ == "__main__":
    import sys
    print("\n  TMC2209 PROTOCOL SELF TEST\n")
    sys.exit(0 if _selftest() else 1)
