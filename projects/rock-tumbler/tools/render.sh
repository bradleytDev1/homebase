#!/usr/bin/env bash
# render.sh -- regenerate every STL and render, and prove the assembly fits.
#
# WHY THIS EXISTS
#   cad/tumbler.scad was written and committed over several sessions before
#   OpenSCAD was ever run against it. When it finally was, it turned out not
#   to parse at all (adjacent string literals, which C and Python concatenate
#   and OpenSCAD does not), and once it did parse, the roller sat 3 mm out of
#   place so the barrel end rode on a flange instead of the tyre. Neither was
#   catchable by reading the file. Both were obvious the moment it ran.
#
#   So: run this after any change to the CAD.
#
# USAGE
#   tools/render.sh            # from the project root
#
# OUTPUT
#   build/*.stl                printable parts (gitignored)
#   cad/renders/*.png          assembly, section and liner views (committed)
#
# EXIT
#   0 if everything parses, every part is a valid solid, and nothing collides.
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1

SCAD=cad/tumbler.scad
BUILD=build
RENDERS=cad/renders
PARTS=(roller_hub tyre end_plate motor_mount hex_liner lifter_liner)
fail=0

command -v openscad >/dev/null || {
    echo "openscad not found. Install with: brew install --cask openscad@snapshot"
    exit 1
}
mkdir -p "$BUILD" "$RENDERS"

# --- 1. does it parse, and what geometry does it report? -------------------
echo "== parse and build sheet =="
if ! openscad -o "$BUILD/.parse.stl" "$SCAD" 2>&1 | grep -E '^(ECHO|ERROR|WARNING)'; then :; fi
openscad -o "$BUILD/.parse.stl" "$SCAD" 2>&1 | grep -q 'ERROR' && { echo "  PARSE FAILED"; exit 1; }
rm -f "$BUILD/.parse.stl"

# --- 2. is every part a valid, manifold solid? -----------------------------
echo
echo "== parts =="
for p in "${PARTS[@]}"; do
    printf "  %-14s " "$p"
    # Delete first: OpenSCAD writes no file for an empty result, so a stale
    # STL from the last run would be counted as this run's part (LE-18).
    rm -f "$BUILD/$p.stl"
    out=$(openscad -D "PART=\"$p\"" -o "$BUILD/$p.stl" "$SCAD" 2>&1)
    # Match OpenSCAD's real error prefix only. A case-insensitive "error"
    # also matches its SUCCESS line, "Status: NoError".
    if echo "$out" | grep -qE '^ERROR:|not a valid 2-manifold|is not manifold'; then
        echo "FAILED"; echo "$out" | grep -E '^ERROR:|manifold' | sed 's/^/      /'; fail=1
    elif [ -s "$BUILD/$p.stl" ]; then
        printf "ok   %7s facets\n" "$(grep -c 'facet normal' "$BUILD/$p.stl")"
    else
        echo "FAILED (empty)"; fail=1
    fi
done

# --- 3. does anything collide? ---------------------------------------------
# The dispatch block is stripped so the test file renders ONLY the test
# intersection; leaving it in makes every test silently render the whole
# assembly instead, and two different tests then return identical results.
echo
echo "== interference =="
T="$BUILD/.interference.scad"
sed '/^\/\/ --- DISPATCH ---/,$d' "$SCAD" > "$T"
cat >> "$T" <<'SCADEOF'
module _barrel() {
    translate([0, -BARREL_LEN/2, AXIS_Z + RIDE_HEIGHT]) rotate([-90,0,0])
        cylinder(d = BARREL_OD, h = BARREL_LEN);
}
module _plates() {
    for (y = [-(BARREL_LEN/2 + 20), BARREL_LEN/2 + 20])
        translate([0, y, 0]) rotate([90,0,0]) translate([0,0,-PLATE_T/2]) end_plate();
}
module _rollers() {
    for (x = [-ROLLER_SPACE/2, ROLLER_SPACE/2])
        translate([x, -(BARREL_LEN/2 + 2 + FLANGE_H), AXIS_Z]) rotate([-90,0,0]) roller_hub();
}
if (TEST == "control")           intersection() { _barrel(); _barrel(); }
if (TEST == "barrel_vs_plates")  intersection() { _barrel(); _plates(); }
if (TEST == "barrel_vs_flanges") intersection() { _barrel(); _rollers(); }
SCADEOF

facets() {
    # Remove the previous result FIRST: OpenSCAD writes no file for an empty
    # object, so a stale STL would be recounted and every test would report
    # the last non-empty result.
    rm -f "$BUILD/.t.stl"
    openscad -D "TEST=\"$1\"" -o "$BUILD/.t.stl" "$T" >/dev/null 2>&1
    grep -c 'facet normal' "$BUILD/.t.stl" 2>/dev/null || echo 0
}

# The control MUST be non-empty. If it is empty the harness is broken and
# every "no collision" result below is meaningless.
n=$(facets control)
printf "  %-22s " "control (must be >0)"
if [ "$n" -gt 0 ]; then echo "ok ($n facets)"; else
    echo "HARNESS BROKEN -- results below mean nothing"; fail=1; fi

for t in barrel_vs_plates barrel_vs_flanges; do
    n=$(facets "$t")
    printf "  %-22s " "$t"
    if [ "$n" -eq 0 ]; then echo "clear"; else echo "*** COLLISION *** ($n facets)"; fail=1; fi
done
rm -f "$BUILD/.t.stl" "$T"

# --- 4. renders -------------------------------------------------------------
echo
echo "== renders =="
openscad -o "$RENDERS/assembly.png" --imgsize=1700,1200 \
    --camera=230,-330,210,0,0,55 --colorscheme=Tomorrow "$SCAD" >/dev/null 2>&1 \
    && echo "  assembly.png"
# Section, not elevation: from the front the near end plate hides the cradle.
openscad -D 'PART="section"' -o "$RENDERS/section.png" --imgsize=1400,1100 \
    --camera=0,-420,76,0,0,76 --projection=ortho --colorscheme=Tomorrow "$SCAD" >/dev/null 2>&1 \
    && echo "  section.png"
openscad -D 'PART="lifter_liner"' -o "$RENDERS/lifter_liner.png" --imgsize=1200,1000 \
    --autocenter --viewall --colorscheme=Tomorrow "$SCAD" >/dev/null 2>&1 \
    && echo "  lifter_liner.png"

echo
[ "$fail" -eq 0 ] && echo "ALL CHECKS PASSED" || echo "SOMETHING IS WRONG"
exit $fail
