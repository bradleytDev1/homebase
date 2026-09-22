#!/usr/bin/env python3
"""Survey a project before adopting the Docket.

    ./docket-survey.py [path]        # human-readable
    ./docket-survey.py [path] --json # for the agent

Answers three questions, mechanically, so adoption starts from evidence rather
than from an impression:

  1. Is the Docket already here — fully, partly, or not at all?
  2. Which existing files already play a Docket role, and should be **adopted in
     place**? (Adopting keeps the file, its name and its history. Only files
     whose content gets redistributed are archived.)
  3. What is left over, and what does each leftover look like?

It reads files to form a view. A specific proposal — "this reads like three
post-mortems and a design sketch" — is far easier to answer than a filename.

**This script never writes anything.** It reports; the agent acts.

**Its output is a hypothesis, not a verdict.** The heuristics are filename
patterns and word frequencies, and they are wrong often enough that the agent
must open each file before doing anything with it. What the survey buys is a
sorted starting point on a project with forty markdown files, not a decision.
"""
import argparse
import json
import re
import sys
from pathlib import Path

DOCKET = [
    "Gameplan.md", "features_and_functions.md", "development_plan.md",
    "CHANGELOG.md", "lessons_learned.md", "open_questions.md",
    "answered_questions.md", "critical_path.md",
]

# filename → the role it probably plays. Checked before content.
BY_NAME = {
    r"^changelog": ("CHANGELOG.md", "adopt", "already a changelog"),
    r"^(readme|index)": ("README.md", "adopt", "the project's front door"),
    r"^(architecture|design|technical|internals)": (
        "development_plan.md", "adopt", "architecture under another name"),
    r"^(decisions?|adr|rfc)": ("Gameplan.md", "adopt", "decisions with reasoning"),
    r"^(lessons|postmortem|post-mortem|gotchas|pitfalls)": (
        "lessons_learned.md", "adopt", "things that went wrong"),
    r"^(roadmap|plan|milestones)": ("critical_path.md", "adopt", "ordering of work"),
    r"^(features?|functions?|spec)": (
        "features_and_functions.md", "adopt", "what it does"),
    r"^(todo|backlog|ideas?)": (
        "features_and_functions.md", "redistribute",
        "a list whose items belong in several documents"),
    r"^(questions?|open[-_]?questions)": ("open_questions.md", "adopt", "unresolved things"),
    r"^(contributing|license|licence|code_of_conduct|security)": (
        None, "leave", "a repository convention, not project reasoning"),
}

# content → what it smells like, when the name says nothing.
BY_CONTENT = [
    # Several versioned headings, not one — a single "## 2.0" in a design note
    # is not a changelog. Checked for count below.
    (r"^#{1,3}\s*\[?(v?\d+\.\d+|unreleased)", "CHANGELOG.md", "adopt",
     "several versioned entries"),
    (r"(?i)\b(we decided|decision:|chose .* because|rationale)\b", "Gameplan.md",
     "redistribute", "decisions with reasoning in them"),
    (r"(?i)\b(post-?mortem|root cause|what went wrong|this bit us|gotcha)\b",
     "lessons_learned.md", "redistribute", "things that went wrong"),
    (r"(?i)^\s*[-*]\s*\[[ x]\]", "features_and_functions.md", "redistribute",
     "a checklist of work"),
    (r"(?i)\b(should we|open question|TBD|unresolved|\?\?\?)\b", "open_questions.md",
     "redistribute", "unresolved questions"),
    (r"(?i)\b(architecture|module|component|data flow|schema)\b",
     "development_plan.md", "redistribute", "technical description"),
]


def sniff(path):
    """A view of one file: which role it looks like, and why."""
    name = path.name
    try:
        text = path.read_text(errors="replace")
    except OSError:
        return None
    lines = text.count("\n") + 1

    stem = path.stem.replace("_", "-").lower()
    for pattern, (role, action, why) in BY_NAME.items():
        # The word can sit anywhere in the name: NVLLM-PLAN.md is a plan.
        if re.search(pattern.lstrip("^"), stem, re.I):
            return {"file": name, "lines": lines, "role": role,
                    "action": action, "why": why, "basis": "name"}

    hits = []
    for pattern, role, action, why in BY_CONTENT:
        found = len(re.findall(pattern, text, re.M))
        # One match is noise; a role needs a pattern that recurs.
        threshold = 3 if role == "CHANGELOG.md" else 2
        if found >= threshold:
            hits.append((found, role, action, why))
    if hits:
        hits.sort(reverse=True)
        _, role, action, why = hits[0]
        extra = ""
        if len(hits) > 1:
            extra = f"; also reads as {hits[1][1].replace('.md','')}"
        return {"file": name, "lines": lines, "role": role, "action": action,
                "why": why + extra, "basis": "content"}

    return {"file": name, "lines": lines, "role": None, "action": "leave",
            "why": "nothing in it maps to a Docket role", "basis": "content"}


def survey(root):
    root = Path(root).resolve()
    # Match by real directory listing, not `exists()`. macOS and Windows are
    # case-insensitive, so `(root/"lessons_learned.md").exists()` is True when
    # the file is actually `LESSONS_LEARNED.md` — which made the survey report
    # a document as both already present *and* needing adoption.
    actual = {f.name for f in root.glob("*.md")}
    present, differently_cased = [], {}
    for f in DOCKET:
        if f in actual:
            present.append(f)
            continue
        match = next((a for a in actual if a.lower() == f.lower()), None)
        if match:
            present.append(f)
            differently_cased[match] = f
    claude = root / "CLAUDE.md"
    mentions = claude.exists() and "Docket" in claude.read_text()
    checks = (root / "scripts" / "check-docs.sh").exists()

    if len(present) >= 6 and mentions and checks:
        installed = "full"
    elif present or mentions or checks:
        installed = "partial"
    else:
        installed = "none"

    others = []
    for f in sorted(root.glob("*.md")):
        if f.name in DOCKET or f.name in differently_cased or \
           f.name in ("README.md", "CLAUDE.md"):
            continue
        s = sniff(f)
        if s:
            others.append(s)

    return {
        "root": str(root),
        "installed": installed,
        "docket_present": present,
        "docket_missing": [f for f in DOCKET if f not in present],
        "claude_mentions_docket": mentions,
        "has_checks": checks,
        "differently_cased": differently_cased,
        "others": others,
    }


def main():
    ap = argparse.ArgumentParser(description="Survey a project before adopting the Docket.")
    ap.add_argument("path", nargs="?", default=".")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    r = survey(args.path)

    if args.json:
        print(json.dumps(r, indent=2))
        return 0

    verdict = {
        "full": "The Docket is already here. Maintain it; do not reinstall.",
        "partial": "Partly here. Fold in what exists, add what is missing.",
        "none": "Not here. This is an adoption.",
    }[r["installed"]]
    print(f"\n{r['root']}\n{verdict}\n")

    if r["docket_present"]:
        print("  Docket documents present:")
        for f in r["docket_present"]:
            print(f"    {f}")
    if r["docket_missing"] and r["installed"] != "full":
        print("\n  Missing:")
        for f in r["docket_missing"]:
            print(f"    {f}")
    if r.get("differently_cased"):
        print("\n  Present, but differently cased — rename to match:")
        for actual, want in r["differently_cased"].items():
            print(f"    {actual}  ->  {want}")
    print(f"\n  CLAUDE.md mentions the Docket : {'yes' if r['claude_mentions_docket'] else 'no'}")
    print(f"  check-docs.sh present        : {'yes' if r['has_checks'] else 'no'}")

    if r["others"]:
        buckets = {"adopt": [], "redistribute": [], "leave": []}
        for o in r["others"]:
            buckets[o["action"]].append(o)
        titles = {
            "adopt": "Already play a Docket role — adopt in place, keep the name",
            "redistribute": "Content belongs in the Docket — archive after redistributing",
            "leave": "Nothing maps — leave alone, and say so in the question",
        }
        for action in ("adopt", "redistribute", "leave"):
            if not buckets[action]:
                continue
            print(f"\n  {titles[action]}:")
            for o in buckets[action]:
                dest = f" -> {o['role']}" if o["role"] else ""
                print(f"    {o['file']:26} {o['lines']:>5} lines{dest}")
                print(f"    {'':26}       {o['why']}")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
