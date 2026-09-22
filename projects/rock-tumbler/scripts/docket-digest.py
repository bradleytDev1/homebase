#!/usr/bin/env python3
"""
What this project is waiting on, written as a message to the person who can
answer it.

    python3 scripts/docket-digest.py              # print it
    python3 scripts/docket-digest.py --tier soon  # include "needed soon" too

**It prints. It does not send.** Delivery is a separate decision with
credentials attached; this is the part that has to be right first, and it is
the part the Docket can do that a generic reminder cannot: **it knows what each
question is blocking.** Every entry records `**Affects:**`, and the feature list
says what those codes are, so the message can say *waiting on this in order to
proceed with that* rather than "you have 6 open questions".

The tone is deliberate. The reader is the person who owns the decisions, not a
maintainer: no codes without their meaning, no jargon, and the working
assumption stated plainly so that saying nothing is a visible choice rather
than an oversight.
"""

import argparse
import datetime
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
TIERS = {"blocking": "🔴", "soon": "🟡", "whenever": "⚪"}


def project_name():
    r = ROOT / "README.md"
    if r.exists():
        for line in r.read_text().splitlines():
            if line.startswith("# "):
                return line[2:].strip()
    return ROOT.name


def feature_titles():
    """code -> the one-line description, so a code can be named in English."""
    f = ROOT / "features_and_functions.md"
    out = {}
    if not f.exists():
        return out
    for line in f.read_text().splitlines():
        # Strip the question markers BEFORE matching, not after. "❓**Q-07**"
        # contains a hyphen, and the title pattern splits on the first dash it
        # sees — so the description came out as "07 — The readiness signal".
        # They are also noise in a message to the person being asked.
        line = re.sub(r"❓\s*\*{0,2}Q-\d+\*{0,2}", "", line)
        m = re.match(r"\s*-\s*[^\s]*\s*\*\*([A-Z]{1,4}\d*)\*\*[^—-]*[—-]\s*(.+)", line)
        if m:
            text = re.sub(r"[`*]", "", m.group(2))
            out.setdefault(m.group(1), " ".join(text.split()).rstrip(".")[:90])
    return out


def _tidy(text, limit=200):
    """One readable sentence. Truncating mid-word reads as a broken tool."""
    t = " ".join(re.sub(r"[`*]", "", text).split())
    if len(t) <= limit:
        return t
    cut = t[:limit]
    for stop in (". ", "; ", ", "):
        i = cut.rfind(stop)
        if i > limit * 0.6:
            return cut[:i + 1].rstrip(",;")
    return cut[:cut.rfind(" ")] + "\u2026"


def questions():
    f = ROOT / "open_questions.md"
    if not f.exists():
        return []
    text = f.read_text()
    tier_of, tier = {}, "whenever"
    for line in text.splitlines():
        if line.startswith("## "):
            for name, glyph in TIERS.items():
                if glyph in line:
                    tier = name
        m = re.match(r"### (Q-\d+)", line)
        if m:
            tier_of[m.group(1)] = tier

    out = []
    for b in re.split(r"^(?=### Q-\d+)", text, flags=re.M):
        m = re.match(r"### (Q-\d+)\s*(.*)", b)
        if not m or "✅" in m.group(2):
            continue
        code = m.group(1)
        raised = re.search(r"\*\*Raised:\*\*\s*(\d{4}-\d{2}-\d{2})", b)
        affects = re.search(r"\*\*Affects:\*\*\s*([^\n·]*)", b)
        assume = re.search(r"\*\*Working assumption:\*\*\s*(.+?)(?:\n\n|\Z)", b, re.S)
        out.append({
            "code": code,
            "title": re.sub(r"[`*]", "", m.group(2)).strip(" —-"),
            "tier": tier_of.get(code, "whenever"),
            "raised": raised.group(1) if raised else None,
            # Drop Q-nn first: otherwise "Q-07" yields the code "07", which
            # then matches whatever feature happens to be numbered that way.
            "affects": re.findall(
                r"\b([A-Z]{1,4}\d*)\b",
                re.sub(r"\bQ-\d+\b", "", re.sub(r"[`*]", "", affects.group(1)))
            ) if affects else [],
            "assumption": _tidy(assume.group(1)) if assume else None,
        })
    return out


def render(qs, titles, today):
    name = project_name()
    lines = [f"Subject: {name} — waiting on you ({len(qs)} decision"
             f"{'' if len(qs) == 1 else 's'})", ""]
    lines.append("Friendly reminder. These are the decisions this project is "
                 "waiting on. Each one")
    lines.append("has a working assumption in force, so nothing has stopped — "
                 "but the assumption is")
    lines.append("what happens if you never answer, and a sentence from you "
                 "replaces it.")
    lines.append("")
    for q in qs:
        age = ""
        if q["raised"]:
            d = (today - datetime.date.fromisoformat(q["raised"])).days
            age = f"  ({d} day{'' if d == 1 else 's'} waiting)" if d else "  (today)"
        lines.append(f"• {q['title']}{age}")
        named = [f"{titles[c]}" for c in q["affects"] if c in titles]
        if named:
            lines.append(f"    Needed in order to proceed with: {named[0]}")
            for extra in named[1:2]:
                lines.append(f"    ...and: {extra}")
        if q["assumption"]:
            lines.append(f"    If you say nothing: {q['assumption']}")
        lines.append("")
    lines.append("Answer any of them in a sentence, however you like. "
                 "They are written up at")
    lines.append(f"{ROOT / 'open_questions.md'}, or in the questions console "
                 f"when it is running.")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tier", default="blocking",
                    choices=["blocking", "soon", "all"],
                    help="blocking only (default), plus needed-soon, or everything")
    a = ap.parse_args()

    titles = feature_titles()
    qs = questions()
    wanted = {"blocking": {"blocking"},
              "soon": {"blocking", "soon"},
              "all": {"blocking", "soon", "whenever"}}[a.tier]
    qs = [q for q in qs if q["tier"] in wanted]
    qs.sort(key=lambda q: (q["raised"] or "9999"))

    if not qs:
        print(f"    nothing at the '{a.tier}' level is waiting — no reminder to send")
        return 0
    print(render(qs, titles, datetime.date.today()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
