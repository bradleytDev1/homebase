#!/usr/bin/env python3
"""No pre-3.0.0 names survive in a project that claims to be on 3.0.0 or later.

    python3 scripts/check_legacy_names.py

**Rule 4, applied to the framework's own rename.** Until 3.0.0 this framework
was called the Codex and stamped `.codex-*` into every project it touched. The
updater migrates those names, and every reader still accepts both prefixes for
two releases — which is exactly the arrangement that lets a half-finished
migration go unnoticed. A project can carry `.codex-version` *and*
`.docket-version`, disagree with itself about which one is true, and pass every
other gate while doing it.

So this fails while any legacy name survives in a project that says it is on
3.0.0 or later. Being *behind* is not an error — a project still on 2.x is
simply not there yet, and is skipped.

    Reads          .docket-version, the project root, scripts/
    Fails when     a .codex-* file remains, or a renamed script is still present
    Skips when     the project is on a framework older than 3.0.0
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import docket_version                                            # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent

#: The release that renamed everything.
RENAMED_IN = (3, 0, 0)

LEGACY_SCRIPTS = [
    "build_codex.py", "check_codex_anchors.py", "codex_version.py",
    "codex_theme.py", "codex_questions.py", "codex-server.py",
    "codex-survey.py", "codex-update.py", "codex.sh",
]


def main():
    installed = docket_version.installed_version(ROOT)
    if docket_version.parse(installed) < RENAMED_IN:
        print("    on %s — the rename lands in 3.0.0, nothing to check yet"
              % (installed or "an unrecorded framework"))
        return 0

    bad = []
    bad += ["%s" % p.name for p in sorted(ROOT.glob(".codex-*"))]
    bad += ["scripts/%s" % n for n in LEGACY_SCRIPTS
            if (ROOT / "scripts" / n).exists()]
    if (ROOT / "docs" / "codex.html").exists():
        bad.append("docs/codex.html")

    if not bad:
        print("    no pre-3.0.0 names left")
        return 0

    print("    %d pre-3.0.0 name(s) still here:" % len(bad))
    for b in bad:
        print("      %s" % b)
    print("    the migration did not finish. Run:")
    print("      python3 ~/.claude/skills/docket/scripts/docket-update.py "
          "--project . --full")
    return 1


if __name__ == "__main__":
    sys.exit(main())
