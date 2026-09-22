#!/usr/bin/env python3
"""The project knows which Docket it is running.

**A framework version nobody can read is not a version.** Without
`.docket-version` the updater cannot tell a stale script from a customised one,
the dashboard cannot say what this project has, and the answer to "does this
project have the questions console?" becomes an archaeology exercise over file
contents. So the stamp is a gate, not a nicety.

    missing or unreadable .docket-version   → fails
    behind the installed skill             → says so, and passes
    no skill on this machine               → says so, and passes

**Being behind is not a failure, and making it one would be wrong.** A project
is allowed to sit on an older framework — the owner may be mid-release, or on a
machine where the skill is not installed at all. What is not allowed is not
knowing. The check reports the distance and the update command; taking it is a
decision, and decisions are not the check's to make.

FILE METADATA
-------------
    Created        2026-09-19
    Inputs         .docket-version, and the Docket skill if it is on this machine
    Returns        0 unless the stamp is missing or unreadable
    Writes         nothing
"""
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

try:
    import docket_version
except ImportError:
    print("    docket_version.py is missing — run ./scripts/docket.sh --update --apply")
    sys.exit(1)


#: Where the changelog might live. `KA`: a file that already does the job keeps
#: its name.
CHANGELOGS = ("CHANGELOG.md", "CHANGES.md")


def agrees(version):
    """Does the changelog's `Current:` line say the same thing as `VERSION`?

    **They drifted apart for the length of one session**, because a scripted
    edit bumped the version and then failed before writing the entry. Nothing
    noticed: the changelog was internally consistent, `VERSION` was a valid
    number, and every check passed. But **every project's update report is
    derived from the changelog** — so a release the changelog does not mention
    is a release no project is ever told about, and a `Current:` line behind
    `VERSION` means the newest entry is invisible to the very mechanism it
    exists to feed. `KS`.
    """
    import re
    for name in CHANGELOGS:
        f = ROOT / name
        if not f.exists():
            continue
        text = f.read_text(encoding="utf-8")
        m = re.search(r"\*\*Current:\s*([\w.]+?)\s*(?:\(build\s*\d+\))?\s*\*\*", text)
        if not m:
            print("    %s has no '**Current: …**' line to compare VERSION against" % name)
            return False
        if m.group(1) != version:
            print("    VERSION says %s but %s says %s is current"
                  % (version, name, m.group(1)))
            print("    A release the changelog does not name is a release no")
            print("    project will ever be told about. Write the entry, or")
            print("    put VERSION back.")
            return False
        print("    VERSION and %s agree: %s" % (name, version))
        return True
    return True          # no changelog here; other gates report that


def main():
    s = docket_version.status(ROOT)

    # **The master is its own version.** Here `.docket-version` and `VERSION` are
    # the same number by definition, and "behind" is not a state the framework
    # can be in relative to itself. Say which it is, and pass.
    if s["master"]:
        v = docket_version.framework_version(ROOT)
        print("    MASTER Docket — the framework's own source, at %s" % v)
        if s["unstamped"]:
            print("    no .docket-version yet — run ./scripts/docket.sh --update --apply")
            return 1
        return 0 if agrees(v) else 1

    if s["unstamped"]:
        print("    no .docket-version — this project cannot say which framework it has")
        print("    Run: ./scripts/docket.sh --update --apply")
        return 1

    if not s["current"]:
        print("    framework %s (the skill is not on this machine, so there is"
              " nothing to compare against)" % s["installed"])
        return 0

    if s["behind"]:
        n = len(s["changes"])
        print("    framework %s — the skill has %s, %d release%s ahead"
              % (s["installed"], s["current"], n, "" if n == 1 else "s"))
        for e in s["changes"]:
            print("      %s  %s" % (e["version"], e["summary"]))
        print("    Run: ./scripts/docket.sh --update       (then --apply)")
        return 0

    print("    framework %s — current" % s["installed"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
