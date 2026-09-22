#!/usr/bin/env python3
"""Every code referenced must be a code that exists.

The ❓ invariant has been checked since the Docket was set up; code references
never were. Codes get written into prose before they are defined — **UBGA**
appeared in the changelog a build before it existed — and a reference to a code
nobody defined is a quiet lie about the shape of the project.

Definitions live in:
  features_and_functions.md   feature codes, in status lines
  Gameplan.md                 K decisions, in table rows
  open_questions.md           Q questions, in headings
  lessons_learned.md          LE lessons, in headings
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = sorted(ROOT.glob("*.md")) + sorted(ROOT.glob("chapters/*.md"))

#: **A code is letters, then optionally digits.** From 3.6.0 the leaf is
#: numbered — `C`, `CA`, `CA1`, `CA2` — instead of lettered all the way down.
#:
#: The letters were chosen as initials, which is what makes them readable, and
#: the leaf never was: `CAA` and `CAB` are not mnemonic for anything, they are
#: counting done in the wrong alphabet. Numbering the leaf also ends the
#: rollover rule at the level where it actually bit (a 27th sibling), and makes
#: a leaf code impossible to mistake for an acronym — `CA1` is not a word.
#:
#: **Both shapes are read, and nothing converts between them.** A project that
#: adopted earlier keeps letters, marked by `.docket`; converting would break
#: every cross-reference in the project it was meant to tidy.
#: **The shape depends on the scheme the project declares.** A project whose
#: `.docket` says `numbering: letters` has no numbered codes at all, so letting
#: `[0-9]` into its pattern only invents false ones — `R2` in a sentence about
#: a model, `N1` in a column heading, both reported as undefined codes the
#: moment a project took 3.6.0. A numbered project needs the digits; a lettered
#: one must not have them.
def _shape():
    return r"[A-Z]{1,5}[0-9]{0,3}" if numbering() == "numbers" else r"[A-Z]{1,5}"


def numbering():
    """`"numbers"` or `"letters"`, from `.docket` if the project declares it."""
    f = ROOT / ".docket"
    if f.exists():
        m = re.search(r"^\s*\*{0,2}numbering:\s*\*{0,2}\s*(\w+)",
                      f.read_text(errors="ignore"), re.M | re.I)
        if m:
            return m.group(1).lower()
    return "numbers"


CODE = None          # set below, once numbering() can be called

# Words that look like codes but are not.
NOT_CODES = {
    "A", "I", "OK", "UTC", "PDF", "AI", "UI", "US", "IPA", "SVG", "CSS", "HTML",
    "JSON", "URL", "API", "iOS", "TLS", "DNS", "USB", "SPM", "MOS", "AC", "MC",
    "TASB", "WCAG", "AAA", "AA", "DOB", "S",
    # The framework's own metasyntactic placeholder — `**CODE**` is how the
    # documentation writes "a code goes here". Any project that documents the
    # convention hits this, so it belongs in the shared set.
    "CODE",
    # An astrological abbreviation, not a Docket code. **Q-02** asks whether this
    # and the whole set should be emptied for a fresh install; until it is
    # answered the line stays, and its own comment is the argument for removing it.
    "SP",
}


CODE = _shape()


def definitions():
    """code -> where it is defined."""
    out = {}

    # Headings define codes too: "### CA — Natal computation", "## H — Philosophy".
    for doc in (ROOT / "features_and_functions.md", ROOT / "Gameplan.md",
                ROOT / "development_plan.md"):
        for m in re.finditer(rf"^#{{2,4}}\s+~*({CODE})~*\s+[—-]", doc.read_text(), re.M):
            out.setdefault(m.group(1), doc.name)

    feat = (ROOT / "features_and_functions.md").read_text()
    for line in feat.split("\n"):
        if not re.match(r"^\s*[-*]\s*[✅🔨⬜💡❌]", line):
            continue
        # A line may define several: "✅ **CCA** Placidus · ✅ **CCB** Whole Sign"
        for m in re.finditer(rf"[✅🔨⬜💡❌]️?\s*\*\*~*({CODE})~*\*\*", line):
            out.setdefault(m.group(1), "features_and_functions.md")
    for m in re.finditer(r"^\|\s*\*\*([A-Z])\*\*\s*\|", feat, re.M):   # domain table
        out[m.group(1)] = "features_and_functions.md"

    game = (ROOT / "Gameplan.md").read_text()
    for m in re.finditer(r"^\|\s*~*\s*(K[A-Z]{0,3})\s*~*\s*(?:✅)?\s*\|", game, re.M):
        if m.group(1) != "Code":
            out[m.group(1)] = "Gameplan.md"

    for doc in sorted((ROOT / "chapters").glob("*.md")):
        for m in re.finditer(rf"^\s*[-*]\s*(?:[✅🔨⬜💡❌]️?\s*)+\*\*({CODE})\*\*", doc.read_text(), re.M):
            out.setdefault(m.group(1), doc.name)

    # Questions live in two files: the open ones, and the archive they move to
    # once settled. Both define codes — a Q code is permanent wherever it sits.
    for name in ("open_questions.md", "answered_questions.md"):
        f = ROOT / name
        if not f.exists():
            continue
        for m in re.finditer(r"^###\s+(Q-\d+)", f.read_text(), re.M):
            out.setdefault(m.group(1), name)
    for m in re.finditer(r"^##\s+(LE-\d+)", (ROOT / "lessons_learned.md").read_text(), re.M):
        out[m.group(1)] = "lessons_learned.md"
    return out


def main():
    defined = definitions()
    unknown = {}

    for doc in DOCS:
        text = doc.read_text()
        # A reference is a bold code: **UCAF**, **Q-15**, **LE-23**, **KAA**.
        for m in re.finditer(rf"\*\*(?:~~)?({CODE}|Q-\d+|LE-\d+)(?:~~)?\*\*", text):
            code = m.group(1)
            if code in NOT_CODES or code in defined:
                continue
            unknown.setdefault(code, set()).add(doc.name)

    # A code named only by an open question is *proposed*: the question says what
    # would exist if it were answered one way. That is legitimate, and reported
    # rather than failed.
    proposed = {c: w for c, w in unknown.items()
                if w <= {"open_questions.md", "answered_questions.md"}}
    broken = {c: w for c, w in unknown.items() if c not in proposed}

    for code in sorted(broken):
        print(f"    UNDEFINED  {code} referenced in {', '.join(sorted(broken[code]))}")
    if broken:
        print(f"    {len(broken)} code(s) referenced but never defined")
        return 1

    note = f"; {len(proposed)} proposed by open questions" if proposed else ""
    if numbering() == "letters":
        note += "; lettered leaves (.docket) — do not re-index"
    print(f"    {len(defined)} codes defined, every reference resolves{note}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
