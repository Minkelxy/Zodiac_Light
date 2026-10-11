# 37 mm 双面 NFC 符咒

本目录存放硬件工程、评审记录和制造草案。当前项目目标与同步状态见[当前项目说明](../../docs/current-project.md)；各类详细资料及历史快照入口见[文档地图](../../docs/document-map.md)。

当前原生工程已集成两款独立的 37 mm 双面 NFC 符咒：**马 + 射手座**与**蛇 + 狮子座**。两款共用核心电路，各有一块独立的 100×100 mm、五片拼板。对称 LED 已应用：Top D1/D2=(-6,0)/(+6,0) mm、Bottom D3/D4=(-6,0)/(+6,0) mm（核心板原生坐标）；R1–R4 保持原位。核心板和两块拼板保存重开 DRC 均为空。当前结论、UUID、审计与导出入口见[当前项目说明](../../docs/current-project.md)。项目仍处于 `HOLD_CAM_C1_PHYSICAL_VALIDATION_PENDING`：C1采购、正式 CAM 和首件光效/RF/NFC 验收未完成，记录模板仍待填写。

## 重要边界

- 本目录有离线生成脚本和嘉立创EDA桥接脚本。请按[文档地图](../../docs/document-map.md)先读对应说明和脚本；不要把 Python/SVG 或编号脚本目录不加辨别地全部运行，部分编号脚本会改写活动 EDA 文档。
- 当前原生工程和共同检查以 `variants/common/export-manifest.json`、`native-archive-validation.json`、`native-copper-audit.json`、`face-geometry-audit.json` 为入口；两款各自的 Gerber/BOM/PnP review 文件在 `variants/horse-sagittarius/manufacturing-draft/` 与 `variants/snake-leo/manufacturing-draft/`。
- 根目录 `manufacturing/draft/` 与旧原生快照是历史版本，不是两款新版导出。当前新版仍是待 CAM、C1 采购和实物验收的草案，不能视为制造放行。
