# 37 mm 双面 NFC 符咒

本目录存放硬件工程、评审记录和制造草案。当前项目目标与同步状态见[当前项目说明](../../docs/current-project.md)；各类详细资料及历史快照入口见[文档地图](../../docs/document-map.md)。

最新[十二星座与十二生肖盖板](variants/twelve-options/README.md)包含两块各五个星座、两块各五个生肖的 100 × 100 mm 普通绿白 PCB，配合马/蛇两块绿白整套拼板补齐完整选择。2026-10-20 修订将六块绿白板的图案边缘统一为白色纹理框与内外分界线；四块选项板仍为无元件盖板，不重复电路。[统一九 PCB 工程](variants/twelve-options/eda/native/nfc-twelve-options.epro2)保留核心板与原彩色两板；两块绿白整套拼板有意更新丝印，保护铜、天线、电路、孔槽和原阻焊。六板均已保存重开且 DRC 为 0，原生工程与普通 Gerber 已重新导出；审计适用版本由对应源文件哈希确认。

原彩色原生归档已集成两款独立的 37 mm 双面 NFC 符咒：**马 + 射手座**与**蛇 + 狮子座**。两款共用核心电路，各有一块独立的 100×100 mm、五片拼板。对称 LED 已应用：Top D1/D2=(-6,0)/(+6,0) mm、Bottom D3/D4=(-6,0)/(+6,0) mm（核心板原生坐标）；R1–R4 保持原位。原彩色归档的核心板和两块拼板保存重开 DRC 均为空。对应结论、UUID、审计与导出入口见[当前项目说明](../../docs/current-project.md)。项目仍处于 `HOLD_CAM_C1_PHYSICAL_VALIDATION_PENDING`：C1采购、正式 CAM 和首件光效/RF/NFC 验收未完成，记录模板仍待填写。

## 工艺版本

原彩色双款保留在原工程与原归档中。[绿色阻焊 + 白色丝印普通工艺版](variants/standard-green-white/README.md)的马与蛇各有独立 PCB，名称分别为 `Horse-Sagittarius-GreenWhite-100-v1`、`Snake-Leo-GreenWhite-100-v1`。绿色来自未开窗的阻焊，白色动物、星图、文字与纹理边框来自丝印，阻焊仍仅在原孔槽周围开窗。两款当前版本与四块选项板共用[统一九 PCB 工程](variants/twelve-options/eda/native/nfc-twelve-options.epro2)，状态见[独立清单](variants/standard-green-white/export-manifest.json)。[旧五 PCB 归档](variants/standard-green-white/eda/native/nfc-color-and-green-white.epro2)保留为加边框前历史快照，不覆盖。

工艺版本的工程、图案和清单见[版本导航](variants/README.md)。原彩色归档的 DRC 结果不直接证明新增绿白 PCB 的检查结果；绿白版仍保持相同制造 HOLD。

## 重要边界

- 本目录有离线生成脚本和嘉立创EDA桥接脚本。请按[文档地图](../../docs/document-map.md)先读对应说明和脚本；不要把 Python/SVG 或编号脚本目录不加辨别地全部运行，部分编号脚本会改写活动 EDA 文档。
- 当前原生工程和共同检查以 `variants/common/export-manifest.json`、`native-archive-validation.json`、`native-copper-audit.json`、`face-geometry-audit.json` 为入口；两款各自的 Gerber/BOM/PnP review 文件在 `variants/horse-sagittarius/manufacturing-draft/` 与 `variants/snake-leo/manufacturing-draft/`。
- 根目录 `manufacturing/draft/` 与旧原生快照是历史版本，不是两款新版导出。当前新版仍是待 CAM、C1 采购和实物验收的草案，不能视为制造放行。
