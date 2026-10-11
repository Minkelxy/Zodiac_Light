# EasyEDA ERC attribution — current native project

**Project:** `37mm双面NFC符咒首版`, UUID `c051e4069a83472198ecce7729fbd257`. **Schematic:** UUID `293c7786afd689e8`. **Read-only check:** fresh verbose `eda.sch_Drc.check(true,false,true)` on the currently open schematic. No schematic write/save was issued.

## Current result

- 0 errors; 1 warning group; rule `ATTRMATCHCODE`.
- Affected instances (11): U1, C1, CT1, CT2, R5, R6, R7, R1, R2, R3, R4.
- The API result identifies rule and instance list, but provides no field name, expected/actual values, or device/library side of a mismatch. Therefore the exact trigger is **not identified**.
- Existing current core DRC log: 0 groups, 15 components, 38 pads, 126 lines, 10 vias, 1 fill (`eda/logs/25-core-pcb-drc-current.json`). Existing current panel DRC log: 0 groups, 15 components, 146 pads, 126 lines, 10 vias, 1 fill, 118 polylines (`eda/logs/26-panel-pcb-drc-current.json`). This review made no geometry edit, so these checks were not rerun.

## Attribute comparison performed

Compared schematic instance records in the native JSONL source (per EasyEDA source format, records split on `||`) against available embedded/library device attribute records and the saved library query results. Observations include:

- Flagged schematic instances carry fixed display `Name` values while several library templates use expressions such as `={Value}` / `={Manufacturer Part}`. This is not sufficient attribution: unflagged D1–D4 show the same general class of instance override.
- Schematic instance `Footprint` attributes are null for multiple parts while their library templates have footprint references; the same pattern appears on unflagged LEDs, so this is not proven causal.
- CT2 retains a placeholder identity/value while its intended population is DNP, but the warning also includes the other ten devices.
- Current system-library UUIDs returned by lookup differ from historic embedded UUIDs; that alone does not establish an `ATTRMATCHCODE` mismatch.

No field difference is promoted to the exact ERC cause without field-level API detail or a controlled, reversible one-variable test. No library match code was changed, no check was hidden, and no component attributes were edited to suppress the warning.

## Evidence and next diagnostic

`fresh-live-erc.json` records the latest live result shape and affected instances; the existing raw API log at `eda/logs/24-schematic-erc-current.json` is the persisted baseline response and has the same result. `eda/logs/12-schematic-erc.json` is the earlier ERC run. For exact diagnosis, query/inspect the native match-code implementation or obtain an EasyEDA diagnostic that exposes the compared attribute pair; then test one reversible field correction at a time on a backed-up project, save/reopen, and rerun full ERC/DRC. The current bridge result alone cannot tell which field is responsible.

