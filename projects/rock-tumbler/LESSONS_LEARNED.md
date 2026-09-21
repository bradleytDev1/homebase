# Lessons learned

Written while the design was still warm. Most of these cost something to find
out, and a few of them were embarrassing enough to be worth recording properly.

---

## Verification

### A structural check is not a syntax check

`cad/tumbler.scad` was committed across four sessions and declared
"structurally verified" every time. The check was a Python script counting
`{}`, `()` and `[]` for balance, plus confirming every dispatched `PART` had a
matching `module`.

It all passed. **The file did not parse.** It had never parsed.

Balanced brackets say nothing about grammar. A file can be perfectly balanced
and syntactically meaningless. The only check that counts is running the real
tool against it, and that check took ninety seconds once it was finally tried.

> If you find yourself inventing a proxy for "does this work", the proxy is
> probably the problem. Go and get the actual tool.

### Cross-language muscle memory is the dangerous kind

The parse failure was this:

```c
" mm (circumference at the mid-thickness, "
"plus ~10 mm overlap)"
```

C concatenates adjacent string literals. So does Python. **OpenSCAD does
not** — it needs them as separate `str()` arguments.

The bugs that survive review are the ones that look idiomatic. Nothing about
those two lines looks wrong; they look wrong only in a language you weren't
thinking in. Be most careful in the languages that *resemble* ones you know
well.

### A test that can only report success is not a test

The boolean interference harness — does the barrel collide with the end plates
or the roller flanges? — returned confident, wrong answers **twice**:

1. **First version** didn't strip the file's dispatch block, so setting
   `PART="none"` fell through to `else assembly()` and every test rendered the
   entire assembly instead of the intersection. Both tests reported collisions.
2. **Second version** fixed that but counted a stale file: OpenSCAD writes *no
   output file at all* for an empty object, so each empty test silently
   recounted the previous test's STL.

The fix was a **control**: intersect the barrel with itself, which must be
non-empty. If the control comes back empty, the harness is broken and every
other result in the run is meaningless.

> Every verification harness needs at least one case whose answer you already
> know, and it should be a case that fails loudly if the plumbing is wrong.

### Identical results from different tests are a smell

The first broken harness reported `16280 facets` for two completely different
intersections. Two unrelated questions returning byte-identical answers is
almost never a coincidence — it means neither question was actually asked.

Watch for suspiciously equal numbers. They are cheaper to notice than to debug.

### `grep -i error` matches `NoError`

The validation script marked all six parts as FAILED because OpenSCAD's
*success* line is:

```
Status:     NoError
```

Case-insensitive substring matching on `error` is a trap in any toolchain that
reports `NoError`, `ErrorCount: 0`, or `errors=0`. Match the tool's actual
error prefix — `^ERROR:` — not a hopeful substring.

### Empty output is not the same as no output

OpenSCAD writes nothing when a result is empty. Many tools behave this way.
If your script reads the output file afterwards, it reads whatever was there
before.

**Delete the target before you generate it.** One line, and it removes a class
of silent false-pass.

### Two independent implementations agreeing is real evidence

The cradle geometry is computed twice — once in `tools/tumbler_calc.py` for the
build sheet, once in `cad/tumbler.scad` for the model. They agree to four
figures (97.7037 mm spacing, 58.2194 mm ride height).

That agreement is worth far more than either number alone, because the two were
written at different times in different languages and would have to be wrong
in exactly the same way to be wrong together.

### Validate the model against something real before writing any code

The single best check in the project cost nothing: the critical-speed formula
`N = 42.3/√D`, run at 45%, predicts **56 rpm** for a 4.5-inch barrel. A Lortone
3A — on hobbyists' benches since the 1960s — runs at 55–60.

Physics and sixty years of folklore agreeing meant the whole physical model was
sound before a single part was drawn. Find that anchor early. It is the
cheapest confidence you will ever buy.

---

## Designing for the long run

### Systems that run for weeks have their own bug class

Two faults in the Arduino firmware would have been invisible in every test and
fatal in week four:

| Bug | Why it bites | Fix |
|---|---|---|
| `millis()` wraps at **49.7 days** | A stage runs 42 days; a four-stage campaign runs months | `(uint32_t)(now - then) >= gap`, which is correct across the wrap |
| AVR `float` is **32-bit** | 24-bit mantissa: above ~16.7 M, increments start vanishing. A microstep counter crosses that in half an hour; a realistic fractional accumulator drifts **4% in fifty minutes** | Integer dose arithmetic throughout |

Neither shows up in a ten-minute bench test. Both were found by asking "what
does this look like on day 40?" — a question worth asking explicitly of
anything designed to run unattended.

### Choose the dose variable the physics cares about

Every tumbling instruction says "run seven days." Abrasive wear follows
**Archard's law** — volume removed is proportional to load × *sliding
distance* — and sliding distance is **revolutions**, not hours.

The striking part: a current commercial machine's headline feature is a memory
function that survives a power cut. They solved exactly the same persistence
problem, engineered storage for it, **and stored the weaker variable**.

> Before building the machinery to record a number, check you are recording the
> right number.

### Features couple across subsystems in ways you cannot anticipate

Direction reversal was added for load packing and even tyre wear — a control
decision, in firmware.

It reached back three subsystems and constrained a *rubber profile inside the
barrel*. Commercial barrels use an asymmetric scoop lifter, which lifts
beautifully in one direction; a machine that reverses would drag it backwards
through the charge half the time. So the printed lifter had to be a symmetric
trapezoid — slightly worse at lifting, identical both ways.

You only find couplings like that by designing the whole machine, not a pile of
subsystems.

---

## Materials and sourcing

### Match the material property to the job, not to convenience

TPU was the obvious liner material: printable, tough, wonderfully abrasion
resistant. But the job is *two* jobs — **damping** and **lift** — and TPU is
only good at one of them. It is resilient; it gives energy back rather than
dissipating it as heat.

Tire rubber (SBR/natural rubber, carbon black) is formulated for high
hysteretic damping *and* abrasion resistance. A truck mudflap is nearly free.

The answer was to split the jobs: **rubber sheet for damping, printed TPU bars
for geometry.** Cheaper and better than either alone.

### Don't print what you should buy

Three reasons not to print the barrel, each sufficient: layer lines leak over a
six-week wet run, silicon carbide excavates layer boundaries, and a leaking
barrel redistributes abrasive slurry across everything you own.

Owning a 3D printer creates a quiet pressure to print everything. The barrel is
the one component where the commercial product is genuinely better engineering,
and it carries the project's largest failure risk. Buy it.

### Read the commercial product as a design document

Two Amazon listing images were worth more than an hour of thinking:

- The control panel counts **days**, has **three fixed speeds**, and advertises
  a memory function — which told us what the market values, and where it
  settles for a proxy.
- The barrel cutaway showed **discrete lifter bars, not hex flats**, an
  **asymmetric scoop** profile, **tire rubber**, and a **compression lid with
  no threads in the grit path**.

Competitors have already paid for a lot of iteration. The photographs are free.

### Check marketing numbers for internal consistency

The barrel claims "up to 75% quieter" and "70 dB → 40 dB" on the same image.
30 dB is a *thousandfold* reduction in acoustic power, and 40 dB is roughly a
quiet library. By the usual convention of 10 dB per halving of perceived
loudness, 30 dB is ~87% — while 75% corresponds to about 20 dB.

**Their own two numbers disagree.** The mechanism was real and worth copying;
the magnitude was not. You rarely need outside data to catch this — just make
the claims agree with each other first.

---

## Honesty

### Say plainly when the economics don't work

~$60 of parts against a $170–200 finished machine, for fifteen to twenty-five
hours of work. That is well under minimum wage.

Building it is still right — for the instrumentation, the parametric sizing,
and because building it is the point. But "it's cheaper" is not a reason, and a
design document that implies otherwise is lying to its reader.

### Distinguish "committed" from "confirmed"

For four rounds, the CAD was described as verified when it had only been
*checked*. Writing "this has never actually been run" into the open-items list
is what eventually made someone install OpenSCAD.

Every document here now separates what was tested from what was merely
written. `CLAUDE.md` carries an explicit **Open items** list for exactly this
reason, and right now its most important line is that *nothing has been
printed yet* — so every clearance in this repo remains nominal.
