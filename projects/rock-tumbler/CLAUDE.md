# Rock tumbler — working notes for Claude

A two-roller rotary rock tumbler driven by a NEMA 17. Design is derived from
mill physics rather than rules of thumb; see `README.md` for the full rationale.

## Where things stand

Designed and verified in software; **nothing physical exists yet**. Read
`WHATS_NEXT.md` before starting work — it carries the prioritised plan, the
four open decisions, and the risk list. `LESSONS_LEARNED.md` records the
verification failures that shaped how this repo checks itself.

Build log, newest first:

| Done | What |
|---|---|
| CAD rendered and proven | OpenSCAD 2026.09.18 run for the first time. Found the file had never parsed (adjacent string literals) and that the rollers sat 3 mm off, putting the barrel end on a flange. Both fixed and proven by boolean interference test |
| `tools/render.sh` added | Parse, manifold export, interference tests with a control, renders. Mandatory after any CAD change |
| Barrel design revised | Lifter bars alongside the hex liner; `RUBBER_T` lets a rubber sheet sit behind the printed liner with no adhesive |
| Arduino route added | Timer1 CTC hardware step generation; wrap-safe timing; integer dose maths; EEPROM ring odometer |
| Pico route + calculators | TMC2209 VACTUAL drive, revolution-dose odometer, slip detection, reversal |

## Layout

```
tools/tumbler_calc.py       barrel speed, cradle geometry, torque, VACTUAL
tools/render.sh             CAD: parse, manifold, interference, renders
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
tools/render.sh                           # CAD: parse, manifold, interference, renders
```

The Arduino compile-check needs the AVR toolchain, which is **not currently
installed on this Mac**: `brew tap osx-cross/avr && brew install avr-gcc`.
The other five run as-is.

All six must pass before any commit. They run without hardware.

`tools/render.sh` is not optional after a CAD change. The file sat committed
for several sessions without OpenSCAD ever being run against it, and when it
finally was it did not parse at all, and then had a 3 mm misalignment that put
the barrel end on a roller flange. Neither was visible by reading it.

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
brew install --cask openscad@snapshot   # render the CAD; the plain
                                        # "openscad" cask is disabled (Gatekeeper)
brew tap osx-cross/avr && brew install avr-gcc   # for firmware/arduino/test
brew install arduino-cli              # to actually flash the sketch
```

## Open items

- **The liner can be printed with or without a rubber sheet behind it.** Set
  `RUBBER_T` in `cad/tumbler.scad` to the measured sheet thickness; both liner
  modules shrink so the printed sleeve clamps the rubber without adhesive.
- ~~The OpenSCAD has never been visually rendered.~~ **Done.** OpenSCAD
  2026.09.18 (`brew install --cask openscad@snapshot`; the plain `openscad`
  cask is disabled over a Gatekeeper check). All six parts export manifold
  STLs, the barrel clears both the end plates and the roller flanges, and the
  echoed geometry matches `tumbler_calc.py` to four figures. Renders are in
  `cad/renders/`.
- **Nothing has been printed or measured in the real world yet.** Every
  clearance above is nominal, with no allowance for printer tolerance. Print
  one roller hub and one end plate first and check the 608 bearing is a firm
  press fit before committing to the set.
- The Arduino sketch is compile-verified, not run on hardware. Timer1 output
  should be confirmed with a scope or frequency counter on D9 before trusting
  the step rate.
- `f_clk` in the Pico driver and `TARGET_RPM_X10` in the sketch both want
  trimming against a measured barrel revolution count after first assembly.
