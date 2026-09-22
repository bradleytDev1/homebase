#!/usr/bin/env python3
"""
This project can undo a bad write. Warns when it cannot.

**What replaced `DOCS_LOCK.md`.** The lock was an advisory file: take it before
writing to the Docket, release it after. It was retired in `4.0.0` after being
measured — **it was never once refused, in any project, in its whole life**, and
`check-docs.sh` only ever *printed* the holder and never failed on it. It could
not stop anything by construction, which is exactly what this framework's Rule 4
calls a disclaimer rather than a mechanism.

The failure it was built for is real: on 2026-09-16 two sessions wrote to one
document inside a minute and the second silently won. But what makes that
survivable is not a text file asking people to take turns. **It is having a
repository**, because then the clobber is a `git checkout` rather than a loss.

So this warns — it does not fail — while a project has no repository, and says
the one command that fixes it. It never creates one: `git init` without being
asked is not this framework's business, and publishing anything is emphatically
not (`GD`).

    python3 scripts/check_git.py
"""

import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent


def git(*args):
    try:
        r = subprocess.run(["git", "-C", str(ROOT), *args],
                           capture_output=True, text=True, timeout=15)
        return r.returncode, r.stdout.strip()
    except Exception:                                        # noqa: BLE001
        return 1, ""


def main():
    code, _ = git("rev-parse", "--is-inside-work-tree")
    if code != 0:
        print("    \033[33mno repository here — a bad write to the Docket cannot "
              "be undone\033[0m")
        print("    The documentation lock that used to stand in for this was "
              "retired in 4.0.0:")
        print("    it was never once refused and nothing ever failed on it. A "
              "repository is")
        print("    what actually makes a clobber survivable.")
        print("    \033[1mgit init && git add -A && git commit -m 'the project "
              "as found'\033[0m")
        return 0                       # a warning, not a gate

    code, head = git("rev-parse", "--short", "HEAD")
    if code != 0:
        print("    repository present, no commits yet — nothing to return to")
        print("    \033[1mgit add -A && git commit -m 'the project as found'\033[0m")
        return 0

    _, dirty = git("status", "--porcelain")
    n = len([l for l in dirty.splitlines() if l.strip()])
    where = f"{n} uncommitted change(s)" if n else "clean"
    print(f"    a bad write can be undone — at {head}, {where}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
