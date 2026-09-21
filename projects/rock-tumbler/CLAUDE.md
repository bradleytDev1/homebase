# Rock tumbler — working notes for Claude

A two-roller rotary rock tumbler driven by a NEMA 17. Design is derived from
mill physics rather than rules of thumb; see `README.md` for the full rationale.

## Layout

```
tools/tumbler_calc.py       barrel speed, cradle geometry, torque, VACTUAL
tools/timer1_calc.py        AVR Timer1 step-generation maths
cad/tumbler.scad            parametric OpenSCAD model
firmware/tmc2209.py         TMC2209 single-wire UART driver      } Pico route
firmware/main.py            control loop, odometer, slip detect  }
firmware/arduino/tumbler_uno/tumbler_uno.ino   Arduino + any STEP/DIR driver
firmware/arduino/test/      avr-gcc compile-check harness (shim, not runtime)
```

Two firmware routes drive the same machine. Pick by available parts.

## Verify everything

```bash
python3 tools/tumbler_calc.py --selftest
python3 tools/timer1_calc.py  --selftest
python3 firmware/tmc2209.py
python3 firmware/main.py --selftest       # simulates a six-week campaign
cd firmware/arduino/test && make          # compile-checks the .ino, expect 0 warnings
```

All five must pass before any commit. They run without hardware.

## Constraints that are load-bearing

Changing any of these silently breaks a machine that runs unattended for six
weeks, so treat them as invariants unless the physics is re-derived:

- **Barrel speed is 35–50% of critical**, `N_crit = 42.3/sqrt(D)`. Above it the
  load centrifuges; below it, it slides as a lump instead of cascading.
- **D9 is not reassignable** in the Arduino sketch. It is OC1A, the hardware
  toggle output that makes Timer1 step generation work at all.
- **All AVR dose arithmetic stays integer.** AVR `float` is 32-bit; a
  microstep counter loses precision within the hour. `timer1_calc.py`
  demonstrates the failure numerically.
- **All AVR timing uses `(uint32_t)(now - then) >= gap`.** `millis()` wraps at
  49.7 days and campaigns run months.
- **Progress is measured in barrel revolutions, not elapsed time.** Abrasive
  wear follows Archard's law and scales with sliding distance.
- **Structural prints are PETG/ASA, never PLA.** A continuously energised
  stepper exceeds PLA's glass transition.
- **Driver current runs low** (~0.4–0.6 A). The load needs ~11 N·cm against a
  NEMA 17's 40–50; surplus current is just heat for a thousand hours.

The firmware deliberately does *not* auto-advance between grit stages. That is
intentional — the barrel must be washed by hand first, and the machine cannot
verify that happened.

## macOS toolchain

```bash
brew install --cask openscad          # render the CAD
brew tap osx-cross/avr && brew install avr-gcc   # for firmware/arduino/test
brew install arduino-cli              # to actually flash the sketch
```

## Open items

- **The liner can be printed with or without a rubber sheet behind it.** Set
  `RUBBER_T` in `cad/tumbler.scad` to the measured sheet thickness; both liner
  modules shrink so the printed sleeve clamps the rubber without adhesive.
- **The OpenSCAD has never been visually rendered.** It was written and
  structurally checked in a container without OpenSCAD installed. Render the
  assembly view first (`openscad cad/tumbler.scad`, no `-D`) and confirm the
  barrel sits in the vee at the computed ride height before printing anything.
- The Arduino sketch is compile-verified, not run on hardware. Timer1 output
  should be confirmed with a scope or frequency counter on D9 before trusting
  the step rate.
- `f_clk` in the Pico driver and `TARGET_RPM_X10` in the sketch both want
  trimming against a measured barrel revolution count after first assembly.
