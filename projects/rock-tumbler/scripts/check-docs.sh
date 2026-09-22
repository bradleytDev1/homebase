#!/usr/bin/env bash
#
# check-docs.sh — verify the documentation invariants.
#
# These are easy to break silently, and a stale cross-reference is worse than
# none (see lessons_learned.md LE-13). Run before finishing a session.
#
#   1. Every markdown link between documents resolves.
#   2. A ❓Q-nn marker exists in the outline iff that question is unanswered.

set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
fail=0

# ── The documentation lock ──────────────────────────────────────────────
# Two sessions can be open on one project, and there is often no git here, so a
echo "==> This project can undo a bad write"
python3 scripts/check_git.py || fail=1


echo "==> Docket check — cross-document links"
python3 - <<'PYEOF'
# **A link inside backticks is an example, not a link.** `FRAMEWORK.md`
# documents this very gate as "every `](file.md)` resolves", and the shell
# version of this check dutifully reported `file.md` as broken — a document
# cannot describe the check that reads it. Same family as `LE-03` and `LE-04`:
# the mechanism must not be tripped by documentation of the mechanism.
import glob, re, sys
from pathlib import Path

# **And the gate was narrowed one notch too far.** It only ever matched links
# ending in `.md`, so `README.md` carried `](skill/)` — a directory that does
# not exist — past every run of this check. A gate tightened to remove false
# positives can stop asserting the thing it is named for, and nothing says so;
# the check still printed "all resolve". Now any relative target counts, and a
# directory link is satisfied by a directory. (LE, 3.1.0)
CODE = re.compile(r"```.*?```|~~~.*?~~~|`[^`\n]*`", re.S)
LINK = re.compile(r"\]\((?!https?://|mailto:|#)([A-Za-z0-9_./-]+/?)(?:#[^)]*)?\)")

bad = 0
for f in sorted(glob.glob("*.md") + glob.glob("chapters/*.md")):
    text = CODE.sub(lambda m: " " * len(m.group(0)), open(f, encoding="utf-8").read())
    for link in LINK.findall(text):
        target = (Path(f).parent / link).resolve()
        if not target.exists():        # a directory link is satisfied by a directory
            print(f"    BROKEN  {f} -> {link}")
            bad += 1
if bad:
    sys.exit(1)
print("    all resolve")
PYEOF
[ $? -ne 0 ] && fail=1

echo "==> Open-question markers"
python3 - <<'PY'
import re, sys, glob
# Parse the two files SEPARATELY. Concatenating them means the last entry of
# open_questions.md runs on into the top of answered_questions.md and inherits
# its checkmarks, which silently reported an open question as answered.
sources = ["open_questions.md", "answered_questions.md"]
# A question is answered if the checkmark is in its `###` heading (the form the
# templates ask for) or on its `Status:` line (where it is natural to write it,
# and where putting it alone used to report the answer as an unmarked open
# question forever — LE-28). Only those two lines count: a checkmark loose in
# the body usually belongs to some other question being cited.
entries = []
for src in sources:
    try:
        text = open(src).read()
    except OSError:
        continue
    blocks = re.split(r"^(?=### Q-\d+)", text, flags=re.M)
    for b in blocks:
        m = re.match(r"### (Q-\d+)(.*)$", b, re.M)
        if not m:
            continue
        heading = m.group(2)
        status = "".join(re.findall(r"^.*\*\*Status:\*\*.*$", b, re.M))
        entries.append((m.group(1), "✅" in heading or "✅" in status))
open_qs  = {c for c, done in entries if not done}
closed_qs = {c for c, done in entries if done}
open_qs -= closed_qs

marked = {}
for f in glob.glob("*.md"):
    if f == "open_questions.md":
        continue
    for code in re.findall(r"❓\*\*(Q-\d+)\*\*", open(f).read()):
        marked.setdefault(code, []).append(f)

bad = False
for c in sorted(open_qs - set(marked)):
    print(f"    UNMARKED  {c} is open but appears in no outline"); bad = True
for c in sorted(set(marked) & closed_qs):
    print(f"    STALE     {c} is answered but still marked in {marked[c]}"); bad = True
if not bad:
    print(f"    {len(open_qs)} open, all marked; {len(closed_qs)} answered, none stale")
sys.exit(1 if bad else 0)
PY
[ $? -ne 0 ] && fail=1

echo "==> Code references"
python3 scripts/check_codes.py || fail=1

echo "==> Status consistency"
python3 scripts/check_status.py || fail=1

echo "==> Every link in the Docket viewer's rail reaches a heading"
python3 scripts/check_docket_anchors.py || fail=1

echo "==> Answers recorded at /questions are in the Docket"
python3 scripts/check_answer_inbox.py || fail=1

# Master-only gates. This file IS copied into a fresh install, so an
# unguarded call to a script the framework deliberately never ships makes
# check-docs.sh permanently red in a brand-new project (LE-33). Reported from
# tts2, which hit it on adoption.
if [ -f .docket-master ]; then
  echo "==> Flaws reported by projects are in this Docket"
  python3 scripts/check_framework_reports.py || fail=1
fi

echo "==> The Docket is this project's, not the one it was copied from"
python3 - <<'PYEOF'
# A framework distributed as files carries its source project's content into
# every install. It has happened twice: the viewer printed another project's
# name at the top of every page, and the templates' {{PLACEHOLDERS}} survive an
# install nobody finished. Both are silent — the page renders, the docs read
# fine, and they are simply about a different project.
import glob, re, sys
from pathlib import Path

ROOT = Path(".")
MASTER = (ROOT / ".docket-master").exists()
bad = False

# 1. An install that was never adapted still holds its placeholders.
# A line that *writes about* placeholders carries `placeholder-exempt`, the
# same convention the other prose-scanning gates use. Without it a document
# cannot describe the check that reads it.
#
# **It scans the Docket documents, not every markdown file at the root.** A
# project's other prose — a specification, a design note, the framework's own
# SKILL.md — may legitimately *write about* placeholders, and a gate that fails
# on documentation of the thing it checks is a gate people switch off. An
# unadapted install shows up in these files or not at all.
PLACEHOLDER = re.compile(r"\{\{[A-Z_]+\}\}")
DOCKET_DOCS = ["README.md", "CLAUDE.md", "Gameplan.md", "features_and_functions.md",
              "critical_path.md", "development_plan.md", "open_questions.md",
              "answered_questions.md", "lessons_learned.md", "CHANGELOG.md",
              "CHANGES.md"]
for f in [d for d in DOCKET_DOCS if Path(d).exists()] + sorted(glob.glob("chapters/*.md")):
    hits = set()
    for line in open(f, encoding="utf-8"):
        if "placeholder-exempt" in line:
            continue
        hits.update(PLACEHOLDER.findall(line))
    if hits:
        print(f"    UNADAPTED  {f} still contains {', '.join(sorted(hits))}")
        bad = True

# 2. The generated viewer must carry this project's name. Derived the same way
#    build_docket.py derives it, so the two cannot disagree.
def project_name():
    for name in ("README.md", "Gameplan.md", "features_and_functions.md"):
        f = ROOT / name
        if not f.exists():
            continue
        m = re.search(r"^#\s+(.+?)\s*$", f.read_text(encoding="utf-8"), re.M)
        if m:
            title = re.split(r"\s+[\u2014\u2013-]\s+|\s*\(", m.group(1))[0].strip()
            # The framework's templates are all headed "The Docket", so that name
            # normally means an install nobody finished — except in the master,
            # where it is the actual name and `.docket-master` says so.
            if title and (MASTER or title.lower() != "the docket"):
                return title
    return ROOT.resolve().name

viewer = ROOT / "docs" / "docket.html"
if viewer.exists():
    want = project_name()
    head = viewer.read_text(encoding="utf-8", errors="ignore")[:4000]
    m = re.search(r"<title>(.*?)</title>", head)
    got = m.group(1) if m else "(no title)"
    if want not in got:
        print(f"    FOREIGN    docs/docket.html is titled {got!r}; this project is {want!r}")
        print("               Rebuild with scripts/build_docket.py; if it is still wrong,")
        print("               the build script has a hardcoded name in it.")
        bad = True
    else:
        print(f"    the viewer names this project ({want})")
else:
    print("    no viewer built yet (scripts/docket.sh builds one)")

if not bad:
    print("    no unadapted placeholders")
sys.exit(1 if bad else 0)
PYEOF
[ $? -ne 0 ] && fail=1

# ── Project gates ──────────────────────────────────────────────────────
# Add the checks your language and domain need. Two that earned their place in
# the project this came from:
#   * a structural check — it caught a module calling a function it never
#     imported, which the bundler compiled happily
#   * a regression suite over known-good inputs, asserting things checkable
#     against the world rather than snapshots of its own output
# Delete these two lines if you have nothing yet, and add gates as lessons
# accumulate. See FRAMEWORK.md rule 4.
#
# echo "==> Structural check"
# <your command> || fail=1
#
echo "==> The changelog has a section for what it calls current"
python3 - <<'PYEOF'
import os, re, sys
# **The version scheme is read, never assumed.** This gate used to require a
# major version of literally `1` in both of its regexes, so every project at 0.x
# or 2.x failed it on every run for a reason that had nothing to do with its
# changelog. The header says what the version is; take it from there.
name = next((n for n in ("CHANGELOG.md", "CHANGES.md") if os.path.exists(n)), None)
if not name:
    print("    no changelog found"); sys.exit(1)
text = open(name).read()

# A fenced block is an example of the format, not a release.
text = re.sub(r"^(```|~~~).*?^\1[^\n]*$",
              lambda m: "\n" * m.group(0).count("\n"), text, flags=re.M | re.S)

header = re.search(r"\*\*Current:\s*([\w.]+?)\s*(?:\(build\s*\d+\))?\s*\*\*", text)
if not header:
    print(f"    {name} has no '**Current: …**' line"); sys.exit(1)
cur = header.group(1)
sections = re.findall(r"^##\s+([\w.]+)", text, re.M)
if cur not in sections:
    print(f"    header says {cur} is current but there is no '## {cur}' section")
    sys.exit(1)
print(f"    {name}: {cur} has a section; {len(sections)} version sections present")
PYEOF
[ $? -ne 0 ] && fail=1

# echo "==> Regression tests"
# <your command> || fail=1

# ── Rock tumbler's own gates ────────────────────────────────────────────
# Each exists because something needed checking against the world, not
# against a snapshot of this project's output (development_plan.md,
# Verification). A gate whose tool is missing is SKIPPED with a reason, never
# silently passed: an absent tool must not read as a green check (LE-17).
RT_TMP="$(mktemp -d)"

echo "==> Physics anchored against a real machine (TA1, LE-08)"
if python3 tools/tumbler_calc.py --selftest >"$RT_TMP/calc" 2>&1; then
  echo "    tumbler_calc: all checks pass"
else cat "$RT_TMP/calc"; fail=1; fi

echo "==> Timer1 arithmetic and the long-run AVR bugs (TA2, LE-09)"
if python3 tools/timer1_calc.py --selftest >"$RT_TMP/t1" 2>&1; then
  echo "    timer1_calc: all checks pass"
else cat "$RT_TMP/t1"; fail=1; fi

echo "==> Firmware protocol and control logic (TB3)"
if ( cd firmware && python3 tmc2209.py && python3 main.py --selftest ) >"$RT_TMP/fw" 2>&1; then
  echo "    tmc2209 + main.py (simulated campaign): all checks pass"
else cat "$RT_TMP/fw"; fail=1; fi

echo "==> The CAD parses, is manifold, and nothing collides (TB1, LE-01)"
if command -v openscad >/dev/null 2>&1; then
  if bash tools/render.sh >"$RT_TMP/render" 2>&1; then
    echo "    render.sh: all checks pass"
  else tail -25 "$RT_TMP/render"; fail=1; fi
else
  echo "    SKIPPED — openscad not installed (brew install --cask openscad@snapshot)"
fi

echo "==> The Arduino sketch compiles for the ATmega328P (TB2)"
if command -v avr-g++ >/dev/null 2>&1; then
  if ( cd firmware/arduino/test && make clean && make ) >"$RT_TMP/avr" 2>&1; then
    echo "    compiles clean"
  else cat "$RT_TMP/avr"; fail=1; fi
else
  echo "    SKIPPED — avr-gcc not installed (brew tap osx-cross/avr && brew install avr-gcc)"
fi
rm -rf "$RT_TMP"

echo "==> The console's surface list is well-formed"
python3 scripts/check_console.py || fail=1

echo "==> Master-only material stays in the master"
python3 scripts/check_master_only.py || fail=1

if [ -f .docket-master ]; then
  echo "==> Every script ships or is declared master-only"
  python3 scripts/check_ships.py || fail=1
fi

echo "==> No pre-3.0.0 names survive the rename"
python3 scripts/check_legacy_names.py || fail=1

echo "==> This project knows which Docket framework it is running"
python3 scripts/check_version.py || fail=1

exit $fail
