#!/usr/bin/env python3
"""
check_console.py — the console's surface list says what it means.

`.docket-surfaces.json` is optional. When it exists it decides what the front
door shows, and **every way it can be wrong is silent**: a trailing comma makes
the whole file unreadable and the console quietly falls back to three built-in
cards; a surface missing `path` is skipped without a word; a `path` that is not
rooted is probed against the wrong URL and reports "not running" forever. None
of those raise, so none of them announce themselves — which is exactly the
shape of fault this project gates rather than hopes to notice.

FILE METADATA
-------------
    Created        2026-09-17
    Reads          .docket-surfaces.json
    Returns        0 when absent or sound, 1 with the reason
"""
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
#: The hues `dashboard/theme.html` defines a tone for. A surface given a tone
#: that has no tokens renders with no ground at all and no error anywhere, which
#: is why this is a gate rather than a convention.
#:
#: `amber` is kept as an alias for `yellow`: it was the name before the tone
#: system grew to ten hues, and a config written against the old set should not
#: start failing. See `console_tone()` in the server for the mapping.
TONES = {"blue", "green", "cyan", "purple", "indigo",
         "red", "orange", "yellow", "pink", "gray", "amber"}


def main():
    f = ROOT / ".docket-surfaces.json"
    if not f.exists() and (ROOT / ".codex-surfaces.json").exists():
        f = ROOT / ".codex-surfaces.json"          # pre-3.0.0, still honoured
    if not f.exists():
        print("    no .docket-surfaces.json — the console shows its built-in cards")
        return 0

    try:
        cfg = json.loads(f.read_text(encoding="utf-8"))
    except ValueError as exc:
        print("    %s is not valid JSON: %s" % (f.name, exc))
        return 1
    if not isinstance(cfg, dict):
        print("    %s must hold an object" % f.name)
        return 1

    bad = []
    surfaces = cfg.get("surfaces") or []
    if not isinstance(surfaces, list):
        print("    'surfaces' must be a list")
        return 1

    for i, s in enumerate(surfaces):
        at = "surfaces[%d]" % i
        if not isinstance(s, dict):
            bad.append("%s is not an object" % at)
            continue
        label = s.get("label")
        path = s.get("path")
        at = "%s (%s)" % (at, label or "unnamed")
        if not label:
            bad.append("%s has no label" % at)
        if not path:
            bad.append("%s has no path" % at)
        elif not str(path).startswith("/"):
            bad.append("%s path %r must start with '/' — it is joined to a "
                       "server base, so a bare word never resolves" % (at, path))
        tone = s.get("tone")
        if tone and tone not in TONES:
            bad.append("%s tone %r is not one of: %s"
                       % (at, tone, ", ".join(sorted(TONES))))

    for key in ("live",):
        v = cfg.get(key)
        if v and not str(v).startswith("http"):
            bad.append("'%s' must be a full URL, got %r" % (key, v))
    also = cfg.get("also_local") or []
    if not isinstance(also, list):
        bad.append("'also_local' must be a list of base URLs")
    else:
        for b in also:
            if not str(b).startswith("http"):
                bad.append("also_local %r must be a full URL" % b)

    if bad:
        for b in bad:
            print("    %s" % b)
        return 1

    # **"Resolvable" was a lie, and a quiet one.** This gate reads the JSON:
    # a label, a path that starts with a slash, a tone the server knows. It has
    # never fetched anything, so it cannot say a surface resolves — and while it
    # said so, all three of the master's surfaces pointed at routes that did not
    # exist. The console probes them at request time and shows a start command
    # instead of a dead link, which is the right runtime behaviour; the wrong
    # thing was a check claiming more than it checked. (LE-14)
    print("    %d surface%s declared, all well-formed"
          % (len(surfaces), "" if len(surfaces) == 1 else "s"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
