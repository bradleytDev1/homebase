# What's next

Everything so far is drawings, arithmetic and firmware that compiles. Nothing
has been printed, wired or turned on. This is the path from here to a machine
tumbling rock, ordered so the cheap checks come before the expensive
commitments.

**Critical path:** tolerance test print → barrel decision → print set →
assemble → set Vref → calibrate → instrument → first batch.

---

## Decisions needed before anything else

Four answers change what gets bought and built. Nothing downstream is blocked
on the others.

| # | Decision | Options | Notes |
|---|---|---|---|
| 1 | **Barrel route** | A: PVC + rubber + printed lifters (~$26)  ·  B: PVC + printed liner only (~$20)  ·  C: bought rubber barrel ($40–60) | C removes the biggest failure risk. A is the best value and the most interesting. See README § *Build or buy?* |
| 2 | **Which driver** | A4988 · DRV8825 · TB6600 · TMC2209 | All speak STEP/DIR, so the Arduino sketch covers any of them. Determines the Vref procedure, and whether you get StealthChop |
| 3 | **Supply voltage** | 12 V or 24 V | 24 V roughly doubles the stepper's corner speed. Not needed at 169 rpm, but free headroom if you have the supply |
| 4 | **Controller** | Pico + TMC2209 (`firmware/main.py`) · Arduino + STEP/DIR (`firmware/arduino/`) | Both are written and tested. Pico gets VACTUAL and UART diagnostics; Arduino gets whatever driver you already own |

---

## Phase 0a — Local toolchain (5 minutes)

- [ ] `brew tap osx-cross/avr && brew install avr-gcc` — needed for the Arduino
      compile-check (`firmware/arduino/test && make`); the only sweep step that
      does not currently run on this Mac
- [ ] `brew install arduino-cli` — to actually flash the sketch
- [x] OpenSCAD — installed (`openscad@snapshot` 2026.09.18; the plain
      `openscad` cask is disabled over a Gatekeeper check)

## Phase 0 — One test print before spending anything

**~1 hour. Do not skip this.** Every clearance in the CAD is nominal, with no
allowance for your printer's tolerance.

- [ ] Print **one `roller_hub`** and **one `end_plate`** in PETG or ASA
- [ ] Check a **608-2RS** is a firm press fit in the plate pocket — not loose,
      not requiring a hammer. Adjust `BRG_POCKET_FIT` (currently 0.15 mm) and
      reprint the plate alone until it's right
- [ ] Check the **8 mm rod** slides through the hub bore with a little
      resistance. Adjust the `ROD_D + 0.25` clearance if not
- [ ] Measure the printed hub OD against `HUB_OD` and note your printer's
      actual offset — it applies to every other part

Everything else inherits these two fits. Getting them wrong wastes the whole
print set.

## Phase 1 — Mechanical

- [ ] **Measure your real barrel's OD** with calipers and put it in
      `BARREL_OD_MM` (`cad/tumbler.scad`, `firmware/main.py`,
      `firmware/arduino/.../tumbler_uno.ino`). The cradle spacing and the step
      rate both depend on it
- [ ] Run `tools/render.sh` — confirm no interference at your real dimensions
- [ ] Print the set: 2 × `end_plate`, 2 × `roller_hub`, 1 × `motor_mount` in
      PETG/ASA (4 perimeters, 30% infill); 2 × `tyre`, 1 × liner in TPU 95A
- [ ] If going the rubber route: set `RUBBER_T` to the **measured** sheet
      thickness first, re-render, then print the liner
- [ ] Assemble onto a plywood or 2020 base
- [ ] **Spin the barrel by hand.** It should roll freely, stay centred, and
      not climb. This is the moment the 40° contact angle either works or
      doesn't

**Watch for:** the flange lip is only 5 mm proud of the tyre. If the barrel
walks under hand test, increase `FLANGE_H` or the flange diameter before
motorising anything.

## Phase 2 — Drive

- [ ] **Set the driver current before connecting the motor.** Measure Vref
      between trimpot wiper and ground. Read your board's sense resistors
      (`R050`/`R068`/`R100`) — do not assume. Start at 0.6 A; see README
      § *Set the current low*
- [ ] Wire per the header comment in your chosen firmware. **Common ground
      between controller and driver**
- [ ] **Confirm the step rate on D9** with a scope or frequency counter before
      trusting it. Expect ~8,989 Hz. This is the one hardware claim in the
      project that has never been measured
- [ ] Run **unloaded**, ramp up, confirm the barrel turns and the soft start
      doesn't break traction
- [ ] **Calibrate:** run for a measured 10 minutes, count barrel revolutions
      against a stopwatch, and trim `f_clk` (Pico) or `TARGET_RPM_X10`
      (Arduino) until commanded and measured agree
- [ ] Run loaded with a full charge of rock and water. Wind the current *down*
      in 0.1 A steps until it fails to start, then add 30% back

## Phase 3 — Instrumentation

This is the part that makes it worth building rather than buying. Prove each
piece deliberately rather than assuming.

- [ ] Fit the magnet to the barrel end cap and the hall sensor to the frame.
      Confirm **exactly one pulse per revolution** — miscounting here corrupts
      the dose silently
- [ ] **Pull the plug mid-run.** Power back up and confirm it resumes at the
      right revolution count from EEPROM
- [ ] **Induce slip deliberately** — a little water or soap on a tyre — and
      confirm the slip percentage climbs and the fault threshold trips
- [ ] Confirm **direction reversal** fires on schedule and the barrel restarts
      cleanly the other way
- [ ] Let it run 24 hours unattended and check nothing has drifted, overheated
      or loosened. **Feel the motor and the printed mount** — if the mount is
      warm enough to be soft, the current is still too high

## Phase 4 — First batch

- [ ] Source grit: 60/90 and 120/220 SiC, 500 pre-polish, cerium oxide
      (~$25–40 for a four-stage kit), plus ceramic media or plastic pellets
- [ ] Load: barrel ⅔–¾ full, **one rock hardness per batch**, water just below
      the top of the load
- [ ] Run stage 1 to 600,000 revolutions (~7 days at 60 rpm)
- [ ] **Wash everything** between stages — stones, barrel, lid, hands, bench.
      One grain of 60 grit in the polish stage ruins the batch. The firmware
      deliberately will not auto-advance for this reason
- [ ] Record actual revolutions and subjective finish at each stage

---

## Risks worth watching

| Risk | Signal | Mitigation |
|---|---|---|
| Bearing pocket wrong for your printer | Bearing loose or won't seat | Phase 0 test print |
| Barrel walks off the rollers | Drifts axially on hand test | Taller flanges before motorising |
| Drip tray won't fit | Only **20 mm** under the barrel | Raise `FOOT_W`, or a shallow tray |
| Grit seizes cleanout threads | Plug stiffens each time | Clean threads every open, or a compression lid |
| Printed mount softens | Motor mount warm/deformed | Lower current; ASA over PETG |
| Hall miscounts | Dose advances at the wrong rate | Verify pulses/rev in Phase 3 |
| Step rate wrong | Barrel speed off from calculated | Scope D9 in Phase 2 |

---

## Once it runs

Roughly in order of how soon they'd pay off.

**Blender charge simulation.** Blender is already installed. Export the barrel
and liner as STL, fill with a few hundred rigid-body rock proxies, and spin it.
This would settle the **hex-versus-lifter-bars** question empirically, and show
the difference between 35% and 50% of critical — before committing TPU to
either. Crude next to proper DEM, easily good enough to tell cascading from
sliding from centrifuging. *This is the highest-value item here and it costs an
afternoon.*

**Dose–finish curves.** You now have a controlled dose variable that nobody
else in the hobby records. Stop batches at 300/450/600/750 krev and measure
finish. That's an actual Archard curve for your local rock — a genuinely novel
piece of data.

**Acoustic monitoring.** Cascading and sliding have different spectra. A MEMS
mic and an FFT on the Pico could close the loop on the *quality* of the
tumbling action, not just its speed — tune the speed until the spectrum says
cascading. Ball-mill operators have done acoustic load monitoring for decades;
nobody has bothered at hobby scale.

**ESP32 + dashboard.** LEDC does the same hardware-PWM job as Timer1, plus
WiFi. Watch the dose curve from your phone and get a push notification when
slip starts climbing. Appealing for a machine running unattended for six weeks.

**Direct barrel drive (v2).** Couple the stepper straight to a barrel shaft.
Steppers are happiest at 50–60 rpm, which *is* barrel speed, and it eliminates
slip entirely — the roller tumbler's main failure mode. Costs easy barrel
removal and a simple seal.

**Vibratory conversion.** Finishes in days rather than weeks and preserves
shape rather than rounding. Different machine, same electronics, off-centre
masses on the steppers you already have.

---

## Housekeeping

- [ ] Decide whether this should stay in `homebase` (currently sharing a repo
      with a fast.ai notebook) or move to its own repository. It's isolated on
      the `claude/diy-rock-tumbler-6qi824` branch, so moving it is cheap
- [ ] Merge the branch once you're happy with it
- [ ] `MCP_DOCKER` failed to connect in the last session — worth a restart if
      the Blender bridge lives there and you want the simulation work
