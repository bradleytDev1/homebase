# Rock tumbler — Open Questions

**The inbox for things needing the owner, that the owner has not answered yet.**

Anything the agent raises lands here the moment it is raised, not only in the
conversation. Chat scrolls away; this does not.

## How this works

The agent files here without being asked. The owner answers when they have time,
in a sentence, in any session — or at `/questions` in the console.

**Every entry carries a working assumption** so nothing is blocked while it
waits. If the answer differs from the assumption, the assumption says exactly
what has to be revisited.

**Every entry is written in plain English.** It explains what the thing is
before asking about it, expands every code and filename the first time, and
says what changes depending on the answer.

**When answered:** mark it ✅ **in the `###` heading itself**, record the
answer and where the decision went, remove the ❓ markers from every code it
touched, and move the entry to [`answered_questions.md`](answered_questions.md).
**Nothing is deleted.**

| Priority | Meaning |
|---|---|
| 🔴 | Blocking work now |
| 🟡 | Needed before a specific thing can ship |
| ⚪ | Whenever — a direction question, not a blocker |

---

## 🔴 Blocking

*None open.* The first physical step, a single test print of one roller hub
and one end plate, needs none of the answers below.

---

## 🟡 Needed soon

### Q-01 — Which barrel?
**Raised:** 2026-09-21 (in `WHATS_NEXT.md`), filed 2026-09-22 · **Affects:** **BA1**, **BA2**, **BB2**, **BB3** · **Status:** open

The barrel is the part that holds the rock, grit and water for six weeks. It
carries the project's biggest failure risk, a leak, and it decides which
printed liner (the sleeve inside the barrel that lifts the rocks) gets made.
Three routes are costed in the README's *Build or buy?* section:

- **A.** 4-inch PVC drain pipe with a screw-in cleanout plug, a sheet of
  rubber (truck mudflap or inner tube) inside it, and the printed lifter-bar
  liner pressed in over the rubber. About $26. Best value, quietest DIY option.
- **B.** The same pipe with only a printed liner, no rubber. About $20.
  Simpler; louder and harder on the stone.
- **C.** Buy a Lortone or Thumler's rubber barrel as a spare part. $40–60.
  Removes the leak risk entirely.

**Why now:** the liner can't be printed until this is settled, and route A
needs the rubber sheet's real thickness measured first.

**Working assumption:** **route A.** I will treat the lifter-bar liner as the
one to print, with `RUBBER_T` set once a sheet is in hand. If you choose C,
the printed liner isn't needed at all and the cradle must be re-computed from
that barrel's measured outside diameter. If B, `RUBBER_T` stays 0.

### Q-02 — Which stepper driver board will you use?
**Raised:** 2026-09-21 (in `WHATS_NEXT.md`), filed 2026-09-22 · **Affects:** **EA2** · **Status:** open

A driver board sits between the controller and the motor and sets how much
current the motor gets. You mentioned having stepper controllers in the
drawer. The common ones are the A4988, DRV8825, TB6600 and TMC2209. All of
them take the same two-wire step and direction signal, so the Arduino firmware
works with any of them. What differs is **how you set the current** (a
different formula per board, and it depends on tiny resistors printed on the
board) and **how loud it is** (the TMC2209 is near-silent; the others whine).

**Why now:** the current has to be set before the motor is first connected,
and the procedure depends on the board.

**Working assumption:** **an A4988 or DRV8825 on the Arduino**, since those
are the commonest boards in a drawer. The README's table covers both. If it
is a TMC2209, the Pico route (**Q-04**) becomes the more natural choice.

### Q-04 — Pico or Arduino?
**Raised:** 2026-09-21 (in `WHATS_NEXT.md`), filed 2026-09-22 · **Affects:** **FA1**, **FA2**, **FB1**, **FB2** · **Status:** open

Two complete sets of firmware exist, and only one will run the machine.

- **Pico + TMC2209.** The driver generates its own steps, so speed is one
  setting, and it reports faults such as overheating or a loose wire. Needs
  a TMC2209 specifically.
- **Arduino + any driver.** The Arduino's own hardware timer generates the
  steps. Works with whatever driver board you already have.

Both do the revolution counting, slip detection and reversal.

**Why now:** it decides what gets wired and flashed first, and which of the
two firmwares gets tested on real hardware.

**Working assumption:** **Arduino**, because it works with whichever driver is
in the drawer (**Q-02**). If you choose the Pico, the Arduino route stays in
the repo untested and the TMC2209 becomes a purchase.

---

## ⚪ Whenever

### Q-03 — 12 V or 24 V supply?
**Raised:** 2026-09-21 (in `WHATS_NEXT.md`), filed 2026-09-22 · **Affects:** **EA4** · **Status:** open

The motor supply voltage. At this machine's speed (about 169 rpm at the
motor) 12 V is enough. 24 V roughly doubles the speed a stepper can reach
before its torque falls away, so it is free headroom if you already own one.

**Working assumption:** **whichever you already have; 12 V if both.** Nothing
in the design changes either way. The driver's current setting (**KE**) is
independent of supply voltage.

### Q-05 — Should the tumbler stay in `homebase`?
**Raised:** 2026-09-21, filed 2026-09-22 · **Affects:** where the project lives · **Status:** open

The project lives in `projects/rock-tumbler/` inside your GitHub repository
`homebase`. It landed there because the first cloud session was attached to
that repo, not because anyone chose it. `homebase` otherwise holds only an
old fast.ai notebook from 2021. All the tumbler work is on the branch
`claude/diy-rock-tumbler-6qi824`, with pull request #1 open and unmerged.

Moving it to its own repository is cheap now and gets more tedious the more
history it gathers. It would also make this folder the repository root, which
suits the Docket's own tools better.

**Working assumption:** **it stays where it is, on the branch, with the pull
request unmerged,** until you say otherwise. If you want it moved, I'll create
a `rock-tumbler` repository carrying the full history, and `homebase` goes
back to how it was.

### Q-06 — Three files were left outside the Docket
**Raised:** 2026-09-22 · **Affects:** adoption · **Status:** open

When the Docket was adopted, most of the existing documentation was kept in
place or redistributed (see [`docket-archive/MANIFEST.md`](docket-archive/MANIFEST.md)).
I read these and deliberately left them alone:

- **`README.md`**, 700 lines. The full design narrative: the physics, the
  build-or-buy analysis, the parts list, the barrel and material reasoning,
  failure modes and sources. It is the project's long form, and the Docket
  documents now link into it rather than repeat it. I only added a short
  Docket section and the version line near the top. **Suggest:** leave it as
  the long form. Splitting it into chapters would scatter an argument that
  currently reads in order. One small wrinkle: its *Project status* table uses
  ✅ to mean "verified", while the Docket uses ✅ to mean "usable now". The
  two don't conflict, but they are different claims.
- **`CLAUDE.md`**. Your earlier working notes, kept in full. I added the
  Docket protocol above them and struck through the lines that pointed at the
  now-archived `WHATS_NEXT.md`, without deleting them. Its *Build log* table
  overlaps the new `CHANGELOG.md`. **Suggest:** let the changelog own the
  history going forward and freeze the build log.
- **`cad/renders/`, `build/`**. Generated output, not documentation.
  **Suggest:** leave them.

**Working assumption:** all three stay as they are. Say which to fold in, and
where, and I'll do it.

### Q-07 — Should the console show anything of the tumbler's own?
**Raised:** 2026-09-22 · **Affects:** the Docket console · **Status:** open

The Docket comes with a small local web page, the "console", at
`http://127.0.0.1:7373`, which opens with one card per thing the project
builds, alongside cards for the Docket itself and these questions. The
tumbler has no web interface, so for now the console shows only the Docket's
own cards.

It could show a card for the CAD renders or a generated build sheet, if
seeing those at a glance would be useful.

**Working assumption:** **no project cards.** The console shows the Docket,
the questions and the capture page, and nothing else.

### Q-08 — May the two downloaded reference designs be committed to the repository?
**Raised:** 2026-09-22 · **Affects:** **XD1** · **Status:** open

Two open designs were downloaded into this folder: Arofarn's *Affordable Rock
Tumbler — NEMA17* (licensed CC BY-SA 4.0) and 3DPrintOrlando's *Heavy Duty &
Adjustable* (CC BY-NC-SA 4.0, which forbids commercial use). Both licences
allow copying them with attribution. Committing them would still mean
**publishing someone else's files** in your GitHub repository, which is your
call. It would also add about 3.6 MB of STLs and zips.

The evaluation took **ideas only** from them, no geometry or code, so none of
this project's own files carries any obligation either way.

**Working assumption:** **they stay on disk and out of git** (listed in
`.gitignore`); the chapter records what was learned and credits both authors.
If you want them committed, I'll move them into a `reference/` folder with
their licence and attribution alongside.

### Q-09 — Which ideas from the reference designs should be adopted?
**Raised:** 2026-09-22 · **Affects:** **MA5**, **MA6**, **MB6**, **MB7**, **MB8**, **EB2**, **EC1** · **Status:** open

The evaluation ([`chapters/XD1-reference-designs.md`](chapters/XD1-reference-designs.md))
found seven things the two published tumblers do that this one doesn't. Each
is marked 💡 (an idea, not approved) until you say otherwise:

1. **TPU feet** to isolate vibration (**MB6**). Both designs have them.
2. **A belt guard** (**MB7**). Both designs guard their drive.
3. **An electronics enclosure** (**EC1**). Both designs box theirs.
4. **Two barrels at once** on longer rollers (**MA6**). Doubles throughput,
   or runs two rock hardnesses at once. Needs longer shafts, a second sensor,
   and firmware that keeps two doses.
5. **Adjustable roller spacing** (**MA5**). Worth it only if you'll use more
   than one barrel size.
6. **A display and knob** on the machine (**EB2**).
7. **End plates cut from sheet material** rather than printed (**MB8**).

**My recommendation:** approve **1, 2 and 3** now. They are cheap, both
reference designs independently agree on them, and they address noise, safety
and splash, which this design hasn't covered. Park **4** until the first
batch has run. **5**, **6** and **7** are optional.

**Working assumption:** all seven stay as ideas. Nothing changes in the CAD or
the plan until you choose; approving 1–3 would add three small parts to the
print set in `critical_path.md` column 2.

---

## Answered

*Settled questions move to [`answered_questions.md`](answered_questions.md).*
