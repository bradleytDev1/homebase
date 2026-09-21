// ===========================================================================
// tumbler.scad -- Parametric stepper-driven rock tumbler
//
// WHAT THIS IS
//   A two-roller rotary tumbler. A barrel sits in the vee between two parallel
//   rollers; one roller is driven, and friction carries the barrel round.
//   Every printed part is generated from the parameter block below, so
//   changing the barrel diameter re-cuts the end plates automatically.
//
// WHAT YOU SUPPLY (not printed)
//   - 2 x 8 mm smooth steel rod, ROD_LEN long (roller shafts)
//   - 4 x 608-2RS sealed skate bearings (22 OD x 8 ID x 7)
//   - 1 x NEMA 17 stepper
//   - GT2 belt + two 20T pulleys (or a 5-to-8 mm flexible coupler for direct drive)
//   - a barrel: see the README. Do not print the barrel.
//
// PRINT NOTES -- these matter more than usual
//   * End plates and roller hubs: PETG or ASA, NOT PLA. A stepper run
//     continuously sits at 60-80 C, and PLA's glass transition is ~60 C.
//     A PLA motor mount will sag over a six-week polish run. This is the
//     single most common way a printed tumbler quietly destroys itself.
//   * Tyres and barrel liner: TPU (95A). TPU is exceptionally abrasion
//     resistant and it is what makes the machine quiet.
//   * 4 perimeters, 30%+ infill. This thing vibrates for weeks at a time.
//
// RENDER ONE PART
//   openscad -D 'PART="roller_hub"' -o roller_hub.stl tumbler.scad
//   PART values: "roller_hub" "tyre" "end_plate" "motor_mount"
//                "hex_liner" "lifter_liner" "assembly" "section"
// ===========================================================================

// --- PART SELECTOR ---------------------------------------------------------
PART = "assembly";          // overridden on the command line with -D

// --- BARREL ----------------------------------------------------------------
BARREL_ID      = 100;       // inside diameter, mm -- sets the tumbling speed
BARREL_WALL    = 6;         // wall thickness, mm
BARREL_LEN     = 120;       // length of the barrel body, mm

// --- ROLLERS ---------------------------------------------------------------
// The roller diameter is your gearbox. Bigger roller = slower motor and more
// torque demand; smaller roller = faster motor and less torque. 40 mm puts a
// NEMA 17 at ~170 rpm, comfortably inside its flat torque region.
ROLLER_OD      = 40;        // outside diameter INCLUDING the tyre, mm
TYRE_T         = 3;         // TPU tyre wall thickness, mm
ROD_D          = 8;         // shaft diameter, mm
ROD_LEN        = 220;       // shaft length, mm
FLANGE_H       = 6;         // height of the axial retaining flanges, mm
CONTACT_ANGLE  = 40;        // cradle half-angle from bottom dead centre, deg

// --- BEARINGS (608-2RS) ----------------------------------------------------
BRG_OD         = 22;
BRG_W          = 7;
BRG_POCKET_FIT = 0.15;      // radial clearance so the bearing presses in snug

// --- END PLATES ------------------------------------------------------------
PLATE_T        = 10;        // thickness, mm
PLATE_MARGIN   = 14;        // material around each bearing pocket, mm
FOOT_W         = 18;        // width of the base foot, mm
BASE_HOLE_D    = 5.4;       // clearance for M5 into the baseboard

// --- MOTOR (NEMA 17) -------------------------------------------------------
NEMA_FACE      = 42.3;
NEMA_BOLT      = 31;        // bolt-circle square spacing, mm
NEMA_BOSS_D    = 23;        // clearance for the locating boss, mm
NEMA_SCREW_D   = 3.4;       // M3 clearance

// --- BARREL LINER ----------------------------------------------------------
LINER_FACETS   = 6;         // hexagonal lift is the classic; 6 or 8
LINER_T        = 4;         // TPU liner thickness at the flats, mm

// Thickness of a rubber sheet fitted between the barrel wall and the printed
// liner, in mm. Set to 0 for a printed liner alone. When non-zero, both liner
// modules shrink to suit, so the printed sleeve's own springiness clamps the
// rubber against the barrel wall and NO ADHESIVE IS NEEDED. Measure your
// actual sheet: mudflap is usually 5-6 mm, a split motorcycle inner tube 2-3.
RUBBER_T       = 0;

// Lifter-bar liner (the alternative to the hexagon -- see lifter_liner below).
LIFTER_N       = 6;         // number of bars around the bore
LIFTER_H       = 6;         // how far each bar protrudes inward, mm
LIFTER_W       = 9;         // bar width at its base, mm
LIFTER_TIP     = 4;         // bar width at its tip, mm (< LIFTER_W = tapered)

$fn = 96;

// --- DERIVED GEOMETRY ------------------------------------------------------
// Barrel rests in the vee. With contact points at CONTACT_ANGLE either side of
// bottom dead centre, the barrel-centre-to-roller-centre line has length
// (R_barrel + R_roller) and makes that angle with vertical. Hence:
BARREL_OD     = BARREL_ID + 2 * BARREL_WALL;
SUM_R         = (BARREL_OD + ROLLER_OD) / 2;
ROLLER_SPACE  = 2 * SUM_R * sin(CONTACT_ANGLE);   // shaft centre-to-centre, mm
RIDE_HEIGHT   = SUM_R * cos(CONTACT_ANGLE);       // barrel axis above shaft axes
HUB_OD        = ROLLER_OD - 2 * TYRE_T;
PLATE_W       = ROLLER_SPACE + BRG_OD + 2 * PLATE_MARGIN;
PLATE_H       = BRG_OD / 2 + PLATE_MARGIN + FOOT_W;
AXIS_Z        = FOOT_W;                            // shaft axis height above the foot

// Echo the build sheet to the console every time the file is opened, so the
// numbers you need at the bench are never more than one render away.
echo(str("barrel OD = ", BARREL_OD, " mm"));
echo(str("roller shaft spacing = ", ROLLER_SPACE, " mm"));
echo(str("barrel ride height above shafts = ", RIDE_HEIGHT, " mm"));
echo(str("plate = ", PLATE_W, " x ", PLATE_H, " x ", PLATE_T, " mm"));
if (RUBBER_T > 0)
    echo(str("rubber sheet: cut ", 3.14159 * (BARREL_ID - 2 * RUBBER_T), " x ",
             BARREL_LEN - 6, " mm (circumference at the mid-thickness, ",
             "plus ~10 mm overlap)"));

// ===========================================================================
// MODULE: roller_hub
//   The printed core of a roller. Bores 8 mm for the shaft, carries a recessed
//   band for the TPU tyre, and ends in two flanges that cage the barrel so it
//   cannot walk off the end of the machine.
//   Inputs:  none (uses globals). Output: one printable solid, axis along Z.
//   Print:   PETG/ASA, on end, no supports.
// ===========================================================================
module roller_hub() {
    tyre_band = BARREL_LEN + 4;          // tyre slightly longer than the barrel
    total_h   = tyre_band + 2 * FLANGE_H;
    difference() {
        union() {
            // Tyre seat: sunk by TYRE_T so the tyre finishes flush at ROLLER_OD.
            translate([0, 0, FLANGE_H]) cylinder(d = HUB_OD, h = tyre_band);
            // Retaining flanges, proud of the tyre, that trap the barrel axially.
            cylinder(d = ROLLER_OD + 10, h = FLANGE_H);
            translate([0, 0, total_h - FLANGE_H])
                cylinder(d = ROLLER_OD + 10, h = FLANGE_H);
        }
        // Shaft bore, with a touch of clearance for a printed fit.
        translate([0, 0, -1]) cylinder(d = ROD_D + 0.25, h = total_h + 2);
        // Two M3 grub screws at 90 degrees lock the hub to the shaft.
        for (z = [FLANGE_H + 8, total_h - FLANGE_H - 8])
            for (a = [0, 90])
                rotate([0, 0, a])
                    translate([0, 0, z]) rotate([0, 90, 0])
                        cylinder(d = 2.9, h = ROLLER_OD, center = true);
    }
}

// ===========================================================================
// MODULE: tyre
//   A TPU sleeve that slips over the hub's tyre seat. This is the part that
//   actually grips the barrel, absorbs vibration and keeps the machine quiet.
//   Print it slightly undersize on the bore so it stretches on and stays put.
//   Inputs:  none (uses globals). Output: one ring, axis along Z.
//   Print:   TPU 95A, 100% infill (it is thin), no supports.
// ===========================================================================
module tyre() {
    band = BARREL_LEN + 4;
    difference() {
        cylinder(d = ROLLER_OD, h = band);
        // -0.4 mm interference: TPU stretches, and an interference fit means
        // the tyre cannot creep round the hub under load.
        translate([0, 0, -1]) cylinder(d = HUB_OD - 0.4, h = band + 2);
    }
}

// ===========================================================================
// MODULE: bearing_pocket
//   A blind pocket for a 608 bearing plus the through-hole for the shaft.
//   Inputs:  none (uses globals). Output: a negative solid, to be differenced.
// ===========================================================================
module bearing_pocket() {
    // Bearing seat, open toward -Z (the inside face of the plate).
    translate([0, 0, -0.01])
        cylinder(d = BRG_OD + 2 * BRG_POCKET_FIT, h = BRG_W + 0.01);
    // Shaft clearance all the way through.
    translate([0, 0, -1]) cylinder(d = ROD_D + 2, h = PLATE_T + 2);
}

// ===========================================================================
// MODULE: end_plate
//   One of the two plates that hold the roller shafts at the spacing computed
//   from the barrel and roller diameters. Sits flat on the print bed.
//   Inputs:  none (uses globals). Output: one printable solid.
//   Print:   PETG/ASA, flat, 4 perimeters. Two required.
// ===========================================================================
module end_plate() {
    difference() {
        union() {
            // Main body: a rounded slab spanning both bearings.
            hull() {
                for (x = [-ROLLER_SPACE / 2, ROLLER_SPACE / 2])
                    translate([x, AXIS_Z, 0])
                        cylinder(d = BRG_OD + 2 * PLATE_MARGIN, h = PLATE_T);
                translate([-PLATE_W / 2, 0, 0]) cube([PLATE_W, 1, PLATE_T]);
            }
            // Foot: gives the plate a bolt-down flange onto the baseboard.
            translate([-PLATE_W / 2, 0, 0]) cube([PLATE_W, FOOT_W, PLATE_T]);
        }
        // Bearing pockets at the computed spacing.
        for (x = [-ROLLER_SPACE / 2, ROLLER_SPACE / 2])
            translate([x, AXIS_Z, 0]) bearing_pocket();
        // Baseboard fixing holes, outboard of the bearings.
        for (x = [-PLATE_W / 2 + 9, PLATE_W / 2 - 9])
            translate([x, FOOT_W / 2, -1]) cylinder(d = BASE_HOLE_D, h = PLATE_T + 2);
    }
}

// ===========================================================================
// MODULE: motor_mount
//   A NEMA 17 face plate with slotted holes, so belt tension is set by sliding
//   the motor rather than by reprinting the bracket.
//
//   IMPORTANT: mount the motor OUTBOARD of the end plate and below the barrel
//   line, but never directly under the drip zone. Wet silicon carbide slurry
//   in a stepper's bearings ends the stepper.
//   Inputs:  none (uses globals). Output: one printable solid.
//   Print:   PETG or ASA ONLY. This part gets hot. See header.
// ===========================================================================
module motor_mount() {
    w = NEMA_FACE + 16;
    h = NEMA_FACE + 26;
    t = 6;
    difference() {
        cube([w, h, t], center = false);
        // Central clearance for the motor boss and shaft.
        translate([w / 2, h - NEMA_FACE / 2 - 8, -1])
            cylinder(d = NEMA_BOSS_D, h = t + 2);
        // Four M3 slots, elongated along Y for belt tensioning.
        for (dx = [-NEMA_BOLT / 2, NEMA_BOLT / 2])
            for (dy = [-NEMA_BOLT / 2, NEMA_BOLT / 2])
                hull()
                    for (s = [0, 7])
                        translate([w / 2 + dx, h - NEMA_FACE / 2 - 8 + dy - s, -1])
                            cylinder(d = NEMA_SCREW_D, h = t + 2);
        // Two M5 holes fixing the bracket to the baseboard.
        for (dx = [-w / 4, w / 4])
            translate([w / 2 + dx, 9, -1]) cylinder(d = BASE_HOLE_D, h = t + 2);
    }
}

// ===========================================================================
// MODULE: hex_liner
//   A flexible hexagonal sleeve that press-fits inside a round barrel.
//
//   This is the part that earns the 3D printer its keep. Commercial tumbler
//   barrels are rubber-lined and hexagonal for two reasons: the rubber damps
//   the noise and cushions the stone, and the flats LIFT the load so it
//   cascades instead of sliding as a lump against a smooth wall. A plain PVC
//   pipe tumbles badly; the same pipe with this liner tumbles like a Thumler's.
//
//   Inputs:  none (uses globals). Output: a hollow faceted sleeve, axis on Z.
//   Print:   TPU 95A, 3 perimeters, no supports. Roll it to insert.
// ===========================================================================
module hex_liner() {
    // Circumscribed radius so the hex corners touch the barrel bore, less any
    // rubber sheet fitted behind it.
    r_out = BARREL_ID / 2 - 0.5 - RUBBER_T;
    r_in  = r_out - LINER_T;
    difference() {
        cylinder(r = r_out, h = BARREL_LEN - 6, $fn = LINER_FACETS);
        translate([0, 0, -1])
            cylinder(r = r_in, h = BARREL_LEN - 4, $fn = LINER_FACETS);
    }
}

// ===========================================================================
// MODULE: lifter_bar
//   Cross-section of one lifter, extruded along the barrel axis. The base sits
//   on the liner's inner wall and the bar protrudes toward the axis.
//
//   SYMMETRY IS NOT OPTIONAL HERE. Commercial barrels use an asymmetric scoop
//   profile, which lifts beautifully -- in one direction. They can afford that
//   because they only ever turn one way. This machine reverses every six hours
//   to stop the load packing into a channel, so an asymmetric bar would spend
//   half its life dragging backwards through the charge. Symmetric trapezoid
//   it is: slightly worse at lifting than a scoop, identical in both directions.
//
//   Inputs:  h (number) -- extrusion length along the barrel axis, mm.
//   Returns: a solid positioned with its base at the origin, growing in -X.
// ===========================================================================
module lifter_bar(h) {
    linear_extrude(height = h)
        polygon([[0,           -LIFTER_W / 2],
                 [0,            LIFTER_W / 2],
                 [-LIFTER_H,    LIFTER_TIP / 2],
                 [-LIFTER_H,   -LIFTER_TIP / 2]]);
}

// ===========================================================================
// MODULE: lifter_liner
//   A round TPU sleeve carrying discrete lifter bars -- the mineral-processing
//   answer to the same problem the hexagon solves, and the one commercial
//   barrels actually use.
//
//   WHY BARS RATHER THAN FLATS. Both exist to stop the charge sliding as a
//   lump against a smooth shell. For a 100 mm barrel they deliver a similar
//   amount of lift -- a hex varies the inner radius by about 6.1 mm, a 6 mm
//   bar by 6.0 mm -- but they deliver it completely differently. The hexagon
//   spreads its lift gradually around each flat; a bar presents a discrete
//   step that catches the charge and carries it to a definite release point.
//   Tumbling mills have used lifter bars for a century for exactly this
//   reason: positive engagement, and no reliance on shell friction.
//
//   Print in TPU and bond it to a rubber sheet liner if you want both the
//   geometry and the damping -- see the README.
//
//   Inputs:  none (uses globals). Output: a hollow sleeve, axis on Z.
//   Print:   TPU 95A, 3 perimeters, no supports. Roll it to insert.
// ===========================================================================
module lifter_liner() {
    r_out = BARREL_ID / 2 - 0.5 - RUBBER_T;   // sits against rubber, or the bore
    r_in  = r_out - LINER_T;
    h     = BARREL_LEN - 6;
    union() {
        difference() {
            cylinder(r = r_out, h = h);
            translate([0, 0, -1]) cylinder(r = r_in, h = h + 2);
        }
        for (i = [0 : LIFTER_N - 1])
            rotate([0, 0, i * 360 / LIFTER_N])
                translate([r_in, 0, 0]) lifter_bar(h);
    }
}

// ===========================================================================
// MODULE: assembly
//   Non-printable visualisation: confirms at a glance that the barrel actually
//   sits in the vee at the height the arithmetic promised, and that nothing
//   collides. Ghosted barrel in translucent grey.
//   Inputs:  none (uses globals). Output: a rendered scene.
// ===========================================================================
module assembly() {
    // Two end plates, facing each other across the barrel length.
    for (y = [-(BARREL_LEN / 2 + 20), BARREL_LEN / 2 + 20])
        translate([0, y, 0]) rotate([90, 0, 0])
            translate([0, 0, -PLATE_T / 2]) color("SteelBlue") end_plate();

    // Rollers, laid along Y at the computed spacing.
    // Position so the TYRE BAND is centred on the barrel, not the whole hub:
    // the hub begins with a flange, so the band starts FLANGE_H further along.
    for (x = [-ROLLER_SPACE / 2, ROLLER_SPACE / 2])
        translate([x, -(BARREL_LEN / 2 + 2 + FLANGE_H), AXIS_Z]) rotate([-90, 0, 0]) {
            color("DimGray") roller_hub();
            color("Black") translate([0, 0, FLANGE_H]) tyre();
        }

    // Shafts, running through both end plates.
    for (x = [-ROLLER_SPACE / 2, ROLLER_SPACE / 2])
        color("Silver")
            translate([x, -ROD_LEN / 2, AXIS_Z]) rotate([-90, 0, 0])
                cylinder(d = ROD_D, h = ROD_LEN);

    // Ghosted barrel, sitting where RIDE_HEIGHT says it should.
    color("Gainsboro", 0.35)
        translate([0, -BARREL_LEN / 2, AXIS_Z + RIDE_HEIGHT])
            rotate([-90, 0, 0]) cylinder(d = BARREL_OD, h = BARREL_LEN);
}

// ===========================================================================
// MODULE: section
//   The assembly cut in half across the barrel axis. Render this, not the
//   front elevation: from the front the near end plate occludes the rollers
//   and the barrel's lower half, so you cannot see the one thing worth
//   checking -- that the barrel really does sit in the vee at RIDE_HEIGHT,
//   touching both tyres and nothing else.
//   Inputs:  none. Output: a rendered scene, not printable.
// ===========================================================================
module section() {
    difference() {
        assembly();
        translate([-400, -800, -400]) cube([800, 800, 800]);   // keep y > 0
    }
}

// --- DISPATCH --------------------------------------------------------------
if      (PART == "roller_hub")  roller_hub();
else if (PART == "tyre")        tyre();
else if (PART == "end_plate")   end_plate();
else if (PART == "motor_mount") motor_mount();
else if (PART == "hex_liner")   hex_liner();
else if (PART == "lifter_liner") lifter_liner();
else if (PART == "section")     section();
else                            assembly();
