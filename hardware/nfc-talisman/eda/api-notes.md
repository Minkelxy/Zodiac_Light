# EasyEDA API notes (reference check)

Checked against `C:\Users\20177\.codex\skills\easyeda-api\references` and its `format/pcb` and `guide/cli.md` on 2026-10-09.

## Export files

- `eda.sys_FileManager.getProjectFile(fileName?, password?, fileType?: 'epro'|'epro2'): Promise<File|undefined>`. Requires Project Management > Download Project permission; missing permission throws. Save either with `sys_FileSystem.saveFile()` (browser/Electron save API) or `saveFileToFileSystem()`.
- `eda.pcb_ManufactureData.getGerberFile(...)`, `getPickAndPlaceFile(...)`, `getBomFile(...)` return `File|undefined`; each is documented Beta and remarks recommend `sys_FileSystem.saveFile()`.
- `saveFile(fileData: File|Blob, fileName?): Promise<void>` uses browser download / Electron save-file API and accepts no destination path.
- `saveFileToFileSystem(uri, fileData: File|Blob, fileName?, force?): Promise<boolean>` is Beta, client-only, and requires extension External Interactions permission. `uri` is a full file path unless it ends in `/` or Windows `\\` (folder); guide examples show absolute Windows paths. Example: `await eda.sys_FileSystem.saveFileToFileSystem('C:/Users/name/Documents/out.xlsx', file, undefined, true)`.
- The bridge result travels through JSON serialization, so don't return a `File`/`Blob` as if it were binary. Prefer saving inside EDA and return only `{saved,size,name}`. If text is needed, return `await file.text()`. Binary transfer can be base64 of `await file.arrayBuffer()` and decoded by the local caller, with payload-size overhead.

## Current document source

- `getDocumentSource(): Promise<string|undefined>` returns source for the currently active/open document; undefined means no document open or retrieval failed. `setDocumentSource(source:string): Promise<boolean>` returns false for invalid source format. Both are Beta.
- Source records are JSONL-like lines, each two JSON objects joined by `||` and ending `|`; first is metadata `{type,id,ticket}`, second is the primitive key/value object. A `DOCHEAD` begins each document. PCB docType is `PCB`; panels use docType `PANEL`. `getDocumentSource()` is a current document source, not a whole-project multi-document archive.
- PCB component instance `COMPONENT` carries anchor `positionX/Y`, `angle`, layer, attrs; `PAD_NET` maps pad number/net and optional footprint padId. In the format docs, footprint master data is a separate `FOOTPRINT` document. `PAD` records include centerX/Y but format documentation does not clearly specify in the component section whether any PCB override pad coordinates are component-local or board-global. Do not translate parent position and pad centers together without confirming actual source/API semantics for the concrete record IDs.
- Panel format page documents panelization setting records (`PANELIZE`, `PANELIZE_STAMP`, `PANELIZE_SIDE`) only. API has `dmt_Panel.copyPanel(panelUuid)` which duplicates a panel document; it does not describe importing a PCB/core into a panel or translating component and primitive geometry. No source-backed universal transform recipe found.

## Nets and DRC

- `NET` is net metadata; `PAD_NET` maps instance pad to named net. The EasyEDA API and PCB source-format references do not expose a bridge-copper/net-tie property on `FILL` through the documented API.
- The official EasyEDA user guide does document a native UI **bridge copper** property for PCB fill regions. It permits explicitly listed distinct nets to be shorted within that fill, and reports DRC errors if other nets enter the region. This is the intended way to represent the ANT_LA-to-ANT_LB spiral while preserving the two NFC chip nets. The exact bridge setting has not yet been applied or round-trip verified in this project; use the fill-region Properties panel, save, reopen, rerun DRC, and inspect Gerber before accepting it. [Official guide](https://prodocs.lceda.cn/cn/pcb/place-fill-region/)
- `pcb_Drc.check(strict,userInterface,false)` returns boolean; third arg `true` returns detailed array (`Array<any>` per docs). `sch_Drc.check` similarly returns `Array<ISCH_DrcError>` when verbose. Both beta.

## Live core-board status (2026-10-10)

- Active project `37mm双面NFC符咒首版`, core PCB document `eb14b9eaec4f920c` (`PCB1`). Live baseline had 15 components, 36 pads, no lines/vias. After the first safe signal/LED pass, 19 copper segments are saved; details are in `logs/20-core-nonantenna-routes.json`.
- Fresh native DRC after that pass reports 22 connection entries (ANT_LA 3, ANT_LB 3, VOUT 10, GND 6) and one netlist mismatch for the unrepresented physical L1 antenna. The returned report had no separate short/clearance group. Core routing remains incomplete; do not call this board DRC-clean.
- A fresh native schematic ERC on 2026-10-10 returned one warning class, `ATTRMATCHCODE`, for the library-backed parts; it returned no schematic errors. This should still be reviewed before release, especially alongside the PCB netlist mismatch.
- The 100×100 mm panel is a separate PCB document (`4a4719695b24dc2b`). Its geometry report passes basic topology checks, but the minimum star/slot and slot/slot material webs are only about 1 mm and its short routed slots need CAM review. The same 19 partial signal/LED traces were mirrored into the panel with a 50 mm offset (`scripts/21-panel-import-nonantenna-routes.js`); power, ground and antenna copper are still absent. No manufacturing files have been exported or reviewed yet.
