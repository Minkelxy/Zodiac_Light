# 当前项目状态

本仓库交付灯带软件、40 cm 亚克力制作稿和两款 NFC 符咒设计草案。下表与 NFC 明细以保存文件和对应清单为依据；全项目检查与交付包使用方法见[复现与交付指南](delivery.md)。

## 40 cm 灯带与刻线稿

| 项目 | 当前保存内容与边界 |
|---|---|
| WS2812 布局 | [作者布局](../data/layout.json)保留 21 星、24 边，编译为 66 个裁切段、268 灯，面板为 400 × 400 mm；裁切、串接和灯效的使用说明见[总 README](../README.md)。 |
| 亚克力刻线 | 2026-10-14 选定 U1 紧凑短发与肩胸造型；[刻线母图](../output/engraving-final-u1/engraving-master.svg)为 290 条直线。U1 PDF 共 7 页，第 2–7 页是六张 1:1 A4 拼接纸；[制作资料入口](../output/README.md)列出打印和校准方法。 |
| 灯条定位 | 定位 PDF 共 9 页，第 2–7 页拼接，第 8–9 页为裁切表；定位清单与 U1 清单记录保存布局的来源哈希。 |
| 软件与固件 | Python 预览和原生 ESP32 灯效实现已有测试；ESP-IDF 5.5.1 构建成功属于开发记录。接收者须重新运行[项目检查](../scripts/check_project.py)并按[固件说明](hardware.md)安装 SDK 构建。板端刷新、色序、供电和实物光效尚未验收。 |

## NFC 双款

### 十二星座与生肖扩展（2026-10-15）

已新增[四块五片盖板拼板](../hardware/nfc-talisman/variants/twelve-options/README.md)：两块覆盖其余十个星座，两块覆盖其余十个生肖，配合原有射手、狮子与马、蛇补齐各十二款。四板均为 100 × 100 mm、绿色阻焊与白色丝印，盖板为 37 mm AF，可复用现有 NFC 核心。四板已保存、关闭重开，DRC 均为 0；[全九 PCB 原生工程](../hardware/nfc-talisman/variants/twelve-options/eda/native/nfc-twelve-options.epro2)、四份 Gerber、[来源及设计清单](../hardware/nfc-talisman/variants/twelve-options/design-manifest.json)、[实际 Gerber 与连板检查](../hardware/nfc-talisman/variants/twelve-options/gerber-geometry-audit.json)已保存。[五页展示 PDF](../output/pdf/十二星座与生肖_拼板展示.pdf)可直接分享。原有五份 PCB 的几何和图案保留；新盖板仍待供应商 CAM、板厚/拆板、叠装与光效首件确认。

原彩色两款 NFC 的原生集成、保存重开 DRC 与导出快照已同步；实体验收和制造放行仍未完成。星图美观和 LED 布局的结论见[双款设计审阅](../hardware/nfc-talisman/variants/common/design-review.md)。新增绿白普通工艺版的状态单列如下，所有版本入口见[工艺版本导航](../hardware/nfc-talisman/variants/README.md)。

### 新增绿色阻焊 + 白色丝印版

[绿白普通工艺版](../hardware/nfc-talisman/variants/standard-green-white/README.md)为马/蛇两款分别新增独立 PCB，名称为 `Horse-Sagittarius-GreenWhite-100-v1`、`Snake-Leo-GreenWhite-100-v1`。原彩色工程与图案保留；绿色来自未开窗的阻焊，白色轮廓、星图和文字来自丝印，无彩色喷印、无装饰铜。阻焊仅在原孔槽周围开窗；导出清单记录原孔槽、铜、天线与电路保护基线保持。

图案 SVG/PNG 和导入几何已生成，[对比展示 PDF](../output/pdf/NFC符咒_绿白普通工艺展示.pdf)为效果示意。[全五 PCB 集成归档](../hardware/nfc-talisman/variants/standard-green-white/eda/native/nfc-color-and-green-white.epro2)已导出，包含 1 个共用核心、2 个原彩色拼板和 2 个绿白拼板，大小 1,121,683 bytes；[独立导出清单](../hardware/nfc-talisman/variants/standard-green-white/export-manifest.json)记录两款新增 PCB 已保存重开且 DRC 均为 0，普通 Gerber 已导出。独立文件检查与 Gerber 图案区域审计通过，制造 HOLD 保持。

### 当前目标

- 两款产品：**马 + 射手座**、**蛇 + 狮子座**。
- 每款都是独立的 37 mm 双面 NFC 符咒，使用各自的 **100×100 mm、五片拼板**；两款不合并为十片同板。
- 两款已集成在同一个嘉立创EDA工程，共用核心板 PCB1，并各有独立拼板 PCB。
- LED 按每面相对中心成对对称：Top D1=(-6,0)、D2=(+6,0) mm；Bottom D3=(-6,0)、D4=(+6,0) mm，坐标以核心板原生局部坐标为准。对称要求只针对 LED，R1–R4 保持原布局。保留首件光效验收待办与记录模板，但不把复杂光学优化作为对称布局的前提。

### 原彩色双款归档证据记录的状态

| 项目 | 当前可确认状态 |
|---|---|
| 共用原生工程 | 项目 UUID `c051e4069a83472198ecce7729fbd257`。核心 PCB1 UUID `eb14b9eaec4f920c`；Horse-Sagittarius-100 拼板 UUID `4a4719695b24dc2b`；Snake-Leo 拼板 UUID `fe8ee4534ee0b941`（EDA 树名称仍为 `ManufacturingPanel100_1`）。三块 PCB 均已保存/重开，DRC 返回空数组。详见 [`export-manifest.json`](../hardware/nfc-talisman/variants/common/export-manifest.json)。 |
| 两款盖板图案 | 马、射手座、蛇、狮子座四个 37 mm 盖板图像已集成到原生拼板并通过 blob/源文件完整性审计；候选预览分别见 [Horse–Sagittarius](../hardware/nfc-talisman/variants/horse-sagittarius/artwork/cover-review-preview.png) 与 [Snake–Leo](../hardware/nfc-talisman/variants/snake-leo/artwork/cover-review-preview.png)。狮子座为 9 星/10 条图案边：8 条物理槽，2 条短边仅印线。 |
| LED 对称布局 | 已应用 Top D1/D2=(-6,0)/(+6,0) mm，Bottom D3/D4=(-6,0)/(+6,0) mm（核心板原生局部坐标）；只对称 LED，R1–R4 保持原位。LED 对称位置、网络连接与铜审计通过，三块 PCB 保存/重开 DRC 均为空。布局图见 [`symmetric-core-layout-review.png`](../hardware/nfc-talisman/variants/common/layout-review/symmetric-core-layout-review.png)。 |
| 原生归档及几何 | [`native-archive-validation.json`](../hardware/nfc-talisman/variants/common/native-archive-validation.json)、[`native-copper-audit.json`](../hardware/nfc-talisman/variants/common/native-copper-audit.json) 与 [`face-geometry-audit.json`](../hardware/nfc-talisman/variants/common/face-geometry-audit.json) 均为 PASS；共同原生工程归档为 [`nfc-two-variants.epro2`](../hardware/nfc-talisman/variants/common/eda/native/nfc-two-variants.epro2)，952,968 bytes。 |
| 新版制造数据 | 新版制造数据已导出，共同导出清单 [`export-manifest.json`](../hardware/nfc-talisman/variants/common/export-manifest.json) 记录 19 项文件；[`assembly-review-manifest.json`](../hardware/nfc-talisman/variants/common/assembly-review-manifest.json) 另记录 10 项装配审阅文件。两款各自的 Gerber ZIP、原始 BOM/PnP 与 four-led/two-led review BOM/PnP 位于 [Horse–Sagittarius 草案](../hardware/nfc-talisman/variants/horse-sagittarius/manufacturing-draft/README.md) 和 [Snake–Leo 草案](../hardware/nfc-talisman/variants/snake-leo/manufacturing-draft/README.md)。四灯/两灯为 14/12 个装配件；CT2 排除，C1 采购保持 HOLD。 |
| ERC 与放行状态 | ERC 为 0 errors，仍有 1 组 `ATTRMATCHCODE` 警告，涉及 11 个器件，触发字段待归因。放行状态为 `HOLD_CAM_C1_PHYSICAL_VALIDATION_PENDING`。 |
| 实物与制造验收 | 光效、RF/NFC 叠装调谐、正式 CAM 与样件验收仍待完成；首件验收记录模板为空/待填写。当前文件审计与 DRC 通过不代表已制造或放行。 |

## 资料边界

旧版光学候选、BOM、单拼板 Gerber 与检查摘要仍对应各自历史版本。原彩色两款工程与导出以 `variants/common/export-manifest.json` 及各自 variant 草案目录为准；普通绿白版使用独立目录与清单。`variants/snake-leo/README.md` 描述独立候选生成阶段，单拼板 `manufacturing/` 的旧记录可能仍写有“马图未导入”等当时状态；原彩色双款图案集成以共同清单和审计为准。归档的保存重开 DRC 和离线几何审计通过属于该版本；光效、RF/NFC、正式 CAM、C1 选料及实物首件仍未验收。查看分类入口请到[文档地图](document-map.md)。

40 cm 灯带的 21 星/24 边与 37 mm NFC 背面的星孔/槽图案是不同制作方案，不能混用其裁切、坐标或 BOM。U1 是当前亚克力打印稿；T4 和其他 E/R/T/U 候选保留用于设计过程对照。全项目文件检查通过表示归档内数据一致，不自动重跑 EDA，也不改变制造放行状态。

更新本页时，应写入实际文件路径、原生板名或导出清单版本，并区分离线几何检查、原生 ERC/DRC、官方 CAM 与实体测试。未找到同步证据时继续标为“待同步”。
