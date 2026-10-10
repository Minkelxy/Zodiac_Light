# NFC 符咒硬件工程入口

这是 37 mm 双面 NFC 符咒的可审阅本地工程资料与离线生成工具。当前目录保存了原理图/网表交接数据、机械与图案源数据、预览、检查日志，以及从嘉立创EDA读取的部分原生源快照。`eda/native/*.jsonl` 是各文档源快照，`eda/native/*netlist.json` 是网表快照。原生项目备份 [`eda/native/nfc-talisman-before-routing.epro2`](eda/native/nfc-talisman-before-routing.epro2) 保存于本轮布线前；大小 81,585 字节，SHA-256 为 `7693e32ad0698fc63b5f0cbb01309796e909396d6653143ebdb65f4ab077eaa5`。当前原生项目见 [`eda/native/nfc-talisman-current.epro2`](eda/native/nfc-talisman-current.epro2)，其精确版本与导出 SHA-256 以 [`manufacturing/draft/export-manifest.json`](manufacturing/draft/export-manifest.json) 为准。活动项目名、核心板与拼板文档 UUID、实时状态以 [`eda/api-notes.md`](eda/api-notes.md) 为准。

## 先看这些

- [`manufacturing/design-review-v3.md`](manufacturing/design-review-v3.md)：最新原理图整理、PCB 布局调整、板框检查和 BOM 结论。
- [`eda/schematic-review.png`](eda/schematic-review.png)：实际原理图预览；[`geometry/core-layout-review-v3.png`](geometry/core-layout-review-v3.png) 为两面布局预览；[`manufacturing/bom-ready.csv`](manufacturing/bom-ready.csv) 为汇总物料表，C1 状态见 [`manufacturing/bom-review.md`](manufacturing/bom-review.md)。
- [`electrical/source-index.md`](electrical/source-index.md)：电路来源与交接资料。
- [`electrical/assembly.md`](electrical/assembly.md)：器件与电路装配说明。
- [`geometry/README.md`](geometry/README.md)：机械几何定义及检查入口。
- [`artwork/README.md`](artwork/README.md)：图案源数据与评审状态。
- [`manufacturing/README.md`](manufacturing/README.md)：板材、层序、拼板和加工要求。
- [`manufacturing/draft/export-manifest.json`](manufacturing/draft/export-manifest.json)：本轮制版草案文件清单及参数。
- [`manufacturing/validation-status.md`](manufacturing/validation-status.md)：已有检查状态与未决事项。
- [`manufacturing/acceptance-checklist.md`](manufacturing/acceptance-checklist.md)：样件、CAM 与制造放行清单。
- [`eda/api-notes.md`](eda/api-notes.md)：本地与 live EDA 的边界、文档 UUID、近期 ERC/DRC 记录。

## 离线环境与再生成

在仓库根目录 `D:\星座灯` 执行。Python 3.11+ 是电气生成脚本要求；机械几何和预览生成依赖 Shapely 2.x 与 Pillow，依赖已列在本目录 [`requirements.txt`](requirements.txt)。

```powershell
python -m pip install -r hardware/nfc-talisman/requirements.txt
python hardware/nfc-talisman/scripts/build_electrical.py
python hardware/nfc-talisman/scripts/build_mechanical.py
python hardware/nfc-talisman/scripts/build_star_face.py
python hardware/nfc-talisman/scripts/build_mechanical.py --assembly-only
python hardware/nfc-talisman/scripts/build_antenna_fill_candidate.py
python hardware/nfc-talisman/scripts/validate_antenna_geometry.py
python hardware/nfc-talisman/scripts/audit_existing_routes.py
python hardware/nfc-talisman/scripts/summarize_checks.py
python hardware/nfc-talisman/scripts/archive_check_summary.py
```

`build_mechanical.py` 从仓库根目录 `data/constellation.json` 读取星座源数据，重建本目录 `geometry/` 下的几何、验证结果与预览；`--assembly-only` 只重建装配辅助文件。`build_electrical.py` 重建 `electrical/` 下电气交接产物；只有明确需要下载器件资料时才加 `--download-sources`。天线填充候选与几何复核、已有走线审计均为离线步骤。生成会更新对应输出文件，需在提交前检查差异。

射手座当前保留 8 个 Ø0.8 mm 星孔与 11 条 1 mm 独立槽，每个槽端分别优化，最短槽由 1.202 mm 延长到 1.489 mm；名义实材目标为 1.03 mm。新增 8 个细星环与 22 条细连接线，保留拉丁文字。已将深底浅线的 37×37 mm RGBA 图嵌入拼板；孔槽和板外透明。预览见 [`artwork/sagittarius-face-review.png`](artwork/sagittarius-face-review.png)，原生画布见 [`artwork/panel-native-render.png`](artwork/panel-native-render.png)。

实际原生与 Gerber 核对见 [`manufacturing/draft/star-face-audit.json`](manufacturing/draft/star-face-audit.json)；彩印注册、原生嵌图和专用文件完整性见 [`manufacturing/draft/star-color-audit.json`](manufacturing/draft/star-color-audit.json)。普通线稿和原色图片叠放的最终颜色、透明区及刀补仍须官方加工预览确认。`build_star_face.py` 只更新本地源和候选图；`42-*`、`43-*` 是带备份/保护条件的阶段性实时修改，已执行后不能重复运行。

## 嘉立创EDA桥接操作

`scripts/*` 不是可以整体一键执行的 EDA 安装/导入程序。编号 `.js` 文件是针对具体活动文档与阶段编写的桥接片段；部分脚本会修改 live EDA 文档，执行前必须先读 [`eda/api-notes.md`](eda/api-notes.md) 和对应脚本，确认目标文档、操作内容及是否有 `APPLY` 开关。离线 Python 生成的中间文件也不会自动写入嘉立创EDA。

尤其是 `build_panel_import.py` 会从机械、图案和电气数据编译桥接脚本输入；它本身不连接 EDA。`scripts/20-*`、`21-*` 等编号脚本属于按阶段执行的 live 文档操作；其所需阶段输入快照已保留在 `eda/native/`，`24-schematic-erc-current.js`、`25-core-pcb-drc-current.js`、`26-panel-pcb-drc-current.js` 则在客户端检查指定文档并写出日志。不要把脚本目录直接全选运行，也不要把已生成的几何/天线候选视为已写入 EDA。

检查日志位于被 Git 忽略的 `eda/logs/`。生成最新三项检查的机器可读摘要：

```powershell
python hardware/nfc-talisman/scripts/summarize_checks.py
python hardware/nfc-talisman/scripts/archive_check_summary.py
```

摘要对缺日志、读取失败、检查错误和 DRC/ERC 发现分别给出明确状态。当前核心板和拼板已完成布线；保存、关闭并重开后的原生 DRC 均返回空结果，天线桥接铜皮也已原生往返确认。面板原 22 条轮廓 GKO 未显式闭合造成的加工缺口已在生成器和 live 面板中修正；更新后保存、关闭并重开，DRC 仍为空。制造草案和导出清单见 [`manufacturing/draft/export-manifest.json`](manufacturing/draft/export-manifest.json)。`bom-all.csv`/`pnp-all.csv` 是包含 DNP 占位的原始导出，不可用于装配；推荐默认四灯配置为 14 件，另有移除 D2/D4 的两灯减载版本 12 件（R2/R4 保持 Fit）。仅 CT2 固定 DNP，默认仍为四灯。制造草案已通过只读 CAM 几何初检：22/22 条 GKO 闭合、10 个 PTH 与 108 个 NPTH、线圈/引出铜一致性、TP1/TP2 铜与阻焊开窗/无锡膏均通过。正式刀补、槽加工与工艺评审仍待完成；PTH 两个导出文件命中位置相同，正式CAM需择一避免重复钻孔。当前 Gerber 为 `colorSilkscreen=true`，已有射手座彩印专用文件；马图未包含，彩印合成效果待官方加工预览。裸板/叠装 RF、手机、马图光路和实物验收尚未完成。TP1/TP2已加入当前快照：核心板VOUT/GND顶层圆铜直径0.8 mm，阻焊开窗0.9 mm，无孔、无钢网开窗，且不进入BOM/PnP。


当前 ERC/DRC 检查摘要与原生源文件哈希归档于 [`eda/check-summary.json`](eda/check-summary.json)，可用 `scripts/archive_check_summary.py` 重建；摘要标为 `current_draft`，并非制造放行。只读铜审计 `scripts/audit_native_copper.py` 与草案 CAM 审计 `scripts/audit_manufacturing_draft.py` 分别输出 `electrical/native-copper-audit.json` 和 `manufacturing/draft/cam-audit.json`。只有在 native 快照和导出 manifest 对应同一版设计后才运行/采信审计；这些本地离线审计不连接或修改 live 嘉立创EDA。

2026-10-10：新增 [十二符咒与十二星座素材索引](artwork/reference-collection/index.html)、[来源说明](artwork/reference-collection/README.md) 与 [ZIP整包](artwork/reference-collection.zip)。符咒提供完整源 PNG 和十二张独立动物透明 PNG，可在索引中切换对照；透明版采用原像素蒙版，未重绘，保留 200×141 画布及原配色/朝向。星图有可编辑 SVG；本轮未改 EDA/制造设计。
