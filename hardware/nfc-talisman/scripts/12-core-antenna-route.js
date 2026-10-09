const APPLY = false;
// Unit correction alone does not fix the original return-route collisions.
// See electrical/antenna-geometry-review.json for the independently checked
// replacement proposal. Keep this baseline helper non-applicable for now.
const GEOMETRY_REVIEW_APPROVED = false;
const MM = 1 / 0.0254;
// Documented layer IDs; the bridge runtime does not expose the enum global.
const TOP = 1;
const BOTTOM = 2;
const OUTLINE = 11;
const width = 0.25 * MM;
const viaHole = 0.20 * MM;
const viaDiameter = 0.45 * MM;
// Geometry inputs stay in mm. octPoint/octagon convert their outputs once.
const outlineA = 18.5;
const outerTraceA = 16.875;
const pitch = 0.5;
const turns = 4;
const stepsPerTurn = 32;
const startAngle = Math.PI;
const wrap = (value, period) => ((value + period / 2) % period + period) % period - period / 2;
const octPoint = (apothem, angle) => {
  const delta = wrap(angle, Math.PI / 4);
  const radius = apothem / Math.cos(delta);
  return { x: radius * Math.cos(angle) * MM, y: radius * Math.sin(angle) * MM };
};
const octagon = apothem => Array.from({ length: 8 }, (_, i) => {
  const angle = Math.PI / 8 + i * Math.PI / 4;
  const radius = apothem / Math.cos(Math.PI / 8);
  return { x: radius * Math.cos(angle) * MM, y: radius * Math.sin(angle) * MM };
});
const coil = Array.from({ length: turns * stepsPerTurn + 1 }, (_, i) => {
  const progress = i / stepsPerTurn;
  const angle = startAngle + progress * Math.PI * 2;
  const apothem = outerTraceA - pitch * progress;
  return octPoint(apothem, angle);
});
const vias = [
  { name: 'U1_LA_breakout', x: -80, y: 80 },
  { name: 'U1_LB_breakout', x: -10, y: 80 },
  { name: 'coil_outer_terminal', x: coil[0].x, y: coil[0].y },
  { name: 'coil_inner_terminal', x: coil[coil.length - 1].x, y: coil[coil.length - 1].y }
];
const points = [
  { name: 'U1_LA', x: -23.6, y: 19.7 },
  { name: 'U1_LB', x: 0, y: 23.6 }
];
const board = octagon(outlineA);
const segmentList = (pts, close = false) => {
  const out = [];
  for (let i = 0; i < pts.length - 1; i++) out.push([pts[i], pts[i + 1]]);
  if (close) out.push([pts[pts.length - 1], pts[0]]);
  return out;
};
const tracks = [
  ...segmentList(coil).map(([a, b]) => ({ layer: TOP, width, a, b, role: '4-turn octagonal spiral; net assignment intentionally blank' })),
  { layer: TOP, width, a: points[0], b: vias[0], role: 'U1 LA pad breakout' },
  { layer: TOP, width, a: points[1], b: vias[1], role: 'U1 LB pad breakout' },
  { layer: BOTTOM, width, a: vias[0], b: vias[2], role: 'outer-end return' },
  { layer: BOTTOM, width, a: vias[3], b: vias[1], role: 'inner-end return' }
];
const summary = {
  units: 'EasyEDA PCB core coordinates in mil; dimensions are generated in mm then converted by 1/0.0254',
  apply: APPLY,
  geometryReviewApproved: GEOMETRY_REVIEW_APPROVED,
  outerCopperFlatToFlat_mm: 34,
  turns,
  trackWidth_mm: 0.25,
  nominalTrackGap_mm: 0.25,
  outerCenterlineApothem_mm: 16.875,
  innerCenterlineApothem_mm: 14.875,
  boardOutlineFlatToFlat_mm: 37,
  permanentMountingHoles: 0,
  vias: vias.map(v => ({ name: v.name, x_mil: v.x, y_mil: v.y, drill_mm: 0.20, diameter_mm: 0.45 })),
  expectedElectricalLimitation: 'The two-terminal L1 spiral joins ANT_LA to ANT_LB. The official EasyEDA UI supports bridge copper on a FILL region to list these allowed nets; this installed API has no documented bridge property. Use a reviewed solid fill and enable the bridge in the native Properties panel before accepting DRC.',
  lineCount: tracks.length + 8,
  trackGeometry: tracks,
  outlineSegments: segmentList(board, true).map(([a, b]) => ({ layer: OUTLINE, width: 1, a, b }))
};
if (!APPLY) return summary;
if (!GEOMETRY_REVIEW_APPROVED) throw Error('Refusing to apply: baseline geometry has return/via/pad collisions; use the reviewed replacement fill geometry and enable ANT_LA/ANT_LB bridge copper in the native Properties panel first.');
const existingLines = await eda.pcb_PrimitiveLine.getAll();
const existingVias = await eda.pcb_PrimitiveVia.getAll();
if (existingLines.length || existingVias.length) throw Error('Refusing to apply: this PCB already contains line or via primitives; inspect and clear the board explicitly first.');
const created = [];
for (const t of tracks) {
  const line = await eda.pcb_PrimitiveLine.create('', t.layer, t.a.x, t.a.y, t.b.x, t.b.y, width, false);
  if (!line) throw Error('Track creation failed at segment ' + created.length);
  created.push(line.getState_PrimitiveId());
}
for (const v of vias) {
  // Documented through-via enum value 0; enum globals are unavailable here.
  const via = await eda.pcb_PrimitiveVia.create('', v.x, v.y, viaHole, viaDiameter, 0, null, null, false);
  if (!via) throw Error('Via creation failed at ' + v.name);
  created.push(via.getState_PrimitiveId());
}
for (const t of segmentList(board, true)) {
  const line = await eda.pcb_PrimitiveLine.create('', OUTLINE, t[0].x, t[0].y, t[1].x, t[1].y, 1, false);
  if (!line) throw Error('Board outline creation failed at segment ' + created.length);
  created.push(line.getState_PrimitiveId());
}
return { applied: true, createdPrimitiveIds: created, summary };
