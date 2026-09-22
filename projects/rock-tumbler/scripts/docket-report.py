#!/usr/bin/env python3
"""
Report a flaw in the Docket framework itself, from whatever project found it.

    python3 scripts/docket-report.py "the install step cannot bootstrap" \
        --detail "docket-update.py imports docket_version, which it has not copied yet" \
        --where "SKILL.md step 3"

**Why this exists.** A session working in a project finds a bug in the framework
far more often than a session working in the framework does — it is the one
actually using it. And `LE-25` recorded what happens then: a broken instruction
was **read, silently routed around, and never reported**, for as long as the
file had existed. *"An agent that knows the system routes around a broken
instruction without reporting it. That is a good instinct for getting the job
done and a bad one for keeping the documentation true."*

So reporting is not a habit here. The report lands in the master's inbox, and
the master's own `check-docs.sh` **fails while it sits unfiled** — the same
shape as `check_answer_inbox.py`, and for the same reason: the inbox and the
Docket are claiming different things.

**It never edits the master.** It appends one line. Filing it — writing the
`LE`, making the fix, bumping the version — is a deliberate act in the master,
by somebody who has its lock.

**Append-only, and filing is a row rather than a flag**, so re-reporting
something that was filed puts it straight back in the queue.
"""

import argparse
import datetime
import json
import os
import pathlib
import sys
import uuid

INBOX = "inbox/framework-reports.jsonl"


def find_master(start=None):
    """Where the framework's own source lives.

    The skill is a symlink to it, which is the normal case. Falling back to a
    marker search means this still works on a machine where the skill was
    installed some other way.
    """
    env = os.environ.get("DOCKET_MASTER")
    if env and (pathlib.Path(env) / ".docket-master").exists():
        return pathlib.Path(env).resolve()
    skill = pathlib.Path.home() / ".claude" / "skills" / "docket"
    if (skill / ".docket-master").exists():
        return skill.resolve()
    here = pathlib.Path(start or os.getcwd()).resolve()
    for d in [here, *here.parents]:
        if (d / ".docket-master").exists():
            return d
        sibling = d / "docket"
        if (sibling / ".docket-master").exists():
            return sibling.resolve()
    return None


def project_name(root):
    readme = root / "README.md"
    if readme.exists():
        for line in readme.read_text().splitlines():
            if line.startswith("# "):
                return line[2:].strip()
    return root.name


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("summary", help="one line: what is wrong")
    ap.add_argument("--detail", default="", help="what you saw, and how to reproduce it")
    ap.add_argument("--where", default="", help="the file, script or section at fault")
    ap.add_argument("--blocking", action="store_true",
                    help="this stopped the work; say so and fix it in the master too")
    ap.add_argument("--dir", default=".")
    a = ap.parse_args()

    project = pathlib.Path(a.dir).resolve()
    master = find_master(project)
    if not master:
        print("  Could not find the master Docket (no .docket-master anywhere).")
        print("  Set DOCKET_MASTER=/path/to/docket and try again.")
        return 1
    if master == project:
        print("  This IS the master — write the LE directly, there is nothing to report to.")
        return 1

    record = {
        "id": uuid.uuid4().hex[:10],
        "kind": "report",
        "at": datetime.datetime.now().isoformat(timespec="seconds"),
        "project": project_name(project),
        "path": str(project),
        "version": (project / ".docket-version").read_text().strip()
                   if (project / ".docket-version").exists() else None,
        "summary": a.summary.strip(),
        "detail": a.detail.strip(),
        "where": a.where.strip(),
        "blocking": bool(a.blocking),
    }

    inbox = master / INBOX
    inbox.parent.mkdir(parents=True, exist_ok=True)
    with inbox.open("a") as fh:
        fh.write(json.dumps(record) + "\n")

    print(f"  Reported to the master Docket — {record['id']}")
    print(f"    {record['summary']}")
    print(f"  {master / INBOX}")
    print()
    print("  The master's check-docs.sh now fails until this is filed as an LE.")
    if a.blocking:
        print("  You marked this BLOCKING: fix it in the master too, in this turn,")
        print("  with the LE, the VERSION bump and the CHANGES.md entry.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
