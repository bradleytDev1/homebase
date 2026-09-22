#!/usr/bin/env python3
"""Master-only material stays in the master.

    python3 scripts/check_master_only.py

**Some of what is in the master is *about* the framework rather than part of
it.** The specification, the version number, the changelog, the working papers,
the list of every project on this machine and the Web Awesome kit id — none of
that belongs in a project that merely adopted the Docket. A project gets the
eight documents, the scripts and the gates; it does not get the framework's own
identity.

Nothing enforced that. The shipping lists in `docket-update.py` are a hand-kept
table, and a new master-only file added to the wrong one would arrive in nine
projects before anyone noticed — carrying, in one case, a paid kit id that
belongs to whoever bought it and a JSON file naming every project on the disk.

So this gate runs in both directions:

    in the master     nothing master-only appears in TRACKED or DROP_IN
    in a project      no master-only artifact has appeared here

    Reads          scripts/docket-update.py, the project root
    Fails when     a master-only name is shipped, or has landed in a project
"""
import importlib.util
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import docket_version                                            # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent

#: What the master must never *ship*. Checked against the updater's own tables.
NEVER_SHIPPED = [
    # the specification — the product, not the documents it produces
    "SKILL.md", "FRAMEWORK.md", "ADOPTING.md", "DASHBOARD.md",
    # the framework's own identity. A project carries `.docket-version`
    # and `.docket-changes.md` instead, which is the whole point of them.
    "VERSION", "CHANGES.md", ".docket-master",
    # the fleet. `.docket-projects.json` names every project on this disk;
    # it is nobody else's business, least of all a project's.
    ".docket-projects.json", ".docket-roots", "scripts/docket-projects.py",
    # the master receives flaw reports from projects; a project receives none.
    # `scripts/docket-report.py` DOES ship — that is the end that sends.
    "scripts/check_framework_reports.py", "inbox/framework-reports.jsonl",
    # asserts that every script here ships or is declared master-only; the
    # tables it reads exist only in the master (LE-30)
    "scripts/check_ships.py",
    # the working papers for publishing. They deliberately still say "Codex".
    "going-public/",
    # the source of every install
    "templates/",
    # the master's licence is the framework's, not the project's
    "LICENSE",
]

#: What must never *appear in a project* — and it is a much shorter list.
#:
#: **The first version of this file conflated the two, and the fleet caught it.**
#: `VERSION`, `CHANGES.md`, `LICENSE`, `templates/` and even `SKILL.md` are all
#: things a project may perfectly well have of its own: `lifecodex` keeps a
#: `VERSION`, and failed this gate for it. The framework's copies must not be
#: shipped; a project's own files of the same name are nobody's business but the
#: project's. Only files that could have arrived here by mistake belong below.
NEVER_IN_A_PROJECT = [
    ".docket-master",            # declares a directory to BE the framework
    ".docket-projects.json",     # names every project on the owner's disk
    ".docket-roots",
    "scripts/docket-projects.py",
    "going-public/",             # the master's working papers
]


def shipping_lists():
    """TRACKED + DROP_IN destinations, read from the updater itself."""
    spec = importlib.util.spec_from_file_location(
        "docket_update", ROOT / "scripts" / "docket-update.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    out = []
    for src, dst in list(m.TRACKED) + list(m.DROP_IN):
        out.append((src, dst))
    return out


def main():
    bad = []

    if docket_version.is_master(ROOT):
        try:
            pairs = shipping_lists()
        except Exception as e:                                   # noqa: BLE001
            print("    could not read the updater's file lists: %s" % e)
            return 1
        for src, dst in pairs:
            for name in NEVER_SHIPPED:
                d = name.rstrip("/")
                # CHANGES.md is allowed to ship *renamed* — that is exactly how
                # a project is told what it is missing without gaining a second
                # changelog of its own.
                if src == "CHANGES.md" and dst == ".docket-changes.md":
                    continue
                if src == d or src.startswith(d + "/"):
                    if not (name == "templates/" and not dst.startswith("templates")):
                        bad.append("ships %s -> %s" % (src, dst))
                if dst == d or dst.startswith(d + "/"):
                    bad.append("installs %s into a project" % dst)
        if not bad:
            print("    %d master-only name(s), none of them shipped"
                  % len(NEVER_SHIPPED))
    else:
        for name in NEVER_IN_A_PROJECT:
            p = ROOT / name.rstrip("/")
            if p.exists():
                bad.append("%s is here, and belongs only to the master" % name)
        if not bad:
            print("    no master-only material has landed here")

    if bad:
        print("    %d problem(s):" % len(bad))
        for b in sorted(set(bad)):
            print("      %s" % b)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
