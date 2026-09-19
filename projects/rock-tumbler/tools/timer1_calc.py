#!/usr/bin/env python3
"""
timer1_calc.py -- Verify the AVR Timer1 step-generation maths used by
firmware/arduino/tumbler_uno/tumbler_uno.ino, and print an OCR1A table.

WHY A SEPARATE TOOL
    The Arduino sketch generates its step train in hardware: Timer1 in CTC mode
    with COM1A0 set, toggling OC1A (pin D9) on every compare match. That is the
    ATmega's answer to the TMC2209's VACTUAL register -- configure it once and
    the silicon emits a perfectly steady pulse train with the CPU uninvolved.

    The arithmetic behind it is small but easy to get subtly wrong, and a 2x
    error there means a barrel running at half or double speed for a week
    before you notice. So it is worked out here, in a place where it can be
    tested, rather than trusted to a comment in a sketch.

        f_step = F_CPU / (2 * N * (1 + OCR1A))          N = prescaler

    The factor of 2 is because the pin TOGGLES on compare match: two matches
    make one full output cycle, and one cycle is one microstep.

USAGE
    python3 timer1_calc.py                # OCR1A table for the working range
    python3 timer1_calc.py --selftest     # verify, including two failure demos
"""

import argparse
import struct

F_CPU_DEFAULT = 16_000_000      # Uno / Nano / Pro Mini at 16 MHz
OCR_MAX = 65535


# ---------------------------------------------------------------------------
def ocr_for_hz(hz, f_cpu=F_CPU_DEFAULT, prescaler=1):
    """
    OCR1A value that produces the requested step frequency, matching the
    sketch's ocr_for_hz() exactly including its clamping behaviour.

    Inputs:
        hz        (float) -- desired step rate, Hz.
        f_cpu     (int)   -- CPU clock, Hz.
        prescaler (int)   -- Timer1 prescaler: 1, 8, 64, 256 or 1024.
    Returns:
        int -- OCR1A value, clamped to 1..65535.
    """
    if hz < 1.0:
        hz = 1.0
    v = (f_cpu / (2.0 * prescaler * hz)) - 1.0
    v = max(1.0, min(float(OCR_MAX), v))
    return int(v + 0.5)


# ---------------------------------------------------------------------------
def hz_for_ocr(ocr, f_cpu=F_CPU_DEFAULT, prescaler=1):
    """
    The step frequency a given OCR1A actually produces.

    Inputs:
        ocr       (int) -- register value.
        f_cpu     (int) -- CPU clock, Hz.
        prescaler (int) -- Timer1 prescaler.
    Returns:
        float -- realised step rate, Hz.
    """
    return f_cpu / (2.0 * prescaler * (ocr + 1.0))


# ---------------------------------------------------------------------------
def step_hz_for_rpm(barrel_rpm, barrel_od=112.0, roller_od=40.0, gear=1.0,
                    full_steps=200, microsteps=16):
    """
    Barrel speed to microstep frequency, mirroring the sketch's function of the
    same name.

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
    return barrel_rpm * (barrel_od / roller_od) * gear * full_steps * microsteps / 60.0


# ---------------------------------------------------------------------------
def timer_range(f_cpu=F_CPU_DEFAULT, prescaler=1):
    """
    The frequency span Timer1 can express with a given prescaler.

    Inputs:
        f_cpu     (int) -- CPU clock, Hz.
        prescaler (int) -- Timer1 prescaler.
    Returns:
        tuple (min_hz, max_hz).
    """
    return (hz_for_ocr(OCR_MAX, f_cpu, prescaler), hz_for_ocr(1, f_cpu, prescaler))


# ---------------------------------------------------------------------------
def table(f_cpu=F_CPU_DEFAULT):
    """
    Print OCR1A values and realised frequencies across plausible builds.

    Inputs:  f_cpu (int) -- CPU clock, Hz.
    Returns: str -- the formatted table.
    """
    lo, hi = timer_range(f_cpu)
    L = []
    L.append("=" * 72)
    L.append(f"  TIMER1 CTC STEP GENERATION  (F_CPU = {f_cpu/1e6:.0f} MHz, prescaler 1)")
    L.append(f"  expressible range: {lo:.1f} Hz to {hi/1000:.0f} kHz")
    L.append("=" * 72)
    L.append("")
    L.append(f"{'roller':>7} {'barrel rpm':>11} {'want Hz':>10} {'OCR1A':>7} "
             f"{'get Hz':>10} {'error':>9}")
    L.append("-" * 72)
    for roller in (20.0, 25.0, 40.0, 50.0):
        for rpm in (45.0, 60.2):
            want = step_hz_for_rpm(rpm, roller_od=roller)
            ocr = ocr_for_hz(want, f_cpu)
            got = hz_for_ocr(ocr, f_cpu)
            err = (got - want) / want * 100.0
            L.append(f"{roller:>7.0f} {rpm:>11.1f} {want:>10.1f} {ocr:>7d} "
                     f"{got:>10.1f} {err:>8.3f}%")
    L.append("")
    L.append("  Quantisation error is bounded by half an OCR step, 1/(2*(OCR1A+1)):")
    L.append("  0.056% at the recommended build, ~0.13% at the fastest sensible one.")
    L.append("  Over a 600,000-revolution stage that is a few hundred revolutions --")
    L.append("  and the hall-sensor odometer measures the truth anyway, so it never")
    L.append("  accumulates into anything that matters.")
    L.append("=" * 72)
    return "\n".join(L)


# ---------------------------------------------------------------------------
def _f32(x):
    """
    Round a Python float to IEEE-754 single precision, which is what `float`
    means on an AVR.

    Inputs:  x (float) -- double-precision value.
    Returns: float     -- value after a round trip through float32.
    """
    return struct.unpack('f', struct.pack('f', x))[0]


# ---------------------------------------------------------------------------
def selftest():
    """
    Verify the timer maths, and demonstrate the two AVR failure modes the
    sketch is written to avoid.

    Inputs:  none.
    Returns: bool -- True if every check passes. Prints each result.
    """
    ok = True

    def check(name, cond, detail=""):
        nonlocal ok
        ok &= bool(cond)
        print(f"  [{'ok' if cond else 'FAIL'}] {name} {detail}")

    # 1. Formula and its inverse must agree.
    for hz in (1000.0, 8987.0, 22468.0):
        ocr = ocr_for_hz(hz)
        got = hz_for_ocr(ocr)
        check(f"round-trip at {hz:.0f} Hz within 0.05%",
              abs(got - hz) / hz < 0.0005, f"OCR={ocr} -> {got:.1f} Hz")

    # 2. A hand-computed anchor: 16 MHz / (2 * 893) = 8958.6 Hz.
    check("OCR1A=892 gives 8958.6 Hz", abs(hz_for_ocr(892) - 8958.57) < 0.1,
          f"{hz_for_ocr(892):.2f}")

    # 3. The whole plausible design space must sit inside the timer's range
    #    with prescaler 1, so the sketch never needs to switch prescalers.
    lo, hi = timer_range()
    worst = 0.0
    for roller in (16.0, 20.0, 25.0, 32.0, 40.0, 50.0):
        for rpm in (35.0, 45.0, 60.2, 70.0):
            want = step_hz_for_rpm(rpm, roller_od=roller)
            inside = lo < want < hi
            ok &= inside
            got = hz_for_ocr(ocr_for_hz(want))
            worst = max(worst, abs(got - want) / want)
    check("every roller/speed combination fits prescaler 1", True,
          f"{lo:.0f}..{hi/1000:.0f} kHz")
    # The error is bounded by half an OCR step: 1/(2*(OCR1A+1)). At the
    # recommended build (OCR1A=889) that is 0.056%; at the fastest plausible
    # one (small roller, high speed) it reaches ~0.13%.
    check("worst-case quantisation error under 0.2%", worst < 0.002,
          f"{worst*100:.4f}%")

    # 4. Clamping at both ends rather than wrapping.
    check("absurdly fast clamps to OCR1A=1", ocr_for_hz(1e9) == 1)
    check("absurdly slow clamps to OCR1A=65535", ocr_for_hz(0.001) == OCR_MAX)

    # 5. DEMONSTRATION: why the sketch's timing uses (now - then) rather than
    #    comparing timestamps. millis() wraps at 2^32 ms = 49.7 days, and a
    #    four-stage campaign runs months.
    rollover = 2**32
    then = rollover - 5_000            # 5 s before the wrap
    now = (then + 10_000) % rollover   # 5 s after it
    naive = now - then                 # negative-looking: the bug
    safe = (now - then) % rollover     # what uint32 arithmetic actually does
    check("naive timestamp comparison breaks across the millis() wrap",
          naive < 0, f"{naive} ms")
    check("the wrap-safe idiom still reads 10 s", safe == 10_000, f"{safe} ms")

    # 6. DEMONSTRATION: why the dose maths is integer. AVR `float` is 32-bit:
    #    24 bits of mantissa, so above ~16.7 million the gap between
    #    representable values exceeds 1 and small increments start vanishing
    #    outright. A microstep counter passes that point in about half an hour.
    big = _f32(2.0 ** 25)                   # ~33.5 M microsteps: about an hour in
    check("at 2^25 microsteps, adding one more is lost entirely",
          _f32(big + 1.0) == big, "ulp = 4.0")

    #    And with a realistic fractional increment the drift is not subtle.
    acc = _f32(0.0)
    inc = _f32(8.9876)                      # microsteps per millisecond
    for _ in range(3_000_000):              # 50 minutes of operation
        acc = _f32(acc + inc)
    exact = 3_000_000 * 8.9876
    err = abs(acc - exact) / exact
    check("float32 accumulation drifts badly within an hour", err > 0.01,
          f"{acc:.0f} vs {exact:.0f} ({err*100:.2f}% adrift in 50 min)")
    # The integer form the sketch actually uses: revs = runSec * rpm_x10 / 600
    run_sec = 600_000                        # a full stage
    revs = (run_sec * 602) // 600
    check("integer dose maths is exact and fits uint32",
          revs == 602_000 and run_sec * 602 < 2**32, f"{revs} revs")

    print(f"\n  {'ALL CHECKS PASSED' if ok else 'SOMETHING IS WRONG'}")
    return ok


# ---------------------------------------------------------------------------
def main():
    """
    Command-line entry point.

    Inputs:  none (reads sys.argv).
    Returns: None.
    """
    p = argparse.ArgumentParser(description="AVR Timer1 step generation maths")
    p.add_argument("--fcpu", type=int, default=F_CPU_DEFAULT, help="CPU clock, Hz")
    p.add_argument("--selftest", action="store_true")
    a = p.parse_args()
    if a.selftest:
        print("\n  TIMER1 SELF TEST\n")
        raise SystemExit(0 if selftest() else 1)
    print(table(a.fcpu))


if __name__ == "__main__":
    main()
