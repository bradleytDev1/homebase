#!/usr/bin/env python3
"""Build the Docket viewer — a single self-contained HTML page over the
planning documents.

Reads the Docket (Gameplan KY), extracts its headings, descriptions and the
permanent section codes, and writes docs/docket.html.

Run it with scripts/docket.sh, which builds and opens it.
"""
import html
import os
import re
import sys
from datetime import date, datetime
from pathlib import Path

try:
    import markdown
except ImportError:                                            # pragma: no cover
    # **One dependency, and it should fail in a sentence.** This is the only
    # third-party import in the framework; everything else is standard library.
    # A stranger's first command should not be a traceback.
    raise SystemExit(
        "The Docket viewer needs Python-Markdown, the one third-party package\n"
        "this framework uses. Install it with:\n"
        "\n"
        "    python3 -m pip install markdown\n"
        "\n"
        "Everything else here is standard library, and the checks run without it.")

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "docket.html"


def project_name() -> str:
    """The project's own name, never a hardcoded one.

    A build script that ships another project's name puts it at the top of
    every page and in the browser tab — the first thing a reader sees is the
    wrong project. Read it from the documents instead:

      1. README.md's first `# ` heading, up to the first em dash or parenthesis
      2. the `# {NAME} — ...` heading of any Docket document
      3. the directory name

    **"The Docket" is rejected as a name — except in the one project where it is
    the name.** Every template ships headed `# The Docket — …`, so a project that
    installed and never adapted them would otherwise be titled after the
    framework on every page. The master is the exception: it really is called
    that, and `.docket-master` is how it says so. Without this the framework's own
    viewer was headed `docket`, after the directory.

    Nothing here is allowed to fail: a missing README must not stop the build.
    """
    import re as _re
    try:
        import docket_version
        master = docket_version.is_master(ROOT)
    except Exception:
        master = ((ROOT / ".docket-master").exists()
                  or (ROOT / ".codex-master").exists())

    for name in ("README.md", "Gameplan.md", "features_and_functions.md"):
        f = ROOT / name
        if not f.exists():
            continue
        m = _re.search(r"^#\s+(.+?)\s*$", f.read_text(encoding="utf-8"), _re.M)
        if m:
            title = _re.split(r"\s+[—–-]\s+|\s*\(", m.group(1))[0].strip()
            if title and (master or title.lower() != "the docket"):
                return title
    return ROOT.name


PROJECT = project_name()
STAMP = datetime.now().strftime("%Y-%m-%d %H:%M")

# ── The Docket, in reading order ──────────────────────────────────────────────
# `blurb` is the one-line answer to "why would I open this one?"
DOCS = [
    ("Gameplan.md", "Why", "gameplan",
     "Philosophy, intention and the standing decisions (K) that should not be "
     "relitigated without a reason. Bradley's document — Claude drafts into it, "
     "never over it."),
    ("features_and_functions.md", "What", "features",
     "The canonical list of everything the app does or might do, and the "
     "definition of the code system every other document borrows. If this "
     "disagrees with another document, this one wins."),
    ("critical_path.md", "What order", "path",
     "What can be started today and what is waiting on what. Derived from the "
     "feature list, never authoritative over it."),
    ("open_questions.md", "Unsettled", "questions",
     "Everything waiting on Bradley, each with a working assumption so nothing "
     "blocks while it waits. Answered entries stay, with the answer."),
    ("development_plan.md", "How", "devplan",
     "The technical record — architecture, file map, and the reasoning behind "
     "specific implementation choices."),
    # **Whichever name this project's changelog has.** `KA` says a file that
    # already does the job keeps its name, and a project that kept its history
    # in `CHANGES.md` should not have the viewer report its changelog missing.
    ("CHANGELOG.md" if (ROOT / "CHANGELOG.md").exists() else "CHANGES.md",
     "When", "changelog",
     "What shipped, in which build, and what it fixed."),
    ("lessons_learned.md", "What broke", "lessons",
     "Traps already hit (LE-nn), and how each one hid. The ones worth reading "
     "twice produced *plausible wrong output* rather than a crash."),
    ("answered_questions.md", "Settled", "answered",
     "Questions asked and answered, with the answer and a pointer to where the "
     "decision was recorded. Nothing is ever deleted."),
]

# Chapters are discovered, never hardcoded — a build script must not ship one
# project's chapter filename to every other project. Anything in chapters/ is
# picked up automatically, and a chapter adopted in place elsewhere is declared
# in .docket-chapters (one path per line, blank lines and # comments ignored).
def _chapters():
    out = []
    for f in sorted((ROOT / "chapters").glob("*.md")):
        if f.name.lower() == "readme.md":
            continue
        out.append(f"chapters/{f.name}")
    listed = ROOT / ".docket-chapters"
    if not listed.exists() and (ROOT / ".codex-chapters").exists():
        listed = ROOT / ".codex-chapters"          # pre-3.0.0, still honoured
    if listed.exists():
        for line in listed.read_text(encoding="utf-8").splitlines():
            line = line.split("#", 1)[0].strip()
            if line and (ROOT / line).exists() and line not in out:
                out.append(line)
    return out


def _chapter_title(rel):
    """A chapter's own `# ` heading, minus the project name.

    **Twenty chapters all labelled "Long form" is not a label.** The rail showed
    the same kicker on every one, so the filename was doing all the work and
    `F-google-ads-api.md` and `F-meta-marketing-api.md` looked like the same
    thing. Each chapter already titles itself in its first heading; use it.
    """
    # `read()` and `clean()` are defined below this point, so the file is read
    # directly rather than moving two helpers to satisfy one caller.
    path = ROOT / rel
    if not path.exists():
        return Path(rel).stem
    for line in path.read_text(encoding="utf-8").split("\n")[:12]:
        if line.startswith("# "):
            t = re.sub(r"\*\*|`|~~", "", line[2:]).strip()
            # Chapters head themselves three ways — "A — Affordances",
            # "Chapter M — The demand thesis…", and occasionally just a title.
            # Drop the code prefix, then keep the first clause of what is left.
            t = re.sub(r"^(?:Chapter\s+)?[A-Z]{1,3}\s*[—–-]\s*", "", t)
            for sep in (": ", " — ", " – "):
                if sep in t:
                    t = t.split(sep)[0]
                    break
            t = t.strip().rstrip(",")
            if len(t) > 46:
                t = t[:44].rsplit(" ", 1)[0] + "…"
            return t or Path(rel).stem
    return Path(rel).stem


for _rel in _chapters():
    _stem = Path(_rel).stem
    DOCS.append((_rel, _chapter_title(_rel), f"ch-{_stem.lower()}",
                 "A chapter: the long form, for a topic too large for a list "
                 "entry. Chapters are derived, never authoritative."))

RATIONALE = """
The reasoning behind the code is worth more than the code, and it evaporates
when a session ends. The Docket exists so that a decision made in conversation —
in an answer, an aside, a correction, a choice between options — is written down
in the same turn it is made, in the document that owns it.

It is built to be read by someone arriving cold: a person, or a fresh Claude
session with no memory of how any of this came to be.
"""

PRACTICES = [
    ("Codes are permanent",
     "A letter is a domain; each added letter is a level down: <code>C</code> a "
     "domain, <code>CA</code> an area within it, <code>CAA</code> a feature, "
     "<code>CAAA</code> a detail. A retired feature keeps its code and a new sibling never "
     "renumbers its neighbours, so a reference written a year ago still resolves. "
     "When a sequence is exhausted it rolls over — <code>KZ</code> is followed by "
     "<code>KAA</code>, not by a renumbering."),
    ("One vocabulary across every document",
     "The same code means the same thing in all eight documents. That is what "
     "lets a topic be followed from the decision that created it, through the "
     "feature entry, the technical plan, the build it shipped in, and the lesson "
     "learned when it broke."),
    ("Supersede, never delete",
     "A decision that changes keeps its row, struck through, pointing at the one "
     "that replaced it and saying what changed. <b>KR</b> and <b>KAA</b> are the "
     "worked example: the superseded row is where the reasoning lives, and "
     "deleting it would erase the most useful thing in the file."),
    ("Record the reasoning, not just the outcome",
     "&ldquo;Fluency&rdquo; alone is useless. &ldquo;Fluency, because it names "
     "the reader rather than implying the app is hard&rdquo; is the thing worth "
     "keeping. Use Bradley's own words where the phrasing itself is the decision, "
     "and date everything."),
    ("Nothing blocks on an unanswered question",
     "Every open question carries a working assumption, so work proceeds while it "
     "waits. A question is only genuinely blocking when proceeding on <em>any</em> "
     "assumption would waste the work."),
    ("The cross-reference runs both ways, and is enforced",
     "A question names every code it affects, and each of those codes carries a "
     "❓ marker until it is settled. The invariant — a marker exists if and only "
     "if the matching question is unanswered — is checked by "
     "<code>scripts/check-docs.sh</code>, the Docket check, rather than by "
     "remembering."),
    ("Separate what is authoritative from what is derived",
     "The feature list says what exists; the critical path says what order to do "
     "it in; a chapter gathers reasoning in one place. Only the first is "
     "authoritative. When two disagree, the feature list wins — which is stated "
     "in both of the others."),
    ("Mark inference as inference",
     "A decision Bradley stated and a conclusion Claude drew are different kinds "
     "of thing, and the difference has to survive the session that made it. If it "
     "is unclear whether something was decided, it is filed as a question with a "
     "working assumption, never recorded as a decision."),
]

MARKERS = [
    ("✅", "built"), ("🔨", "in progress"), ("⬜", "planned"),
    ("💡", "idea, not approved"), ("❌", "decided against"),
    ("⚠️", "beta-blocking — impedes testing at all"),
    ("❓", "has an unanswered question attached"),
    ("🔴", "question: blocking work now"), ("🟡", "question: needed soon"),
    ("⚪", "question: whenever"),
]


def read(rel):
    p = ROOT / rel
    return p.read_text(encoding="utf-8") if p.exists() else ""


# ── Canonical code list, harvested from the documents that define codes ──────
def harvest_codes():
    """Only codes the Docket actually defines, so the index has no false hits."""
    codes = {}
    feat = read("features_and_functions.md")
    for m in re.finditer(r"^\s*[-*]\s*(?:[✅🔨⬜💡❌]\s*)?\*\*([A-Z]{1,4})\*\*\s*(.+)$",
                         feat, re.M):
        codes.setdefault(m.group(1), ("feature", clean(m.group(2))[:150]))
    for m in re.finditer(r"^\|\s*~?~?(K[A-Z]{0,3})~?~?\s*\|\s*~?~?(.+?)~?~?\s*\|",
                         read("Gameplan.md"), re.M):
        if m.group(1) != "Code":
            codes[m.group(1)] = ("decision", clean(m.group(2))[:150])
    for m in re.finditer(r"^###\s+(Q-\d+)\s*✅?\s*—\s*(.+)$", read("open_questions.md"), re.M):
        codes.setdefault(m.group(1), ("question", clean(m.group(2))[:150]))
    for m in re.finditer(r"^##\s+(LE-\d+)\s+—\s+(.+)$", read("lessons_learned.md"), re.M):
        codes[m.group(1)] = ("lesson", clean(m.group(2))[:150])
    return codes


def clean(t):
    t = re.sub(r"`([^`]*)`", r"\1", t)
    t = re.sub(r"\*\*([^*]*)\*\*", r"\1", t)
    t = re.sub(r"\*([^*]*)\*", r"\1", t)
    t = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", t)
    t = re.sub(r"~~([^~]*)~~", r"\1", t)
    return re.sub(r"\s+", " ", t).strip()


def first_sentence(lines, limit=210):
    """The description for a heading: the first real prose beneath it."""
    buf = []
    for ln in lines:
        s = ln.strip()
        if not s:
            if buf:
                break
            continue
        if s.startswith(("#", "|", "```", ">", "---")):
            if buf:
                break
            continue
        if re.match(r"^\s*[-*]\s", s) and not buf:
            s = re.sub(r"^\s*[-*]\s*", "", s)
        buf.append(s)
        if len(" ".join(buf)) > limit:
            break
    text = clean(" ".join(buf))
    if not text:
        return ""
    m = re.match(r"^(.{40,}?[.!?])(\s|$)", text)
    out = m.group(1) if m else text
    return out[:limit].rstrip() + ("…" if len(out) > limit else "")


def outline(src):
    """(level, title, anchor-slug, description, urgency) for each h2/h3.

    `urgency` is `(red, amber)` — how many blocking and soon-needed markers live
    **under** that heading, counted to the next heading of the same level or
    shallower. It is what the rail's chips show.

    **Counted from the section's own text, not from its title.** A heading reading
    `## 🔴 Blocking` carries one red glyph and nine questions; a heading with no
    glyph at all can sit above a dozen. Counting the title would say the opposite
    of the truth in both directions.
    """
    lines = src.split("\n")
    heads, fence = [], False
    for i, ln in enumerate(lines):
        if ln.startswith("```"):
            fence = not fence
        if fence:
            continue
        m = re.match(r"^(#{2,3})\s+(.*)$", ln)
        if not m:
            continue
        title = clean(m.group(2))
        if not title:
            continue
        heads.append((i, len(m.group(1)), title))

    items = []
    for n, (i, lvl, title) in enumerate(heads):
        end = len(lines)
        for j, l2, _ in heads[n + 1:]:
            if l2 <= lvl:
                end = j
                break
        body = "\n".join(lines[i:end])
        items.append((lvl, title, slug(title),
                      first_sentence(lines[i + 1:]),
                      (body.count("🔴"), body.count("🟡"))))
    return items


def slug(t):
    """A heading's anchor. **Entities are decoded first, and that is the fix.**

    `LE-76` was the rail and the page slugging different strings. This is the
    same fault surviving in one input: a heading written with HTML entities in
    the markdown source — `*"the best thing about this &lt;quality&gt; is…"* —
    reaches one side escaped and the other decoded. Stripping non-word
    characters then turns `&lt;quality&gt;` into `ltqualitygt` on one side and
    `quality` on the other, and the link is dead.

    A dead in-page link reports nothing: no error, no console message, the page
    simply does not move. Found by a gate newly installed into `J_astro`, on a
    heading that had been broken for as long as it had existed.
    """
    s = html.unescape(t)
    s = re.sub(r"[^\w\s-]", "", s.lower()).strip()
    return re.sub(r"[\s_]+", "-", s)


MD = markdown.Markdown(extensions=["tables", "fenced_code", "attr_list", "sane_lists"])


#: A feature entry begins with a status glyph and a code. Ordinary bullets do
#: not, which is what keeps this from turning every list in the Docket into cards.
_FEAT_LI = re.compile(
    r"<li>\s*(?P<glyph>[\u2705\U0001F528\u2B1C\U0001F4A1\u274C\u26A0\uFE0F]+)\s*"
    r"(?P<q>(?:\u2753<strong>Q-\d+</strong>\s*)*)"
    r"<strong>(?P<code>[A-Z]{1,4}\d*)</strong>\s*"
    r"(?P<rest>.*?)</li>", re.S)

_STATUS = {"\u2705": ("built", "success"), "\U0001F528": ("in progress", "warning"),
           "\u2B1C": ("planned", "neutral"), "\U0001F4A1": ("idea", "brand"),
           "\u274C": ("dropped", "neutral"), "\u26A0": ("blocking", "danger")}


def _feature_cards(html_src):
    """Each feature entry as a `wa-card` rather than one more bullet in a wall.

    Bradley, 2026-09-17, looking at **ZC**: *"does this entry layout look right
    to you? Could we have separators?"* It did not. Three built features — ZCA,
    ZCB, ZCC, each with its own date and file — ran together with no boundary a
    reader could see. And: *"there are wa components to list things like this."*

    There are. A feature entry is *"any self-contained unit of information"*,
    which is what `wa-card` is for — so the code and its status become a header
    and the prose becomes a body, and the boundary is structural instead of
    typographic.

    **Only entries that open with a status glyph and a code are converted.** An
    ordinary bullet stays an ordinary bullet; a list of links does not become a
    stack of cards.
    """
    def one(m):
        g = m.group("glyph")[0]
        label, variant = _STATUS.get(g, ("", "neutral"))
        code = m.group("code")
        rest = m.group("rest").strip()
        # The first bold run after the code is the entry's name; promote it into
        # the header so a reader can find an entry without reading its sentence.
        title = ""
        tm = re.match(r"<strong>(.*?)</strong>\s*(?:&mdash;|—|-)?\s*", rest, re.S)
        if tm:
            title = tm.group(1)
            rest = rest[tm.end():]
        qs = m.group("q") or ""
        return (
            '<wa-card class="feat" with-header>'
            '<div slot="header" class="feathead">'
            f'<span class="featcode">{code}</span>'
            f'<span class="feattitle">{title}</span>'
            f'<span class="featq">{qs}</span>'
            f'<wa-tag size="s" variant="{variant}">{label}</wa-tag>'
            '</div>'
            f'<div class="featbody">{rest}</div>'
            '</wa-card>')

    return _FEAT_LI.sub(one, html_src)


def _open_lists(src):
    """Let a list start even when nobody left a blank line above it.

    **`sane_lists` requires one, and the documents do not always have one** — so
    a run of `- ` bullets after a sentence became lazy continuation and rendered
    as one wall of prose with literal hyphens in it. Bradley saw it on **ZC**,
    where ZCA, ZCB and ZCC ran together into a single paragraph: three built
    features, three dates, three files, and no way to tell where one ended.

    **34 list items across the Docket were being swallowed this way** — 13 in the
    feature list, 11 in the changelog — so this is the renderer meeting the
    documents rather than one badly typed section.

    The blank line is inserted for the parser only. Nothing on disk changes, and
    `sane_lists` keeps doing its real job everywhere else: stopping a line that
    merely begins with a dash from inventing a list.
    """
    out, fence = [], False
    for i, ln in enumerate(src.split("\n")):
        if ln.startswith("```"):
            fence = not fence
        if (not fence and out and re.match(r"^[-*+] ", ln)
                and out[-1].strip()
                and not re.match(r"^([-*+#>|]|\s)", out[-1])):
            out.append("")
        out.append(ln)
    return "\n".join(out)


def render(src):
    src = _open_lists(src)
    blocks = []

    def stash(m):
        blocks.append(m.group(1))
        return f"\n\nDOCKETMERMAID{len(blocks) - 1}ENDMERMAID\n\n"

    src = re.sub(r"```mermaid\n(.*?)```", stash, src, flags=re.S)
    MD.reset()
    out = MD.convert(src)
    for i, b in enumerate(blocks):
        out = re.sub(
            rf"<p>DOCKETMERMAID{i}ENDMERMAID</p>",
            f'<div class="mermaid-wrap"><pre class="mermaid">{html.escape(b)}</pre>'
            f'<details class="msrc"><summary>diagram source</summary>'
            f'<pre><code>{html.escape(b)}</code></pre></details></div>',
            out,
        )
    # give headings ids that match the TOC
    def anchor(m):
        """The id, slugged from the heading's TEXT rather than its markup.

        **The rail and the page were slugging different things.** The rail slugs
        the markdown title — `clean()` drops the `**` and leaves *ZC — Retail
        geography ❓Q-01* — while this ran on the *rendered* heading, where the
        emphasis has already become `<strong>…</strong>`. `clean()` removes
        markdown asterisks, not HTML tags, so the id came out
        `zc-retail-geography-strongq-01strong` and the rail's `#…-q-01` reached
        nothing.

        **Only headings containing markup were affected** — eight of them — which
        is why it looked arbitrary: Bradley first took it for the ones carrying a
        question, and every one of those has a bolded `Q-nn` in the title.

        Tags are stripped here so both sides slug the same string. Gate:
        `scripts/check_docket_anchors.py`.
        """
        # Tags out, then entities back to characters. `&` renders as `&amp;`,
        # and slugging that gives `…-amp-…` where the rail, slugging the raw
        # markdown, gives nothing at all — which is how *Z — Geography & ZIP*
        # broke while its neighbours worked.
        text = html.unescape(re.sub(r"<[^>]+>", "", m.group(2)))
        return f'<h{m.group(1)} id="{slug(clean(text))}">{m.group(2)}</h{m.group(1)}>'
    out = re.sub(r"<h([23])>(.*?)</h\1>", anchor, out, flags=re.S)
    return _feature_cards(out)


# The dark palette is the original and is deliberate — see the alpha note
# inside it. It is emitted twice (system-dark, and the explicit toggle) rather
# than restated, so the two can never drift apart.
DARK_TOKENS = """
  --c-ground:#0f0d09; --c-raised:#1f1b13; --c-nav-bg:#0c0a07; --c-sunken:#0a0906;
  --c-ink:#ece3cd; --c-accent:#c9a35c; --c-bright:#e9cd8b; --c-hard:#bd6743;
  --c-soft:#8ca58e;
  /* Structural edges sit at >=0.55 alpha on purpose: below that gold on this
     ground falls under the 3:1 floor for non-text UI. See critical_path.md
     Column 0 — that measurement is why this file does not repeat the mistake. */
  --c-edge:rgba(201,163,92,.58); --c-edge-soft:rgba(201,163,92,.34);
  --c-wash:rgba(201,163,92,.07); --c-hero-wash:rgba(201,163,92,.09);
  color-scheme:dark;
  --ground:var(--c-ground);
  --raised:var(--c-raised);
  --nav-bg:var(--c-nav-bg);
  --sunken:var(--c-sunken);
  --card:var(--c-raised);
  --card-edge:var(--c-edge);
  --ink:var(--c-ink);
  --accent:var(--c-accent);
  --bright:var(--c-bright);
  --hard:var(--c-hard);
  --soft:var(--c-soft);
  --edge:var(--c-edge);
  --edge-soft:var(--c-edge-soft);
  --wash:var(--c-wash);
  --hero-wash:var(--c-hero-wash);
"""

CSS = """
/* ── Light is the bare :root, dark is the override, and the toggle wins over
      both. Three blocks, in this order, because a token defined only inside a
      media query has no value when the reader has chosen the other way. ── */
:root{
  --c-ground:#faf7ef; --c-raised:#f1ead8; --c-nav-bg:#f4eee0; --c-sunken:#efe7d4;
  --c-ink:#2a2318; --c-accent:#7a5c18; --c-bright:#63490f; --c-hard:#8f3a19;
  --c-soft:#53624f;
  /* Same 3:1 floor as the dark palette, re-measured against parchment rather
     than assumed: gold at .58 over a light ground lands near 1.9:1, so the
     structural edge is a darker brown at a higher alpha instead. */
  --c-edge:rgba(74,54,14,.62); --c-edge-soft:rgba(74,54,14,.30);
  --c-wash:rgba(122,92,24,.08); --c-hero-wash:rgba(122,92,24,.11);
  /* Typography is a property of the LOOK, not of light/dark, so it is
     declared once here and overridden once in the themed block below. */
  --c-f-body:Spectral,"Iowan Old Style","Palatino Linotype",Palatino,Georgia,serif;
  --f-head:var(--f-body);
  --c-f-mono:"IBM Plex Mono",ui-monospace,SFMono-Regular,Menlo,monospace;
  --f-body:var(--c-f-body);
  --f-mono:var(--c-f-mono);
  color-scheme:light;
  --ground:var(--c-ground);
  --raised:var(--c-raised);
  --nav-bg:var(--c-nav-bg);
  --sunken:var(--c-sunken);
  --card:var(--c-raised);
  --card-edge:var(--c-edge);
  --ink:var(--c-ink);
  --accent:var(--c-accent);
  --bright:var(--c-bright);
  --hard:var(--c-hard);
  --soft:var(--c-soft);
  --edge:var(--c-edge);
  --edge-soft:var(--c-edge-soft);
  --wash:var(--c-wash);
  --hero-wash:var(--c-hero-wash);
}
@media (prefers-color-scheme: dark){ :root:not([data-theme="light"]){{DARK_TOKENS}} }
:root[data-theme="dark"]{{DARK_TOKENS}}

/* ── The themed looks. Last, so they win the equal-specificity tie against the
      classic blocks above; scoped off [data-look="classic"], which is set only
      when Classic is chosen. The wa-* surface and text tokens already resolve
      light or dark from the `wa-dark` class, so this block needs no theme
      variants of its own. ── */
:root:not([data-look="classic"]){
  --ground:var(--wa-color-surface-default,var(--c-ground));
  --raised:var(--wa-color-surface-raised,var(--c-raised));
  /* **A card fill that actually steps, in both themes.** `--raised` is a step up
     from the ground in dark and is *identical to it* in light, so anything drawn
     with it is invisible on exactly one of the two — which is how the hero's
     count tiles came to be six rectangles nobody could see. The neutral fills
     step in both directions, so a card built on them has contrast either way. */
  --card:var(--wa-color-neutral-fill-quiet,var(--c-raised));
  /* **Derived from the text colour, because that is the one thing guaranteed to
     contrast with the ground in every theme.** The border token was
     `--wa-color-neutral-fill-normal`: 231 on a 255 ground in light, which is a
     24/255 step — and the fill beside it was 241, so the border was 10 from its
     own fill. Numerically a border; visually nothing. Mixing the ink in gives a
     ~49/255 step in both directions, and cannot be light-on-light or
     dark-on-dark by construction. */
  --card-edge:color-mix(in srgb,var(--ink,var(--c-ink)) 22%,transparent);
  --nav-bg:var(--wa-color-surface-lowered,var(--c-nav-bg));
  --sunken:var(--wa-color-surface-lowered,var(--c-sunken));
  --ink:var(--wa-color-text-normal,var(--c-ink));
  --soft:var(--wa-color-text-quiet,var(--c-soft));
  --accent:var(--wa-color-brand,var(--c-accent));
  --bright:var(--wa-color-text-link,var(--c-bright));
  --hard:var(--wa-color-danger,var(--c-hard));
  --edge:var(--wa-color-surface-border,var(--c-edge));
  --edge-soft:color-mix(in srgb,var(--wa-color-surface-border,var(--c-edge)) 55%,transparent);
  --wash:color-mix(in srgb,var(--wa-color-brand,var(--c-accent)) 7%,transparent);
  --hero-wash:color-mix(in srgb,var(--wa-color-brand,var(--c-accent)) 11%,transparent);
  --f-body:var(--wa-font-family-body,var(--c-f-body));
  --f-head:var(--wa-font-family-heading,var(--c-f-body));
  --f-mono:var(--wa-font-family-code,var(--c-f-mono));
}
*{box-sizing:border-box}
body{margin:0;background:var(--ground);color:var(--ink);
  font:16px/1.65 var(--f-body);
  -webkit-text-size-adjust:100%}
a{color:var(--bright);text-decoration-color:var(--edge-soft);text-underline-offset:2px}
a:hover{text-decoration-color:var(--bright)}
code,pre,kbd{font-family:var(--f-mono)}
code{font-size:.86em;background:var(--wash);border:1px solid var(--edge-soft);
  border-radius:3px;padding:.08em .34em}
pre{background:var(--sunken);border:1px solid var(--edge);border-radius:8px;padding:14px;
  overflow-x:auto}
pre code{background:none;border:0;padding:0;font-size:.8rem;line-height:1.5}

/* `wa-page` owns the grid now, so the old two-column layout is gone. It gives
   the sticky header, the sidebar, and the mobile drawer with its own hamburger
   — none of which is worth hand-rolling, and the drawer is the reason the rail
   can afford to be long. */
html,body{min-height:100%;padding:0;margin:0}
wa-page{--menu-width:320px}
wa-page[view='mobile']{--menu-width:auto}
nav[slot='navigation']{padding:16px 14px 60px;background:var(--nav-bg);
  border-right:1px solid var(--edge)}
main{padding:36px 40px 140px;min-width:0;max-width:1100px}

/* The bar must always paint above the document labels. It is `static` with
   `z-index:auto` by default, which creates no stacking context, so a sticky
   label — which does — painted straight over "Expand all". Offsetting the
   labels was not enough on its own: a label whose article is scrolling out
   slides up THROUGH this band on its way off screen, and on a project with
   long document names it covered the controls the whole way. */
.topbar{display:flex;align-items:baseline;gap:10px;padding:10px 18px;
  background:var(--nav-bg);border-bottom:1px solid var(--edge);
  position:relative;z-index:10}
.topbar .grow{flex:1 1 auto}
.brand{font-family:var(--f-head);font-size:1.25rem;letter-spacing:.02em}
.brand span{color:var(--accent)}
.sub{font-size:.74rem;color:var(--soft);letter-spacing:.06em;
  text-transform:uppercase}

/* ── the accordion rail ──────────────────────────────────────────────────
   Fourteen documents and several hundred headings used to render as one flat
   list that had to be scrolled past to reach anything. Each document is now a
   `wa-details`, shut by default, so the rail opens at fourteen lines and the
   reader expands the one they want. */
.docd::part(base){border:0;background:none}
.docd::part(header){padding:7px 4px;border-radius:6px}
.docd::part(header):hover{background:var(--wash)}
.docd::part(content){padding:2px 0 8px 10px;border:0}
.dsum{display:flex;align-items:center;gap:8px;width:100%}
.dsum .dlab{display:flex;flex-direction:column;min-width:0;flex:1 1 auto}
.dsum small{font-size:.66rem;letter-spacing:.07em;text-transform:uppercase;
  color:var(--soft)}
.dsum b{font-size:.85rem;font-weight:600;overflow:hidden;text-overflow:ellipsis;
  white-space:nowrap}
.jump{display:block;font-size:.74rem;color:var(--soft);text-decoration:none;
  margin:0 0 6px 2px}
.jump:hover{color:var(--accent);text-decoration:underline}

/* Circular counters. Only drawn where there is something to count. */
.chips{display:inline-flex;gap:4px;flex:0 0 auto;margin-left:6px}
.chip::part(base){min-width:1.35em;height:1.35em;padding:0 .35em;
  border-radius:999px;font-size:.66rem;font-weight:700;
  display:inline-flex;align-items:center;justify-content:center}
.heads .chips{margin-left:5px;vertical-align:middle}
#filter{width:100%;padding:8px 10px;background:var(--ground);color:var(--ink);
  border:1px solid var(--edge);border-radius:6px;font:inherit;font-size:.84rem;
  margin-bottom:14px}
#filter:focus{outline:2px solid var(--bright);outline-offset:1px}
/* ── the tree: every nesting level draws its own rail, every item an elbow ── */
.tree,.tree ul{list-style:none;margin:0;padding:0}
.tree ul{margin-left:9px;padding-left:11px;border-left:1px solid var(--edge-soft)}
.tree li{position:relative}
.tree ul>li::before{content:"";position:absolute;left:-11px;top:.92em;width:8px;
  height:1px;background:var(--edge-soft)}
/* cap the rail at the last child so it stops at the elbow */
.tree ul>li:last-child::after{content:"";position:absolute;left:-12px;top:calc(.92em + 1px);
  bottom:-2px;width:3px;background:var(--nav-bg)}
.tree a{display:block;padding:3px 6px;border-radius:4px;text-decoration:none;
  color:var(--soft);font-size:.83rem;line-height:1.45}
.tree a:hover{color:var(--bright);background:var(--wash)}
.tree a.on{color:var(--bright);background:var(--wash);box-shadow:inset 2px 0 0 var(--accent)}
.tree .doc>a{color:var(--ink);font-size:.92rem;padding:6px 8px;margin-top:5px;
  border-left:3px solid var(--edge);border-radius:0 5px 5px 0}
.tree .doc>a:hover,.tree .doc>a.on{border-left-color:var(--bright);background:var(--wash)}
.tree .doc>a small{display:block;color:var(--accent);font-size:.63rem;
  letter-spacing:.09em;text-transform:uppercase;font-family:var(--f-mono)}
.tree .doc>a b{font-weight:600;font-family:var(--f-mono);font-size:.79rem}
.tree .g{color:var(--soft);font-size:.9em;margin-right:3px}
.tree li.hide{display:none}
.built #diag{display:block;margin-top:2px}
.built #diag b{color:var(--bright);font-weight:600}
.built #diag .bad{color:var(--hard);font-weight:600}
.built{margin:-12px 0 12px;font-size:.62rem;color:var(--soft);letter-spacing:.07em;
  font-family:var(--f-mono)}
.look{display:flex;align-items:center;gap:6px;margin:0 0 14px}
.look wa-select{flex:1;min-width:0}
.look wa-select::part(combobox){background:var(--ground);border-color:var(--edge);
  color:var(--ink);font-size:.78rem}
.look wa-button::part(base){color:var(--soft);border-color:var(--edge)}
.look wa-button::part(base):hover{color:var(--bright)}
.railkey{margin:16px 0 6px;color:var(--soft);font-size:.63rem;letter-spacing:.1em;
  text-transform:uppercase;font-family:var(--f-mono);
  border-top:1px solid var(--edge-soft);padding-top:11px}

.hero{border:1px solid var(--card-edge);border-radius:12px;padding:26px 28px;
  background:linear-gradient(180deg,var(--hero-wash),transparent 70%);
  margin-bottom:30px}
/* **The project's name is the headline.** This said "The Docket" at 2.1rem with
   the project's name beneath it in 0.8rem uppercase — which is exactly backwards
   for somebody who runs this framework across a dozen projects and has four of
   their viewers open. Every one of those pages is titled "The Docket". Only one
   of them is titled what you are looking for. */
.hero h1{font-family:var(--f-head);margin:0 0 8px;font-weight:600;
  font-size:clamp(2.5rem,6.5vw,4.25rem);line-height:.96;letter-spacing:-.02em;
  text-wrap:balance;overflow-wrap:anywhere}
.hero .tag{color:var(--soft);font-size:.72rem;letter-spacing:.16em;
  text-transform:uppercase;font-family:var(--f-mono);margin:0 0 6px}
.hero .made{color:var(--soft);font-size:.78rem;font-family:var(--f-mono);
  margin:0 0 14px}
.stats{display:flex;flex-wrap:wrap;gap:10px;margin:18px 0 0;padding:0;list-style:none}
.stats li{border:1px solid var(--card-edge);border-radius:8px;padding:8px 14px;
  background:var(--card);min-width:96px}
.stats b{display:block;font-size:1.5rem;color:var(--bright);line-height:1.15}
.stats span{font-size:.68rem;color:var(--soft);letter-spacing:.07em;
  text-transform:uppercase;font-family:var(--f-mono)}

h2.section{font-family:var(--f-head);font-size:1.45rem;margin:44px 0 14px;padding-bottom:7px;
  border-bottom:1px solid var(--edge)}
.practice{border-left:3px solid var(--edge);padding:2px 0 2px 15px;margin:0 0 17px}
.practice b{color:var(--bright)}
.markers{list-style:none;padding:0;margin:0;display:grid;
  grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:7px}
.markers li{border:1px solid var(--edge-soft);border-radius:6px;padding:6px 11px;
  font-size:.87rem}

/* ── Rail groups, and the two anchors that are not documents ─────────────
   Bradley, 2026-09-17: *"could MAIN sections be bolded and have no extraneous
   items at the root?"* Front matter and the code index are page anchors; they
   wore the same two-line shape as a document, so the rail read as ten Docket
   documents where there are eight. And the eight ran straight into twenty-five
   chapters with no boundary, so the chapters looked like more of the same. */
.jumps{ display:flex; gap:14px; margin:0 0 12px; padding:0 4px }
.jumps a{ font-size:.76rem; color:var(--soft); text-decoration:none;
  letter-spacing:.04em; text-transform:uppercase }
.jumps a:hover{ color:var(--accent) }
.tree li.grouphead{
  font-family:var(--f-head); font-weight:700; font-size:.82rem;
  letter-spacing:.08em; text-transform:uppercase; color:var(--ink);
  margin:16px 0 6px; padding:0 0 5px;
  border-bottom:1px solid var(--edge); list-style:none }
.tree li.grouphead:first-child{ margin-top:2px }

/* ── Feature entries as cards ────────────────────────────────────────────
   Three built features used to run together as one paragraph with literal
   hyphens between them (the list never parsed — see `_open_lists`), and even
   parsed they were three bullets in a wall. Each is a self-contained unit with
   its own code, status, date and file, so each gets a card and the boundary is
   structural rather than typographic.

   Styled through `wa-card`'s documented parts — `header` and `body` — never the
   host. */
wa-card.feat{ --spacing: .7rem; display:block; margin:0 0 12px }
wa-card.feat::part(header){
  background:var(--wash); border-bottom:1px solid var(--edge-soft);
  padding:.45rem .8rem }
wa-card.feat::part(body){ padding:.7rem .8rem .8rem }
.feathead{ display:flex; align-items:baseline; gap:.5rem; flex-wrap:wrap }
.featcode{ font-family:var(--f-mono,ui-monospace,SFMono-Regular,Menlo,monospace);
  font-weight:700; color:var(--accent); letter-spacing:.02em }
.feattitle{ font-weight:600; flex:1 1 auto; min-width:0 }
.featq{ color:var(--hard) }
.featq strong{ font-weight:600 }
.featbody{ font-size:.94rem; line-height:1.62 }
.featbody > :first-child{ margin-top:0 }
.featbody > :last-child{ margin-bottom:0 }
@media print{
  wa-card.feat{ break-inside:avoid }
}

.toc{border:1px solid var(--edge);border-radius:10px;overflow:hidden;margin:0 0 22px}
.toc>summary{padding:13px 18px;cursor:pointer;background:var(--card);
  font-size:1rem;letter-spacing:.01em}
.toc>summary::marker{color:var(--accent)}
.toc .body{padding:6px 18px 16px}
.toc .d{margin:14px 0 0;padding-top:12px;border-top:1px solid var(--edge-soft)}
.toc .d:first-child{border-top:0;padding-top:2px}
.toc .d>a{font-size:1.02rem;font-weight:600;text-decoration:none}
.toc .d p{margin:3px 0 8px;color:var(--soft);font-size:.85rem}
.toc ul{list-style:none;margin:0;padding:0}
.toc ul li{margin:0 0 5px;padding-left:13px;border-left:1px solid var(--edge-soft);
  font-size:.87rem}
.toc ul li.l3{margin-left:19px}
.toc ul li em{color:var(--soft);font-style:normal;font-size:.93em}
.toc ul li em::before{content:" — "}

.codes{width:100%;border-collapse:collapse;font-size:.87rem}
.codes th{text-align:left;border-bottom:1px solid var(--edge);padding:7px 9px;
  color:var(--soft);font-size:.7rem;letter-spacing:.09em;text-transform:uppercase;
  font-family:var(--f-mono);position:sticky;top:0;background:var(--ground)}
.codes td{border-bottom:1px solid var(--edge-soft);padding:7px 9px;vertical-align:top}
.codes td:first-child{font-family:var(--f-mono);color:var(--bright);
  white-space:nowrap;font-size:.84rem}
.codes .kind{font-size:.67rem;letter-spacing:.07em;text-transform:uppercase;
  color:var(--soft);font-family:var(--f-mono);white-space:nowrap}
.codes .where a{margin-right:7px;font-size:.76rem;white-space:nowrap}
.codes tr.hide{display:none}

.ctree,.ctree ul{list-style:none;margin:0;padding:0}
.ctree ul{margin-left:10px;padding-left:14px;border-left:1px solid var(--edge-soft)}
.ctree li{position:relative;margin:1px 0}
.ctree ul>li::before{content:"";position:absolute;left:-14px;top:.82em;width:11px;
  height:1px;background:var(--edge-soft)}
.ctree ul>li:last-child::after{content:"";position:absolute;left:-15px;
  top:calc(.82em + 1px);bottom:-2px;width:3px;background:var(--ground)}
.ctree .row{display:flex;gap:9px;align-items:baseline;padding:2px 5px;border-radius:4px}
.ctree .row:hover{background:var(--wash)}
.ctree .c{font-family:var(--f-mono);color:var(--bright);font-size:.83rem;
  min-width:52px;font-weight:600}
.ctree .m{font-size:.86rem;flex:1;min-width:0}
.ctree .w a{font-size:.7rem;margin-left:6px;white-space:nowrap;opacity:.8}
.ctree .root>.row{border-bottom:1px solid var(--edge-soft);margin-bottom:3px;
  padding-bottom:4px}
.ctree .root>.row .c{color:var(--accent);font-size:.95rem}
.ctree .root>.row .m{color:var(--ink)}
.ctree li.hide{display:none}
article{border-top:1px solid var(--edge);margin-top:52px;padding-top:8px}
/* The document label and the page's own header are both sticky. Pinned at
   top:0 they occupy the same band, and this one — opaque, z-index 5 — painted
   straight over "Expand all" on any project whose document names are long
   enough to reach them. It sticks BELOW the header instead. The offset is
   measured from the real bar at runtime rather than guessed, because the bar's
   height moves with the theme's font. */
article>.head{position:sticky;top:var(--topbar-h,46px);background:var(--ground);
  padding:12px 0 9px;border-bottom:1px solid var(--edge-soft);z-index:4;
  margin-bottom:16px}
/* And it must not grow into the controls even while scrolling past them. */
article>.head{max-width:100%;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
article>.head b{font-size:1.3rem}
article>.head span{color:var(--soft);font-size:.72rem;letter-spacing:.08em;
  text-transform:uppercase;font-family:var(--f-mono);margin-left:9px}
article h1{font-family:var(--f-head);font-size:1.75rem;margin:.5em 0 .4em}
article h2{font-family:var(--f-head);font-size:1.32rem;margin:1.5em 0 .4em;padding-bottom:5px;
  border-bottom:1px solid var(--edge-soft)}
article h3{font-family:var(--f-head);font-size:1.08rem;margin:1.35em 0 .35em;color:var(--bright)}
article table{border-collapse:collapse;width:100%;margin:1em 0;font-size:.9rem;
  display:block;overflow-x:auto}
article th{text-align:left;background:var(--card);border:1px solid var(--card-edge);
  padding:7px 10px}
article td{border:1px solid var(--edge-soft);padding:7px 10px;vertical-align:top}
article blockquote{margin:1em 0;padding:2px 0 2px 16px;border-left:3px solid var(--edge);
  color:var(--soft)}
article hr{border:0;border-top:1px solid var(--edge-soft);margin:2em 0}
article del{color:var(--soft)}
.mermaid-wrap{border:1px solid var(--edge);border-radius:10px;padding:14px;
  margin:1em 0;background:var(--sunken);overflow-x:auto}
.msrc summary{cursor:pointer;color:var(--soft);font-size:.78rem;margin-top:9px}

.top{position:fixed;right:20px;bottom:20px;background:var(--card);
  border:1px solid var(--edge);color:var(--bright);border-radius:8px;
  padding:9px 13px;text-decoration:none;font-size:.82rem}
@media(max-width:900px){ main{padding:22px 18px 100px} }
/* Print wants everything open and nothing chrome. `wa-details` keeps its
   content in the light DOM, so forcing the part visible is enough. */
@media print{
  nav,.top,.topbar{display:none}
  article{break-before:page}
  .docd::part(content){display:block!important}
}
"""

JS = """
const f=document.getElementById('filter');
const docs=()=>[...document.querySelectorAll('nav wa-details.docd')];

/* **Filtering has to open what it finds.** A shut `wa-details` hides its
   matches, so typing a word that occurs three documents down used to leave an
   apparently empty rail — the search worked and looked broken. A document with
   a hit is opened, one without is shut, and clearing the box puts every
   accordion back the way the reader left it. */
let beforeFilter=null;
f.addEventListener('input',()=>{
  const q=f.value.trim().toLowerCase();
  if(q && beforeFilter===null) beforeFilter=docs().map(d=>d.open);
  document.querySelectorAll('nav li').forEach(li=>{
    li.classList.toggle('hide', q && !li.textContent.toLowerCase().includes(q));
  });
  document.querySelectorAll('.codes tbody tr').forEach(tr=>{
    tr.classList.toggle('hide', q && !tr.textContent.toLowerCase().includes(q));
  });
  if(q){
    docs().forEach(d=>{ d.open = d.textContent.toLowerCase().includes(q); });
  }else if(beforeFilter){
    docs().forEach((d,i)=>{ d.open = beforeFilter[i]; });
    beforeFilter=null;
  }
});

// Keep the sticky document label clear of the header bar. Measured, not
// assumed: the bar's height changes with the theme's heading font.
function topbarHeight(){
  const bar=document.querySelector('.topbar');
  if(!bar) return;
  const h=Math.ceil(bar.getBoundingClientRect().height);
  if(h>0) document.documentElement.style.setProperty('--topbar-h', h+'px');
}
topbarHeight();
// Watch the bar rather than measure it once. A single reading was 54px against
// a bar that settled at 61 — the heading font had not loaded yet — and the
// document label then sat 7px over the controls, which is exactly the bug this
// was fixing, smaller. ResizeObserver covers the font load, the theme switch,
// a window resize and the mobile breakpoint without needing to know about any
// of them.
const bar=document.querySelector('.topbar');
if(bar&&window.ResizeObserver) new ResizeObserver(topbarHeight).observe(bar);
else addEventListener('resize', topbarHeight);

const ea=document.getElementById('expandall');
const ca=document.getElementById('collapseall');
if(ea) ea.addEventListener('click',()=>{docs().forEach(d=>d.open=true); beforeFilter=null;});
if(ca) ca.addEventListener('click',()=>{docs().forEach(d=>d.open=false); beforeFilter=null;});
// scroll-spy: the tree shows where you are in the structure
const links=[...document.querySelectorAll('.tree a[href^="#"]')];
const byId=new Map(links.map(a=>[a.getAttribute('href').slice(1),a]));
const seen=new Set();
const io=new IntersectionObserver(es=>{
  es.forEach(e=>e.isIntersecting?seen.add(e.target.id):seen.delete(e.target.id));
  let best=null;
  for(const a of links){const id=a.getAttribute('href').slice(1);
    if(seen.has(id)){best=a;break;}}
  links.forEach(a=>a.classList.remove('on'));
  if(best){best.classList.add('on');
    const li=best.closest('li.doc');
    if(li){
      const j=li.querySelector('a.jump'); if(j) j.classList.add('on');
      /* Open the document you have scrolled into, so the rail follows the
         reader rather than needing to be driven. */
      const d=li.querySelector('wa-details.docd');
      if(d&&!d.open&&!f.value.trim()) d.open=true;
    }}
},{rootMargin:'0px 0px -72% 0px'});
document.querySelectorAll('article[id],article h2[id],article h3[id]')
  .forEach(el=>io.observe(el));
document.addEventListener('keydown',e=>{
  if(e.key==='/'&&document.activeElement!==f){e.preventDefault();f.focus();}
  if(e.key==='Escape'&&document.activeElement===f){f.value='';f.dispatchEvent(new Event('input'));f.blur();}
  if((e.key==='t'||e.key==='T')&&document.activeElement!==f&&!e.metaKey&&!e.ctrlKey){flipTheme();}
});
/* ── Look and light/dark ──────────────────────────────────────────────────
   Shared with the five RainZips pages through the same two localStorage keys,
   so a choice made here is the choice they make. `dark()` resolves what is
   ACTUALLY showing: an explicit choice if one exists, the OS otherwise —
   because `data-theme` is absent, not "light", when nothing has been picked. */
const root=document.documentElement;
const store=(k,v)=>{try{localStorage.setItem(k,v)}catch(e){}};
const recall=k=>{try{return localStorage.getItem(k)}catch(e){return null}};
const dark=()=>root.getAttribute('data-theme')
  ? root.getAttribute('data-theme')==='dark'
  : matchMedia('(prefers-color-scheme: dark)').matches;

function applyTheme(t){
  root.setAttribute('data-theme',t);
  root.classList.toggle('wa-dark', t==='dark');
  store('docket.theme',t);
  paintMermaid(); diag();
}
/* What the page actually resolved to, printed where it can be read without
   opening devtools. `wa` says whether the theme stylesheets are live: if it
   reads FAIL the colours are coming from the classic fallback, which is the
   difference between "the switch is broken" and "the theme never loaded". */
function diag(){
  const el=document.getElementById('diag'); if(!el) return;
  const cs=getComputedStyle(root);
  const g=cs.getPropertyValue('--ground').trim()||'(unset)';
  const wa=cs.getPropertyValue('--wa-color-surface-default').trim();
  /* The look's *name*, not the theme it resolves to. `docket` is the default
     theme with the natural palette, so reading the class printed `default`
     — a diagnostic naming something the reader cannot find in the menu. */
  const look=root.getAttribute('data-look')||recall('docket.look')||recall('tripwire.look')||'docket';
  el.innerHTML='<b>'+look+'</b> · <b>'+(root.getAttribute('data-theme')||'auto')+
    '</b> · wa '+(wa?'ok':'<span class="bad">FAIL</span>')+' · '+g;
}
/* The same table as the bootstrap in <head>, and it has to stay the same:
   a look that paints one way before the script runs and another way after is
   a flash somebody will report as a rendering bug. `docket` is the framework's
   own theme — the default theme with the natural palette, which is what every
   other Docket surface uses. */
const LOOKS={docket:['default','natural'],mellow:['mellow','natural'],
             playful:['playful','rudimentary']};
function applyLook(l){
  root.className=root.className.replace(/wa-theme-\S+|wa-palette-\S+/g,'').trim();
  if(l==='classic'){root.setAttribute('data-look','classic');}
  else{root.removeAttribute('data-look');
    const q=LOOKS[l]||LOOKS.docket;
    root.className=(root.className+' wa-theme-'+q[0]+' wa-palette-'+q[1]).trim();}
  if(dark()) root.classList.add('wa-dark');
  store('docket.look',l);
}

function flipTheme(){ applyTheme(dark()?'light':'dark'); }
/* ── One handler, by delegation. LE-73. ──────────────────────────────────
   This was bound twice — once on the host and once on `.look` by delegation —
   with the delegated one guarded by `e.target !== themebtn` to stop them both
   firing. **That guard was written for the wrong retargeting rule.**

   A click on a component's *shadow* content is retargeted to the host, so
   `e.target === themebtn` and the guard holds. But `<wa-icon>` inside
   `<wa-button>` is a **slotted light-DOM child**, so a real click keeps
   `e.target === WA-ICON`: the guard passes, the delegated handler fires, the
   host handler fires too, and `flipTheme()` runs **twice — flipping the theme
   and flipping it straight back**.

   So the button was never dead. It worked exactly twice, which looks identical
   to not working at all, and `t` worked because it is a third path that touches
   neither. Diagnosed 2026-09-17 by clicking it with a real mouse rather than
   `element.click()` — the JS call *did* work, because it targets the host and
   the guard then suppressed the second fire. **The reproduction only exists
   under a genuine click.**

   One listener now, on the container, using `closest()`. It catches a click on
   the host, on the slotted icon, and on shadow content retargeted to the host —
   three cases, one path, and no arithmetic about which fired. */
const themebtn=document.getElementById('themebtn');
const lookbar=document.querySelector('.look')||document;
lookbar.addEventListener('click',e=>{
  const t=e.target;
  if(t&&t.closest&&t.closest('#themebtn')) flipTheme();
});
const looksel=document.getElementById('look');
if(looksel){
  /* The same default as the bootstrap in <head> and as applyLook. Three
     places is two too many, but they run in three contexts — inline head
     script, page script, and the markup's own value attribute — and a
     select that disagrees with the theme it is showing is a control that
     lies about the state of the page. */
  try{looksel.value=recall('docket.look')||recall('tripwire.look')||'docket'}catch(e){}
  looksel.addEventListener('change',e=>{applyLook(e.target.value);diag();});
}
/* Nothing chosen yet? Then follow the OS as it changes, and stop the moment
   the reader picks a side. */
matchMedia('(prefers-color-scheme: dark)').addEventListener('change',()=>{
  if(!root.getAttribute('data-theme')){ paintMermaid(); diag(); }
});
diag();

/* ── Mermaid, re-themed rather than re-loaded ─────────────────────────────
   Mermaid bakes its colours in at render, so a toggle has to put the source
   back and run it again. The source is kept here before the first render,
   because by the second one the element holds an <svg> and the text is gone. */
let MM=null;
const MSRC=new Map();
document.querySelectorAll('.mermaid').forEach((el,i)=>{
  const id='mm'+i; el.dataset.mid=id; MSRC.set(id, el.textContent);
});
function paintMermaid(){
  if(!MM) return;
  const d=dark();
  MSRC.forEach((src,id)=>{
    const el=document.querySelector('[data-mid="'+id+'"]');
    if(!el) return;
    el.removeAttribute('data-processed'); el.innerHTML=''; el.textContent=src;
  });
  MM.initialize({startOnLoad:false, theme:d?'dark':'neutral',
    themeVariables:d
      ? {background:'#0a0906',primaryColor:'#1f1b13',primaryTextColor:'#ece3cd',
         primaryBorderColor:'#c9a35c',lineColor:'#c9a35c',
         fontFamily:'IBM Plex Mono,monospace'}
      : {background:'#efe7d4',primaryColor:'#f1ead8',primaryTextColor:'#2a2318',
         primaryBorderColor:'#7a5c18',lineColor:'#7a5c18',
         fontFamily:'IBM Plex Mono,monospace'}});
  MM.run({querySelector:'.mermaid'});
}
import('https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs')
  .then(({default:m})=>{MM=m; paintMermaid();})
  .catch(()=>document.querySelectorAll('.mermaid').forEach(p=>{
    p.style.whiteSpace='pre';p.style.fontFamily='monospace';p.style.fontSize='.75rem';
    p.style.color='var(--soft)';
    const d=p.parentElement.querySelector('.msrc'); if(d) d.open=true;
  }));
"""


GLYPHS = "✅🔨⬜💡❌⚠️❓🔴🟡⚪⭐📖"


def chips(red, amber):
    """Two circular counters, shown only when there is something to count.

    **A chip that is always there stops being read.** These appear on a heading
    that actually holds open questions and nowhere else, so a rail with three
    chips on it is telling the reader where to look rather than decorating
    fourteen documents equally.
    """
    out = ""
    if red:
        out += (f'<wa-badge class="chip red" variant="danger" pill '
                f'title="{red} blocking">{red}</wa-badge>')
    if amber:
        out += (f'<wa-badge class="chip amber" variant="warning" pill '
                f'title="{amber} needed soon">{amber}</wa-badge>')
    return f'<span class="chips">{out}</span>' if out else ""


def split_glyph(title):
    """Peel a leading status glyph off a heading so tree text aligns."""
    t = title.strip()
    g = ""
    while t and (t[0] in GLYPHS):
        g += t[0]
        t = t[1:].lstrip("️ ")
    return g, t.strip()


def domain_labels(feat):
    """The domain table in features_and_functions.md, plus synthetic roots."""
    roots = {}
    for m in re.finditer(r"^\|\s*\*\*([A-Z])\*\*\s*\|\s*(.+?)\s*\|\s*$", feat, re.M):
        roots[m.group(1)] = clean(m.group(2))
    roots.setdefault("K", "Standing decisions \u2014 Gameplan K")
    roots["Q"] = "Open questions \u2014 waiting on Bradley"
    roots["LE"] = "Lessons learned \u2014 traps already hit"
    return roots


def build_code_tree(codes, roots):
    """Nest by prefix: C \u2192 CA \u2192 CAA. Q-nn and LE-nn hang off their group."""
    nodes = {c: {"code": c, "kids": []} for c in codes}
    for r, label in roots.items():
        nodes.setdefault(r, {"code": r, "kids": []})
        nodes[r]["label"] = label

    def parent_of(c):
        m = re.match(r"^(Q|LE)-\d+$", c)
        if m:
            return m.group(1)
        for n in range(len(c) - 1, 0, -1):
            if c[:n] in nodes:
                return c[:n]
        return None

    orphans = []
    for c in sorted(codes):
        p = parent_of(c)
        if p and p != c:
            nodes[p]["kids"].append(nodes[c])
        elif c not in roots:
            orphans.append(c)

    def num(c):
        d = re.sub(r"\D", "", c)
        return int(d) if d else 0

    def sortrec(n):
        n["kids"].sort(key=lambda k: (len(k["code"]), num(k["code"]), k["code"]))
        for k in n["kids"]:
            sortrec(k)

    top = [nodes[r] for r in roots if nodes[r]["kids"] or r in codes]
    for n in top:
        sortrec(n)
    top.sort(key=lambda n: (len(n["code"]), n["code"]))
    return top, sorted(orphans)


# ── Web Awesome ─────────────────────────────────────────────────────────────
# The same kit and the same two localStorage keys the five RainZips pages use,
# so choosing dark here is choosing dark there. The bootstrap is BLOCKING and
# sits in <head> on purpose: applied later, the page paints once in the wrong
# theme first. It reads BOTH keys — manual.html shipped a version that read
# only the look and took its light/dark from the OS, which is why that half is
# called out here rather than left to be rediscovered.
#: The Web Awesome kit and the theme both come from `docket_theme`, so the
#: viewer, the console, the capture dashboard and the questions page cannot
#: disagree about which kit this project has or what it looks like. The viewer
#: keeps its own `<head>` rather than using `docket_theme.head()` because it also
#: carries three alternative looks and a classic fallback that needs no
#: components at all — but the kit, the fonts and the tokens are the shared ones.
#:
#: **The kit is a per-owner URL, not a public CDN.** Left hardcoded it fails in
#: the worst available way: the stylesheets 404, no `<wa-*>` element ever
#: upgrades, and the page renders as an unstyled outline with **no error
#: anywhere**. Resolved in order: `DOCKET_WA_KIT`, then `.docket-webawesome` at the
#: project root, then the framework default.
#:
#: **And the viewer works without any of them.** The `classic` look is plain CSS
#: that needs no components, `applyLook('classic')` selects it, and `diag()`
#: prints `wa FAIL` when the theme stylesheets did not load — which is the
#: difference between *"the switch is broken"* and *"the kit is not ours"*.
sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    import docket_theme
    _wa_kit = docket_theme.kit
except ImportError:                       # a project mid-update; never fatal
    def _wa_kit():
        env = os.environ.get("DOCKET_WA_KIT")
        if env:
            return env.rstrip("/")
        f = ROOT / ".docket-webawesome"
        if not f.exists() and (ROOT / ".codex-webawesome").exists():
            f = ROOT / ".codex-webawesome"         # pre-3.0.0, still honoured
        if f.exists():
            line = f.read_text(encoding="utf-8").strip().split("\n")[0].strip()
            if line and not line.startswith("#"):
                return line.rstrip("/")
        return ""          # no kit: the classic look. See docket_theme.DEFAULT_KIT


WA_KIT = _wa_kit()

#: Which framework produced this page. A generated document that cannot say what
#: generated it is the thing every other part of this framework exists to
#: prevent — and the viewer is a file people keep, mail and open months later.
try:
    import docket_version as _cv
    _v = _cv.installed_version(ROOT) or _cv.framework_version()
    FRAMEWORK_LINE = "Docket framework %s" % _v
except Exception:
    FRAMEWORK_LINE = "Docket framework"
HEAD_EXTRA = (
    # The stylesheet has named IBM Plex Mono throughout and never fetched it.
    # Neither it nor Iowan Old Style is on a stock Mac, so the page has been
    # rendering in Palatino and Menlo since it was written. Spectral is the
    # suite's serif (manual.html), so the Docket now reads in the same two faces
    # as the pages it documents.
    # **The Docket look is the default, and it is the framework's one theme.**
    # The same faces, palette and token scale as the console, the capture
    # dashboard and the questions page — `dashboard/theme.html` is the source
    # those three read, and this is the viewer's copy of the same decision.
    # Mellow, Playful and Classic remain: a generated document that somebody
    # reads for an hour should let them change how it looks.
    '<link rel="preconnect" href="https://fonts.bunny.net">'
    '<link rel="stylesheet" href="https://fonts.bunny.net/css?'
    'family=ibm-plex-sans-condensed:300,400,500,600,700&display=swap">'
    '<link rel="stylesheet" href="https://fonts.bunny.net/css?'
    'family=space-grotesk:300,400,500,600,700&display=swap">'
    '<link rel="stylesheet" href="https://fonts.bunny.net/css?'
    'family=space-mono:400,400i,700,700i&display=swap">'
    '<link rel="stylesheet" href="https://fonts.bunny.net/css?'
    'family=podkova:400,500,600,700,800&display=swap">'
    f'<link rel="stylesheet" href="{WA_KIT}/styles/themes/default.css">'
    # The palettes ship with their themes — `mellow.css` imports natural,
    # `playful.css` imports rudimentary — but the Docket look pairs the *default*
    # theme with the *natural* palette, so that one is linked on its own. Without
    # it `wa-palette-natural` is a class that matches nothing and the page
    # renders in the default palette with no error anywhere.
    f'<link rel="stylesheet" href="{WA_KIT}/styles/color/palettes/natural.css">'
    f'<link rel="stylesheet" href="{WA_KIT}/styles/themes/mellow.css">'
    f'<link rel="stylesheet" href="{WA_KIT}/styles/themes/playful.css">'
    f'<script type="module" src="{WA_KIT}/webawesome.loader.js"></script>'
    "<style>:root{"
    "--wa-font-family-body:\"Space Grotesk\",sans-serif;"
    "--wa-font-family-heading:\"IBM Plex Sans Condensed\",sans-serif;"
    "--wa-font-family-code:\"Space Mono\",monospace;"
    "--wa-font-family-longform:Podkova,serif;"
    "--wa-font-weight-body:400;--wa-font-weight-heading:500;"
    "--wa-font-weight-code:400;--wa-font-weight-longform:400;"
    "--wa-border-radius-scale:.75;--wa-border-width-scale:1;"
    "--wa-space-scale:.625;}</style>"
    "<script>(function(){try{"
    "var h=document.documentElement,"
    # **One key per choice, shared with the dashboards, and the old one still
    # read.** The viewer stored `tripwire.theme` while the console, the capture
    # dashboard and the questions page stored `docket.theme` — two names for one
    # choice, so switching to dark in the viewer left every other page light.
    # `tripwire` was also the name of the project this framework was extracted
    # from, leaking into every install; the same class of thing as `Q-02`.
    # The old keys are still read once so nobody's existing choice is lost.
    "l=localStorage.getItem('docket.look')||localStorage.getItem('tripwire.look')||'docket',"
    "t=localStorage.getItem('docket.theme')||localStorage.getItem('tripwire.theme')||"
    "(matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light');"
    "h.className=h.className.replace(/wa-theme-\\S+|wa-palette-\\S+/g,'').trim();"
    "if(l==='classic'){h.setAttribute('data-look','classic');}"
    "else{var P={docket:['default','natural'],mellow:['mellow','natural'],"
    "playful:['playful','rudimentary']},q=P[l]||P.docket;"
    "h.className=(h.className+' wa-theme-'+q[0]+' wa-palette-'+q[1]).trim();}"
    "if(t!=='light'&&t!=='dark')t='light';"
    # **Copy the old choice across once, not merely read it.** Reading alone
    # leaves the viewer on `tripwire.*` and the dashboards on `docket.*` — each
    # correct, still disagreeing — until the reader happens to change something.
    # Writing the resolved values makes every surface agree on the next load.
    "if(!localStorage.getItem('docket.theme'))localStorage.setItem('docket.theme',t);"
    "if(!localStorage.getItem('docket.look'))localStorage.setItem('docket.look',l);"
    "h.setAttribute('data-theme',t);"
    "if(t==='dark')h.classList.add('wa-dark');"
    "}catch(e){}})();</script>"
)

def main():
    codes = harvest_codes()
    present = {rel: read(rel) for rel, *_ in DOCS}
    outlines = {rel: outline(src) for rel, src in present.items()}

    # where each code appears
    where = {}
    for c in codes:
        pat = re.compile(rf"(?<![A-Za-z0-9-]){re.escape(c)}(?![A-Za-z0-9-])")
        where[c] = [(anchor_id, label) for rel, label, anchor_id, _ in
                    [(d[0], d[1], d[2], d[3]) for d in DOCS]
                    if pat.search(present.get(rel, ""))]

    q_open = len(re.findall(r"^### Q-\d+ —", present["open_questions.md"], re.M))
    q_done = len(re.findall(r"^### Q-\d+ ✅", present["open_questions.md"], re.M))

    P = []
    A = P.append
    A(f"<!-- generated {date.today()} by scripts/build_docket.py — do not edit -->")
    # CSS is a plain string, so the placeholder is literal, not an f-slot.
    A("<style>" + CSS.replace("{DARK_TOKENS}", DARK_TOKENS) + "</style>")
    A('<wa-page mobile-breakpoint="900">')
    # **An empty slot for the server to fill, and nothing on disk.**
    # This file is also read on its own — opened from Finder, mailed to somebody,
    # kept after the project is archived — and in that state there is no
    # dashboard to go back to and no way to know there ever was one. So the link
    # is not written here. `docket-server.py` puts it in when it serves this page
    # over HTTP, and a copy read any other way shows an empty comment.
    A('<div slot="header" class="topbar">'
      '<!--{{DOCKET_NAV}}-->'
      '<span class="brand">The <span>Docket</span></span>'
      # The brand already reads "The Docket". On the one project actually called
      # that, printing it again beside itself is the same word twice.
      + (f'<span class="sub">{html.escape(PROJECT)}</span>'
         if PROJECT.strip().lower() != "the docket" else '') +
      '<span class="grow"></span>'
      '<wa-button id="expandall" size="s" appearance="plain">'
      '<wa-icon slot="start" name="chevron-down"></wa-icon>Expand all</wa-button>'
      '<wa-button id="collapseall" size="s" appearance="plain">'
      '<wa-icon slot="start" name="chevron-right"></wa-icon>Collapse all</wa-button>'
      '</div>')
    A('<nav slot="navigation">')
    # `open` focuses an existing tab rather than reloading it, so "is this the
    # build I just made?" was not answerable from the page. Now it is.
    A(f'<p class="built">built {STAMP}<span id="diag"></span></p>')
    A('<div class="look">'
      '<wa-select id="look" size="s" value="docket" aria-label="Look">'
      '<wa-option value="docket">Docket</wa-option>'
      '<wa-option value="mellow">Mellow</wa-option>'
      '<wa-option value="playful">Playful</wa-option>'
      '<wa-option value="classic">Classic</wa-option>'
      '</wa-select>'
      '<wa-button id="themebtn" size="s" appearance="outlined">'
      '<wa-icon name="circle-half-stroke" label="Light or dark (or press t)"></wa-icon>'
      '</wa-button>'
      '</div>')
    A('<input id="filter" placeholder="Filter  (press /)" autocomplete="off">')
    # **The two page anchors are not documents.** They used to sit at the head of
    # the list wearing the same shape as `Gameplan.md`, which made a reader count
    # ten Docket documents where there are eight. They are page furniture, so they
    # get a plain row above the list and no chevron.
    A('<div class="jumps">'
      '<a href="#top">Front matter</a><a href="#index">Code index</a></div>')
    A('<ul class="tree">')
    _group = None
    for rel, label, aid, _ in DOCS:
        # Eight documents, then the chapters. One flat run of thirty-three made
        # the chapters look like more Docket documents rather than the long form
        # underneath them.
        kind = "chapters" if aid.startswith("ch-") else "docket"
        if kind != _group:
            _group = kind
            A('<li class="grouphead">%s</li>'
              % ("The Docket" if kind == "docket" else "Chapters — the long form"))
        items = outlines[rel]
        red = sum(u[0] for _l, _t, _s, _d, u in items if _l == 2)
        amber = sum(u[1] for _l, _t, _s, _d, u in items if _l == 2)
        # `open_questions.md` is the one a reader is most often coming for, and
        # it is the one carrying the chips. It opens; the rest wait to be asked.
        _openattr = " open" if rel.endswith("open_questions.md") else ""
        A(f'<li class="doc"><wa-details class="docd"{_openattr} summary="">'
          f'<span slot="summary" class="dsum">'
          # **Which line is bold depends on which one identifies the thing.**
          # For the eight, the kicker is a role — *Why*, *What order* — and the
          # filename is the name, so the filename leads. For a chapter the title
          # IS the name and the filename is a coordinate, so they swap. Bolding
          # the filename on both made twenty-five chapters look like one list of
          # near-identical files.
          f'<span class="dlab">'
          f'<small>{html.escape(label if kind == "docket" else Path(rel).name)}</small>'
          f'<b>{html.escape(Path(rel).name if kind == "docket" else label)}</b></span>'
          f'{chips(red, amber)}</span>')
        A(f'<a class="jump" href="#{aid}">Open this document</a>')
        if items:
            A('<ul class="heads">')
            open3 = False
            for lvl, title, sl, _desc, urg in items:
                if lvl == 3 and not open3:
                    A("<ul>")
                    open3 = True
                elif lvl == 2 and open3:
                    A("</ul>")
                    open3 = False
                g, rest = split_glyph(title)
                gl = f'<span class="g">{g}</span>' if g else ""
                A(f'<li><a href="#{aid}-{sl}">{gl}{html.escape(rest)}'
                  f'{chips(*urg) if lvl == 2 else ""}</a></li>')
            if open3:
                A("</ul>")
            A("</ul>")
        A("</wa-details></li>")
    A("</ul>")
    A('<p class="railkey">A red chip is blocking work now; amber is needed soon. '
      'The number is how many sit under that heading.</p>')
    A("</nav><main id='top'>")

    # ── front matter ──
    # The name first and largest; what the page *is* goes above it in small
    # caps, and the provenance — framework version, build date — below.
    A('<div class="hero">'
      '<p class="tag">The Docket &middot; the planning documents</p>'
      f'<h1>{html.escape(PROJECT)}</h1>'
      f'<p class="made">{html.escape(FRAMEWORK_LINE)} &middot; '
      f'generated {date.today()}</p>')
    A("".join(f"<p>{html.escape(p.strip())}</p>"
              for p in RATIONALE.strip().split("\n\n")))
    A('<ul class="stats">'
      f'<li><b>{len(DOCS)}</b><span>documents</span></li>'
      f'<li><b>{len(codes)}</b><span>codes</span></li>'
      f'<li><b>{sum(1 for k in codes.values() if k[0]=="decision")}</b><span>decisions</span></li>'
      f'<li><b>{q_open}</b><span>open questions</span></li>'
      f'<li><b>{q_done}</b><span>answered</span></li>'
      f'<li><b>{sum(1 for k in codes.values() if k[0]=="lesson")}</b><span>lessons</span></li>'
      "</ul></div>")

    A('<h2 class="section">How it is kept</h2>')
    A("<p>Loosely after the TASB policy manuals — coded sections, a permanent "
      "numbering, and an index that makes a topic followable across every "
      "volume that touches it.</p>")
    for t, d in PRACTICES:
        A(f'<div class="practice"><b>{t}.</b> {d}</div>')

    A('<h2 class="section">Markers</h2><ul class="markers">')
    for gl, meaning in MARKERS:
        A(f"<li>{gl} &nbsp;{html.escape(meaning)}</li>")
    A("</ul>")

    # ── TOC with descriptions ──
    A('<h2 class="section">Contents</h2>')
    A('<details class="toc" open><summary>Every heading, with what it holds</summary>'
      '<div class="body">')
    for rel, label, aid, blurb in DOCS:
        A(f'<div class="d"><a href="#{aid}">{html.escape(rel)}</a> '
          f'<span class="codes"><span class="kind">{html.escape(label)}</span></span>'
          f"<p>{html.escape(blurb)}</p><ul>")
        for lvl, title, sl, desc, _urg in outlines[rel]:
            cls = "l3" if lvl == 3 else ""
            d = f"<em>{html.escape(desc)}</em>" if desc else ""
            A(f'<li class="{cls}"><a href="#{aid}-{sl}">{html.escape(title)}</a>{d}</li>')
        A("</ul></div>")
    A("</div></details>")

    # ── code index ──
    A('<h2 class="section" id="index">The code index</h2>')
    A("<p>Every code the Docket defines, and every document that mentions it. "
      "This is what the shared vocabulary buys: a topic followed across all "
      "eight documents.</p>")
    roots = domain_labels(present["features_and_functions.md"])
    tree, orphans = build_code_tree(codes, roots)

    def emit(node, cls=""):
        c = node["code"]
        kind, meaning = codes.get(c, ("domain", node.get("label", "")))
        links = "".join(f'<a href="#{aid}">{html.escape(lbl)}</a>'
                        for aid, lbl in where.get(c, [])) or ""
        A(f'<li class="{cls}"><div class="row"><span class="c">{html.escape(c)}</span>'
          f'<span class="m">{html.escape(meaning)}</span>'
          f'<span class="w">{links}</span></div>')
        if node["kids"]:
            A("<ul>")
            for k in node["kids"]:
                emit(k)
            A("</ul>")
        A("</li>")

    A('<ul class="ctree">')
    for r in tree:
        emit(r, "root")
    if orphans:
        A('<li class="root"><div class="row"><span class="c">&mdash;</span>'
          '<span class="m">Codes with no parent domain</span></div><ul>')
        for c in orphans:
            emit({"code": c, "kids": []})
        A("</ul></li>")
    A("</ul>")

    # ── the documents ──
    for rel, label, aid, blurb in DOCS:
        A(f'<article id="{aid}"><div class="head"><b>{html.escape(rel)}</b>'
          f"<span>{html.escape(label)}</span></div>")
        body = render(present[rel])
        body = re.sub(r'<h([23]) id="([^"]+)"', rf'<h\1 id="{aid}-\2"', body)
        A(body)
        A("</article>")

    A('<a class="top" href="#top">↑ top</a>')
    A(f"</main></wa-page><script type='module'>{JS}</script>")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        '<!doctype html><html lang="en"><head>'
        '<meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        + HEAD_EXTRA +
        f"<title>The Docket — {html.escape(PROJECT)}</title></head><body>\n"
        + "\n".join(P) + "\n</body></html>",
        encoding="utf-8")
    kb = OUT.stat().st_size / 1024
    print(f"  {OUT.relative_to(ROOT)}  —  {len(DOCS)} documents, "
          f"{len(codes)} codes, {kb:.0f} KB")
    missing = [r for r, s in present.items() if not s]
    if missing:
        print("  MISSING: " + ", ".join(missing), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
