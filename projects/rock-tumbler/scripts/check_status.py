#!/usr/bin/env python3
"""Two claims the Docket makes about itself, verified.

**The README's status line.** `CLAUDE.md` tells every new session to read
`README.md` first, so a stale status line misinforms exactly the reader it
exists for. It said "build 10" for four builds. It must agree with the
CHANGELOG's current-build line.

**The critical path.** It calls itself derived from the feature list, but it is
written by hand — the worst of both, and it drifted, listing finished work as
pending. Anything the path marks ✅ must be ✅ in the feature list.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


#: The changelog, whatever this project calls it. **Not every project has a
#: `CHANGELOG.md`** — a project that already kept its history in `CHANGES.md`
#: keeps that name (`KA`: adopt in place), and a gate that insists on one
#: spelling turns a naming preference into a failing check.
CHANGELOGS = ("CHANGELOG.md", "CHANGES.md")


def changelog():
    for name in CHANGELOGS:
        f = ROOT / name
        if f.exists():
            return name, f.read_text()
    return None, ""


def main():
    bad = False
    name, log = changelog()
    if not name:
        print("    no changelog found (looked for %s)" % ", ".join(CHANGELOGS))
        return 1
    readme = (ROOT / "README.md").read_text()
    path = (ROOT / "critical_path.md").read_text()
    feat = (ROOT / "features_and_functions.md").read_text()

    # ── the README agrees with the changelog about what is current ─────────
    # **The build number is optional, and assuming it is not was a bug.** A
    # project versioned `1.4 (build 12)` and one versioned `2.3.1` are both
    # ordinary; requiring the parenthesised half failed the second kind on every
    # run for a reason that had nothing to do with its changelog. Same family as
    # the hardcoded `1.x` scheme this gate used to carry.
    cur = re.search(r"\*\*Current:\s*([\w.]+?)\s*(?:\(build\s*(\d+)\))?\s*\*\*", log)
    if not cur:
        print(f"    {name} has no '**Current: …**' line"); return 1
    version, build = cur.group(1), cur.group(2)
    if build:
        if f"build {build}" not in readme and f"({build})" not in readme:
            print(f"    README does not mention build {build}; {name} says it is current")
            bad = True
        else:
            print(f"    README and {name} agree: {version} (build {build})")
    elif version not in readme:
        print(f"    README does not mention {version}; {name} says it is current")
        bad = True
    else:
        print(f"    README and {name} agree: {version}")

    # ── the path does not claim work the feature list has not shipped ───────
    shipped = set(re.findall(r"[✅]️?\s*\*\*~*([A-Z]{1,5})~*\*\*", feat))
    all_codes = set(re.findall(r"[✅🔨⬜💡❌]️?\s*\*\*~*([A-Z]{1,5})~*\*\*", feat))
    claimed = set(re.findall(r"\|\s*✅\s*\*\*([A-Z]{1,5})\*\*", path))

    def is_done(code):
        if code in shipped:
            return True
        # A parent — a section like UF — is done when every child is. Headings
        # carry no status marker of their own, and should not need a fake one.
        kids = [c for c in all_codes if len(c) > len(code) and c.startswith(code)]
        return bool(kids) and all(k in shipped for k in kids)

    overclaimed = sorted(c for c in claimed if not is_done(c))
    if overclaimed:
        for c in overclaimed:
            print(f"    critical_path marks {c} done, features_and_functions does not")
        bad = True
    else:
        print(f"    critical_path claims {len(claimed)} done, all ✅ in the feature list")

    # ── the project tells its own agent what the Docket is ──────────────────
    # This is the one that matters most. A project can hold every Docket
    # document and still begin each session ignorant, because the file loaded
    # automatically is CLAUDE.md — not the Docket. If CLAUDE.md does not carry
    # the protocol, the framework is furniture.
    claude = ROOT / "CLAUDE.md"
    if not claude.exists():
        print("    CLAUDE.md is missing — nothing tells a new session the Docket exists")
        bad = True
    else:
        text = claude.read_text()
        # **"Codex" still counts, and this is not laziness.** 3.0.0 renamed the
        # framework, and `CLAUDE.md` is reported by the updater but never
        # rewritten — its words are the project's. Requiring the new word turned
        # the rename into a check failure on five projects at once, for prose
        # nothing had offered to change. The rename is carried by the updater;
        # it must not be collected from the owner as a broken build. The stale
        # wording is reported below instead, and drops out in two releases.
        missing = [w for w in ("Docket", "open_questions", "Gameplan")
                   if w not in text and not (w == "Docket" and "Codex" in text)]
        if missing:
            print(f"    CLAUDE.md does not mention: {', '.join(missing)}")
            print("    A new session reads CLAUDE.md, not the framework docs.")
            bad = True
        else:
            print("    CLAUDE.md carries the protocol")

    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
