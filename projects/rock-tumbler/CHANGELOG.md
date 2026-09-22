# Rock tumbler — Changelog

**Current: 0.6.0** — designed, computed and verified in software; nothing printed, wired or measured yet.

> Codes in brackets refer to [`features_and_functions.md`](features_and_functions.md).
> The version is a single constant, in [`VERSION`](VERSION).

*Every change gets a version and an entry here, in the same turn it is made:
one version per change, never batched, never unversioned. Checked by
`check_status.py`, which requires `README.md` to agree with the **Current**
line above.*

*Versions **0.1.0**–**0.5.1** were assigned retroactively on 2026-09-22, one
per commit, when the Docket was adopted. Before then the project had no
version. Their dates and contents come from the commit record; the version
numbers themselves are reconstructed.*

---

## 0.6.0 — 2026-09-22 — The Docket adopted

- Adopted the Docket documentation framework (4.2.0) in place: `Gameplan.md`,
  `features_and_functions.md`, `development_plan.md`, `critical_path.md`,
  `open_questions.md`, `answered_questions.md`, `chapters/`, this changelog,
  and the framework's scripts, including `scripts/check-docs.sh`.
- Seven domains confirmed by the owner (**KM**); eleven earlier decisions
  confirmed as standing (**KA**–**KK**); platform recorded as local-only
  (**KL**).
- `LESSONS_LEARNED.md` renamed to `lessons_learned.md` and each lesson given a
  permanent code, **LE-01**–**LE-17**. Found **LE-18** while verifying a claim
  about `tools/render.sh`: its part-export loop reads stale STLs.
- `WHATS_NEXT.md` redistributed into the critical path, the feature list and
  four open questions (**Q-01**–**Q-04**), then archived with a manifest.
- Added the project's own gates to `check-docs.sh`: the four Python
  self-tests, `tools/render.sh` when OpenSCAD is present, and the Arduino
  compile check when `avr-gcc` is present.
- Added `VERSION`, the project's single version constant.

## 0.5.1 — 2026-09-21 — Project state documented · `0ec8a74`

- `WHATS_NEXT.md` (the phased plan, four decisions, risks) and
  `LESSONS_LEARNED.md` (seventeen lessons) written.

## 0.5.0 — 2026-09-21 — CAD rendered for the first time · `63577c9`

- OpenSCAD run against `cad/tumbler.scad` for the first time. It **did not
  parse** (adjacent string literals, **LE-02**) and the rollers sat 3 mm off,
  putting the barrel end on a flange. Both fixed.
- `tools/render.sh` added: parse, manifold export, interference tests with a
  control, renders (**TB1**). A `section` view added.

## 0.4.0 — 2026-09-21 — Rubber sheet option · `327b8ec`

- `RUBBER_T`: a rubber sheet sits behind either printed liner, held without
  adhesive (**BB3**). Parts list split into a common chassis and three barrel
  routes.

## 0.3.0 — 2026-09-20 — Lifter-bar liner · `2e2ef5f`

- Symmetric lifter-bar liner alongside the hexagonal one (**BB2**, **KG**).
  Damping and lift separated into two materials.

## 0.2.2 — 2026-09-20 — Build-or-buy analysis · `980e4a3`

- Honest cost comparison against commercial machines; recommendation to buy
  the barrel (**KH**, **KK**).

## 0.2.1 — 2026-09-19 — Working notes · `8b99e5e`

- `CLAUDE.md` added so a fresh session inherits the project's context.

## 0.2.0 — 2026-09-19 — Arduino route · `ec40f3b`

- Arduino firmware for any STEP/DIR driver: Timer1 hardware stepping on D9
  (**FB1**, **KI**), EEPROM ring odometer (**FB2**), wrap-safe timing and
  integer dose arithmetic (**FB3**, **KJ**). Compile harness (**TB2**) and
  `tools/timer1_calc.py` (**TA2**).

## 0.1.0 — 2026-09-19 — First design · `45a32a1`

- Design calculator (**TA1**), parametric OpenSCAD model, and the Pico +
  TMC2209 firmware (**FA1**, **FA2**) with revolution dosing, reversal and
  slip detection.
