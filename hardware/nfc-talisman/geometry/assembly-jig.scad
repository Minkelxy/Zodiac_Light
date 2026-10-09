// NFC talisman assembly jig. Dimensions mm; print fit is unverified.
// Tray: 50mm across flats, 8mm high, 37.4mm pocket, 6mm deep, 2mm floor.
// Two 12mm finger openings leave the floor intact. Press plate is separate.
$fn = 72;
function octagon(af) = let(h=af/2,b=h*tan(22.5))
    [[-b,-h],[b,-h],[h,-b],[h,b],[b,h],[-b,h],[-h,b],[-h,-b]];
module tray() {
    difference() {
        linear_extrude(8) polygon(octagon(50));
        translate([0,0,2]) linear_extrude(6.1) polygon(octagon(37.4));
        for (x=[-24,24]) translate([x,0,2]) cylinder(h=6.1,d=12);
    }
}
module press_plate() {
    linear_extrude(2) polygon(octagon(37));
    translate([0,0,2]) cylinder(h=6,d=12);
}
tray();
translate([60,0,0]) press_plate();
