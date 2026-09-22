#!/usr/bin/env bash
# Read the Docket.
#
#   ./scripts/docket.sh          build and open it
#   ./scripts/docket.sh --build  build only, print the path
#   ./scripts/docket.sh --check  build, then run the Docket check
#   ./scripts/docket.sh --update bring this project up to the current framework
#                              (reports only; add --apply to act)
#   ./scripts/docket.sh --projects   every project running the Docket and its
#                              version — the master only; see docket-projects.py
#
# The viewer is generated from the planning documents themselves, so it is
# never out of date — rebuild rather than edit docs/docket.html.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

if [ "${1:-}" = "--projects" ]; then
  shift
  exec python3 scripts/docket-projects.py "$@"
fi

if [ "${1:-}" = "--update" ]; then
  shift
  # **Prefer the skill's copy over this project's.** The updater in the project
  # is whatever version it last received, and an old one can only deliver what
  # that old one knew about — it would rewrite itself and then finish the run
  # using the file list it was compiled with, leaving the project half-updated
  # and looking finished. The skill's copy is current by definition.
  for U in "${DOCKET_SKILL:-}/scripts/docket-update.py" \
           "$HOME/.claude/skills/docket/scripts/docket-update.py" \
           "$HOME/Projects/docket/scripts/docket-update.py" \
           "scripts/docket-update.py"; do
    [ -f "$U" ] && exec python3 "$U" --project . "$@"
  done
  echo "docket-update.py not found — is the Docket skill installed?" >&2
  exit 1
fi

echo "==> Building the Docket viewer"
python3 scripts/build_docket.py

OUT="docs/docket.html"
case "${1:-}" in
  --build) echo "    $PWD/$OUT" ;;
  --check) echo; ./scripts/check-docs.sh ;;
  *)       echo "==> Opening"
           # **`open` is macOS.** On Linux this was a command-not-found at the
           # very end of a successful build — the worst place for it, because
           # the work is done and the tool looks broken. Python's `webbrowser`
           # is already a dependency of the server and knows every platform.
           python3 -c "import sys,webbrowser,pathlib; webbrowser.open(pathlib.Path(sys.argv[1]).resolve().as_uri())" "$OUT" \
             || echo "    could not open a browser — the file is $PWD/$OUT" ;;
esac
