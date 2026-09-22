#!/usr/bin/env python3
"""Convert a project's lettered leaves to numbered ones. Opt-in, and refusable.

    python3 scripts/docket-renumber.py              # what would change
    python3 scripts/docket-renumber.py --apply
    python3 scripts/docket-renumber.py --apply --force   # against its advice

**3.6.0 numbers the leaf of a code — `CA1` rather than `CAA` — and existing
projects are deliberately left alone.** That default is right for the large
ones: the risk of a conversion is not the idea, it is the number of references
that have to move together, and the depth of the tree they sit in. A project
with three hundred codes nested five deep is where a rewrite goes quietly
wrong. A project with forty, three deep, is not.

So this exists, it is opt-in, and it declines the jobs it should decline.

THE RULE THAT MAKES IT SAFE
---------------------------
**Position, not order.** `CAA` becomes `CA1`, `CAB` becomes `CA2`, `CAC`
becomes `CA3` — by the letter's place in the alphabet, never by counting the
entries that happen to exist.

That distinction is the whole design. Counting would close the gaps, and the
gaps are load-bearing: a retired feature keeps its code, so `CAB` missing
between `CAA` and `CAC` *means something*. Renumbering to `CA1`, `CA2` would
silently reassign `CA2` from a retired feature to a live one, and every
sentence written about `CAB` in the last year would now point at the wrong
thing. Positional mapping keeps the hole exactly where it was.

It is also reversible, which counting is not.

WHAT IT REFUSES
---------------
    a blind checker     the project's own `check_codes.py` must be able to read
                        a numbered code before any are written. A customised
                        copy is left alone by the updater — quite correctly —
                        and an old one matches `[A-Z]{1,5}` only, so converting
                        first would rename every leaf into something its own
                        gate cannot see. **This is the failure the converter
                        would itself cause**, which is why it is checked first
    depth 4 or more     the new shape has three levels; there is nowhere to put
                        a fourth, and inventing one is not a conversion
    unresolved refs     if the check does not pass before, it cannot be trusted
                        to say whether the conversion broke something

Both are overridable with `--force`, and both are refusals you should respect.

    Reads       features_and_functions.md and every *.md in the project
    Writes      every *.md, .docket, and a backup beside the project first
    Verifies    the code count is unchanged and every reference still resolves
"""
import argparse
import pathlib
import re
import shutil
import subprocess
import sys
import tarfile
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent
CODE_IN_TEXT = re.compile(r"(?<![A-Za-z0-9])([A-Z]{3,5})(?![A-Za-z0-9])")


def letters_to_number(tail):
    """`"A"` → 1, `"B"` → 2 … by position, so a gap stays a gap.

    **Returns None for anything that is not a single A–Z.** Without that guard
    a leaf that is already a digit sails through: `"1"` gives `ord("1") -
    ord("A") + 1`, which is **-15**, and a second run would rewrite `EA1` to
    `EA-15`. Converting twice has to be a no-op, not a corruption. (LE-20)
    """
    if len(tail) != 1 or not ("A" <= tail <= "Z"):
        return None
    return ord(tail) - ord("A") + 1


def defined_codes():
    """Every code this project defines, from the feature list and chapters.

    **Counts both shapes, and that is not a detail.** The first version matched
    `[A-Z]{1,5}` only — the shape being converted *away from* — so after a
    correct conversion it counted 61 where it had counted 74, declared the
    missing 13 a catastrophe and printed the command to restore a good result.
    A converter's verifier has to know the thing it converts to. (LE-19)
    """
    out = set()
    files = [ROOT / "features_and_functions.md"] + sorted((ROOT / "chapters").glob("*.md")) \
        if (ROOT / "chapters").is_dir() else [ROOT / "features_and_functions.md"]
    for f in files:
        if not f.exists():
            continue
        for line in f.read_text(errors="ignore").splitlines():
            for m in re.finditer(r"[✅\U0001F528⬜\U0001F4A1❌]️?\s*\*\*~*([A-Z]{1,5}[0-9]{0,3})~*\*\*", line):
                out.add(m.group(1))
        for m in re.finditer(r"^#{2,4}\s+~*([A-Z]{1,5}[0-9]{0,3})~*\s+[—-]", f.read_text(errors="ignore"), re.M):
            out.add(m.group(1))
    return out


def plan(codes):
    """`{old: new}` for every convertible code, plus what blocks the rest."""
    mapping, blocked = {}, []
    for c in sorted(codes):
        if any(ch.isdigit() for ch in c):
            continue                      # already numbered; nothing to do
        if len(c) <= 2:
            continue                      # domains and areas keep their letters
        if len(c) > 3:
            blocked.append(c)             # nowhere to put a fourth level
            continue
        n = letters_to_number(c[2])
        if n is None:
            blocked.append(c)
            continue
        mapping[c] = "%s%d" % (c[:2], n)
    return mapping, blocked


def occurrences(mapping):
    """Where each old code appears, across every markdown file."""
    files = sorted(ROOT.glob("*.md")) + sorted((ROOT / "chapters").glob("*.md"))
    hits = {}
    for f in files:
        text = f.read_text(errors="ignore")
        n = sum(len(re.findall(r"(?<![A-Za-z0-9])%s(?![A-Za-z0-9])" % old, text))
                for old in mapping)
        if n:
            hits[f] = n
    return hits


def rewrite(mapping, apply_):
    files = sorted(ROOT.glob("*.md")) + sorted((ROOT / "chapters").glob("*.md"))
    changed = 0
    # Longest first: with three-letter codes only this cannot collide, but the
    # habit costs nothing and the next shape change will not be so tidy.
    ordered = sorted(mapping, key=len, reverse=True)
    for f in files:
        text = old = f.read_text(errors="ignore")
        for c in ordered:
            text = re.sub(r"(?<![A-Za-z0-9])%s(?![A-Za-z0-9])" % c, mapping[c], text)
        if text != old:
            changed += 1
            if apply_:
                f.write_text(text, encoding="utf-8")
    return changed


def backup():
    stamp = time.strftime("%Y-%m-%d-%H%M%S")
    out = ROOT.parent / ("%s-before-renumber-%s.tar.gz" % (ROOT.name, stamp))
    with tarfile.open(out, "w:gz") as tar:
        for f in sorted(ROOT.glob("*.md")) + sorted((ROOT / "chapters").glob("*.md")):
            tar.add(f, arcname=str(f.relative_to(ROOT)))
    return out


def check():
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "check_codes.py")],
                       capture_output=True, text=True)
    return r.returncode, (r.stdout + r.stderr).strip()


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--project", default=None,
                    help="the project to convert (default: the one this script sits in)")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--force", action="store_true",
                    help="convert despite a refusal. Read the refusal first")
    a = ap.parse_args()
    if a.project:
        global ROOT
        ROOT = pathlib.Path(a.project).resolve()

    if not (ROOT / "features_and_functions.md").exists():
        sys.exit("no features_and_functions.md — this is not a Docket project.")

    # **First, because it is the one this tool would cause.** A project whose
    # checker still matches `[A-Z]{1,5}` will not see `EA1` as a code at all.
    cc = ROOT / "scripts" / "check_codes.py"
    if cc.exists() and "[0-9]{0,3}" not in cc.read_text(errors="ignore"):
        print("Project : %s\n" % ROOT)
        print("REFUSING — this project's scripts/check_codes.py cannot read a")
        print("numbered code. It matches [A-Z]{1,5} only, so the moment a leaf")
        print("becomes EA1 its own gate stops seeing it, and every reference to")
        print("it reads as undefined.\n")
        print("Usually this just means the project has not had the 3.6.0 update:")
        print("\n    ./scripts/docket.sh --update --apply\n")
        print("If that leaves the file alone, the project has customised it —")
        print("correctly left alone. Widen its four code patterns by hand to")
        print("[A-Z]{1,5}[0-9]{0,3}, keeping whatever the project added, and")
        print("re-run. The framework's copy to compare against:")
        print("\n    diff %s \\\n         %s" % (
            pathlib.Path(__file__).resolve().parent / "check_codes.py", cc))
        if not a.force:
            return 1
        print("\n--force given. This will leave the project's check failing.\n")

    codes = defined_codes()
    mapping, blocked = plan(codes)

    print("Project : %s" % ROOT)
    print("Codes   : %d defined, %d convertible, %d too deep\n"
          % (len(codes), len(mapping), len(blocked)))

    if not mapping and not blocked:
        print("Nothing to convert — this project has no lettered leaves.")
        return 0

    if blocked:
        print("REFUSING — %d code(s) are four or more levels deep, and the new" % len(blocked))
        print("shape has three. Converting these would mean inventing a level:")
        for c in sorted(blocked)[:10]:
            print("   %s" % c)
        if len(blocked) > 10:
            print("   … and %d more" % (len(blocked) - 10))
        print("\nThis is the case the default is for. A project this deep is where")
        print("a rewrite goes quietly wrong, and nothing here is broken as it is.")
        if not a.force:
            return 1
        print("\n--force given. Continuing, and converting only the three-deep codes.\n")

    rc, out = check()
    if rc != 0:
        print("REFUSING — the code check does not pass before the conversion:\n")
        print(out)
        print("\nIf it fails now it cannot tell you whether the conversion broke")
        print("anything. Fix that first.")
        if not a.force:
            return 1

    hits = occurrences(mapping)
    total = sum(hits.values())
    print("%d code(s) → numbered leaves, %d occurrence(s) across %d file(s):\n"
          % (len(mapping), total, len(hits)))
    for f, n in sorted(hits.items(), key=lambda kv: -kv[1])[:12]:
        print("   %-34s %d" % (f.name, n))
    print()
    sample = sorted(mapping.items())[:6]
    print("   " + "   ".join("%s→%s" % (a_, b) for a_, b in sample)
          + ("   …" if len(mapping) > 6 else ""))
    gaps = [c for c in mapping if letters_to_number(c[2]) and
            "%s%s" % (c[:2], chr(ord(c[2]) - 1)) not in mapping and c[2] != "A"]
    if gaps:
        print("\n   %d code(s) sit after a gap; the gap is preserved by position —" % len(gaps))
        print("   %s keeps its number rather than closing up." % sorted(gaps)[0])

    if not a.apply:
        print("\nNothing was changed. Re-run with --apply.")
        return 0

    b = backup()
    print("\nBacked up every document to %s" % b.name)
    changed = rewrite(mapping, True)
    dk = ROOT / ".docket"
    if dk.exists():
        dk.write_text(dk.read_text().replace("**numbering: letters**",
                                             "**numbering: numbers**"), encoding="utf-8")
    print("Rewrote %d file(s)." % changed)

    rc, out = check()
    print("\n" + out)
    if rc != 0:
        print("\nThe check FAILED after the conversion. Restore with:")
        print("   tar -xzf %s -C %s" % (b, ROOT))
        return 1
    after = defined_codes()
    if len(after) != len(codes):
        print("\nCode count moved from %d to %d — that should not happen."
              % (len(codes), len(after)))
        print("   tar -xzf %s -C %s" % (b, ROOT))
        return 1
    print("\nSame %d codes, every reference resolves." % len(after))
    return 0


if __name__ == "__main__":
    sys.exit(main())
