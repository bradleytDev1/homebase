#!/usr/bin/env python3
"""Which version of the Docket framework a project is on, and what it is missing.

    python3 scripts/docket_version.py            # this project, in one screen
    python3 scripts/docket_version.py --json

**One number, in one file.** The framework's version lives in `VERSION` at the
skill root. The updater stamps that number into the project as `.docket-version`.
Everything else — the dashboard header, the update report, the check — reads one
of those two and compares. Nothing computes a version from a file list or a
hash, because a version has to survive a project editing its own copies.

    the skill's VERSION      what the framework is now
    the project's            what this project last received
      .docket-version
    CHANGES.md               what the distance between them means

That last file is the part worth having. "You are on 2.1.3, current is 2.2.0"
tells a reader nothing they can act on; the entries between those two numbers
tell them whether to care. `changes_since()` returns exactly those entries, and
both the updater and the dashboard show them.

WHY THE SKILL IS FOUND RATHER THAN ASSUMED
------------------------------------------
These scripts are copied *into* every project that adopts the Docket, so
`__file__` is the project, not the skill. A project asking "is there a newer
framework?" has to locate the skill the same way the updater does — and be
content when there is none, because a project may well be on a machine the
skill was never installed on. `available()` returns `None` there rather than
guessing, and every caller treats that as "cannot say", not "up to date".

FILE METADATA
-------------
    Created        2026-09-19
    Inputs         a project directory; the Docket skill, if it is on this machine
    Returns        version strings, and parsed CHANGES.md entries
    Writes         nothing
"""
import json
import os
import pathlib
import re
import sys

__version__ = "1.0.0"

#: Used when the skill has no `VERSION` file — an install old enough to predate
#: it. It is deliberately the version that introduced the file: anything older
#: cannot be told apart, and claiming a newer one would invent an upgrade.
FALLBACK = "2.2.0"


# ── finding the two ends ────────────────────────────────────────────────────
def find_skill(start=None):
    """The skill directory, or None. Never raises, never guesses.

    A project that adopted the Docket carries its own copy of these scripts, so
    `__file__` is no evidence at all about where the skill is. Look for a
    directory that actually carries the framework — `SKILL.md` beside
    `templates/` — and accept that there may not be one.
    """
    here = pathlib.Path(__file__).resolve().parent.parent
    for c in (os.environ.get("DOCKET_SKILL"), os.environ.get("CODEX_SKILL"),
              start, here,
              pathlib.Path.home() / ".claude" / "skills" / "docket",
              pathlib.Path.home() / "Projects" / "docket",
              pathlib.Path.home() / ".claude" / "skills" / "codex",
              pathlib.Path.home() / "Projects" / "codex"):
        if not c:
            continue
        try:
            c = pathlib.Path(c).expanduser().resolve()
        except OSError:
            continue
        if (c / "SKILL.md").exists() and (c / "templates").is_dir():
            return c
    return None


def _read(path):
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""


# ── the pre-3.0.0 name ──────────────────────────────────────────────────────
#: Until 3.0.0 the framework was called the Codex and stamped `.codex-*` into
#: every project it touched. Those files are the *interface* — the updater reads
#: them to decide what a project has and what it edited — so a rename that only
#: looked forward would orphan every install: the updater would find no
#: `.docket-version`, conclude the project never adopted, and route it to the
#: installer, which is the one path that can overwrite work.
#:
#: So every reader accepts both prefixes, new preferred, and the updater
#: migrates. This is kept for two releases; `check_legacy_names.py` fails while
#: a project claiming >= 3.0.0 still carries one.
PREFIX = ".docket-"
LEGACY_PREFIX = ".codex-"


def project_file(root, suffix):
    """The project's `.docket-<suffix>`, falling back to the legacy name.

    Returns the **new** path when neither exists, so callers can write through
    it without thinking about the migration.

        project_file(proj, "version")  ->  <proj>/.docket-version
                                       or  <proj>/.codex-version   if only that
    """
    root = pathlib.Path(root)
    new = root / (PREFIX + suffix)
    if new.exists():
        return new
    old = root / (LEGACY_PREFIX + suffix)
    return old if old.exists() else new


#: The file that declares a directory to be the framework's own source.
MASTER_FLAG = ".docket-master"
LEGACY_MASTER_FLAG = ".codex-master"


def is_master(root):
    """Is this directory the master Docket — the framework's own source?

    **Asked of a flag file, not inferred from a path.** Path equality against
    the resolved skill directory works until somebody keeps a second checkout,
    or the skill symlink points elsewhere, or a project is opened through a path
    that resolves differently — and then the framework silently treats its own
    source as an ordinary project and offers to update it from itself. A
    declaration cannot be wrong by accident.

    Path equality is kept as a fallback for a master checkout made before the
    flag existed.
    """
    root = pathlib.Path(root).resolve()
    if (root / MASTER_FLAG).exists() or (root / LEGACY_MASTER_FLAG).exists():
        return True
    skill = find_skill()
    return bool(skill and skill == root)


def framework_version(skill=None):
    """What the framework is now, from the skill's `VERSION`."""
    skill = skill or find_skill()
    if skill:
        v = _read(skill / "VERSION").strip().split("\n")[0].strip()
        if v:
            return v
    return FALLBACK


def installed_version(project):
    """What this project last received, from `.docket-version`. None if never."""
    v = _read(project_file(project, "version")).strip().split("\n")[0].strip()
    return v or None


# ── comparing them ──────────────────────────────────────────────────────────
def parse(v):
    """`"2.10.1"` → `(2, 10, 1)`. Non-numeric parts sort as 0 rather than raise.

    A version that cannot be parsed must not take the dashboard down with it —
    `.docket-version` is a file a person can edit, and the only sane failure is
    "looks like the beginning of time", which reads as *behind* and prompts an
    update rather than silently claiming to be current.
    """
    if not v:
        return (0, 0, 0)
    parts = re.findall(r"\d+", str(v))[:3]
    while len(parts) < 3:
        parts.append("0")
    return tuple(int(p) for p in parts)


def behind(installed, current):
    """Is `installed` older than `current`? Unknown counts as behind."""
    return parse(installed) < parse(current)


# ── what the distance means ─────────────────────────────────────────────────
#: `## 2.2.0 — 2026-09-19`, with the date optional so a section can be written
#: before it ships without the parser losing the whole entry.
_HEAD = re.compile(r"^##\s+(\d+\.\d+\.\d+)\s*(?:—|-|–)?\s*(\S+)?\s*$", re.M)

#: **A fenced block is an example, not a release.** `CHANGES.md` documents its
#: own format, and that documentation contains a `## 2.2.0` heading — which the
#: first version of this parser dutifully read as a second release with the
#: instructions as its bullets. Blank the fences before matching anything, and
#: keep the line count identical so nothing else has to care.
_FENCE = re.compile(r"^(```|~~~).*?^\1[^\n]*$", re.M | re.S)


#: **A parsed entry is display data, not markdown.** The changelog is written in
#: markdown because a person reads the file, but everything that consumes these
#: entries — a terminal report, a tag on a web page — shows them as text, and
#: `**what changed**` rendered literally in a browser is markup that escaped.
#: Stripped here, once, rather than in each of the three places that display it.
_EMPH = [(re.compile(r"<!--.*?-->", re.S), ""),   # a marker comment is not prose
         (re.compile(r"\*\*([^*]+)\*\*"), r"\1"),
         (re.compile(r"(?<!\w)\*([^*]+)\*(?!\w)"), r"\1"),
         (re.compile(r"`([^`]+)`"), r"\1"),
         (re.compile(r"\[([^\]]+)\]\([^)]*\)"), r"\1")]


def _plain(text):
    for pat, rep in _EMPH:
        text = pat.sub(rep, text)
    return text.strip()


def _defence(text):
    return _FENCE.sub(lambda m: "\n" * m.group(0).count("\n"), text or "")


def parse_changes(text):
    """`CHANGES.md` → a list of entries, newest first.

    Each is `{version, date, summary, bullets, do}`. The format is the one
    documented at the top of `CHANGES.md`; anything that does not match a
    heading is preamble and is dropped, so the file can explain itself without
    the explanation turning into a release.

    **Continuation follows markdown's rule, not "the previous line was a
    bullet".** A wrapped bullet is indented; an unindented paragraph after one
    is a new paragraph, and a `---` is a rule. Reading every following line as
    more of the last bullet is how a release's bullet list ends up carrying the
    section separator and half the next heading's prose.
    """
    text = _defence(text)
    out = []
    heads = list(_HEAD.finditer(text))
    for i, m in enumerate(heads):
        body = text[m.end(): heads[i + 1].start() if i + 1 < len(heads) else len(text)]
        bullets, do, summary, in_bullet = [], [], [], False
        for raw in body.split("\n"):
            line = raw.strip()
            indented = raw[:1] in (" ", "\t")
            if not line:
                in_bullet = False
                continue
            if line.startswith(("- ", "* ")):
                bullets.append(line[2:].strip())
                in_bullet = True
            elif line.startswith("**Do:**"):
                do.append(line[len("**Do:**"):].strip())
                in_bullet = False
            elif in_bullet and indented:
                bullets[-1] += " " + line
            elif not bullets and not do and not line.startswith(("#", "---", "***")):
                summary.append(line)      # the opening paragraph, however wrapped
            else:
                in_bullet = False
        out.append({"version": m.group(1), "date": m.group(2) or "",
                    "summary": _plain(" ".join(summary)),
                    "bullets": [_plain(b) for b in bullets],
                    "do": [_plain(d) for d in do]})
    out.sort(key=lambda e: parse(e["version"]), reverse=True)
    return out


def changes_text(project=None, skill=None):
    """`CHANGES.md`, preferring the skill's copy over the project's.

    The skill is the live truth; the project's `.docket-changes.md` is the copy
    it was given, and exists so a machine without the skill can still say what
    the project has.
    """
    skill = skill if skill is not None else find_skill()
    if skill:
        t = _read(skill / "CHANGES.md")
        if t:
            return t
    if project:
        return _read(project_file(project, "changes.md"))
    return ""


def changes_since(installed, current, text):
    """The entries a project on `installed` has not been told about.

    Strictly newer than `installed`, no newer than `current` — an entry written
    for a release the skill has not shipped yet is not something to offer.
    When `installed` is None the project has no stamp at all, so everything up
    to `current` is new to it.
    """
    lo, hi = parse(installed), parse(current)
    return [e for e in parse_changes(text) if lo < parse(e["version"]) <= hi]


# ── the one call the dashboard and the check make ───────────────────────────
def status(project=".", skill=None):
    """Everything a caller needs about this project's framework version.

    Never raises. A missing skill, a missing stamp and an unreadable changelog
    are all ordinary states here, and each is reported as itself rather than
    flattened into a number.
    """
    project = pathlib.Path(project).resolve()
    skill = skill if skill is not None else find_skill()
    installed = installed_version(project)
    current = framework_version(skill) if skill else None
    text = changes_text(project, skill)

    #: With no skill on this machine there is nothing to compare against, so the
    #: honest answer is "cannot say" — not "up to date", which would be a claim
    #: made from no evidence.
    master = is_master(project)
    #: The master *is* the framework, so it cannot be behind it. Computing the
    #: comparison anyway and then ignoring the answer is how a page ends up
    #: offering to update the thing that defines the update.
    is_behind = (not master) and bool(current) and behind(installed, current)
    return {
        "installed": installed,
        "current": current,
        "behind": is_behind,
        "master": master,
        "unstamped": installed is None,
        "skill": str(skill) if skill else None,
        "changes": changes_since(installed, current, text) if is_behind else [],
        # **The whole history, each entry marked with whether this project has
        # it.** A releases panel that only lists what is missing answers half the
        # question; "what am I actually running" needs the other half, and the
        # line between them is the interesting part of the list.
        "history": [dict(e, have=master or parse(e["version"]) <= parse(installed))
                    for e in parse_changes(text)[:20]],
    }


def main():
    project = "."
    as_json = False
    for a in sys.argv[1:]:
        if a == "--json":
            as_json = True
        elif not a.startswith("-"):
            project = a
    s = status(project)
    if as_json:
        print(json.dumps(s, indent=2))
        return 0

    print("Docket framework")
    if s["master"]:
        print("  THIS IS THE MASTER DOCKET — the framework's own source.")
    print("  installed here : %s" % (s["installed"] or "unstamped (no .docket-version)"))
    print("  skill has      : %s" % (s["current"] or "no skill found on this machine"))
    if s["behind"]:
        print("  → behind by %d release%s"
              % (len(s["changes"]), "" if len(s["changes"]) == 1 else "s"))
        for e in s["changes"]:
            print("\n  %s — %s" % (e["version"], e["summary"] or e["date"]))
            for b in e["bullets"]:
                print("      · %s" % b)
            for d in e["do"]:
                print("      do: %s" % d)
        print("\n  Update with: ./scripts/docket.sh --update --apply")
    elif s["current"]:
        print("  → current")
    return 0


if __name__ == "__main__":
    sys.exit(main())
