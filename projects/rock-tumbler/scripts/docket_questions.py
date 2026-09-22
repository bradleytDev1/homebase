#!/usr/bin/env python3
"""
docket_questions.py — the open questions, as records rather than as prose.  v1.0.0

Asked for 2026-09-17: *"due to the length, I am losing the ability to keep track
of open questions."* Seventy-eight of them across a document long enough that
scrolling it had become the obstacle.

**This reads; it does not rewrite.** `open_questions.md` stays the source of
truth, with its own rules about what happens when a question is answered — mark
it ✅, remove the ❓ from every code it touched, move the entry across. Those are
cross-file and need judgement, and **a parser that also edits would eventually
get one of them wrong silently.** So an answer lands in `inbox/answers.jsonl`,
append-only, and a person does the docket work having read it.

WHAT IT PARSES, AND WHAT IT GIVES UP ON
---------------------------------------
The header line is conventional rather than enforced:

    ### Q-94 — What credential runs the weekly write when nobody is there?
    **Raised:** 2026-09-17, building the schedule (**OV**) · **Affects:** **FI**,
    **OV**, **SCA**, **PM** · **Status:** open · 🔴 **because the SOW sells...**

So every field here is **optional in the data and optional in the parse**. A
question with no date sorts last by date rather than failing the page; one with
no priority reads as `⚪`. **The document is not made to fit the viewer.**

FILE METADATA
-------------
    Created        2026-09-17
    Inputs         open_questions.md, answered_questions.md
    Returns        question records; answers appended to inbox/answers.jsonl
"""
import datetime
import json
import os
import pathlib
import re

__version__ = "1.1.0"

def _root():
    """The project root — where `open_questions.md` actually lives.

    **Not simply this file's directory.** An adopting project keeps the scripts
    in `scripts/` and the documents at the root, so a module that looked beside
    itself would read `scripts/open_questions.md` and report a Docket with no
    questions in it — the most convincing wrong answer available. Walk up until
    the document is found; `DOCKET_ROOT` overrides for anything unusual.
    """
    env = os.environ.get("DOCKET_ROOT")
    if env:
        return pathlib.Path(env)
    here = pathlib.Path(__file__).resolve().parent
    for cand in (here, *here.parents):
        if (cand / "open_questions.md").exists():
            return cand
        if cand.name == "scripts" and (cand.parent / "open_questions.md").exists():
            return cand.parent
    # Nothing adopted yet: the parent of scripts/ is where it will be.
    return here.parent if here.name == "scripts" else here


HERE = _root()
OPEN_MD = HERE / "open_questions.md"
DONE_MD = HERE / "answered_questions.md"
ANSWERS = HERE / "inbox" / "answers.jsonl"

PRIORITY = {"🔴": ("blocking", 0), "🟡": ("soon", 1), "⚪": ("whenever", 2)}
_HEAD = re.compile(r"^### (Q-\d+)\s*[—-]\s*(.*)$")
_SECTION = re.compile(r"^## \s*([🔴🟡⚪])?\s*(.*)$")


def _strip(md):
    """Markdown emphasis out of a short field. The codes keep their own bold
    elsewhere; in a chip it is noise."""
    return re.sub(r"\*\*|`|~~", "", md or "").strip()


def _parse(path, answered):
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").split("\n")
    heads = [i for i, l in enumerate(lines) if _HEAD.match(l)]
    out = []
    section, section_pri = "", ""
    seen_head = set()
    for i, l in enumerate(lines):
        m = _SECTION.match(l)
        if m and not l.startswith("###"):
            section_pri, section = m.group(1) or "", _strip(m.group(2))
        if i not in heads:
            continue
        h = _HEAD.match(lines[i])
        code, title = h.group(1), _strip(h.group(2))
        end = next((j for j in heads if j > i), len(lines))
        body = "\n".join(lines[i + 1:end]).strip()
        meta = "\n".join(lines[i + 1:i + 6])

        pri = next((g for g in "🔴🟡⚪" if g in meta), section_pri or "⚪")
        raised = (re.search(r"\*\*Raised:\*\*\s*(\d{4}-\d{2}-\d{2})", meta) or [None, None])[1]
        for_who = re.search(r"\*\*For:\*\*\s*([^·\n]+)", meta)
        affects = re.findall(r"\*\*Affects:\*\*(.*?)(?:·|\n\*\*|$)", meta, re.S)
        codes = re.findall(r"\*\*([A-Z]{1,4}\d*)\*\*", affects[0]) if affects else []
        done = answered or "✅" in lines[i]

        # The first real paragraph, for a list that has to fit on a screen.
        gist = ""
        for para in body.split("\n\n"):
            t = _strip(re.sub(r"\n", " ", para))
            if t and not t.startswith(("Raised:", "Status:", "|", "---", ">")):
                gist = t
                break

        if code in seen_head:
            continue
        seen_head.add(code)
        out.append({
            "code": code,
            "n": int(code.split("-")[1]),
            "title": title.replace(" ✅", "").strip(),
            "priority": pri,
            "priority_name": PRIORITY.get(pri, ("whenever", 2))[0],
            "priority_rank": PRIORITY.get(pri, ("whenever", 2))[1],
            "raised": raised,
            "for": _strip(for_who.group(1)) if for_who else "",
            "affects": codes[:8],
            "section": section,
            "answered": done,
            "gist": gist[:400],
            "body": body,
        })
    return out


def questions(include_answered=False):
    """Every question, open first. Newest-looking first is the caller's business."""
    out = _parse(OPEN_MD, False)
    if include_answered:
        out += _parse(DONE_MD, True)
    return out


def one(code):
    for q in questions(include_answered=True):
        if q["code"].lower() == str(code).lower():
            return q
    return None


def answers(code=None):
    """Every answer captured so far, oldest first. **Append-only, so nothing is
    ever overwritten** — a second thought about Q-88 is a second row, and the
    history of a decision is worth more than its latest state."""
    if not ANSWERS.exists():
        return []
    out = []
    for line in ANSWERS.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        if code is None or rec.get("code", "").lower() == str(code).lower():
            out.append(rec)
    return out


def record_answer(code, text, decided=None, author="Bradley"):
    """Append one answer. Returns it.

    `decided` is the owner saying *this settles it* — the difference between an
    answer and a comment, and the thing that tells a reader which questions are
    waiting on the docket rather than on them.
    """
    code = str(code or "").strip().upper()
    if not re.fullmatch(r"Q-\d+", code):
        raise ValueError("not a question code: %r" % code)
    text = (text or "").strip()
    if not text:
        raise ValueError("an empty answer is not an answer")
    rec = {"code": code, "answer": text, "decided": bool(decided),
           "author": author,
           "at": datetime.datetime.now().isoformat(timespec="seconds")}
    ANSWERS.parent.mkdir(parents=True, exist_ok=True)
    with open(ANSWERS, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec) + "\n")
    return rec


def mark_filed(code, note=""):
    """Record that an answer has been written into the Docket.

    **Append-only needs a second record, not an edit.** The inbox never rewrites
    a line — a second thought is a second row — so "this has been dealt with" is
    itself a row rather than a flag flipped on the answer. It also means the
    filing is dated and attributable, and re-answering a filed question puts it
    straight back in the queue because the newer answer has no filing after it.
    """
    code = str(code or "").strip().upper()
    if not re.fullmatch(r"Q-\d+", code):
        raise ValueError("not a question code: %r" % code)
    rec = {"op": "filed", "code": code, "note": (note or "")[:300],
           "at": datetime.datetime.now().isoformat(timespec="seconds")}
    ANSWERS.parent.mkdir(parents=True, exist_ok=True)
    with open(ANSWERS, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec) + "\n")
    return rec


def pending():
    """Answers recorded but not yet written into the Docket, oldest first.

    **This is the thing nobody was watching.** Bradley answered three questions
    in the console and the only way it reached the work was him saying so — so
    the inbox could fill up silently while the Docket said the questions were
    still open. An answer counts as pending until a `filed` row for that code
    arrives *after* it.
    """
    rows = []
    for line in (ANSWERS.read_text(encoding="utf-8").splitlines()
                 if ANSWERS.exists() else []):
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except ValueError:
            continue
    filed = {}
    for r in rows:
        if r.get("op") == "filed":
            c = r.get("code", "")
            filed[c] = max(filed.get(c, ""), r.get("at", ""))
    out = [r for r in rows
           if r.get("op") != "filed"
           and r.get("at", "") > filed.get(r.get("code", ""), "")]
    return sorted(out, key=lambda r: r.get("at", ""))


def summary():
    qs = questions()
    ans = {a["code"] for a in answers()}
    return {
        "open": len(qs),
        "blocking": sum(1 for q in qs if q["priority"] == "🔴"),
        "soon": sum(1 for q in qs if q["priority"] == "🟡"),
        "whenever": sum(1 for q in qs if q["priority"] == "⚪"),
        "answered_waiting": sum(1 for q in qs if q["code"] in ans),
        "for_others": sum(1 for q in qs if q["for"]),
        "answers_pending": len(pending()),
    }


if __name__ == "__main__":
    import sys
    s = summary()
    print("open %(open)d — %(blocking)d blocking, %(soon)d soon, %(whenever)d whenever; "
          "%(answered_waiting)d answered and waiting on the docket; "
          "%(for_others)d are somebody else's" % s)
    if "-v" in sys.argv:
        for q in sorted(questions(), key=lambda q: (q["priority_rank"], -q["n"])):
            print("  %s %-6s %-10s %s" % (q["priority"], q["code"],
                                          q["raised"] or "—", q["title"][:66]))
