# XD1 — Two published designs, evaluated

*Chapter for **XD1**. Evaluated 2026-09-22 at the owner's request: "thoroughly
evaluate those two and modify our plan or determine what's usable from them."
The canonical list is [`../features_and_functions.md`](../features_and_functions.md);
where this chapter and the list disagree, the list wins.*

---

## The short version

Two open designs were downloaded into this folder, and each was taken apart
with measurements rather than impressions: STL meshes measured, a CAD source
file and a DXF parsed, the firmware read, and the build photos checked.

**The headline is speed.** Run through this project's physics model, the two
designs miss the correct band in opposite directions:

| | Drive | Top barrel speed | % of critical | Correct band (**KB**) |
|---|---|---|---|---|
| **Arofarn**, *Affordable Rock Tumbler — NEMA17* | Stepper through printed gears | 25–28 rpm | **19–22%**: cannot reach rock speed | 35–50% |
| **3DPrintOrlando**, *Heavy Duty & Adjustable* | DC gearmotor, PWM dial | 110–126 rpm | **86–92%**: near centrifuging | 35–50% |

Neither chose its speed from the physics. One is a slow polisher for
metal-filled prints; the other hands over a dial whose right setting,
roughly half throttle, it never tells you. This is the strongest outside
evidence yet for **KB** and for deriving speed rather than choosing it.

**What is worth taking**, in order of value:

1. **Vibration-isolating feet.** Both designs have them; this one doesn't.
   Cheap, printable in TPU, and aimed at the noise problem (**MB6**).
2. **A guard over the drive.** Both designs guard their gears or belt; this
   one's belt is exposed (**MB7**).
3. **An electronics enclosure.** Both designs box the electronics; this one's
   Arduino and driver sit bare near a wet machine (**EC1**).
4. **Two barrels on longer rollers**, separated by guide rings. That would
   allow two rock hardnesses at once, which the one-hardness-per-batch rule
   (**PA2**) otherwise forbids. Our motor has the torque; the odometer would
   need a second sensor (**MA6**).
5. **Slotted end plates** so the roller spacing adjusts to different barrels
   without reprinting (**MA5**).
6. **A local display and knob**, so the machine shows its own progress
   rather than needing a laptop on a serial cable (**EB2**).
7. **End plates cut from sheet** (HDPE, acrylic or plywood) from a DXF the
   model exports, as Arofarn cut its frame by CNC (**MB8**).

**What confirms what we already have:** the Arofarn build is almost exactly
our barrel route A (PVC pipe, screw caps, printed faceted liner, 8 mm rods,
608 bearings, NEMA 17). It exists, it was photographed working, and it
polishes. That is real evidence the architecture works.

**What not to take:** their geometry (licensing, and seven of the heavy-duty
parts are broken meshes), their firmware (it makes the exact AccelStepper
mistake **KI** avoids), gear drive (we need no reduction, **KD**), and a DC
motor (no exact speed, nothing to count).

Two decisions for the owner are filed: **Q-08** (whether these files may be
committed) and **Q-09** (which of the ideas above to adopt).

---

## Method, and how far to trust each number

| Kind | Source |
|---|---|
| **Measured** | Mesh bounding boxes and facet directions (Python over the STLs); Arofarn's frame hole positions (its `frame.dxf`); gear tooth counts and module (its FreeCAD file, `polisseur.fcstd`); firmware behaviour (its `code_polisseur.ino`, from the author's repository); mesh closure (every edge checked for exactly two triangles) |
| **Stated by the author** | Motor speeds, pulley sizes, rod sizes and supplies (the Printables pages and the Arofarn README) |
| **Estimated** | Arofarn's effective roller diameter with its O-ring (~26 mm) and which diameter of its barrel touches the rollers (110–125 mm), both read from photographs. That is why its numbers are given as ranges |
| **Not measured** | The heavy-duty design's range of roller-spacing adjustment. Its slots sit on a curved, sloping face that a straight slice cannot isolate, and the part is an open mesh that OpenSCAD refuses to cut. It is recorded as adjustable, without a number |

One of my own guesses was corrected by measuring. The heavy-duty author says
a 100 mm drum's "max RPM should be 125". I first read that as critical speed
(133.7 rpm by our formula; close). Measuring the parts showed it is the
**drive's top speed**: a 421 rpm motor, 1:1 pulleys, a 30 mm roller, a 100 mm
drum, giving 421 × 30 / 100 = 126 rpm. The closeness to critical speed is a
coincidence, and a dangerous one: flat out, that machine nearly centrifuges.

---

## Arofarn — *Affordable Rock Tumbler, NEMA17 version for CNC routing*

Printables, 2021, updated 2022 · remix of Thingiverse 2744886 ·
**CC BY-SA 4.0** · firmware **GPLv3** · source at framagit.org/arofarn/polisseur

### What it is

A NEMA 17 turning M8 threaded rods through a printed **16/25-tooth, module 2
gear pair** (a 1.5625:1 reduction). The barrel rides on four 24.4 mm printed
pulleys fitted with O-rings. The frame is two 15 mm HDPE plates, cut by CNC
from a DXF, joined by 10 mm rods. The barrel is a 110 mm PVC pipe with
screw-on caps, fitted with a printed **decagonal** insert. An ATmega328 board
with a four-digit display and a rotary encoder sets speed and a countdown
timer. Its stated purpose is **polishing 3D prints made from metal-filled
filament**, "and rocks of course".

### Measured

| | Arofarn | This project |
|---|---|---|
| Shaft spacing | **70 mm** (bearing seats at −60 and +10 in `frame.dxf`) | 97.7 mm |
| Cradle half-angle | **28–31°** | 40° (**MA1**) |
| Roller | 24.4 mm pulley + O-ring, ~26 mm | 40 mm hub + TPU tyre (**KD**) |
| Reduction | 25/16 = 1.5625 (gears) | none; the roller diameter is the ratio |
| Microstepping | 1/8, capped at 5,000 steps/s | 1/16, ~8,990 steps/s in hardware |
| Barrel top speed | **25–28 rpm, 19–22% of critical** | 60 rpm, 45% |
| Liner | 10 flats, ~2.5 mm of lift | 6 flats (6.1 mm) or 6 lifter bars (6 mm) |
| Meshes | all 10 closed | all closed (**TB1**) |

### Reading it against this project

- **The speed is right for its purpose and wrong for rock.** At 19–22% of
  critical the charge slides rather than cascades, per **KB**. For burnishing
  brass-filled prints, gentle is correct. For grinding stone it would take far
  longer than seven days per stage, if it rounded the stone at all.
- **Its cradle is at the edge of stable.** 28–31° is at the "wanders" end of
  **MA1**'s 30–50° range. In the photographs the barrel's own screw caps sit
  against the pulleys and act as flanges, which is probably what keeps it on.
- **The firmware demonstrates the trap **KI** avoids.** It steps with
  AccelStepper's `runSpeed()` inside a loop that also multiplexes the display
  and polls the encoder, and it drops to 1/8 microstepping to stay under a
  5,000 steps/s cap. Every display refresh delays a step.
- **The firmware's `current_rpm` is steps per second.** AccelStepper's
  `setSpeed()` takes steps/s, so the number the display calls RPM overstates
  the motor speed roughly eightfold. The user is dialling a number that means
  something else.
- **Nothing survives a power cut.** The countdown and speed reset. And the
  countdown is elapsed seconds, capped at ten days: time as a proxy for dose,
  the same choice **KA** rejects.
- **Its direction pin is D0**, which is also the serial receive pin while
  `Serial.begin()` runs. Harmless while it only turns one way; a trap for
  anyone who adds reversal. This project uses D2, D7, D8 and D9, and avoids
  D0 and D1.
- **The printed liner scuffs.** The build photo shows grit scoring on the
  insert's flats. It supports treating any printed liner as a consumable, and
  printing ours in TPU (**BB1**, **BB2**).

### Usable from Arofarn

- **The architecture, as evidence.** A built, photographed machine on the same
  motor, rods, bearings, pipe and liner concept. It lowers the risk of **BA1**.
- **The CNC-from-DXF frame**, as an idea (**MB8**).
- **The display and encoder**, as an idea (**EB2**), paired with our dose
  rather than a countdown.
- **Not the gears.** This project needs no reduction because the roller
  diameter is the ratio (**KD**). Printed spur gears are also louder than a
  belt, and put the motor under the barrel, in the drip zone.
- **Not the code.** GPLv3, and the approach is the one this project exists
  to improve on.

---

## 3DPrintOrlando — *Rock Tumbler, Heavy Duty & Adjustable*

Printables, 2024 · **CC BY-NC-SA 4.0** (no commercial use; derivatives must
carry the same licence)

### What it is

A 2020-extrusion frame with printed side covers, two 10 mm rollers (400 mm
and 350 mm) in pillow blocks, the front roller sleeved in a 30 mm TPU tube, a
421 rpm 24 V DC gearmotor with a PWM speed controller, a 1:1 belt drive with
an idler tensioner, a cooling fan, printed TPU feet, and printed guide rings
on the rear roller that separate up to three barrels. The author states
~100 hours of printing, ~1 kg PETG, ~150 g TPU and about $130 of parts, and
that it takes two standard drums or one 15 lb drum.

### Measured

| | Heavy duty | This project |
|---|---|---|
| Roller | 30 mm TPU sleeve over a 10 mm rod, full length | 40 mm, 3 mm TPU tyre on a PETG hub |
| Top barrel speed | 126 rpm (100 mm drum), 110 rpm (4.5 in drum) | 60 rpm, fixed by the arithmetic |
| As % of critical | **86–92%** | 45% |
| Right PWM setting | ~49–52% of full, never stated | not applicable |
| Speed regulation | none: a DC motor's speed falls with load and supply | exact, step-locked |
| Barrels | up to three, with guide rings | one |
| Spacing | adjustable in slots; range not measurable here | fixed per barrel, reprint to change |
| Feet | TPU, 24.5 × 19.5 mm hourglass | none |
| Meshes | **7 of 22 open**, the front motor bracket with 573 bad edges | all closed |

### Reading it against this project

- **Full speed would chip the stones, and nothing says so.** At 86–92% of
  critical the charge is close to pinning to the wall. Its owner has to find
  the right PWM position by ear. This project computes it.
- **The DC motor is simpler and blinder.** It has no exact speed and nothing
  to count, so no dose, no slip detection and no reversal. It is the
  machine this project was designed not to be.
- **Its broken meshes are a warning about third-party geometry.** Slicers
  quietly repair open meshes, so they print. OpenSCAD refuses them, so none of
  these parts could be combined with this project's model without repair first
  (**LE-19**).

### Usable from the heavy-duty design

- **TPU feet** (**MB6**). Both designs have them.
- **Guarding the drive and the electronics** (**MB7**, **EC1**). It covers the
  belt, the motor and the power entry.
- **Multiple barrels on long rollers with guide rings** (**MA6**). The idea
  that changes the process most: two barrels can run two rock hardnesses, or
  two grit stages, at once. Our motor's margin drops from ~3.6× to ~1.8× with
  two 1.5 kg charges (22 N·cm against 40–50), which is still workable. The
  8 mm shafts would lengthen, and their deflection should be checked before
  committing. Each barrel would need its own hall sensor for its own dose.
- **Adjustable spacing** (**MA5**), if more than one barrel size is ever used.
- **Not the geometry.** Its licence forbids commercial use and requires
  derivatives to carry the same licence; seven parts are open meshes; and
  it is dimensioned for a different machine. Ideas are free to use; the files
  are not ours to build on.

---

## Licensing, in one place

| | Licence | Consequence |
|---|---|---|
| Arofarn models | CC BY-SA 4.0 | Free to use and adapt with attribution; **anything derived from the geometry must carry the same licence** |
| Arofarn firmware | GPLv3 | Same, for code |
| Heavy-duty models | CC BY-NC-SA 4.0 | As above, **and no commercial use** |

**Everything taken from them here is an idea, not geometry or code**, so this
project's own files carry no obligation from either. Whether the downloaded
files themselves should be committed to the repository is **Q-08**.

## Attribution

- Arofarn, *Affordable Rock Tumbler — NEMA17 Version for CNC routing*,
  Printables model 53950, and framagit.org/arofarn/polisseur.
- 3DPrintOrlando, *Rock Tumbler — Heavy Duty & Adjustable*, Printables model
  854211.
