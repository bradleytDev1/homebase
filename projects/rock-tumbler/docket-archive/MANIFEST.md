# Docket archive — manifest

**What came from where, when, and why.** Nothing in this folder was deleted;
each file was moved here after its content was redistributed into the Docket,
and the move is reversible with `git mv`.

---

## `WHATS_NEXT.md`

**Archived 2026-09-22**, at Docket adoption (0.6.0). Written 2026-09-21 by the
Mac session (`0ec8a74`).

It was the project's plan: four decisions, phases 0–4 from toolchain to first
batch, a risk table, a list of experiments, and housekeeping. Every section
now lives in the Docket:

| Section of `WHATS_NEXT.md` | Went to |
|---|---|
| *Decisions needed before anything else* (barrel, driver, voltage, controller) | `open_questions.md` **Q-01**, **Q-02**, **Q-03**, **Q-04**, each with a working assumption |
| *Phase 0a — Local toolchain* | `critical_path.md` column 1 (**TB2**); the OpenSCAD line was already done and is recorded in `CHANGELOG.md` 0.5.0 |
| *Phase 0 — One test print* | `critical_path.md` column 1, tolerance test print (**MB1**, **MA2**) |
| *Phase 1 — Mechanical* | `critical_path.md` columns 2–3; parts as **MA1**–**MA4**, **MB1**–**MB5**, **BB1**–**BB3** in `features_and_functions.md` |
| *Phase 2 — Drive* | `critical_path.md` column 4 (**EA3**, **FB1**, **FD1**) |
| *Phase 3 — Instrumentation* | `critical_path.md` column 5 (**EB1**, **FB2**, **FC2**, **FC3**) |
| *Phase 4 — First batch* | `critical_path.md` column 6; **PA1**–**PA3** |
| *Risks worth watching* | `critical_path.md` § Risks, verbatim in substance |
| *Once it runs* (six experiments) | `features_and_functions.md` domain **X**, all 💡 (**XA1**, **XB1**–**XB3**, **XC1**–**XC2**) |
| *Housekeeping*: stay in `homebase`? | `open_questions.md` **Q-05** |
| *Housekeeping*: merge the branch | Folded into **Q-05** |
| *Housekeeping*: `MCP_DOCKER` failed to connect | Not carried: a session-environment note, not a project fact. It failed again on 2026-09-22 |

Why archived rather than adopted in place: its content was **redistributed**
across four documents, and left in place it would have become a second,
drifting plan (adoption rule 1).
