#!/usr/bin/env python3
"""The Docket dashboard — a local server for the project you are working on.

    ./scripts/docket-server.py            # http://127.0.0.1:7373
    ./scripts/docket-server.py --port 8080

**This runs shell commands.** That is the point — a page that cannot build,
check or commit is a document, not a dashboard — but it means the design has to
be deliberate:

  * bound to 127.0.0.1, never 0.0.0.0
  * an explicit allowlist of actions; anything else is refused
  * started by hand, and not left running

## What it does, and what it deliberately does not

**Answers are captured, not filed.** Answering a question here appends to
`docket-inbox.md`. It does not rewrite `open_questions.md`, because filing an
answer properly means marking it ✅, recording the decision in `Gameplan.md`,
removing the ❓ markers from every affected code and moving the entry to the
archive — judgement the agent should exercise, not a form post.

The division: **you answer, the agent files.** The value is that the answer
becomes durable the moment you think of it, instead of waiting for a session.
"""
import argparse
import json
import os
import re
import socket
import subprocess
import sys
import threading
import time
import uuid
import webbrowser
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
#: Where the skill itself lives. A project that adopted the Docket gets its own
#: copy of the scripts, so ROOT and HERE are the same; a project running the
#: skill in place keeps its documents in ROOT and its assets here.
HERE = ROOT
#: **Every inbox call names its encoding, and that is not fussiness.**
#: Without `encoding=`, Python uses `locale.getpreferredencoding()` — **cp1252
#: on a Windows box and UTF-8 on a Mac**. `docket-inbox.md` is a shared file in
#: a shared folder, so it became a different file depending on who touched it
#: last: creating it on Windows raises `UnicodeEncodeError` outright, and
#: reading a Mac-written one there dies on `0xb7` — a `·`. Found in RainZips,
#: 2026-09-21, and fixed here rather than there because a project that patches
#: its own copy of a framework file is pinned to that copy forever.
INBOX = ROOT / "docket-inbox.md"

sys.path.insert(0, str(ROOT / "scripts"))

#: **The theme and the version are shared, and optional.** Both live in modules
#: that arrive with an update, so a project that has not updated yet must still
#: get a working dashboard — losing the console because a project is on an older
#: framework is precisely the failure the version display exists to prevent.
try:
    import docket_theme
except ImportError:
    docket_theme = None
try:
    import docket_version
except ImportError:
    docket_version = None

# Only these run. A dashboard that can run anything is a remote shell with a
# nice font.
ACTIONS = {
    "check":  ["./scripts/check-docs.sh"],
    "viewer": ["./scripts/docket.sh", "--build"],
    "test":   ["npm", "test"],
    "build":  ["npm", "run", "build"],
    "status": ["git", "status", "--short"],
    "diff":   ["git", "diff", "--stat"],
}


# ── reading the Docket ───────────────────────────────────────────────────────
def read(name):
    f = ROOT / name
    return f.read_text() if f.exists() else ""


def plain(text):
    """Markdown to something a dashboard can show without a renderer."""
    text = re.sub(r"`([^`]*)`", r"\1", text)
    text = re.sub(r"\*\*([^*]*)\*\*", r"\1", text)
    text = re.sub(r"\*([^*]*)\*", r"\1", text)
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    return re.sub(r"\s+", " ", text).strip()


def questions():
    """Open questions, with their priority and working assumption."""
    text = read("open_questions.md")
    out, priority = [], "⚪"
    for block in re.split(r"\n(?=### Q-)", text):
        m = re.match(r"### (Q-\d+)\s*—\s*(.+)", block)
        for mark in ("🔴", "🟡", "⚪"):
            if f"## {mark}" in text[: text.find(block)] if block in text else False:
                pass
        if not m:
            continue
        body = block[m.end():]
        assumption = ""
        a = re.search(r"\*\*Working assumption:\*\*\s*(.+?)(?:\n\n|\Z)", body, re.S)
        if a:
            assumption = plain(a.group(1))[:400]
        # The line reads "**Affects:** X, Y · **Status:** open" — take only the
        # first half; the status is shown by the priority pill already.
        affects = re.search(r"\*\*Affects:\*\*\s*(.+?)(?:·\s*\*\*Status|\n|$)", body)
        out.append({
            "code": m.group(1),
            "title": plain(m.group(2)),
            "assumption": assumption,
            "affects": plain(affects.group(1)) if affects else "",
        })
    return out


def priorities():
    """Which bucket each question sits in."""
    text = read("open_questions.md")
    out = {}
    for mark, name in (("🔴", "blocking"), ("🟡", "soon"), ("⚪", "whenever")):
        i = text.find(f"## {mark}")
        if i < 0:
            continue
        j = min([k for k in (text.find("\n## ", i + 1),) if k > 0] or [len(text)])
        for m in re.finditer(r"### (Q-\d+)", text[i:j]):
            out[m.group(1)] = name
    return out


def project_name():
    """What this project calls itself: the README's first heading, else the
    directory. One definition, because three pages show it."""
    m = re.search(r"^#\s+(.+)", read("README.md"), re.M)
    return m.group(1).strip() if m else ROOT.name


#: **What this process actually loaded, and when.** Python holds a module in
#: memory; editing the file on disk changes nothing for a server already
#: running. So an update lands, the owner reloads the page, and the new surface
#: is not there — with no way to tell that from a broken feature. It happened
#: within two minutes of shipping one: the server had started at 18:52 and the
#: file changed at 18:54.
STARTED_AT = time.time()
try:
    LOADED_MTIME = os.path.getmtime(os.path.abspath(__file__))
except OSError:
    LOADED_MTIME = 0
LOADED_VERSION = (docket_version.installed_version(ROOT)
                  if docket_version else None)


def staleness():
    """Is this process older than the code it was started from?"""
    try:
        now_m = os.path.getmtime(os.path.abspath(__file__))
    except OSError:
        now_m = LOADED_MTIME
    now_v = docket_version.installed_version(ROOT) if docket_version else None
    stale = now_m > LOADED_MTIME + 1 or (now_v and now_v != LOADED_VERSION)
    return {"stale": bool(stale), "loaded": LOADED_VERSION, "now": now_v,
            "started": STARTED_AT,
            "why": "This server is running the code as it was when it started."
                   " The project has been updated since. Restart it to pick the"
                   " change up." if stale else ""}


def state():
    ch = read("CHANGELOG.md")
    cur = re.search(r"\*\*Current:\s*([^*]+?)\*\*", ch)
    qs, pri = questions(), priorities()
    for q in qs:
        q["priority"] = pri.get(q["code"], "whenever")
    return {
        "project": project_name(),
        "current": cur.group(1).strip() if cur else "—",
        "questions": qs,
        "counts": {
            "decisions": len(re.findall(r"^\|\s*~*K[A-Z]{0,3}", read("Gameplan.md"), re.M)),
            "lessons": len(re.findall(r"^## LE-\d+", read("lessons_learned.md"), re.M)),
            "open": len(qs),
            "answered": len(re.findall(r"^### Q-\d+ ✅", read("answered_questions.md"), re.M)),
        },
        "inbox": INBOX.read_text(encoding="utf-8") if INBOX.exists() else "",
        "actions": sorted(ACTIONS),
        # **Which Docket this project is on, and whether that is the current
        # one.** It rides along with the state every page already fetches
        # rather than getting an endpoint of its own: a version nobody looks up
        # is a version nobody knows, and one more request is one more thing to
        # forget to make.
        "docket": docket_version.status(ROOT) if docket_version else None,
        # Which project this server is serving. It is how a second server,
        # starting up, tells "mine, already running" from "somebody else's".
        "root": str(ROOT),
        # For the console's Docket card: whether there is anything to open.
        "built": ("%d decisions, %d lessons recorded"
                  % (len(re.findall(r"^\|\s*~*K[A-Z]{0,3}", read("Gameplan.md"), re.M)),
                     len(re.findall(r"^## LE-\d+", read("lessons_learned.md"), re.M)))
                  if (ROOT / "docs" / "docket.html").exists()
                  else "not built yet — run ./scripts/docket.sh --build"),
    }


# ── writing to the inbox ────────────────────────────────────────────────────
def append_inbox(kind, code, text):
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    if not INBOX.exists():
        INBOX.write_text(
            "# Docket inbox\n\n"
            "**Captured from the dashboard, waiting for the agent to file.**\n\n"
            "Answers and ideas land here the moment they are thought of. The next\n"
            "session reads this file, files each entry properly — a decision into\n"
            "`Gameplan.md`, an answer marked ✅ with its ❓ markers removed, an idea\n"
            "as a 💡 code — and then clears the entry.\n\n"
            "*Nothing here is filed yet. That is the whole point of it being here.*\n\n---\n",
            encoding="utf-8", newline="")
    head = f"### {kind} · {code} · {stamp}" if code else f"### {kind} · {stamp}"
    with INBOX.open("a", encoding="utf-8", newline="") as f:
        f.write(f"\n{head}\n\n{text.strip()}\n")
    return True


#: Cards every Docket project has. The project declares only its own surfaces;
#: these are the framework's, so no project has to describe them.
#:
#: **A surface added here is added for every project.** One was once declared
#: only in the *master's* own `.docket-surfaces.json` — which is the master's
#: project file and is deliberately never shipped — so every other project
#: received the page, the route and the gate, and no way to find any of them.
#: A surface that is the framework's belongs in this list, not in the
#: master's. (`LE-22`)
BUILT_IN = [
    {"key": "TheDocket", "label": "The Docket", "path": "/docket", "tone": "cyan",
     "group": "Read it",
     "note": "All the planning documents in one page — what was decided and why, "
             "what broke, what shipped. Counters show which sections hold open "
             "questions.",
     "start": "./scripts/docket.sh --build"},
    {"key": "Openquestions", "label": "Open questions", "path": "/questions",
     "tone": "purple", "group": "Decide it",
     "note": "Everything still waiting on an answer, sorted by urgency, by how "
             "recently it was asked, or by number. Answer one here and it is "
             "stored straight away."},
    {"key": "Capture", "label": "Capture", "path": "/dashboard", "tone": "gray",
     "group": "Note it",
     "note": "Somewhere to put an answer or an idea the moment you have it, and "
             "buttons that run this project's own scripts.",
     "start": ""},
]


def surfaces_config():
    """What this project is building, as it declared it. Never raises.

    A console whose config has a typo should still show the Docket and the
    questions — losing the front door because one JSON comma moved is a bad
    trade. A broken file is reported in the payload instead.
    """
    f = ROOT / ".docket-surfaces.json"
    if not f.exists() and (ROOT / ".codex-surfaces.json").exists():
        f = ROOT / ".codex-surfaces.json"          # pre-3.0.0, still honoured
    if not f.exists():
        return {}, None
    try:
        cfg = json.loads(f.read_text(encoding="utf-8"))
        if not isinstance(cfg, dict):
            raise ValueError("top level is not an object")
        return cfg, None
    except (ValueError, OSError) as exc:
        return {}, "%s: %s" % (f.name, exc)


def _probe(url):
    """Is something there? Returns (reachable, note) — never a bare bool.

    **`F-05`.** This reported a live site as dead and swallowed the reason. The
    site answered `302` in 0.45s; the probe said `False` in 0.23s and the card
    read "not running" beside a start command that would not have helped.

    Three faults, and the first two are the same fault the old code's own comment
    described but did not implement:

    1. **An HTTP error answer is still an answer — except 404.** The old line read
       `return 200 <= e.code < 400  # a 403 still proves a server is up` — and
       `200 <= 403 < 400` is False, so a 403 was reported as nothing there.
       **But the opposite over-correction is worse**: accepting *any* status
       makes a 404 count, and the first local server that happens to be running
       — serving a different project entirely — claims every surface and every
       card links at its 404. 404/410 is a server saying "not mine"; take it at
       its word. Everything else that answers is here.
    2. **A redirect to a login page is a live site, not a dead one.** `urlopen`
       follows redirects, so a gated surface ends on whatever the gate serves —
       here a `/login` that answers `501` to a HEAD. The destination's opinion of
       HEAD is not evidence about the surface.
    3. **`except Exception: return False`** labelled the catch with the reason its
       author had in mind. On a python.org macOS build with no CA bundle wired,
       *every* HTTPS URL raises `CERTIFICATE_VERIFY_FAILED` — `example.com`
       included — and all of it became the word "not running".

    So a certificate that will not verify is now **reported, not silently
    believed**: the probe retries once without verification and says so, and the
    card reads "live site (unverified TLS)". Reading nothing but a status line,
    sending no credentials, to decide which of two links to draw, that is a fair
    trade — but it is a fact about the machine, and it is visible.
    """
    import ssl
    import urllib.error
    import urllib.request

    host = (urlparse(url).hostname or "").lower()
    local = host in ("127.0.0.1", "localhost", "::1")
    # A remote TLS handshake plus a redirect does not fit in the local budget.
    timeout = 1.2 if local else 3.0

    def attempt(ctx):
        req = urllib.request.Request(url, method="HEAD")
        try:
            with urllib.request.urlopen(req, timeout=timeout, context=ctx):
                return True, ""
        except urllib.error.HTTPError as e:
            # An answer proves a *server* is up; it does not prove this *surface*
            # is on it. 404/410 is that server saying "not mine" — take it at its
            # word and try the next base, or the card links confidently at
            # somebody else's 404. Everything else that answers (401, 403 behind
            # a gate; 405/501 refusing HEAD; 5xx broken but present) is here.
            return e.code not in (404, 410), ""
        except urllib.error.URLError as e:
            # Raise the *reason*, not the URLError: a bare `raise` here re-raises
            # the wrapper, which the caller's SSLCertVerificationError handler
            # does not catch, and the retry never happens.
            if isinstance(e.reason, ssl.SSLCertVerificationError):
                raise e.reason from e
            return False, ""

    try:
        return attempt(None)
    except ssl.SSLCertVerificationError:
        pass

    try:
        return attempt(ssl._create_unverified_context())[0], "unverified TLS"
    except Exception:
        return False, ""


def _reachable(url):
    """Kept for callers that only want the yes or no."""
    return _probe(url)[0]


def locate(path, cfg, ours):
    """Where a surface actually is right now, checked rather than assumed.

    Order: this server, then each `also_local` base, then the live site. The
    browser cannot make this call itself — a cross-origin `fetch` to
    `127.0.0.1:8000` comes back opaque, and `no-cors` cannot tell a 200 from a
    refused connection — so it is done here, where it is one socket.
    """
    if path in ours:
        return "this server", path
    for base in cfg.get("also_local") or []:
        base = str(base).rstrip("/")
        ok, note = _probe(base + path)
        if ok:
            where = "another local server"
            return (where + " (%s)" % note if note else where), base + path
    live = (cfg.get("live") or "").rstrip("/")
    if live:
        ok, note = _probe(live + path)
        if ok:
            where = "live site"
            return (where + " (%s)" % note if note else where), live + path
    return "not running", None


def console_payload(ours):
    """The whole page, resolved: built-ins first, then the project's own."""
    cfg, broken = surfaces_config()
    out = []
    for s in BUILT_IN:
        where, href = locate(s["path"], {}, ours)
        out.append(dict(s, where=where, href=href or s["path"],
                        start=s.get("start", "")))
    for s in cfg.get("surfaces") or []:
        path = s.get("path")
        label = s.get("label")
        if not path or not label:
            continue          # the gate reports these; the page just skips them
        where, href = locate(path, cfg, ours)
        out.append({"key": s.get("key") or label, "label": label,
                    "path": path, "tone": s.get("tone") or "blue",
                    "group": s.get("group") or "", "note": s.get("note") or "",
                    "start": s.get("start") or "",
                    "where": where, "href": href or path})
    # **The same name as every other page.** This fell back to the directory
    # name while the dashboard and the questions page read the README's title,
    # so one project could be "Tideline" on two pages and "fresh" on the third —
    # and the name is the whole point of the masthead.
    return {"project": cfg.get("project") or project_name(),
            "docket": docket_version.status(ROOT) if docket_version else None,
        # Which project this server is serving. It is how a second server,
        # starting up, tells "mine, already running" from "somebody else's".
        "root": str(ROOT),
            "lede": cfg.get("lede") or
                    "These run on this machine, against files and logins that "
                    "exist only here.",
            "surfaces": out, "config_error": broken}


def _questions():
    """`docket_questions`, or None. **Never raises** — a project that has not
    adopted the questions console must still get a dashboard."""
    try:
        import sys
        sys.path.insert(0, str(HERE / "scripts"))
        sys.path.insert(0, str(ROOT / "scripts"))
        import docket_questions
        return docket_questions
    except Exception:
        return None


def _projects():
    """`docket-projects`, or None. **Never raises**, like `_questions`.

    Loaded by path rather than imported: the file has a hyphen in its name, so
    it is not a legal module name — and it is master-only, so on a project this
    simply comes back None and the route says so.
    """
    try:
        import importlib.util
        import sys
        sys.path.insert(0, str(HERE / "scripts"))
        sys.path.insert(0, str(ROOT / "scripts"))
        for base in (HERE, ROOT):
            f = base / "scripts" / "docket-projects.py"
            if f.exists():
                spec = importlib.util.spec_from_file_location("docket_projects", f)
                m = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(m)
                return m
        return None
    except Exception:
        return None


#: The way back, added to the Docket viewer **only while this server is serving
#: it**. The built file carries an empty `<!--{{DOCKET_NAV}}-->` comment and
#: nothing else: opened from Finder, mailed to somebody, or kept after the
#: project is gone, it has no dashboard to return to and no business implying
#: there is one. Served over HTTP, there is — so the server puts it in.
#:
#: Styled from the viewer's own tokens rather than the dashboard's, because it
#: has to sit inside whichever of the viewer's four looks is active.
VIEWER_NAV = (
    '<span class="docket-back">'
    '<a href="/" title="The console — everything this project runs">&#8249; Console</a>'
    '<a href="/dashboard" title="Capture an answer or an idea">Capture</a>'
    '<a href="/questions" title="Everything waiting on a decision">Questions</a>'
    '</span>'
    '<style>'
    '.docket-back{display:inline-flex;align-items:baseline;gap:.75rem;'
    'margin-inline-end:.85rem;padding-inline-end:.85rem;'
    'border-inline-end:1px solid var(--edge,#ccc);'
    'font-family:var(--f-mono,ui-monospace,monospace);font-size:.74rem;'
    'letter-spacing:.06em;text-transform:uppercase;white-space:nowrap}'
    '.docket-back a{color:var(--soft,#666);text-decoration:none}'
    '.docket-back a:hover{color:var(--bright,#000);text-decoration:underline}'
    '@media(max-width:700px){.docket-back a:not(:first-child){display:none}}'
    '</style>'
)


def viewer_page(f):
    """The built viewer, with the way back put in.

    A viewer built before this placeholder existed simply has nothing to
    replace, and is served exactly as it was — no error, no missing link that
    somebody has to go and diagnose.
    """
    text = f.read_text(encoding="utf-8")
    return text.replace("<!--{{DOCKET_NAV}}-->", VIEWER_NAV).encode("utf-8")


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype="application/json"):
        raw = body if isinstance(body, bytes) else body.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _page(self, name):
        """A dashboard page with the theme filled in, or None if it is missing.

        **The theme is one file, and the pages are holes in it.** Each page
        carries `<!--{{WA_HEAD}}-->` and `docket_theme` fills it with the
        stylesheets, the fonts, the tokens and the light/dark restore — so
        re-theming three pages is one edit rather than three that drift. The kit
        inside it is per-owner and resolved the same way the viewer resolves it,
        which is why neither surface hardcodes one.
        """
        for f in (HERE / "dashboard" / name, ROOT / "dashboard" / name):
            if f.exists():
                text = f.read_text(encoding="utf-8")
                if docket_theme:
                    text = docket_theme.apply(text, ROOT, (HERE,))
                return text.encode("utf-8")
        return None

    def do_GET(self):
        path = urlparse(self.path).path
        # **The console is the front door.** It is the page to open when a
        # session starts, so it holds `/`; the capture dashboard keeps its own
        # address and is linked from it as a card.
        if path in ("/", "/console"):
            page = self._page("console.html") or self._page("index.html")
            return self._send(200, page or STUB, "text/html; charset=utf-8")
        # **Through `_page`, like every other page.** This route used to serve a
        # string read once at startup, which meant it was the one page the theme
        # was never injected into — it rendered unstyled while the console and
        # the questions page looked right, and the cause was a route, not CSS.
        if path in ("/dashboard", "/index.html"):
            page = self._page("index.html")
            return self._send(200, page or STUB, "text/html; charset=utf-8")

        if path == "/api/surfaces":
            ours = {r for r in ("/docket", "/questions", "/dashboard", "/projects")}
            if not (ROOT / "docs" / "docket.html").exists():
                ours.discard("/docket")
            return self._send(200, json.dumps(console_payload(ours)))

        if path == "/api/state":
            s = state()
            if isinstance(s, dict):
                s["staleness"] = staleness()
            return self._send(200, json.dumps(s))

        if path == "/api/staleness":
            return self._send(200, json.dumps(staleness()))
        if path in ("/docket.html", "/docket"):
            f = ROOT / "docs" / "docket.html"
            if f.exists():
                return self._send(200, viewer_page(f), "text/html; charset=utf-8")
            return self._send(404, json.dumps({"error": "Build it first — ./scripts/docket.sh --build"}))

        # ── the fleet ────────────────────────────────────────────────────
        # **Master-only, and it says so rather than 404ing.** A project that
        # declares this surface and gets "not found" back looks broken; the
        # honest answer is that the question cannot be asked from here.
        if path == "/projects":
            if not (docket_version and docket_version.is_master(ROOT)):
                return self._send(404, json.dumps({
                    "error": "the fleet is the master's. Run this from the "
                             "Docket skill, normally ~/Projects/docket."}))
            page = self._page("projects.html")
            if page is None:
                return self._send(404, json.dumps({"error": "projects.html missing"}))
            return self._send(200, page, "text/html; charset=utf-8")

        if path == "/api/projects":
            if not (docket_version and docket_version.is_master(ROOT)):
                return self._send(404, json.dumps({
                    "error": "the fleet is the master's."}))
            rp = _projects()
            if rp is None:
                return self._send(503, json.dumps(
                    {"error": "docket-projects unavailable"}))
            # Always walk. The cache was read here once, and the page then
            # showed a project's old version minutes after it had been updated.
            rows = rp.scan()
            rp.save(rows)
            for r in rows:
                r["missing"] = not Path(r["path"]).is_dir()
            return self._send(200, json.dumps({
                "current": docket_version.framework_version() if docket_version
                           else "?", "projects": rows}))

        # ── the questions console ────────────────────────────────────────
        if path == "/questions":
            page = self._page("questions.html")
            if page is None:
                return self._send(404, json.dumps({"error": "questions.html missing"}))
            return self._send(200, page, "text/html; charset=utf-8")

        if path == "/api/questions":
            rq = _questions()
            if rq is None:
                return self._send(503, json.dumps({"error": "docket_questions unavailable"}))
            ans = {}
            for a in rq.answers():
                ans.setdefault(a["code"], []).append(a)
            qs = rq.questions(include_answered=True)
            for q in qs:
                q["answers"] = ans.get(q["code"], [])
                q["has_answer"] = bool(q["answers"])
                q["decided"] = any(x.get("decided") for x in q["answers"])
            return self._send(200, json.dumps({"summary": rq.summary(),
                                               "questions": qs}))
        return self._send(404, json.dumps({"error": "not found"}))

    def do_POST(self):
        path = urlparse(self.path).path
        n = int(self.headers.get("Content-Length") or 0)
        try:
            data = json.loads(self.rfile.read(n) or b"{}")
        except ValueError:
            return self._send(400, json.dumps({"error": "bad json"}))

        if path == "/api/capture":
            kind = data.get("kind", "Note")
            if kind not in ("Answer", "Idea", "Note"):
                return self._send(400, json.dumps({"error": "unknown kind"}))
            text = (data.get("text") or "").strip()
            if not text:
                return self._send(400, json.dumps({"error": "empty"}))
            append_inbox(kind, data.get("code", ""), text)
            return self._send(200, json.dumps({"ok": True, "inbox": INBOX.read_text(encoding="utf-8")}))

        # An answer recorded here is **captured, never filed**. Writing it into
        # the Docket means marking the entry, clearing the ❓ from every code it
        # touched and moving it across — cross-file work that needs judgement.
        # `check_answer_inbox.py` fails the Docket check until somebody does it.
        if path.startswith("/api/questions/") and path.endswith("/answer"):
            rq = _questions()
            if rq is None:
                return self._send(503, json.dumps({"error": "docket_questions unavailable"}))
            code = path.split("/")[3]
            try:
                rec = rq.record_answer(code, data.get("answer"),
                                       data.get("decided"),
                                       data.get("author") or "owner")
            except ValueError as exc:
                return self._send(400, json.dumps({"error": str(exc)}))
            return self._send(200, json.dumps(rec))

        if path == "/api/update-report":
            # **Report only. This endpoint can never apply anything.**
            #
            # `--apply` is not passed and is not accepted as input, so there is
            # no argument a browser can send that makes this write. The console
            # tells you what a release contains; only the updater can tell you
            # what it would do to *this* project — which files it would touch,
            # which you have edited, and what it cannot do for itself.
            #
            # Taking the update stays a terminal act. The fleet page has said
            # why since it was written: a lot of irreversible work behind one
            # click, against an updater whose whole discipline is that you read
            # the report first. Reading it is the half worth making easy.
            updater = Path.home() / ".claude" / "skills" / "docket" \
                / "scripts" / "docket-update.py"
            if not updater.exists():
                updater = ROOT / "scripts" / "docket-update.py"
            if not updater.exists():
                return self._send(200, json.dumps(
                    {"ok": False, "out": "no updater on this machine"}))
            try:
                p = subprocess.run(
                    [sys.executable, str(updater), "--project", str(ROOT)],
                    cwd=str(ROOT), capture_output=True, text=True, timeout=300)
                return self._send(200, json.dumps(
                    {"ok": p.returncode == 0,
                     "out": (p.stdout + p.stderr)[-40000:]}))
            except subprocess.TimeoutExpired:
                return self._send(200, json.dumps({"ok": False, "out": "timed out"}))
            except Exception as e:                           # noqa: BLE001
                return self._send(200, json.dumps({"ok": False, "out": str(e)}))

        if path == "/api/run":
            name = data.get("action")
            if name not in ACTIONS:
                # An allowlist is the whole security model; say so plainly.
                return self._send(403, json.dumps(
                    {"error": f"'{name}' is not an allowed action",
                     "allowed": sorted(ACTIONS)}))
            try:
                p = subprocess.run(ACTIONS[name], cwd=ROOT, capture_output=True,
                                   text=True, timeout=900)
                return self._send(200, json.dumps(
                    {"ok": p.returncode == 0, "code": p.returncode,
                     "out": (p.stdout + p.stderr)[-20000:]}))
            except subprocess.TimeoutExpired:
                return self._send(200, json.dumps({"ok": False, "out": "timed out after 15 minutes"}))
            except FileNotFoundError as e:
                return self._send(200, json.dumps({"ok": False, "out": str(e)}))

        return self._send(404, json.dumps({"error": "not found"}))



# ── Finding a port ──────────────────────────────────────────────────────────
#: How many ports to try after the preferred one before giving up on the range.
PORT_SEARCH = 20


def port_is_free(port):
    """Can we actually bind it? Asked by binding, not by asking the OS.

    `HTTPServer` sets `allow_reuse_address`, which lets a socket bind over one
    left in TIME_WAIT but **not** over a live listener — so a failed bind is a
    reliable "something is listening here", and a successful one is a port we
    can have. Anything cleverer (parsing `lsof`, reading `/proc`) is slower and
    answers a different question.
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        sock.bind(("127.0.0.1", port))
        return True
    except OSError:
        return False
    finally:
        sock.close()


def whats_on(port):
    """Who holds this port: a Docket server for which project, or something else.

    Returns the project root as a string, `"other"` for anything that is not a
    Docket server, or `None` when nothing answers. **Never raises and never waits
    long** — this runs before the server starts, and a slow probe here is a
    slow startup every time.
    """
    import urllib.error
    import urllib.request
    try:
        with urllib.request.urlopen("http://127.0.0.1:%d/api/state" % port,
                                    timeout=0.6) as r:
            root = json.loads(r.read() or b"{}").get("root")
            return root or "other"
    except (urllib.error.URLError, ValueError, OSError):
        return "other"


def choose_port(preferred):
    """A port we can bind, and what to say about it.

    Returns `(port, note, mine)`. `mine` is the URL of a Docket server **already
    serving this same project**, in which case the caller should point at it
    rather than start a second one: two servers on one project is two dashboards
    writing to one inbox, and the second is invisible to whoever is looking at
    the first.
    """
    if port_is_free(preferred):
        return preferred, "", None

    held_by = whats_on(preferred)
    if held_by == str(ROOT):
        return None, "", "http://127.0.0.1:%d" % preferred

    if held_by == "other":
        note = "port %d is taken by something that is not a Docket server" % preferred
    else:
        note = "port %d is serving %s" % (preferred, held_by)

    for port in range(preferred + 1, preferred + 1 + PORT_SEARCH):
        if port_is_free(port):
            return port, note, None

    # Everything in the range is busy; let the OS hand out whatever is free.
    # **Better an odd port than a refusal**: the alternative is telling somebody
    # to go and find a free port by hand, which is this function's whole job.
    return 0, note + "; and the %d ports after it" % PORT_SEARCH, None


#: Shown only when `dashboard/index.html` is not installed at all. **The capture
#: dashboard is one card, not the whole server** — refusing to start without it
#: would take the console, the Docket and the questions down with it, which is a
#: poor trade for a page that is optional.
STUB = ("<!doctype html><meta charset=utf-8><title>Capture</title>"
        "<p>dashboard/index.html is not installed. "
        "Run <code>./scripts/docket.sh --update --apply</code>, or "
        "<a href=\"/\">go back to the console</a>.")


def main():
    ap = argparse.ArgumentParser(description="The Docket dashboard, locally.")
    ap.add_argument("--port", type=int, default=7373)
    ap.add_argument("--no-open", action="store_true")
    args = ap.parse_args()

    if not any((base / "dashboard" / "index.html").exists()
               for base in (ROOT, HERE)):
        print("note: dashboard/index.html not installed — /dashboard is a stub",
              file=sys.stderr)

    # **Never collide, and never start a second server for the same project.**
    # The default port is the same in every project, so two of them open at once
    # is the normal case rather than the exception.
    port, note, mine = choose_port(args.port)
    if mine:
        print("Already running — %s" % mine)
        print("  project : %s" % ROOT)
        print("  A second server for the same project would mean two dashboards")
        print("  writing to one inbox, and the second invisible to whoever is")
        print("  looking at the first. Opening the one that is already up.")
        if not args.no_open:
            webbrowser.open(mine)
        return 0

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    port = server.server_address[1]          # 0 means "whatever the OS gave us"
    url = f"http://127.0.0.1:{port}"
    print(f"Console — {url}")
    if note:
        print(f"  note    : {note} — moved here")
    print(f"  project : {ROOT}")
    print(f"  actions : {', '.join(sorted(ACTIONS))}")
    print( "  bound to 127.0.0.1 only. Ctrl-C to stop.")
    # **Say it before serving, not after.** Python line-buffers stdout when it
    # is a terminal and block-buffers it when it is a pipe or a file — so
    # `docket-server.py > log &`, which is how this is usually started in the
    # background, held the whole banner in a buffer until the process exited.
    # The one line telling you which port it actually chose is the line you
    # need *while* it runs.
    sys.stdout.flush()
    if not args.no_open:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
