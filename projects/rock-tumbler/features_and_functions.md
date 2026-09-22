# Rock tumbler — Features and Functions

**What it does.** The canonical list. Every other document refers to these codes.

**Status:** ✅ **usable now** · 🔨 built, not yet proven · ⬜ planned ·
💡 idea, not approved · ❌ decided against

**✅ means the owner can use it today**, not that the code exists. In this
project that bar is high on purpose: firmware that has only run in a
simulation, and parts that have only been rendered, are 🔨 — because nothing
has been printed, wired or measured yet (**LE-17**).

❓**Q-nn** marks an entry with an unanswered question attached. The link is
maintained both ways and checked.

---

## The code system

A single letter is a domain, a second letter an area within it, and a number
the feature. Codes are **permanent**: a retired feature keeps its code, and a
new sibling never renumbers its neighbours.

```
M        Domain
MA       Area
MA1      Feature
```

| Code | Domain |
|---|---|
| **M** | Mechanical: frame, rollers, plates, mount |
| **B** | Barrel: barrel, liner, lifters, rubber, lid |
| **E** | Electronics: motor, driver, supply, sensing |
| **F** | Firmware: the Pico route and the Arduino route |
| **T** | Tools and verification: calculators, render check, test harnesses |
| **P** | Process: actually tumbling rock |
| **X** | Experiments: research that follows once it runs |

*Domains settled 2026-09-22 (**KM**).*

---

## M — Mechanical

### MA — Cradle and rollers

- 🔨 **MA1** Cradle geometry: 40° contact angle, 97.7 mm shaft spacing, 58.2 mm barrel ride height for a 112 mm OD barrel on 40 mm rollers. Computed twice, in `tools/tumbler_calc.py` and in `cad/tumbler.scad`, agreeing to four figures. Rendered; not built
- 🔨 **MA2** Roller hub: PETG/ASA, 8 mm bore, grub-screwed to the shaft, with end flanges that keep the barrel from walking. Exports as a manifold STL; not printed. *Risk: the flange lip is only 5 mm proud of the tyre*
- 🔨 **MA3** TPU tyre, a 0.4 mm interference fit over the hub. Not printed
- 🔨 **MA4** Two 8 mm shafts in four 608-2RS sealed bearings. Specified; not bought
- 💡 **MA5** Slotted end plates, so the roller spacing adjusts to a different barrel without reprinting. From the heavy-duty reference design ([chapter](chapters/XD1-reference-designs.md)). ❓**Q-09**
- 💡 **MA6** Two barrels side by side on longer rollers, separated by guide rings, so two rock hardnesses or two grit stages run at once. Motor margin falls from ~3.6× to ~1.8×; shaft deflection unchecked; needs a second hall sensor. From the heavy-duty design. ❓**Q-09**

### MB — Frame and drive

- 🔨 **MB1** End plates with bearing pockets cut at the computed spacing (`BRG_POCKET_FIT` 0.15 mm, never tested against a real printer). Not printed
- 🔨 **MB2** NEMA 17 motor mount with slotted holes for belt tension, PETG/ASA only (**KC**). Not printed
- ⬜ **MB3** Baseboard: plywood or 2020 extrusion. Not modelled
- ⬜ **MB4** Drip tray. *Risk: only 20 mm of clearance under the barrel*
- ⬜ **MB5** GT2 belt drive, 20T pulleys, motor outboard of the drip zone. Described in the README; not modelled
- 💡 **MB6** TPU vibration-isolating feet. **Both** reference designs have them and this one has none. ❓**Q-09**
- 💡 **MB7** A guard over the belt and pulleys. Both reference designs guard their drive. ❓**Q-09**
- 💡 **MB8** End plates cut from sheet (HDPE, acrylic or plywood) using a DXF exported from the model, as the Arofarn design's frame is CNC-cut. ❓**Q-09**

---

## B — Barrel

### BA — Barrel body

- ⬜ **BA1** 4-inch PVC DWV pipe with a threaded cleanout plug, lined per **BB**. ❓**Q-01**
- ⬜ **BA2** Bought rubber barrel, a Lortone or Thumler's spare part. ❓**Q-01**
- 💡 **BA3** Wide-mouth HDPE jar with a gasketed lid

### BB — Liner

- 🔨 **BB1** Hexagonal TPU liner, about 6.1 mm of gradual lift. Exports manifold; not printed
- 🔨 **BB2** Lifter-bar liner: six symmetric trapezoidal bars, 6 mm high (**KG**). Rendered; not printed. ❓**Q-01**
- 🔨 **BB3** Rubber sheet behind the printed liner: set `RUBBER_T` and both liners shrink, so the sleeve clamps the rubber with no adhesive. Parametric; no rubber sourced yet. ❓**Q-01**

### BC — Lid

- 💡 **BC1** Compression lid: a disc drawn onto a rubber flange by a central wing nut, keeping threads out of the grit path

---

## E — Electronics

### EA — Motor, driver and supply

- 🔨 **EA1** NEMA 17 at ~169 rpm, ~11 N·cm demand against 40–50 available. The owner has the motors; not wired
- ⬜ **EA2** Stepper driver. A4988, DRV8825, TB6600 or TMC2209; all speak STEP/DIR. ❓**Q-02**
- 🔨 **EA3** Driver current procedure: Vref formulas by sense-resistor value, start at 0.6 A, wind down, add 30% (**KE**). Written in the README; never performed
- ⬜ **EA4** Supply: 12 V or 24 V. ❓**Q-03**

### EB — Sensing

- ⬜ **EB1** Hall sensor (A3144) on the frame, magnet on the barrel end cap: exactly one pulse per revolution. Not fitted
- 💡 **EB2** A local display and rotary knob showing dose progress, speed and slip, so the machine reports without a laptop. The Arofarn design has a four-digit display and encoder, though it shows a countdown. ❓**Q-09**

### EC — Enclosure

- 💡 **EC1** A splash-proof enclosure for the controller and driver, outboard of the drip zone. Both reference designs box their electronics; this one's sit bare. ❓**Q-09**

---

## F — Firmware

### FA — Pico route (Raspberry Pi Pico + TMC2209)

- 🔨 **FA1** TMC2209 single-wire UART driver using `VACTUAL`, the chip's internal step generator. CRC cross-checked two ways; the read datagram matches the published example. Never on hardware. ❓**Q-04**
- 🔨 **FA2** Pico control loop: soft start, reversal, odometer in a flash file, slip detection. A simulated six-week campaign passes. Never on hardware. ❓**Q-04**

### FB — Arduino route (Uno/Nano + any STEP/DIR driver)

- 🔨 **FB1** Timer1 CTC hardware step generation on D9 (**KI**). Compiles clean for the ATmega328P; the step rate has never been measured. ❓**Q-04**
- 🔨 **FB2** EEPROM odometer: a 32-slot checksummed ring for wear levelling and power-cut safety. Compiles; never run. ❓**Q-04**
- 🔨 **FB3** Wrap-safe timing and integer-only dose arithmetic (**KJ**). Compiles; never run

### FC — Behaviour both routes share

- 🔨 **FC1** Stage targets measured in barrel revolutions (**KA**)
- 🔨 **FC2** Direction reversal every six hours through a controlled stop
- 🔨 **FC3** Slip detection: commanded against measured revolutions, with a warning at 15% and a fault latch at 40%
- 🔨 **FC4** Stop and wait at the end of each stage; never auto-advance (**KF**)

### FD — Calibration

- ⬜ **FD1** Trim `f_clk` (Pico) or `TARGET_RPM_X10` (Arduino) against a stopwatch count of barrel revolutions

---

## T — Tools and verification

### TA — Calculators

- ✅ **TA1** `tools/tumbler_calc.py`: barrel speed from critical speed, cradle geometry, torque, step rate, `VACTUAL`. Self-test anchored against a real Lortone 3A
- ✅ **TA2** `tools/timer1_calc.py`: AVR Timer1 arithmetic with its quantisation bound, and numerical demonstrations of the two long-run AVR bugs

### TB — Verification

- ✅ **TB1** `tools/render.sh`: parses the CAD with OpenSCAD, exports every part as a manifold STL, runs interference tests with a control, and writes renders. Every target is deleted before it is generated (**LE-18**, fixed 0.6.1)
- 🔨 **TB2** Arduino compile check (`firmware/arduino/test/`): real ATmega328P headers through a minimal Arduino shim. Passed in the cloud container; **cannot run on this Mac until `avr-gcc` is installed**
- ✅ **TB3** Firmware self-tests: `firmware/tmc2209.py` and `firmware/main.py --selftest`, the latter a simulated six-week campaign
- ⬜ **TB4** The project version shown in the upper-right corner of every interface: both calculators' output, `render.sh`'s output, and each firmware's serial banner. Wired to the single `VERSION` file. Required by the owner's standing rule for all projects
- ⬜ **TB5** A gate that compares the OpenSCAD geometry echo against `tumbler_calc.py`, so the four-figure agreement in **LE-07** stops being checked by eye

---

## P — Process

### PA — Running a batch

- ⬜ **PA1** Four grit stages, 600,000 revolutions each: 60/90 SiC, 120/220 SiC, 500 pre-polish, cerium oxide
- ⬜ **PA2** Loading rules: barrel ⅔–¾ full, one rock hardness per batch, water just below the top of the load, ceramic media as filler
- ⬜ **PA3** Record actual revolutions and the finish at each stage

---

## X — Experiments

### XA — Simulation

- 💡 **XA1** Blender rigid-body simulation of the charge. It would settle hex-versus-lifter-bars and 35%-versus-50% of critical before committing TPU. Highest value of the experiments; about an afternoon

### XB — Measurement

- 💡 **XB1** Dose–finish curves: stop batches at 300, 450, 600 and 750 thousand revolutions and measure the finish
- 💡 **XB2** Acoustic monitoring: tune the speed until an FFT of the barrel's sound says "cascading"
- 💡 **XB3** ESP32 with a phone dashboard for watching a run remotely. A platform change if built (**KL**)

### XC — Other machines

- 💡 **XC1** Direct barrel drive: the stepper coupled straight to a barrel shaft, which eliminates slip
- 💡 **XC2** Vibratory conversion: off-centre masses on the steppers already owned

### XD — Reference designs

- ✅ **XD1** Two published designs evaluated with measurements: Arofarn's NEMA 17 CNC tumbler and 3DPrintOrlando's heavy-duty adjustable tumbler. Neither reaches the correct speed band: one tops out at 19–22% of critical, the other runs to 86–92%. Seven ideas extracted (**MA5**, **MA6**, **MB6**, **MB7**, **MB8**, **EB2**, **EC1**). Full evaluation: [chapter](chapters/XD1-reference-designs.md). Whether the downloaded files may be committed: ❓**Q-08**
