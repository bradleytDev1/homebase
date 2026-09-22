#!/usr/bin/env python3
"""The Docket's look, resolved in one place.

Two things every Docket surface needs and neither should work out for itself:

    kit()    which Web Awesome kit this project loads components from
    head()   the theme block — stylesheets, fonts, tokens, light/dark

Both the viewer (`build_docket.py`) and the server (`docket-server.py`) had their
own copy of the kit resolution, which is the arrangement where two surfaces
quietly disagree about which kit a project has and only one of them 404s.

THE KIT IS PER-OWNER, NOT A PUBLIC CDN
--------------------------------------
A Pro kit id belongs to whoever bought it, so a hardcoded default is wrong for
everybody else — and it fails in the worst available way: the stylesheets 404,
no `<wa-*>` element ever upgrades, and the page renders as an unstyled outline
with **no error anywhere**. So it is resolved, in order:

    1. DOCKET_WA_KIT in the environment
    2. `.docket-webawesome` at the project root, holding the URL
    3. DEFAULT_KIT below

and every surface that uses it prints whether the theme actually loaded.

FILE METADATA
-------------
    Created        2026-09-19
    Inputs         DOCKET_WA_KIT, .docket-webawesome, dashboard/theme.html
    Returns        a kit URL; an HTML <head> fragment
    Writes         nothing
"""
import os
import pathlib

__version__ = "1.0.0"

#: **No kit by default, and that is deliberate.** This used to hold the kit id
#: of whoever built the framework — a *paid* Web Awesome kit, which meant the id
#: travelled into every install and would have travelled into a public
#: repository. Anyone else running it got stylesheets that 404 and a page that
#: renders as an unstyled outline, with no error anywhere.
#:
#: Empty means the `classic` look — plain CSS, no kit, everything legible — and
#: `diag()` prints `wa FAIL` so the reason is visible rather than mysterious.
#: A machine that has a kit declares it in `.docket-webawesome`, which is
#: git-ignored precisely because the id belongs to whoever bought it.
DEFAULT_KIT = ""

#: Where the theme fragment lives, relative to a project or the skill.
THEME_FILE = "dashboard/theme.html"

#: The banner, the navigation rail and the script that fills them. Separate from
#: the theme because one is a `<head>` and the other is body markup, but the
#: same idea: **written once, injected everywhere**, so three pages cannot drift
#: into three different navigations.
CHROME_FILE = "dashboard/chrome.html"

ROOT = pathlib.Path(__file__).resolve().parent.parent


def _kit_file(path):
    """The first non-comment line of a `.docket-webawesome`, or None."""
    try:
        for line in path.read_text(encoding="utf-8").split("\n"):
            line = line.strip()
            if line and not line.startswith("#"):
                return line.rstrip("/")
    except (OSError, UnicodeDecodeError):
        pass
    return None


#: Where a self-hosted Web Awesome lives on this machine, if one is installed.
#: **The kit is a URL; this is a directory.** They answer different questions —
#: the kit says *which* Web Awesome, the mirror says *where a local copy of it
#: is on disk* — and a project needs both to work without a network: the copy,
#: and a way to serve it.
#:
#: Pro is licensed per seat and may be self-hosted, so the bytes are the
#: owner's to keep. What must not happen is each project keeping its own copy:
#: that is how three FetchLayer clients drifted apart. One directory, shared.
DEFAULT_MIRROR = "~/Projects/webawesome/dist-cdn"


def mirror(root=None):
    """The on-disk directory of a self-hosted Web Awesome, or None.

    Resolved in order:

      1. `DOCKET_WA_MIRROR` in the environment — **absolute**: if it is set,
         that directory is the answer, and if it does not exist the answer is
         `None`. It is never searched past.
      2. this project's own `.docket-webawesome-mirror`, if it has one
      3. the master Docket's `.docket-webawesome-mirror`
      4. `DEFAULT_MIRROR` — `~/Projects/webawesome/dist-cdn`

    **Returns None when the directory does not exist**, which is the whole
    point: a machine with no mirror carries on using the hosted kit exactly as
    before. Nothing here changes what an existing caller sees.

    Use `dist-cdn`, not `dist`: the first is pre-bundled and loads straight from
    a `<script type="module">`, the second expects a bundler or an importmap.
    """
    # **An explicit override is honoured or nothing is.** Searching past a
    # directory the caller named, and quietly using a different one, would make
    # `DOCKET_WA_MIRROR=/tmp/experiment` silently run against the real mirror —
    # a lie that only shows up as results you cannot explain.
    env = os.environ.get("DOCKET_WA_MIRROR")
    if env:
        path = pathlib.Path(env).expanduser()
        return path if path.is_dir() else None

    candidates = []
    _r = pathlib.Path(root or ROOT)
    own = _kit_file(_r / ".docket-webawesome-mirror")
    if own:
        candidates.append(own)

    try:
        import docket_version
        master = docket_version.find_skill()
    except Exception:
        master = None
    if master:
        inherited = _kit_file(pathlib.Path(master) / ".docket-webawesome-mirror")
        if inherited:
            candidates.append(inherited)

    candidates.append(DEFAULT_MIRROR)

    for c in candidates:
        path = pathlib.Path(c).expanduser()
        if path.is_dir():
            return path
    return None


def kit(root=None, local_base=None):
    """The kit URL for this project, without a trailing slash.

    **Projects inherit the master's kit; they are not asked for one.** A kit id
    belongs to whoever bought it, and in practice every project on a machine
    belongs to the same person and should load components from the same place.
    Making each install ask, and then writing the same URL into every project,
    produced one question nobody wanted to answer and a dozen copies to keep in
    step.

    Resolved in order, most specific first:

      0. `local_base` — a self-hosted mirror the caller is serving (see
         `mirror()`). Opt-in: a caller that passes nothing is unaffected.
      1. `DOCKET_WA_KIT` in the environment — one session, overrides everything
      2. this project's own `.docket-webawesome` — a deliberate exception
      3. **the master Docket's `.docket-webawesome`** — the normal case
      4. `DEFAULT_KIT` below — only when no master is installed on this machine

    Step 3 is what makes an install silent. Change the master's file and every
    project that has not overridden it follows.
    """
    # **Local first, but only when the caller can actually serve it.** A caller
    # that mounts the mirror passes the URL prefix it mounted it at; everyone
    # else passes nothing and gets the hosted kit, exactly as before. Auto-
    # preferring a local path for every project would 404 on the ones that
    # serve no files, which is worse than the network dependency it replaces.
    if local_base and mirror(root):
        return local_base.rstrip("/")

    env = os.environ.get("DOCKET_WA_KIT") or os.environ.get("CODEX_WA_KIT")
    if env:
        return env.rstrip("/")

    _r = pathlib.Path(root or ROOT)
    own = (_kit_file(_r / ".docket-webawesome")
           or _kit_file(_r / ".codex-webawesome"))
    if own:
        return own

    # The master, wherever it is. Never fatal: a project on a machine with no
    # skill installed still has to render.
    try:
        import docket_version
        master = docket_version.find_skill()
    except Exception:
        master = None
    if master:
        inherited = _kit_file(pathlib.Path(master) / ".docket-webawesome")
        if inherited:
            return inherited

    return DEFAULT_KIT


#: What a page gets when `dashboard/theme.html` is not installed — an older
#: project, or one that deleted it. **Not a stub.** A page whose theme file is
#: missing should look the same, not degrade silently into the browser default
#: and leave somebody hunting for a CSS bug that is really a missing file.
#:
#: **It duplicates `dashboard/theme.html`, and that is the cost of the
#: guarantee.** Keep the two in step: the file is the one to edit, this is the
#: copy that has to follow. Both ship in the same release, so they move together
#: or the mismatch is a release that was not finished.
_FALLBACK = """
<link rel="stylesheet" href="{kit}/styles/themes/default.css">
<link rel="stylesheet" href="{kit}/styles/color/palettes/natural.css">
<link rel="stylesheet" href="{kit}/styles/utilities.css">
<link rel="stylesheet" href="{kit}/styles/native.css">
<link rel="stylesheet" href="https://fonts.bunny.net/css?family=ibm-plex-sans-condensed:300,400,500,600,700&display=swap">
<link rel="stylesheet" href="https://fonts.bunny.net/css?family=space-grotesk:300,400,500,600,700&display=swap">
<link rel="stylesheet" href="https://fonts.bunny.net/css?family=space-mono:400,400i,700,700i&display=swap">
<link rel="stylesheet" href="https://fonts.bunny.net/css?family=podkova:400,500,600,700,800&display=swap">
<script type="module" src="{kit}/webawesome.loader.js"></script>
<style>:root{{
  --wa-font-family-body:"Space Grotesk",sans-serif;
  --wa-font-family-heading:"IBM Plex Sans Condensed",sans-serif;
  --wa-font-family-code:"Space Mono",monospace;
  --wa-font-family-longform:Podkova,serif;
  --wa-font-weight-body:400; --wa-font-weight-heading:500;
  --wa-font-weight-code:400; --wa-font-weight-longform:400;
  --wa-border-radius-scale:.75; --wa-border-width-scale:1; --wa-space-scale:.625;
}}
*,*::before,*::after{{box-sizing:border-box}}
.t-amber{{--c-bg:var(--wa-color-yellow-90,#eee5d7);--c-line:var(--wa-color-yellow-70,#c7ab7b);--c-ink:var(--wa-color-yellow-40,#71541d)}}
.docket-masthead{{padding-block:var(--wa-space-xl) var(--wa-space-l);
  border-block-end:var(--wa-border-width-s) solid var(--wa-color-surface-border);
  margin-block-end:var(--wa-space-l)}}
.docket-project{{font-family:var(--wa-font-family-heading);font-weight:600;
  font-size:clamp(2.75rem,7.5vw,5rem);line-height:.95;letter-spacing:-.02em;margin:0;
  text-wrap:balance;overflow-wrap:anywhere}}
.docket-eyebrow{{font-family:var(--wa-font-family-code);font-size:var(--wa-font-size-xs);
  letter-spacing:.18em;text-transform:uppercase;
  color:var(--wa-color-neutral-on-quiet);margin:0 0 var(--wa-space-xs)}}
.docket-tagline{{color:var(--wa-color-neutral-on-quiet);max-width:62ch;
  margin:var(--wa-space-s) 0 0}}
.docket-mast-row{{display:flex;flex-wrap:wrap;gap:var(--wa-space-m);
  align-items:flex-end;justify-content:space-between}}
</style>
<script>(function(){{try{{var h=document.documentElement;
h.className=(h.className.replace(/wa-theme-\\S+|wa-palette-\\S+/g,'')+
' wa-theme-default wa-palette-natural').trim();
var t=localStorage.getItem('docket.theme');
if(t!=='light'&&t!=='dark')t=matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light';
h.setAttribute('data-theme',t);h.classList.toggle('wa-dark',t==='dark');}}catch(e){{}}}})();</script>
"""


def head(root=None, extra_roots=()):
    """The theme block, ready to drop into a `<head>`.

    `root` is the project; `extra_roots` are further places to look for the
    theme file — the skill, when a project is running the framework in place.
    """
    k = kit(root)
    for base in (root or ROOT, *extra_roots):
        if not base:
            continue
        f = pathlib.Path(base) / THEME_FILE
        try:
            return f.read_text(encoding="utf-8").replace("{{WA_KIT}}", k)
        except (OSError, UnicodeDecodeError):
            continue
    return _FALLBACK.format(kit=k)


def chrome(root=None, extra_roots=()):
    """The banner and navigation rail, ready to drop inside `<wa-page>`.

    Returns empty when the file is absent — an older project gets a page with a
    header and no rail, which is what it had before, rather than an error.
    """
    for base in (root or ROOT, *extra_roots):
        if not base:
            continue
        try:
            return (pathlib.Path(base) / CHROME_FILE).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
    return ""


def apply(html, root=None, extra_roots=()):
    """Fill `{{WA_HEAD}}` and `{{WA_KIT}}` in a page. Both, in that order.

    A page may want the kit URL for something of its own — an icon set, a
    component it loads late — so `{{WA_KIT}}` stays available after the head is
    injected, and the head's own copy of it is already resolved.
    """
    block = head(root, extra_roots)
    # **One pass. The injected block is never rescanned.**
    # Substituting the head and then substituting `{{WA_KIT}}` over the whole
    # document means the second pass runs over text the first pass just put
    # there — and if the theme file so much as mentions its own placeholder in a
    # comment, the head is injected a second time inside itself. Marking the
    # site first and filling it last makes that impossible rather than merely
    # unlikely.
    mark = "\x00docket-wa-head\x00"
    navmark = "\x00docket-wa-chrome\x00"
    out = (html.replace("<!--{{WA_HEAD}}-->", mark)
               .replace("{{WA_HEAD}}", mark)
               .replace("<!--{{WA_CHROME}}-->", navmark)
               .replace("{{WA_CHROME}}", navmark)
               .replace("{{WA_KIT}}", kit(root)))
    return out.replace(mark, block).replace(navmark, chrome(root, extra_roots))


if __name__ == "__main__":
    print(head())
