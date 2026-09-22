#!/usr/bin/env python3
"""
docket-update.py — bring a project that adopted the Docket up to the current framework.

    python3 docket-update.py                  # say what would change, change nothing
    python3 docket-update.py --apply          # make the changes
    python3 docket-update.py --full           # apply, rebuild the viewer, run the check
    python3 docket-update.py --apply --force  # also overwrite files the project edited
    python3 docket-update.py --project /path/to/project

**The project owns its content; the framework owns its plumbing — and the line
between them is not where you would guess.**

`check-docs.sh` looks like framework plumbing and is not. Measured on the project
this update came from: the framework ships 173 lines and that project's copy is
**338, carrying 19 gates of its own** — every one a lesson it learned and wrote
down. Replacing that file to deliver two new checks would destroy nineteen. So
this **never overwrites it**: it inserts the missing gate invocations and leaves
everything else alone.

**The eight documents are never touched, in any mode.** They are the project.

WHAT CHANGED, NOT WHICH FILES CHANGED
-------------------------------------
A list of copied filenames answers a question nobody asked. What a project needs
to know is what it has been missing, so this reads `CHANGES.md` and prints the
entries **between the version this project actually has and the current one** —
one section per release, with the manual steps each one needs. `.docket-version`
is the key that makes that possible, which is why stamping it is not optional
and `check_version.py` fails without it.

STALE IS NOT THE SAME AS CUSTOMISED
-----------------------------------
For every framework file, "the project's copy differs from the framework's" has
two opposite meanings, and treating them alike gets one of them wrong:

    stale       the project never touched it; it is simply an older release.
                Replacing it IS the upgrade — refusing to is the failure.
    customised  the project edited it on purpose. Replacing it destroys work.

A diff cannot tell these apart, so this records what it installed. `.docket-manifest`
holds a hash per framework file at the moment it was written into the project.
On the next run:

    matches the framework      already current, nothing to say
    matches the manifest       untouched since install → **stale, replaced**
    differs from the manifest  the project edited it → **left alone**
    no manifest entry          installed before manifests, or by hand → left
                               alone, and named, so you can look and decide

Only the last two need `--force`, and only the last is a real decision: an
edited file should stay edited, but a file with no manifest entry has to be
diffed and judged.

WHAT IT DOES
------------
    new files            copied in            (scripts, templates, the pages)
    stale files          replaced             (proved untouched by the manifest)
    edited files         left alone           (--force to overwrite)
    check-docs.sh        gate lines inserted  (never replaced)
    CLAUDE.md            missing protocol reported, never rewritten
    the documents        never touched

FILE METADATA
-------------
    Created        2026-09-17
    Inputs         the skill directory, and a project that adopted it
    Returns        a report; with --apply, the files it names
    Writes         .docket-version, .docket-manifest, .docket-changes.md
"""
import argparse
import hashlib
import json
import os
import pathlib
import re
import shutil
import sys

__version__ = "1.1.0"

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import docket_version                                          # noqa: E402


def find_skill():
    """Locate the skill directory, or stop.

    This script is copied *into* each project, so its own location is the
    project, not the skill — deriving one from the other is the obvious move and
    it is wrong. `docket_version.find_skill` looks for a directory that actually
    carries the framework; here, unlike in the dashboard, not finding one is
    fatal rather than merely unknown.
    """
    skill = docket_version.find_skill()
    if skill:
        return skill
    sys.exit("cannot find the Docket skill. Set DOCKET_SKILL to its directory\n"
             "(normally ~/Projects/docket, symlinked at ~/.claude/skills/docket).")


SKILL = find_skill()

#: **One number, in one file.** `VERSION` at the skill root is the framework's
#: version; it used to be a constant here, which meant the updater was the only
#: thing that knew it and every other surface had to be told. Written into the
#: project as `.docket-version` so the next run — and the dashboard — can say
#: what changed since.
FRAMEWORK_VERSION = docket_version.framework_version(SKILL)

#: Framework plumbing, tracked in the manifest: added when missing, replaced
#: when stale, left alone when the project edited it. Source and destination are
#: both given because not everything lands under the name it ships under —
#: `CHANGES.md` becomes `.docket-changes.md` so it cannot be mistaken for the
#: project's own changelog.
TRACKED = [(p, p) for p in (
    "scripts/build_docket.py", "scripts/check_codes.py", "scripts/check_status.py",
    "scripts/check_docket_anchors.py", "scripts/check_answer_inbox.py",
    "scripts/check_version.py", "scripts/docket_version.py", "scripts/docket_theme.py",
    "scripts/docket_questions.py", "scripts/docket-server.py", "scripts/docket-survey.py",
    "scripts/check_console.py", "scripts/docket.sh", "scripts/docket-update.py",
    "scripts/check_legacy_names.py", "scripts/check_master_only.py",
    "scripts/docket-renumber.py",
    # The end that SENDS a framework flaw report. `check_framework_reports.py`
    # is the end that receives and stays in the master (KAQ).
    "scripts/docket-report.py",
    # what replaced the lock: warns while a project cannot undo a bad write
    "scripts/check_git.py",
    # prints what a project is waiting on, as a message to whoever answers.
    # Useful standalone; the delivery half is unbuilt (SP, Q-11).
    "scripts/docket-digest.py",
    # The dashboard pages are framework surfaces, not project content. They were
    # once add-only, which meant a project that installed the console in June
    # could never receive a fix to it — the manifest makes replacing an
    # untouched copy safe, so they are tracked like anything else.
    "dashboard/index.html", "dashboard/console.html", "dashboard/questions.html",
    "dashboard/theme.html", "dashboard/chrome.html",
)]

#: **Files the framework has withdrawn.** Shipping a feature is easy and
#: un-shipping one had no path at all: the updater added and replaced, and a
#: retired script simply stayed in every project that had ever received it,
#: still invoked from their `check-docs.sh`, failing on a file nobody meant to
#: keep. Removal follows the same discipline as replacement — a copy still
#: matching the manifest was never touched by the project and can go; one that
#: differs is the project's now, and is reported rather than deleted. (`LE-22`)
RETIRED = [
    ("dashboard/discussion.html", "the discussion page, withdrawn in 3.12.0"),
    ("scripts/docket_discussion.py", "the transcript distiller, withdrawn in 3.12.0"),
    ("scripts/check_promoted.py", "its gate, withdrawn in 3.12.0"),
    # Retired in 4.0.0. Never once refused, in any project, in its whole life,
    # and check-docs.sh only ever printed the holder — it could not stop
    # anything by construction. The block that printed it is guarded by
    # `if [ -f DOCS_LOCK.md ]`, so removing the file silences it with no edit
    # to a file the updater must never replace. See KAS, LE-31.
    ("DOCS_LOCK.md", "the documentation lock, retired in 4.0.0"),
]

#: Gate invocations to take back out of a project's own `check-docs.sh`. The
#: file is still never replaced; these are removed line-pair by line-pair, the
#: exact inverse of how they were inserted.
RETIRED_GATES = ["check_promoted.py"]

#: **Files the project never owns, replaced without asking.** `.docket-changes.md`
#: is the framework's own changelog copied in so a machine without the skill can
#: still say what a project is missing. A project has no business editing it, and
#: a *stale* copy is not a harmless difference — it is the "what's new" panel
#: quietly showing the wrong thing. It sat in the manifest-gated list, so on
#: three projects at once it came up as "differs, predates the manifest — left
#: alone", asking a person to adjudicate a file that is by definition a copy.
ALWAYS = [
    ("CHANGES.md", ".docket-changes.md"),
]

#: Added when absent, never overwritten — a project is expected to edit these.
DROP_IN = [
    # **`KE` says never *replace* check-docs.sh. It does not say never add one.**
    # Those are different states and conflating them left a project that had no
    # scripts at all being told, in this script's own closing line, to run a file
    # it had just been denied. A project's own gates are sacred; the absence of a
    # file is not.
    ("scripts/check-docs.sh", "scripts/check-docs.sh"),
    ("templates/DOCS_LOCK.md", "DOCS_LOCK.md"),
    # The template `README.md` and `CLAUDE.md` both link to `chapters/README.md`.
    # A project adopted without that directory fails the link gate on every run,
    # for a file it was never given.
    ("templates/chapters/README.md", "chapters/README.md"),
    ("templates/.docket-webawesome.example", ".docket-webawesome.example"),
    ("templates/.docket-surfaces.example.json", ".docket-surfaces.example.json"),
]

#: The gates that must be invoked from check-docs.sh, with the line that does it.
GATES = [
    ("check_docket_anchors.py",
     'echo "==> Every link in the Docket viewer\'s rail reaches a heading"\n'
     'python3 scripts/check_docket_anchors.py || fail=1'),
    ("check_answer_inbox.py",
     'echo "==> Answers recorded at /questions are in the Docket"\n'
     'python3 scripts/check_answer_inbox.py || fail=1'),
    ("check_console.py",
     'echo "==> The console\'s surface list resolves"\n'
     'python3 scripts/check_console.py || fail=1'),
    ("check_version.py",
     'echo "==> This project knows which Docket framework it is running"\n'
     'python3 scripts/check_version.py || fail=1'),
    ("check_master_only.py",
     'echo "==> Master-only material stays in the master"\n'
     'python3 scripts/check_master_only.py || fail=1'),
    ("check_legacy_names.py",
     'echo "==> No pre-3.0.0 names survive the rename"\n'
     'python3 scripts/check_legacy_names.py || fail=1'),
]

#: Protocol the project's own CLAUDE.md should carry. Matched on the marker so a
#: project that worded it differently is not told to add it twice.
PROTOCOL = [
    ("DOCS_LOCK",
     "the documentation lock — who may write to the Docket right now"),
    ("answers.jsonl",
     "the answer inbox — answers are captured at /questions and filed by hand, "
     "and check_answer_inbox.py fails the check until they are"),
    (".docket-version",
     "the framework version — .docket-version says which Docket this project has, "
     "and ./scripts/docket.sh --update reports what it is missing"),
]


# ── the 3.0.0 rename ────────────────────────────────────────────────────────
#: Every framework file whose name changed when the Codex became the Docket.
#: Kept as an explicit table rather than a string substitution, because a blind
#: rename inside a project would also rewrite whatever the project itself calls
#: a codex — and this script's one promise is that it never touches the
#: project's own work.
LEGACY_SCRIPTS = {
    "scripts/build_codex.py":          "scripts/build_docket.py",
    "scripts/check_codex_anchors.py":  "scripts/check_docket_anchors.py",
    "scripts/codex_version.py":        "scripts/docket_version.py",
    "scripts/codex_theme.py":          "scripts/docket_theme.py",
    "scripts/codex_questions.py":      "scripts/docket_questions.py",
    "scripts/codex-server.py":         "scripts/docket-server.py",
    "scripts/codex-survey.py":         "scripts/docket-survey.py",
    "scripts/codex-update.py":         "scripts/docket-update.py",
    "scripts/codex.sh":                "scripts/docket.sh",
}

#: The dotfiles the framework stamps into a project. These are the *interface*,
#: which is why the rename is a migration rather than an edit.
LEGACY_DOTFILES = ["version", "manifest", "changes.md", "webawesome",
                   "surfaces.json", "chapters", "master",
                   "webawesome.example", "surfaces.example.json"]

#: Tokens rewritten inside a project's own `check-docs.sh`. **Identifiers only.**
#: That file is never replaced — its gates are the project's, and in one real
#: project it is 338 lines carrying 19 of them. But it *invokes* framework
#: scripts by path, and those paths just changed, so leaving it alone would hand
#: the project a check that cannot run. The rule: rewrite what breaks, leave
#: what merely reads oddly. Prose saying "Codex" is reported, not edited.
CHECK_TOKENS = ([(k, v) for k, v in LEGACY_SCRIPTS.items()]
                + [("check_codex_anchors.py", "check_docket_anchors.py"),
                   ("build_codex.py", "build_docket.py"),
                   ("codex_version.py", "docket_version.py"),
                   ("codex_theme.py", "docket_theme.py"),
                   ("codex_questions.py", "docket_questions.py"),
                   ("docs/codex.html", "docs/docket.html"),
                   ("CODEX_SKILL", "DOCKET_SKILL"),
                   ("CODEX_WA_KIT", "DOCKET_WA_KIT"),
                   # **Bare filenames too, and this is not belt-and-braces.**
                   # A project's check-docs.sh builds one of these paths from
                   # two separate literals — `ROOT / "docs" / "codex.html"` —
                   # so the joined token above cannot match it, and the gate
                   # went on looking for a file the rename had moved. It did
                   # not fail; it reported "no viewer built yet" and passed,
                   # which is the quiet kind. Longest first, so a path token
                   # has already consumed what it owns. (LE, 3.0.0)
                   ("codex.html", "docket.html"),
                   ("codex-server.py", "docket-server.py"),
                   ("codex-survey.py", "docket-survey.py"),
                   ("codex-update.py", "docket-update.py"),
                   ("codex.sh", "docket.sh"),
                   # The identity gate guards against an unfinished install by
                   # comparing the project's title to the template's. The
                   # templates are headed "The Docket" now, so a project still
                   # comparing against "the codex" has a guard that can never
                   # fire again. Logic, not prose — so it is rewritten.
                   ('"the codex"', '"the docket"')]
                + [(".codex-" + s, ".docket-" + s) for s in LEGACY_DOTFILES])


def migrate_legacy(proj, apply, force=False):
    """Carry a pre-3.0.0 project across the rename. Returns report lines.

    **Runs before anything else, because the manifest itself is one of the files
    being renamed.** Three kinds of thing move, and the third is the one that
    needed thinking about:

    1. `.codex-*` → `.docket-*`. A plain rename; these are the interface.
    2. Framework scripts. A copy the project never touched is *deleted* here and
       arrives again under its new name in the ordinary pass. A copy the project
       **edited** is *renamed* instead, so the edit survives and lands under the
       name everything now expects — and its manifest entry moves with it, so
       the next run still recognises it as edited rather than stale.
    3. The project's own `check-docs.sh`, which is never replaced and which
       invokes the renamed scripts by path. Identifier tokens are rewritten in
       place; prose is left alone and reported.

    Returns `(lines, pending)`. **`pending` is why this returns two things.** In
    a dry run nothing has moved yet, so the pass that follows looks for
    `scripts/build_docket.py`, does not find it, and cheerfully reports "would
    add" — when what will actually happen is that the project's own old copy
    gets renamed into that slot and then left alone. The report and the run
    disagreed, and the report is the thing a person decides on. `pending` maps
    each destination to the file that will be sitting there. (LE, 3.1.1)
    """
    out, moved, pending = [], 0, {}

    # 1 — the dotfiles
    for s in LEGACY_DOTFILES:
        old, new = proj / (".codex-" + s), proj / (".docket-" + s)
        if old.exists() and not new.exists():
            out.append("  .codex-%-22s -> .docket-%s" % (s, s))
            moved += 1
            if apply:
                old.rename(new)
            else:
                pending[".docket-" + s] = old

    # 2 — the scripts, manifest-aware
    mpath = docket_version.project_file(proj, "manifest")
    try:
        man = json.loads(mpath.read_text())
    except (OSError, ValueError):
        man = {}
    man_moves = {}
    for rel_old, rel_new in LEGACY_SCRIPTS.items():
        old, new = proj / rel_old, proj / rel_new
        if not old.exists():
            continue
        recorded = man.get(rel_old)
        untouched = recorded is not None and recorded == sha(old)
        if untouched:
            out.append("  %-34s removed (arrives as %s)"
                       % (rel_old, pathlib.Path(rel_new).name))
            if apply:
                old.unlink()
        else:
            why = "edited here" if recorded is not None else "predates the manifest"
            out.append("  %-34s kept, renamed — %s" % (rel_old, why))
            if apply:
                if new.exists():
                    new.unlink()
                old.rename(new)
            if recorded is not None:
                man_moves[rel_old] = rel_new
            if not apply:
                pending[rel_new] = old
        moved += 1

    # the manifest's keys move with the files they describe
    if man_moves and apply:
        for k, v in man_moves.items():
            man[v] = man.pop(k)
        (proj / ".docket-manifest").write_text(json.dumps(man, indent=1),
                                               encoding="utf-8")

    # 3 — the project's own check-docs.sh: rewrite what breaks, only that
    cd = proj / "scripts" / "check-docs.sh"
    if cd.exists():
        try:
            txt = cd.read_text()
        except (OSError, UnicodeDecodeError):
            txt = ""
        new_txt, hits = txt, 0
        for a, b in CHECK_TOKENS:
            if a in new_txt:
                hits += new_txt.count(a)
                new_txt = new_txt.replace(a, b)
        if hits:
            out.append("  scripts/check-docs.sh              %d invocation(s) "
                       "repointed; its gates untouched" % hits)
            moved += 1
            if apply:
                cd.write_text(new_txt, encoding="utf-8")
        left = new_txt.count("Codex") + new_txt.count("codex")
        if left:
            out.append("  scripts/check-docs.sh              %d mention(s) of "
                       "'Codex' left in prose — reword when you like" % left)

    # 4 — the built viewer, which is regenerated anyway
    old_view = proj / "docs" / "codex.html"
    if old_view.exists():
        out.append("  docs/codex.html                    removed "
                   "(rebuilt as docs/docket.html)")
        moved += 1
        if apply:
            old_view.unlink()

    if not moved:
        return [], pending
    head = ["", "The 3.0.0 rename — the Codex is now the Docket", ""]
    tail = ["", "  CLAUDE.md is reported, never rewritten. If it says \"Codex\" or",
            "  calls ./scripts/codex.sh, those are yours to reword."] \
        if (proj / "CLAUDE.md").exists() and "odex" in _read_safe(proj / "CLAUDE.md") \
        else []
    return head + out + tail, pending


def _read_safe(p):
    try:
        return p.read_text()
    except (OSError, UnicodeDecodeError):
        return ""


def sha(p):
    try:
        return hashlib.sha256(p.read_bytes()).hexdigest()
    except OSError:
        return None


def report_changes(was, now, skill):
    """What this project has been missing, release by release.

    Printed before the file list, because it is the part a reader is deciding
    on. A project with no stamp gets the whole history: it cannot be placed, so
    everything is potentially new to it.
    """
    entries = docket_version.changes_since(
        was, now, docket_version.changes_text(skill=skill))
    if not entries:
        return []
    if was:
        print("What changed since %s:" % was)
    else:
        print("This project carries no .docket-version, so everything since the")
        print("first recorded release is potentially new to it:")
    print()
    for e in entries:
        print("  %s%s — %s" % (e["version"], "  " + e["date"] if e["date"] else "",
                               e["summary"]))
        for b in e["bullets"]:
            print("      · %s" % b)
        print()
    return entries


def finish(proj):
    """Rebuild the viewer and run the check, in the project, reporting both.

    Returns the check's exit code, so `--full` fails when the project's own
    gates fail — an update that leaves a project failing its own checks has not
    finished, whatever the file copying did.
    """
    import subprocess

    for label, cmd in (("Rebuilding the viewer", ["./scripts/docket.sh", "--build"]),
                       ("Running the Docket check", ["./scripts/check-docs.sh"])):
        script = proj / cmd[0]
        if not script.exists():
            print("\n%s — skipped, %s is not installed" % (label, cmd[0]))
            continue
        print("\n%s — %s" % (label, " ".join(cmd)))
        # **Flush before handing the terminal to a child.** Our prints are
        # block-buffered when stdout is a pipe; the child writes straight
        # through. Without this the labels arrive after the output they label,
        # or — piped into anything — not at all.
        sys.stdout.flush()
        try:
            r = subprocess.run(cmd, cwd=proj)
        except OSError as exc:
            print("    could not run it: %s" % exc)
            return 1
        if r.returncode and cmd[0].endswith("check-docs.sh"):
            print("\nThe check failed. That is the project's own gates talking,")
            print("not the update — read what they said and fix those.")
            return r.returncode
        if r.returncode:
            print("    exited %d" % r.returncode)
            return r.returncode
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--project", default=".", help="the project to update (default: cwd)")
    ap.add_argument("--apply", action="store_true", help="make the changes")
    ap.add_argument("--force", nargs="*", metavar="FILE", default=None,
                    help="take the framework's copy of a file the project edited, or "
                         "that predates the manifest. Bare --force means every such "
                         "file; --force scripts/x.py scripts/y.sh means only those. "
                         "**Per-file is usually what you want** — a project with some "
                         "stale copies and some customised ones is the normal case, "
                         "and all-or-nothing is the wrong granularity for it")
    ap.add_argument("--full", action="store_true",
                    help="apply, then rebuild the viewer and run the Docket check")
    a = ap.parse_args()
    # **`--full` is the whole job, because the job is not done when the files
    # land.** Every release so far has ended with "rebuild the viewer" as a
    # manual step, and a viewer left unbuilt is the one surface still showing
    # the old framework — which is exactly the state somebody then reports as a
    # bug in the new one.
    if a.full:
        a.apply = True

    # **A named file that matches nothing is a typo, and must not pass
    # quietly.** Silently forcing nothing looks exactly like forcing something
    # that made no difference, and the person walks away believing they took
    # the framework's copy.
    forceable = [dst for _, dst in TRACKED] + [dst for _, dst in DROP_IN] \
        + [dst for _, dst in ALWAYS]
    force_set, bad_names = set(), []
    if a.force:
        by_base = {}
        for rel in forceable:
            by_base.setdefault(pathlib.PurePath(rel).name, []).append(rel)
        for name in a.force:
            name = name.lstrip("./")
            if name in forceable:
                force_set.add(name)
            elif name in by_base and len(by_base[name]) == 1:
                force_set.add(by_base[name][0])       # a bare basename is fine
            else:
                bad_names.append(name)
    if bad_names:
        sys.exit("--force names %s, which the framework does not ship.\n"
                 "\nForceable files are:\n\n%s\n"
                 % (", ".join(repr(n) for n in bad_names),
                    "\n".join("    " + r for r in sorted(forceable))))

    def forced(rel):
        """Bare --force means everything; --force with names means those."""
        if a.force is None:
            return False
        return True if not a.force else rel in force_set

    proj = pathlib.Path(a.project).resolve()

    # **The skill is allowed to keep a Docket of its own.** It builds and updates
    # other projects, and it is also a project — one with decisions worth
    # recording and questions worth filing. What it cannot do is *update* from
    # itself: source and destination are the same directory, so every copy is a
    # file onto itself and the manifest would record hashes of files against
    # themselves.
    #
    # It still needs the stamp. Without `.docket-version` its own dashboard says
    # "cannot say which Docket it has", which is absurd for the thing that
    # defines the number — so stamp it, from `VERSION`, and do nothing else.
    if docket_version.is_master(proj):
        print("Project : %s" % proj)
        print("This is the MASTER Docket — the framework's own source, marked by")
        print(".docket-master. It *is* framework %s, so there is nothing to carry"
              % FRAMEWORK_VERSION)
        print("into it. Stamping the version and stopping.")
        if a.apply:
            (proj / ".docket-version").write_text(FRAMEWORK_VERSION + "\n",
                                                 encoding="utf-8")
            print("\nStamped .docket-version %s." % FRAMEWORK_VERSION)
        else:
            print("\nNothing was changed. Re-run with --apply to stamp it.")
        return 0

    if not (proj / "features_and_functions.md").exists():
        # **Say what to do instead.** "Refusing" with no next step sends somebody
        # looking for a flag that does not exist; an install is a different job,
        # with an interview in it, and it belongs to the skill rather than here.
        sys.exit(
            "refusing: %s has no features_and_functions.md.\n"
            "\n"
            "It has not adopted the Docket, so this is an install rather than an\n"
            "update — a different job, with an interview in it. Start there:\n"
            "\n"
            "    python3 %s/scripts/docket-survey.py %s\n"
            "\n"
            "then ask Claude to \"adopt the Docket\" in that project, which runs the\n"
            "skill and does the install properly. This script only carries a newer\n"
            "framework into a project that already has one." % (proj, SKILL, proj))

    # **Before anything else**, because the manifest is itself one of the files
    # the 3.0.0 rename moves.
    migration, pending = migrate_legacy(proj, a.apply, a.force)

    stamp = proj / ".docket-version"
    was_v = docket_version.installed_version(proj)
    mpath = docket_version.project_file(proj, "manifest")
    try:
        manifest = json.loads(mpath.read_text())
    except (OSError, ValueError):
        manifest = {}
    mpath = proj / ".docket-manifest"      # always written under the new name

    print("Project : %s" % proj)
    print("Was     : framework %s   Now: %s"
          % (was_v or "unrecorded (no .docket-version)", FRAMEWORK_VERSION))
    print()
    if migration:
        print("\n".join(migration))
        print()
    entries = report_changes(was_v, FRAMEWORK_VERSION, SKILL)

    added, stale, edited, unknown, gated, notes, took = [], [], [], [], [], [], []
    retired = []

    # **A project being updated predates the numbered leaf, by definition.**
    # 3.6.0 numbers the leaf of a code — `CA1` rather than `CAA` — for projects
    # adopted after it. Every project reaching this line adopted before it, and
    # its codes are already cited throughout its own documents, so the only
    # safe thing is to record which scheme it is on and never convert. Stamped
    # rather than asked, because a question here has exactly one right answer.
    dk = proj / ".docket"
    if not dk.exists():
        notes.append(".docket — recorded that this project numbers with letters, "
                     "so no update re-indexes it")
        if a.apply:
            src = SKILL / "templates" / ".docket.legacy"
            if src.exists():
                shutil.copy2(src, dk)

    written = dict(manifest)   # what the manifest will say when we are done

    def install(src, dst, rel, bucket):
        bucket.append(rel)
        if a.apply:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            if dst.suffix == ".sh":
                os.chmod(dst, 0o755)
            written[rel] = sha(src)

    # ── withdrawn: taken back out, on the same terms as replacing ────────
    for rel, why in RETIRED:
        dst = proj / rel
        if not dst.exists():
            continue
        recorded = manifest.get(rel)
        if recorded is not None and recorded == sha(dst):
            retired.append("%s — %s" % (rel, why))
            if a.apply:
                dst.unlink()
                written.pop(rel, None)
        else:
            notes.append("%s is withdrawn (%s) but differs from what was "
                         "installed, so it is left for you to delete" % (rel, why))
    cdw = proj / "scripts" / "check-docs.sh"
    if cdw.exists():
        txt = cdw.read_text(errors="ignore")
        new = txt
        for g in RETIRED_GATES:
            new = re.sub(r"\n?echo \"==>[^\n]*\"\npython3 scripts/%s \|\| fail=1\n"
                         % re.escape(g), "\n", new)
        if new != txt:
            retired.append("scripts/check-docs.sh — the withdrawn gate's invocation")
            if a.apply:
                cdw.write_text(new, encoding="utf-8")

    # ── never the project's: copied in, replaced without ceremony ────────
    for rel_src, rel in ALWAYS:
        src, dst = SKILL / rel_src, proj / rel
        if src.exists() and (not dst.exists() or sha(dst) != sha(src)):
            install(src, dst, rel, added if not dst.exists() else stale)

    # ── tracked framework files ──────────────────────────────────────────
    for rel_src, rel in TRACKED:
        src, dst = SKILL / rel_src, proj / rel
        if not src.exists():
            continue
        # In a dry run the migration has not moved anything yet, so ask what
        # *will* be sitting at this path once it has.
        present = dst if dst.exists() else pending.get(rel)
        if present is None:
            install(src, dst, rel, added)
            continue
        here = sha(present)
        if here == sha(src):
            written[rel] = here            # already current; keep it recorded
        elif rel in manifest and manifest[rel] == here:
            install(src, dst, rel, stale)  # untouched since install → the upgrade
        elif rel in manifest:
            edited.append(rel)
            if a.apply and forced(rel):
                install(src, dst, rel, [])
                took.append(rel)
        else:
            unknown.append(rel)
            if a.apply and forced(rel):
                install(src, dst, rel, [])
                took.append(rel)

    # **If it just replaced itself, start again as the new version.**
    # A stale updater can only deliver what the stale updater knows about: it
    # rewrites its own file, then goes on to stamp the version and file list it
    # was compiled with, leaving the project half-updated and looking finished.
    # One re-exec, guarded against looping, and the rest of this run is done by
    # the version the project now actually has.
    if a.apply and "scripts/docket-update.py" in (added + stale) \
            and os.environ.get("DOCKET_UPDATE_REEXEC") != "1":
        env = dict(os.environ, DOCKET_UPDATE_REEXEC="1")
        print("   ^ scripts/docket-update.py — re-running as the new version\n")
        # **Flush before exec, or the report is lost.** `execve` replaces the
        # process image, and anything still sitting in Python's stdout buffer
        # goes with it. That buffer is only line-flushed when stdout is a
        # terminal — so this worked in every interactive test and silently
        # discarded the entire pre-re-exec report, the migration included, the
        # moment anyone piped the output to a file or a log. (LE, 3.0.0)
        sys.stdout.flush()
        sys.stderr.flush()
        os.execve(sys.executable,
                  [sys.executable, str(proj / "scripts" / "docket-update.py")]
                  + sys.argv[1:], env)

    # ── drop-ins: added when absent, never overwritten ───────────────────
    for rel_src, rel_dst in DROP_IN:
        src, dst = SKILL / rel_src, proj / rel_dst
        if src.exists() and not dst.exists():
            install(src, dst, rel_dst, added)

    # ── check-docs.sh: insert, never replace ─────────────────────────────
    cd = proj / "scripts" / "check-docs.sh"
    if cd.exists():
        text = cd.read_text(encoding="utf-8")
        missing = [(n, line) for n, line in GATES if n not in text]
        gated.extend(n for n, _ in missing)
        if missing and a.apply:
            ins = "\n\n".join(line for _, line in missing)
            if "\nexit $fail" in text:
                text = text.replace("\nexit $fail", "\n" + ins + "\n\nexit $fail", 1)
            else:
                text = text.rstrip() + "\n\n" + ins + "\n"
            cd.write_text(text, encoding="utf-8")

    # ── CLAUDE.md: report, never rewrite ─────────────────────────────────
    cm = proj / "CLAUDE.md"
    if cm.exists():
        text = cm.read_text(encoding="utf-8")
        notes.extend(what for marker, what in PROTOCOL if marker not in text)

    # ── report ───────────────────────────────────────────────────────────
    did, would = ("Added", "Replaced") if a.apply else ("Would add", "Would replace")
    if added:
        print("%s:" % did)
        for x in added:
            print("   + %s" % x)
    if stale:
        print("%s (older release, untouched since install):" % would)
        for x in stale:
            print("   ^ %s" % x)
    if gated:
        print("%s scripts/check-docs.sh:" % ("Wired into" if a.apply else "Would wire into"))
        for x in gated:
            print("   + %s" % x)
    if retired:
        print("Withdrawn — removed from this project:")
        for x in retired:
            print("   - %s" % x)
    if took:
        print("Took the framework's copy (--force):")
        for x in took:
            print("   ! %s" % x)
    kept_e = [x for x in edited if x not in took]
    kept_u = [x for x in unknown if x not in took]
    if kept_e:
        print("EDITED by this project — left alone:")
        for x in kept_e:
            print("   ~ %s" % x)
    if kept_u:
        print("Differs, and predates the manifest — left alone:")
        for x in kept_u:
            print("   ? %s" % x)
        print("     No manifest recorded these, so an old release cannot be told")
        print("     from a deliberate edit. Diff one and decide:")
        print('       diff "%s/%s" "%s/%s"' % (SKILL, kept_u[0], proj, kept_u[0]))
        print("     Then take that one and leave the rest:")
        print("       --apply --force %s" % kept_u[0])
    if notes:
        print("CLAUDE.md does not mention:")
        for n in notes:
            print("   ! %s" % n)
        print("     Add these in the project's own words — see the skill under")
        print("     'The lock' and 'The questions console'.")
    if not (added or stale or gated or edited or unknown or notes):
        print("Nothing to do — already current.")

    if a.apply:
        stamp.write_text(FRAMEWORK_VERSION + "\n", encoding="utf-8")
        mpath.write_text(json.dumps(written, indent=2, sort_keys=True) + "\n",
                         encoding="utf-8")
        print()
        print("Stamped .docket-version %s and recorded %d files in .docket-manifest."
              % (FRAMEWORK_VERSION, len(written)))
        # **A file copied into place is not a thing that has taken effect.** The
        # manual steps of every release crossed are printed here, together,
        # because they are the difference between an update that happened and
        # one that will be discovered to have half-happened next week.
        # **Once each, in order.** Four releases that each say "rebuild the
        # viewer" are one rebuild, and printing it four times makes a reader
        # wonder which four things they were supposed to do.
        steps, seen = [], set()
        for e in entries:
            for d in e["do"]:
                if d not in seen:
                    seen.add(d)
                    steps.append(d)
        if steps:
            print()
            if a.full:
                # Saying "still to do by hand" and then doing it is how somebody
                # ends up doing it twice, or worse, not trusting that it ran.
                print("Manual steps these releases named (--full does the rebuild below):")
            else:
                print("Still to do by hand:")
            for d in steps:
                print("   → %s" % d)
        if a.full:
            return finish(proj)
        print()
        print("Now run: ./scripts/docket.sh --build && ./scripts/check-docs.sh")
    else:
        print()
        print("Nothing was changed. Re-run with --apply.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
