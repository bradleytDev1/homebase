#!/usr/bin/env python3
"""Answers recorded in the console but not yet written into the Docket.

Asked 2026-09-17: *"how will you know to look for answers? Is it something we
should add to the docket updates? Some other mechanism?"*

**It was not a mechanism — the owner mentioned it.** Three questions were answered
at `/questions`, and the only thing that moved the work was him saying so. The
inbox could have filled up for a week while `open_questions.md` went on saying
those questions were unsettled, and **nothing anywhere would have disagreed**.

So it becomes the thing that already runs. `check-docs.sh` is the Docket check,
the working agreement says to run it before finishing, and this makes an unfiled
answer **fail it** — the same way a stale ❓ marker does, and for the same
reason: the inbox and the Docket are claiming different things about the same
question.

**Filing is a row, not a flag.** The inbox is append-only, so
`docket_questions.mark_filed()` appends a `filed` record. Re-answering a question
that was already filed puts it straight back in this list, because the newer
answer has no filing after it.

    python3 scripts/check_answer_inbox.py
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))


def main():
    try:
        import docket_questions as rq
    except Exception as exc:
        print("    SKIP  rain_questions unavailable (%s)" % exc)
        return 0

    waiting = rq.pending()
    if not waiting:
        print("    no answers waiting to be filed")
        return 0

    print("    %d answer(s) recorded at /questions and NOT yet in the Docket:"
          % len(waiting))
    for a in waiting:
        first = (a.get("answer") or "").strip().split("\n")[0]
        print("      %-7s %s  %s%s"
              % (a.get("code"), a.get("at", "")[:16],
                 "[settles it] " if a.get("decided") else "",
                 first[:66] + ("…" if len(first) > 66 else "")))
    print()
    print("           File each one: mark it ✅, record the decision in its")
    print("           proper home, clear the ❓ markers, make the edit the answer")
    print("           implies, move the entry to answered_questions.md — then")
    print("           docket_questions.mark_filed('Q-nn', 'what you did').")
    return 1


if __name__ == "__main__":
    sys.exit(main())
