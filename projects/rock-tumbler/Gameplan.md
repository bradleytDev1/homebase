# Rock tumbler — Gameplan

**Why this exists, and what has been settled.** This document belongs to the
owner. The agent drafts into it and proposes rows; it never rewrites the prose
or resolves the open questions.

---

## G — Intention

### GA — What this is

A two-roller rotary rock tumbler driven by a NEMA 17 stepper motor, plus the
toolkit that designs it: a calculator that derives every dimension from
tumbling-mill physics, a parametric OpenSCAD model, and two firmware routes
(Raspberry Pi Pico with a TMC2209 driver, or Arduino with any STEP/DIR driver).

Its distinguishing idea is **instrumentation**: it counts barrel revolutions
as the abrasive dose, detects slip, reverses on a schedule, and survives power
cuts. It was begun on 2026-09-19 with the owner's words *"I have a quantity of
high quality stepper motors, and a 3d printer. Plus other junk. I'd like to
build my own rock tumbler. For fun."*

*Owner confirmed this reading 2026-09-22.*

### GB — What this is not

- **Not a product.** One machine, for the owner's bench.
- **Not a money-saver.** Roughly $70–110 of new parts against a $170–200
  finished machine, for fifteen to twenty-five hours of work
  ([`README.md`](README.md) § *Build or buy?*). Building it is justified by the
  instrumentation and by the building, never by the price (**KK**).
- **Not hosted.** Nothing about it runs anywhere but the Mac and the bench
  (**KL**).

### GC — Who it is for

The owner, who designs on the Mac and runs the machine in the workshop.

---

## GD — Platform

**What shape this thing is, who can reach it, and where it runs.**

| | |
|---|---|
| **Shape** | A physical bench machine with embedded firmware, plus local command-line design tools (Python calculators, an OpenSCAD model, a render/verification script). No web interface of any kind. The Docket console shows no project cards (❓**Q-07**) |
| **Runs on** | Design tools: the owner's Mac. Machine: a Raspberry Pi Pico or an Arduino Uno/Nano in the workshop (❓**Q-04**) |
| **Reached by** | The owner only |
| **Repository** | `projects/rock-tumbler/` inside the owner's `homebase` repo, on branch `claude/diy-rock-tumbler-6qi824`, pull request #1 open. ❓**Q-05** asks whether it should move to its own repository |
| **Holds** | Nothing sensitive: no credentials, keys or personal data |
| **Today** | Software only. Designed, computed and verified in software; **nothing printed, wired or measured** |
| **Intended** | A running bench machine. Still local-only |
| **Deploy** | Flash the firmware. Arduino: `arduino-cli compile` / `upload` from `firmware/arduino/tumbler_uno/`. Pico: copy `firmware/tmc2209.py` and `firmware/main.py` to the board. *Neither has been run yet; write the exact command here the first time it is.* |

### The questions to ask

Ask these at install, and again whenever someone says *"can you put this
somewhere I can use it?"*. That sentence is a platform change, not a feature.

1. **What shape is it?** A CLI · a library · a desktop program · a web app · a
   mobile app · a background service with no interface · a scheduled job · a
   document generator. Be precise, because the words mislead: **a program that
   serves `127.0.0.1` is a local tool wearing a web coat, not a website.**
2. **Who can reach it, and from where?** Only the person who runs it · anyone on
   the home or office network · a named handful of people over the internet ·
   the public. Each step outward is a different security problem, not a bigger
   version of the same one.
3. **Where does it run today, and where is it meant to run?** Keep these
   separate.
4. **What does it hold?** **Anything holding a credential must never be exposed
   without auth in front of it.**
5. **What happens when it is not running?** Here: nothing. A stage is
   measured in revolutions, so a stopped machine simply resumes the dose where
   it left off.
6. **Who operates it?** The owner.

**The one foreseeable platform change** is remote monitoring: an ESP32
dashboard for watching a six-week run from a phone (**XB3**). That would move
*Reached by* to the home network and is a **K** row and a **GD** edit when it
happens, not a feature toggle.

---

## H — Principles

### HA — Measure before asserting
Every number in these documents was checked. The physical model was anchored
against a real machine before a part was drawn: the critical-speed formula
predicts 56 rpm for a 4.5-inch barrel, and a Lortone 3A runs 55–60
(**LE-08**).

### HB — Verify the artefact, not the source
Confirm the CAD by running OpenSCAD against it, not by reading it (**LE-01**).
Confirm the step rate on D9 with a scope, not from the arithmetic.

### HC — Honest surfaces
Never offer something the system cannot actually do, and never imply a guarantee
it cannot keep. Here that means keeping *committed* and *confirmed* apart
(**LE-17**): nothing is called working until it has run.

---

## K — Standing decisions

Decisions that should not be relitigated without a reason. **A superseded
decision keeps its row**; the replacement says what changed.

*`KA`–`KZ`, then `KAA`, `KAB`, … Codes are never renumbered.*

**Provenance.** Rows **KA**–**KK** were made across the sessions of 2026-09-19
to 2026-09-21 and are **reconstructed** from that history and the commit
record. The owner confirmed all of them as standing on 2026-09-22.

| Code | Decision | Date | Rationale |
|---|---|---|---|
| KA | **Barrel revolutions are the dose, not elapsed days.** Grit stages are specified as revolution targets (600,000 each). | 2026-09-19 · confirmed 2026-09-22 | Abrasive wear follows Archard's law: volume removed ∝ load × *sliding distance*, and sliding distance is revolutions. "Seven days" silently assumes the barrel speed, charge and uptime of whoever wrote the instructions; a revolution count survives changing the barrel, the speed, or a power cut. Commercial machines persist elapsed days, which is the same storage problem solved for the weaker variable (**LE-10**) |
| KB | **Barrel speed is 35–50% of critical speed; 45% by default.** `N_crit = 42.3/√D`, D in metres. | 2026-09-19 · confirmed 2026-09-22 | Above ~50% the load starts cataracting and chips stones; near 100% it centrifuges. Below ~35% it slides as a lump instead of cascading. The formula at 45% reproduces a Lortone 3A's 55–60 rpm, which anchors the whole model (**LE-08**) |
| KC | **Structural prints are PETG or ASA, never PLA.** | 2026-09-19 · confirmed 2026-09-22 | A stepper energised 24/7 runs at 60–80 °C; PLA's glass transition is ~60 °C. A PLA motor mount sags over a six-week run, pulls the rollers out of parallel, and the barrel walks off |
| KD | **Rollers are 40 mm in diameter.** | 2026-09-19 · confirmed 2026-09-22 | The roller diameter is the gearbox. 40 mm puts the motor at ~169 rpm, inside a NEMA 17's flat-torque region, at ~11 N·cm demand against 40–50 available, and a step rate any driver handles |
| KE | **Driver current runs low, about 0.4–0.6 A per phase**, set by winding down until a full barrel fails to start and adding 30% back. | 2026-09-19 · confirmed 2026-09-22 | The load needs ~11 N·cm. A stepper draws full current whether loaded or not, so surplus current is only heat, for a thousand hours, next to a printed bracket (see **KC**) |
| KF | **The firmware never auto-advances between grit stages.** It stops at the target and waits. | 2026-09-19 · confirmed 2026-09-22 | Between stages every grain of the previous grit must be washed off by hand. One grain of 60 grit in the polish stage ruins the batch, and the machine cannot verify the washing happened |
| KG | **Lifter bars are symmetric trapezoids**, not the asymmetric scoop commercial barrels use. | 2026-09-20 · confirmed 2026-09-22 | This machine reverses direction every six hours. An asymmetric scoop lifts well one way and drags backwards through the charge the other. A feature in the firmware constrains a rubber profile three subsystems away (**LE-11**) |
| KH | **Do not print the barrel.** Buy one, or use PVC or HDPE with a printed liner. | 2026-09-20 · confirmed 2026-09-22 | Layer lines leak over a six-week wet run, silicon carbide excavates layer boundaries, and a leak spreads abrasive slurry everywhere. It is the one part where the commercial product is genuinely better engineering (**LE-13**) |
| KI | **On Arduino, steps come from Timer1 in CTC mode toggling OC1A, which is pin D9.** Not AccelStepper; and D9 cannot be reassigned. | 2026-09-19 · confirmed 2026-09-22 | AccelStepper tops out near 4,000 steps/s on a 16 MHz AVR; this machine needs ~8,990. Timer1 generates the pulse train in hardware with the CPU uninvolved, which is the ATmega's equivalent of the TMC2209's internal step generator. OC1A is fixed to D9 by the silicon |
| KJ | **All AVR dose arithmetic is integer, and all timing uses `(uint32_t)(now - then) >= gap`.** | 2026-09-19 · confirmed 2026-09-22 | AVR `float` is 32-bit: a fractional accumulator drifts 4% in fifty minutes. `millis()` wraps at 49.7 days, and a campaign runs months. Both are invisible in bench tests and fatal in week four (**LE-09**) |
| KK | **Built for fun and for the instrumentation, not to save money.** | 2026-09-19 · confirmed 2026-09-22 | The owner's opening words were *"For fun."* The arithmetic confirms it: the build costs well under minimum wage against buying one. A design document that implied otherwise would be misleading its reader (**LE-16**) |
| KL | **Local only. Nothing is hosted.** Design on the Mac; the machine runs on a microcontroller on the bench. | 2026-09-22 | Owner confirmed at Docket adoption. It holds no credentials and has one user. Remote monitoring (**XB3**) would be a platform change requiring a new row here and an edit to **GD** |
| KM | **The Docket's seven domains are M Mechanical, B Barrel, E Electronics, F Firmware, T Tools & verification, P Process, X Experiments.** | 2026-09-22 | Owner accepted the proposed set at adoption. They follow how the files and the README already divide the work. Codes hung on them are permanent |
