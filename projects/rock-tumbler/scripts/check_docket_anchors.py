#!/usr/bin/env python3
"""Every link in the Docket viewer's rail must land somewhere.

**LE-76.** The rail and the page were slugging different strings. The rail slugs
the markdown heading; the page slugged the *rendered* heading, where emphasis has
already become `<strong>`. `clean()` strips markdown asterisks, not HTML tags, so
a heading like

    ### ZC — Retail geography ❓**Q-01**

became `id="zc-retail-geography-strongq-01strong"` while the rail pointed at
`#…-zc-retail-geography-q-01`. Clicking it did nothing.

**Only headings containing markup broke**, which is why it looked arbitrary —
Bradley: *"I thought at first it was only those that have a question… But it's
not consistent."* Every question-carrying heading has a bolded `Q-nn` in it, so
the pattern was real but the cause was not the question.

A dead in-page link reports nothing: no error, no console message, the page
simply does not move. **That is exactly the class of fault a gate is for.**

    python3 scripts/check_docket_anchors.py
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGE = os.path.join(ROOT, "docs", "docket.html")


def main():
    if not os.path.exists(PAGE):
        print("    SKIP  docs/docket.html not built — run scripts/docket.sh --build")
        return 0
    html = open(PAGE, encoding="utf-8").read()

    # Both quote styles: the shell writes id='top' and the renderer writes id="…".
    ids = set(re.findall(r"""\bid=["']([^"']+)["']""", html))
    # Only the rail's links; the prose is full of external hrefs.
    nav = re.search(r"<nav[^>]*>(.*?)</nav>", html, re.S)
    if not nav:
        print("    no <nav> in the built page")
        return 1
    hrefs = re.findall(r'href="#([^"]+)"', nav.group(1))

    dead = sorted({h for h in hrefs if h not in ids})
    print("==> Every rail link reaches a heading (LE-76)")
    if dead:
        for h in dead[:12]:
            print("    DEAD  #%s" % h)
        if len(dead) > 12:
            print("    ...and %d more" % (len(dead) - 12))
        print("    %d of %d rail links go nowhere." % (len(dead), len(hrefs)))
        print("           A dead in-page link is silent: no error, the page just")
        print("           does not move. Check slug() is fed the same string on")
        print("           both sides — see LE-76.")
        return 1
    print("    %d rail link(s), every one lands on a heading" % len(hrefs))
    return 0


if __name__ == "__main__":
    sys.exit(main())
