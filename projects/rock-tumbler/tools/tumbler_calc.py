#!/usr/bin/env python3
"""
tumbler_calc.py -- Design calculator for a stepper-driven rotary rock tumbler.

PURPOSE
    A rotary tumbler is a barrel rolling on two parallel rollers. Almost every
    dimension you care about falls out of four numbers: barrel inside diameter,
    roller outside diameter, the angle at which the rollers cradle the barrel,
    and the fraction of "critical speed" you want the barrel to turn at.

    This module turns those four numbers into the things you actually need to
    cut, print and program: roller centre-to-centre spacing, barrel ride height,
    required roller RPM, stepper step rate, and the TMC2209 VACTUAL register
    value that makes the motor spin at that rate with no step pulses at all.

THEORY (the one equation that matters)
    A barrel centrifuges -- the load pins to the wall and stops tumbling --
    when centripetal acceleration at the wall equals gravity:

        omega^2 * R = g   ->   omega = sqrt(g / R)

    Converting to RPM with R = D/2 and g = 9.80665 m/s^2:

        N_critical = (60 / 2*pi) * sqrt(g / (D/2)) = 42.3 / sqrt(D)   [D in metres]

    That 42.3 is the same constant used for ball mills in mineral processing;
    a rock tumbler is a ball mill that has been told to relax. Ball mills run
    at 65-75% of critical (violent "cataracting" impact, because they want to
    fracture rock). Tumblers want gentle abrasion, not fracture, so they run
    at roughly 35-50% of critical -- a "cascading" roll where the load climbs
    one wall and slides back down over itself.

USAGE
    python3 tumbler_calc.py                 # worked example, default design
    python3 tumbler_calc.py --barrel 150    # 150 mm barrel
    python3 tumbler_calc.py --selftest      # verify the maths against knowns

REFERENCES
    Wills, B.A. & Finch, J. -- Mineral Processing Technology, 8th ed., ch. 7
        (tumbling mills, critical speed, cascading vs cataracting).
    Trinamic/ADI TMC2209 datasheet rev 1.09 -- VACTUAL (0x22), IHOLD_IRUN (0x10).
    Hobart King, rocktumbler.com -- empirical barrel speed tables, grit stages.
"""

import argparse
import math

# --- Physical constants -----------------------------------------------------
G = 9.80665                 # standard gravity, m/s^2
CRIT_K = 60.0 / (2.0 * math.pi) * math.sqrt(2.0 * G)   # == 42.3, the mill constant


# ---------------------------------------------------------------------------
def critical_rpm(barrel_id_mm):
    """
    Speed at which the load centrifuges against the barrel wall and stops
    tumbling. This is the ceiling; you never run here.

    Inputs:
        barrel_id_mm (float) -- barrel INSIDE diameter in millimetres. Inside,
                                not outside: the load rides on the inner wall.
    Returns:
        float -- critical speed in revolutions per minute.
    """
    d_m = barrel_id_mm / 1000.0
    return CRIT_K / math.sqrt(d_m)


# ---------------------------------------------------------------------------
def barrel_rpm(barrel_id_mm, crit_fraction=0.45):
    """
    Working barrel speed for good cascading action.

    Inputs:
        barrel_id_mm  (float) -- barrel inside diameter, mm.
        crit_fraction (float) -- fraction of critical speed. 0.35 is a slow,
                                 gentle roll (good for fragile or already-shaped
                                 stone in the polish stage); 0.50 is a brisk
                                 cascade (good for coarse grind). 0.45 default.
    Returns:
        float -- target barrel speed in RPM.
    """
    return critical_rpm(barrel_id_mm) * crit_fraction


# ---------------------------------------------------------------------------
def roller_spacing(barrel_od_mm, roller_od_mm, contact_angle_deg=40.0):
    """
    Centre-to-centre distance between the two roller shafts, and the resulting
    barrel ride height.

    Geometry: the barrel of radius R rests in the vee formed by two rollers of
    radius r. If the contact points sit at angle alpha either side of bottom
    dead centre, then the line from barrel centre to roller centre has length
    (R + r) and makes angle alpha with vertical. Therefore:

        half_spacing = (R + r) * sin(alpha)
        ride_height  = (R + r) * cos(alpha)      [barrel axis above roller axes]

    Choosing alpha:
        < 30 deg -- cradle too shallow; the barrel wanders and walks.
        40 deg   -- sweet spot. Good traction, stable, easy to lift the barrel out.
        > 50 deg -- barrel sits deep, drive traction falls off and it can climb.

    Inputs:
        barrel_od_mm      (float) -- barrel OUTSIDE diameter, mm (this is what
                                     actually touches the rollers).
        roller_od_mm      (float) -- roller outside diameter including its tyre, mm.
        contact_angle_deg (float) -- alpha, degrees from bottom dead centre.
    Returns:
        dict with keys 'spacing_mm', 'ride_height_mm', 'contact_angle_deg'.
    """
    a = math.radians(contact_angle_deg)
    sum_r = (barrel_od_mm + roller_od_mm) / 2.0
    return {
        "spacing_mm": 2.0 * sum_r * math.sin(a),
        "ride_height_mm": sum_r * math.cos(a),
        "contact_angle_deg": contact_angle_deg,
    }


# ---------------------------------------------------------------------------
def roller_rpm(barrel_od_mm, roller_od_mm, target_barrel_rpm):
    """
    Friction drive: the roller surface and the barrel surface move at the same
    linear velocity, so the roller spins faster by the diameter ratio.

        v = pi * D_barrel * N_barrel = pi * d_roller * N_roller
        N_roller = N_barrel * D_barrel / d_roller

    Note this is a SPEED INCREASER, which is the one awkward thing about roller
    tumblers driven by steppers: steppers make their best torque at low RPM,
    and a friction drive asks them to run fast. Fortunately the torque demand
    is tiny (see required_torque), so there is plenty of headroom.

    Inputs:
        barrel_od_mm      (float) -- barrel outside diameter, mm.
        roller_od_mm      (float) -- roller outside diameter, mm.
        target_barrel_rpm (float) -- desired barrel speed, RPM.
    Returns:
        float -- required roller speed, RPM.
    """
    return target_barrel_rpm * barrel_od_mm / roller_od_mm


# ---------------------------------------------------------------------------
def required_torque(load_kg, barrel_id_mm, roller_od_mm, barrel_od_mm,
                    cm_offset_frac=0.55, repose_deg=35.0, efficiency=0.75):
    """
    Torque the motor must supply, and the mechanical power that implies.

    Model: the tumbling load is a mass whose centre of mass is dragged off
    vertical by the rotation. Its centre sits at some fraction of the barrel
    radius from the axis, displaced by the dynamic angle of repose. The
    restoring moment the motor fights is:

        T_barrel = m * g * r_cm * sin(theta_repose)

    This deliberately ignores media-on-media shear losses, so divide by an
    efficiency factor to stay honest.

    Inputs:
        load_kg        (float) -- total mass inside the barrel: rock + grit +
                                  ceramic media + water.
        barrel_id_mm   (float) -- barrel inside diameter, mm.
        roller_od_mm   (float) -- roller outside diameter, mm.
        barrel_od_mm   (float) -- barrel outside diameter, mm.
        cm_offset_frac (float) -- centre of mass radius as a fraction of the
                                  barrel inside radius. ~0.55 for a 2/3-full load.
        repose_deg     (float) -- dynamic angle of repose of a wet grit slurry,
                                  degrees. 30-40 is typical.
        efficiency     (float) -- drivetrain + internal shear efficiency, 0-1.
    Returns:
        dict: 'barrel_Nm', 'roller_Nm' (what the motor actually sees),
              'power_W' at the stated barrel RPM is NOT included here --
              call mech_power() for that.
    """
    r_cm = (barrel_id_mm / 2000.0) * cm_offset_frac        # metres
    t_barrel = load_kg * G * r_cm * math.sin(math.radians(repose_deg))
    t_barrel /= efficiency
    # Torque scales down through the friction drive by the radius ratio,
    # exactly as speed scales up. Free lunch: none, as usual.
    t_roller = t_barrel * (roller_od_mm / barrel_od_mm)
    return {"barrel_Nm": t_barrel, "roller_Nm": t_roller}


# ---------------------------------------------------------------------------
def mech_power(torque_nm, rpm):
    """
    Mechanical power at the shaft.

    Inputs:
        torque_nm (float) -- torque, newton-metres.
        rpm       (float) -- rotational speed, revolutions per minute.
    Returns:
        float -- power in watts.
    """
    return torque_nm * rpm * 2.0 * math.pi / 60.0


# ---------------------------------------------------------------------------
def step_rate(motor_rpm, full_steps_per_rev=200, microsteps=16, gear_ratio=1.0):
    """
    Microstep pulse rate the controller must generate.

    Inputs:
        motor_rpm          (float) -- speed at the ROLLER, RPM.
        full_steps_per_rev (int)   -- 200 for a 1.8 deg motor, 400 for 0.9 deg.
        microsteps         (int)   -- driver microstep setting (1,2,4,8,16,...).
        gear_ratio         (float) -- motor revs per roller rev. 1.0 for direct
                                      drive; 2.0 for a 2:1 belt reduction (motor
                                      turns twice per roller turn).
    Returns:
        dict: 'motor_rpm', 'usteps_per_rev', 'usteps_per_sec'.
    """
    m_rpm = motor_rpm * gear_ratio
    upr = full_steps_per_rev * microsteps
    return {
        "motor_rpm": m_rpm,
        "usteps_per_rev": upr,
        "usteps_per_sec": m_rpm * upr / 60.0,
    }


# ---------------------------------------------------------------------------
def tmc2209_vactual(usteps_per_sec, f_clk_hz=12_000_000):
    """
    Convert a desired microstep rate into the TMC2209's VACTUAL register value.

    The TMC2209 has an internal step generator. Write a nonzero velocity into
    VACTUAL (register 0x22) over UART and the driver steps the motor itself,
    forever, with no STEP pulses from the microcontroller at all. For a machine
    whose entire job is "turn at one constant speed for six weeks", this is
    close to perfect: no timer interrupt to jitter, no CPU load, and changing
    speed or direction is a single register write. Negative values reverse.

    From the datasheet, one velocity LSB corresponds to f_CLK / 2^24 microsteps
    per second. With the internal 12 MHz oscillator that is ~0.7152 usteps/s.

        VACTUAL = usteps_per_sec * 2^24 / f_CLK

    CAVEAT WORTH PRINTING ON THE LID: the internal oscillator is only specified
    to a few percent, and the exact microstep unit interacts with the MRES
    setting. Treat the returned value as a starting point and trim it with the
    measured barrel revolution count -- which the firmware logs anyway, because
    revolutions are the number you actually care about.

    Inputs:
        usteps_per_sec (float) -- desired microstep rate.
        f_clk_hz       (float) -- driver clock. 12e6 for the internal oscillator.
    Returns:
        int -- VACTUAL value, clamped to the signed 24-bit register range.
    """
    v = int(round(usteps_per_sec * (1 << 24) / f_clk_hz))
    limit = (1 << 23) - 1
    return max(-limit, min(limit, v))


# ---------------------------------------------------------------------------
def design(barrel_id=100.0, wall=6.0, roller_od=40.0, crit_fraction=0.45,
           contact_angle=40.0, load_kg=1.5, microsteps=16, gear_ratio=1.0,
           full_steps=200):
    """
    Run the whole chain and return one dictionary describing the machine.

    Inputs:
        barrel_id     (float) -- barrel inside diameter, mm.
        wall          (float) -- barrel wall thickness, mm (ID + 2*wall = OD).
        roller_od     (float) -- roller outside diameter including tyre, mm.
        crit_fraction (float) -- fraction of critical speed to run at.
        contact_angle (float) -- roller cradle half-angle, degrees.
        load_kg       (float) -- total charge mass inside the barrel, kg.
        microsteps    (int)   -- driver microstep setting.
        gear_ratio    (float) -- motor revs per roller rev.
        full_steps    (int)   -- motor full steps per revolution.
    Returns:
        dict -- every derived quantity, ready to print or to paste into the
                OpenSCAD parameter block.
    """
    barrel_od = barrel_id + 2.0 * wall
    n_crit = critical_rpm(barrel_id)
    n_barrel = n_crit * crit_fraction
    geom = roller_spacing(barrel_od, roller_od, contact_angle)
    n_roller = roller_rpm(barrel_od, roller_od, n_barrel)
    tq = required_torque(load_kg, barrel_id, roller_od, barrel_od)
    rate = step_rate(n_roller, full_steps, microsteps, gear_ratio)
    return {
        "barrel_id_mm": barrel_id,
        "barrel_od_mm": barrel_od,
        "roller_od_mm": roller_od,
        "critical_rpm": n_crit,
        "crit_fraction": crit_fraction,
        "barrel_rpm": n_barrel,
        "roller_rpm": n_roller,
        "spacing_mm": geom["spacing_mm"],
        "ride_height_mm": geom["ride_height_mm"],
        "contact_angle_deg": contact_angle,
        "torque_barrel_Nm": tq["barrel_Nm"],
        "torque_roller_Ncm": tq["roller_Nm"] * 100.0,
        "power_W": mech_power(tq["barrel_Nm"], n_barrel),
        "motor_rpm": rate["motor_rpm"],
        "usteps_per_sec": rate["usteps_per_sec"],
        "vactual": tmc2209_vactual(rate["usteps_per_sec"]),
        "revs_per_day": n_barrel * 60.0 * 24.0,
    }


# ---------------------------------------------------------------------------
def report(d):
    """
    Pretty-print a design dictionary as a build sheet.

    Inputs:
        d (dict) -- the output of design().
    Returns:
        str -- multi-line human-readable report.
    """
    L = []
    L.append("=" * 62)
    L.append("  ROCK TUMBLER DESIGN SHEET")
    L.append("=" * 62)
    L.append("")
    L.append("  BARREL")
    L.append(f"    inside dia          {d['barrel_id_mm']:8.1f} mm")
    L.append(f"    outside dia         {d['barrel_od_mm']:8.1f} mm")
    L.append(f"    critical speed      {d['critical_rpm']:8.1f} rpm  (do not go here)")
    L.append(f"    target speed        {d['barrel_rpm']:8.1f} rpm  "
             f"({d['crit_fraction']*100:.0f}% of critical)")
    L.append(f"    revolutions / day   {d['revs_per_day']:8.0f}")
    L.append("")
    L.append("  ROLLER CRADLE  -- print these into the end plates")
    L.append(f"    roller dia          {d['roller_od_mm']:8.1f} mm")
    L.append(f"    contact angle       {d['contact_angle_deg']:8.1f} deg from vertical")
    L.append(f"    shaft spacing (c-c) {d['spacing_mm']:8.1f} mm")
    L.append(f"    barrel ride height  {d['ride_height_mm']:8.1f} mm above shaft axes")
    L.append("")
    L.append("  DRIVE")
    L.append(f"    roller speed        {d['roller_rpm']:8.1f} rpm")
    L.append(f"    motor speed         {d['motor_rpm']:8.1f} rpm")
    L.append(f"    torque at barrel    {d['torque_barrel_Nm']:8.3f} N.m")
    L.append(f"    torque at motor     {d['torque_roller_Ncm']:8.2f} N.cm  "
             f"(NEMA 17 holding ~40-50 N.cm)")
    L.append(f"    mechanical power    {d['power_W']:8.2f} W")
    L.append("")
    L.append("  CONTROLLER")
    L.append(f"    microstep rate      {d['usteps_per_sec']:8.0f} usteps/s")
    L.append(f"    TMC2209 VACTUAL     {d['vactual']:8d}  (trim against measured revs)")
    L.append("")
    L.append("=" * 62)
    return "\n".join(L)


# ---------------------------------------------------------------------------
def selftest():
    """
    Sanity-check the maths against values that are independently known, so a
    typo in a constant cannot quietly ship a machine that centrifuges.

    Inputs:  none.
    Returns: bool -- True if every check passes; prints each result.
    """
    ok = True

    # 1. The mill constant should reproduce the textbook 42.3.
    got = CRIT_K
    ok &= abs(got - 42.3) < 0.05
    print(f"  [{'ok' if abs(got-42.3)<0.05 else 'FAIL'}] mill constant = {got:.3f} (expect 42.3)")

    # 2. A 4.5 in (114.3 mm) barrel -- the Lortone 3A / Thumler's B size --
    #    should land near the 50-60 rpm those machines actually run at.
    n = barrel_rpm(114.3, 0.45)
    good = 48.0 <= n <= 62.0
    ok &= good
    print(f"  [{'ok' if good else 'FAIL'}] 4.5in barrel at 45% crit = {n:.1f} rpm (expect 50-60)")

    # 3. Roller spacing degenerates correctly: at 90 deg contact angle the
    #    rollers sit exactly one barrel-plus-roller diameter apart and the
    #    barrel rides at zero height (it is pinched, not cradled).
    g = roller_spacing(100.0, 20.0, 90.0)
    good = abs(g["spacing_mm"] - 120.0) < 1e-9 and abs(g["ride_height_mm"]) < 1e-9
    ok &= good
    print(f"  [{'ok' if good else 'FAIL'}] spacing at 90deg = {g['spacing_mm']:.1f} mm, "
          f"height = {g['ride_height_mm']:.1f} mm (expect 120.0, 0.0)")

    # 4. Friction drive preserves surface speed: a 5:1 diameter ratio must
    #    give a 5:1 speed ratio.
    r = roller_rpm(100.0, 20.0, 60.0)
    good = abs(r - 300.0) < 1e-9
    ok &= good
    print(f"  [{'ok' if good else 'FAIL'}] 100/20 barrel:roller at 60 rpm -> {r:.1f} rpm roller")

    # 5. Torque must scale DOWN by the same ratio that speed scales UP --
    #    power in equals power out.
    t = required_torque(1.5, 100.0, 20.0, 112.0)
    ratio = t["roller_Nm"] / t["barrel_Nm"]
    good = abs(ratio - 20.0 / 112.0) < 1e-9
    ok &= good
    print(f"  [{'ok' if good else 'FAIL'}] torque ratio = {ratio:.4f} (expect {20/112:.4f})")

    # 6. VACTUAL round-trip: 0.7152 usteps/s per LSB.
    v = tmc2209_vactual(12_800.0)
    back = v * 12_000_000 / (1 << 24)
    good = abs(back - 12_800.0) < 1.0
    ok &= good
    print(f"  [{'ok' if good else 'FAIL'}] VACTUAL {v} -> {back:.1f} usteps/s (expect 12800)")

    print(f"\n  {'ALL CHECKS PASSED' if ok else 'SOMETHING IS WRONG'}")
    return ok


# ---------------------------------------------------------------------------
def main():
    """
    Command-line entry point.

    Inputs:  none (reads sys.argv).
    Returns: None. Prints a design sheet or the self-test results.
    """
    p = argparse.ArgumentParser(description="Stepper rock tumbler design calculator")
    p.add_argument("--barrel", type=float, default=100.0, help="barrel inside dia, mm")
    p.add_argument("--wall", type=float, default=6.0, help="barrel wall thickness, mm")
    p.add_argument("--roller", type=float, default=40.0, help="roller outside dia, mm")
    p.add_argument("--crit", type=float, default=0.45, help="fraction of critical speed")
    p.add_argument("--angle", type=float, default=40.0, help="roller contact angle, deg")
    p.add_argument("--load", type=float, default=1.5, help="charge mass, kg")
    p.add_argument("--microsteps", type=int, default=16, help="driver microstepping")
    p.add_argument("--gear", type=float, default=1.0, help="motor revs per roller rev")
    p.add_argument("--selftest", action="store_true", help="run maths self-checks")
    a = p.parse_args()

    if a.selftest:
        print("\n  SELF TEST\n")
        raise SystemExit(0 if selftest() else 1)

    print(report(design(a.barrel, a.wall, a.roller, a.crit,
                        a.angle, a.load, a.microsteps, a.gear)))


if __name__ == "__main__":
    main()
