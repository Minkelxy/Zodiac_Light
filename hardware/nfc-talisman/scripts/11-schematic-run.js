await eda.dmt_EditorControl.openDocument('293c7786afd689e8');await new Promise(r=>setTimeout(r,1000));
// Connect the already placed schematic devices using the reviewed connectivity
// handoff. This is intended to run in the EasyEDA script bridge (global `eda`).
// Input snapshots below are taken from:
//   eda/logs/06-schematic-place.json -> result.placed
//   electrical/netlist.json -> nets
// Keep these snapshots in sync if either input file changes.

const placementResult = {
  placed: [
    { ref: 'U1', pins: [[1,220,575,180],[2,220,565,180],[3,220,555,180],[4,220,545,180],[5,300,545,0],[6,300,555,0],[7,300,565,0],[8,300,575,0]] },
    { ref: 'C1', pins: [[1,530,680,180],[2,570,680,0]] },
    { ref: 'CT1', pins: [[1,95,470,180],[2,125,470,0]] },
    { ref: 'CT2', pins: [[1,95,370,180],[2,125,370,0]] },
    { ref: 'R5', pins: [[2,570,560,0],[1,530,560,180]] },
    { ref: 'R6', pins: [[2,570,450,0],[1,530,450,180]] },
    { ref: 'R7', pins: [[2,570,340,0],[1,530,340,180]] },
    { ref: 'R1', pins: [[2,780,660,0],[1,740,660,180]] },
    { ref: 'D1', pins: [[1,930,660,180],[2,970,660,0]] },
    { ref: 'R2', pins: [[2,780,550,0],[1,740,550,180]] },
    { ref: 'D2', pins: [[1,930,550,180],[2,970,550,0]] },
    { ref: 'R3', pins: [[2,780,440,0],[1,740,440,180]] },
    { ref: 'D3', pins: [[1,930,440,180],[2,970,440,0]] },
    { ref: 'R4', pins: [[2,780,330,0],[1,740,330,180]] },
    { ref: 'D4', pins: [[1,930,330,180],[2,970,330,0]] },
  ],
};

const netlist = {
  nets: {
    ANT_LA: [['U1','1'],['CT1','1'],['CT2','1']],
    GND: [['U1','2'],['C1','2'],['D1','K'],['D2','K'],['D3','K'],['D4','K']],
    SCL: [['U1','3'],['R5','2']],
    FD: [['U1','4'],['R7','2']],
    SDA: [['U1','5'],['R6','2']],
    VOUT: [['U1','6'],['U1','7'],['C1','1'],['R5','1'],['R6','1'],['R7','1'],['R1','1'],['R2','1'],['R3','1'],['R4','1']],
    ANT_LB: [['U1','8'],['CT1','2'],['CT2','2']],
    LED1_A: [['R1','2'],['D1','A']],
    LED2_A: [['R2','2'],['D2','A']],
    LED3_A: [['R3','2'],['D3','A']],
    LED4_A: [['R4','2'],['D4','A']],
  },
};

const requireResult = (value, label) => {
  if (value === undefined || value === null || value === false) throw new Error(`${label} failed`);
  return value;
};

// Native LED symbol pins are numbered 1 and 2; the confirmed device mapping is
// 1=K and 2=A. The netlist deliberately expresses those pins by polarity name.
const netPinNumber = (ref, pin) => {
  if (/^D[1-4]$/.test(ref)) {
    if (pin === 'K') return '1';
    if (pin === 'A') return '2';
  }
  return String(pin);
};

const run = async () => {
  if (!eda?.sch_PrimitiveWire || !eda?.sch_PrimitiveComponent || !eda?.sch_PrimitiveText || !eda?.sch_Document || !eda?.sys_FileManager) {
    throw new Error('Required EasyEDA schematic APIs are unavailable');
  }

  const placedByRef = new Map(placementResult.placed.map(item => [item.ref, item]));
  const pinByKey = new Map();
  for (const component of placementResult.placed) {
    for (const [number, x, y, rotation] of component.pins) {
      pinByKey.set(`${component.ref}:${number}`, { x, y, rotation });
    }
  }

  // Verify the snapshots agree before changing the active schematic.
  for (const [net, members] of Object.entries(netlist.nets)) {
    for (const [ref, logicalPin] of members) {
      if (!placedByRef.has(ref)) continue; // L1 and test points are virtual.
      const pinNumber = netPinNumber(ref, logicalPin);
      if (!pinByKey.has(`${ref}:${pinNumber}`)) throw new Error(`No placed pin for ${ref}.${logicalPin} on ${net}`);
    }
  }

  const wireCountBefore = (await eda.sch_PrimitiveWire.getAll()).length;
  const createdWires = [];
  const createdPorts = [];

  for (const [net, members] of Object.entries(netlist.nets)) {
    for (const [ref, logicalPin] of members) {
      if (!placedByRef.has(ref)) continue;
      const pin = pinByKey.get(`${ref}:${netPinNumber(ref, logicalPin)}`);
      // Pins face 0° (right) or 180° (left). A 20-unit stub leaves U1's
      // 10-unit pin pitch intact and gives each label its own attachment point.
      const dx = pin.rotation === 180 ? -20 : 20;
      const portX = pin.x + dx;
      const wire = requireResult(
        await eda.sch_PrimitiveWire.create([pin.x, pin.y, portX, pin.y], net),
        `wire ${ref}.${logicalPin} (${net})`,
      );
      const port = requireResult(
        await eda.sch_PrimitiveComponent.createNetPort('BI', net, portX, pin.y, pin.rotation, false),
        `net port ${ref}.${logicalPin} (${net})`,
      );
      createdWires.push(wire.getState_PrimitiveId());
      createdPorts.push(port.getState_PrimitiveId());
    }
  }

  // L1 is implemented as the PCB spiral, and TP1/TP2 as PCB test pads. Show
  // their named connection points and explain the schematic representation.
  const virtualPorts = [
    { net: 'ANT_LA', x: 1120, y: 590, text: 'L1 PCB spiral end 1 (ANT_LA)' },
    { net: 'ANT_LB', x: 1120, y: 550, text: 'L1 PCB spiral end 2 (ANT_LB)' },
    { net: 'VOUT', x: 1120, y: 430, text: 'TP1 PCB test pad on VOUT' },
    { net: 'GND', x: 1120, y: 390, text: 'TP2 PCB test pad on GND' },
  ];
  for (const item of virtualPorts) {
    const port = requireResult(
      await eda.sch_PrimitiveComponent.createNetPort('BI', item.net, item.x, item.y, 0, false),
      `virtual net port ${item.text}`,
    );
    const text = requireResult(
      await eda.sch_PrimitiveText.create(item.x + 25, item.y, item.text, 0, null, null, 10, false, false, false),
      `annotation ${item.text}`,
    );
    createdPorts.push(port.getState_PrimitiveId());
  }

  const saved = await eda.sch_Document.save();
  if (saved !== true) throw new Error('SCH_Document.save() returned false');
  const nativeSource = await eda.sys_FileManager.getDocumentSource();
  if (typeof nativeSource !== 'string' || nativeSource.length === 0) throw new Error('Could not retrieve native schematic source');
  const wireCountAfter = (await eda.sch_PrimitiveWire.getAll()).length;

  return {
    status: 'schematic-wired-and-saved',
    wireCountBefore,
    wireCountAfter,
    createdWireIds: createdWires,
    createdNetPortIds: createdPorts,
    nativeSource,
    note: 'Connectivity construction only; no ERC result is asserted.',
  };
};

return await run();
