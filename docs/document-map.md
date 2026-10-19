# 项目文档地图

最新修订：[十二星座与十二生肖](../hardware/nfc-talisman/variants/twelve-options/README.md)、[统一九 PCB 原生工程](../hardware/nfc-talisman/variants/twelve-options/eda/native/nfc-twelve-options.epro2)。六块绿白 PCB 采用统一白色纹理边框与内外分界线，均已保存重开且 DRC 为 0，原生与普通 Gerber 已重新导出；核心板和原彩色两板保留。两份展示 PDF 的来源由本轮清单绑定。

从[总 README](../README.md)进入项目，从[当前项目状态](current-project.md)查看灯带、U1 制作稿和 NFC 双款的保存状态。安装、检查和打包见[复现与交付指南](delivery.md)。

## 灯带与亚克力制作

| 主题 | 入口 | 用途与边界 |
|---|---|---|
| 40 cm 当前制作稿 | [output/README.md](../output/README.md)、[U1 刻线母图](../output/engraving-final-u1/engraving-master.svg) | U1 最终选定造型；六张 A4 打印拼接，先校准 100 mm 尺。 |
| 作者数据与来源 | [data/README.md](../data/README.md)、[数据模型](data-model.md) | 21 星/24 边天文身份、图坐标、268 灯实体裁切与串接，及来源许可。 |
| 软件预览与导出 | [总 README 的灯带说明](../README.md#40-cm-ws2812-星座灯) | 九种灯效、静态图、运行表、裁切 CSV 与 C 头文件。 |
| ESP32 驱动与协议 | [hardware.md](hardware.md)、[protocol.md](protocol.md) | ESP-IDF 编译、接线、CLP1 握手和帧协议；实板验收待完成。 |
| 图案过程记录 | [output/README.md 的设计过程](../output/README.md#设计过程) | A–D、E/F、R、T 与 U 候选；比较图不作为当前加工母图。 |
| 检查与交付 | [delivery.md](delivery.md)、[check_project.py](../scripts/check_project.py)、[package_project.py](../scripts/package_project.py) | 全项目验证、按提交打包、逐文件 SHA-256 与接收流程。 |

## NFC 当前双款及历史资料

硬件目录的短入口是 [`hardware/nfc-talisman/README.md`](../hardware/nfc-talisman/README.md)，工艺区别见[版本导航](../hardware/nfc-talisman/variants/README.md)。原彩色版以 `variants/common/` 清单和两款 `manufacturing-draft/` 为准；普通绿白版使用 `variants/standard-green-white/` 独立入口。其他目录中的旧描述按对应阶段阅读。

| 主题 | 入口 | 用途与边界 |
|---|---|---|
| 项目状态 | [`docs/current-project.md`](current-project.md) | 当前双款目标、归档证据与实物待办；制造 HOLD 保持。 |
| 星图与 LED 审阅 | [双款设计审阅](../hardware/nfc-talisman/variants/common/design-review.md) | 美观判断、槽与星孔的视觉取舍、对称 LED 布局及实物光效验证边界。 |
| 原彩色共用工程与清单 | [`variants/common/export-manifest.json`](../hardware/nfc-talisman/variants/common/export-manifest.json)、[`variants/common/native-archive-validation.json`](../hardware/nfc-talisman/variants/common/native-archive-validation.json) | 原彩色 3 PCB 归档：共用核心和两拼板 UUID、保存重开 DRC 及文件清单。 |
| 普通绿白双款 | [standard-green-white/README.md](../hardware/nfc-talisman/variants/standard-green-white/README.md)、[统一九 PCB 工程](../hardware/nfc-talisman/variants/twelve-options/eda/native/nfc-twelve-options.epro2)、[独立导出清单](../hardware/nfc-talisman/variants/standard-green-white/export-manifest.json)、[对比展示 PDF](../output/pdf/NFC符咒_绿白普通工艺展示.pdf) | 两款整套拼板的白色纹理框修订；原电气/孔槽/阻焊保护，保存重开 DRC 为 0、实际 Gerber 图案审计通过。 |
| 绿白历史五板快照 | [nfc-color-and-green-white.epro2](../hardware/nfc-talisman/variants/standard-green-white/eda/native/nfc-color-and-green-white.epro2) | 加边框前 5 PCB 归档保留，按旧版对应清单查阅。 |
| 共用铜/面板几何审计 | [`native-copper-audit.json`](../hardware/nfc-talisman/variants/common/native-copper-audit.json)、[`face-geometry-audit.json`](../hardware/nfc-talisman/variants/common/face-geometry-audit.json)、[对称核心布局图](../hardware/nfc-talisman/variants/common/layout-review/symmetric-core-layout-review.png) | 当前两面、两拼板审计和 LED 对称布局图。 |
| Horse + Sagittarius 当前包 | [`Horse–Sagittarius Gerber 与 BOM/PnP`](../hardware/nfc-talisman/variants/horse-sagittarius/manufacturing-draft/README.md)、[盖板预览](../hardware/nfc-talisman/variants/horse-sagittarius/artwork/cover-review-preview.png) | 当前候选盖板及该版本制造草案；仍待 CAM、C1 与实体验证。 |
| Snake + Leo 当前包 | [`Snake–Leo Gerber 与 BOM/PnP`](../hardware/nfc-talisman/variants/snake-leo/manufacturing-draft/README.md)、[盖板预览](../hardware/nfc-talisman/variants/snake-leo/artwork/cover-review-preview.png) | 9 星/10 图案边、8 物理槽、2 短印线；当前候选盖板及该版本制造草案。 |
| 电路与装配 | [`electrical/source-index.md`](../hardware/nfc-talisman/electrical/source-index.md)、[`electrical/assembly.md`](../hardware/nfc-talisman/electrical/assembly.md) | 电路来源、元件和既有装配说明。 |
| 机械和板框 | [`geometry/README.md`](../hardware/nfc-talisman/geometry/README.md)、[`geometry/layout-review-v3.md`](../hardware/nfc-talisman/geometry/layout-review-v3.md) | 既有 37 mm 外形、五片拼板和布局依据。 |
| 图案 | [`artwork/README.md`](../hardware/nfc-talisman/artwork/README.md)、[`artwork/production-study-v1/README.md`](../hardware/nfc-talisman/artwork/production-study-v1/README.md) | 图案源数据、校样和历史候选。 |
| LED 与光效历史 | [`manufacturing/star-led-review-v1/README.md`](../hardware/nfc-talisman/manufacturing/star-led-review-v1/README.md) | 首件 LED/星孔位置与光路推演。旧坐标不代表当前灯位；当前坐标见共同导出清单。点源模型不是实物光效验证，首件光效验收仍待完成。 |
| 首件与放行待办 | [`manufacturing/acceptance-checklist.md`](../hardware/nfc-talisman/manufacturing/acceptance-checklist.md)、[`manufacturing/sample-test-plan.md`](../hardware/nfc-talisman/manufacturing/sample-test-plan.md) | 实物、CAM、RF/NFC、供电与点亮的记录要求；需按当前双款快照选择适用项，空模板不代表验收完成。 |
| 单拼板制造历史 | [`manufacturing/README.md`](../hardware/nfc-talisman/manufacturing/README.md)、[`manufacturing/validation-status.md`](../hardware/nfc-talisman/manufacturing/validation-status.md) | 旧材料/单拼板草案与检查历史，可能记有已被双款集成替代的图案状态。 |
| 历史推进记录 | [`manufacturing/improvement-review-2026-10-11.md`](../hardware/nfc-talisman/manufacturing/improvement-review-2026-10-11.md)、[`manufacturing/design-review-v3.md`](../hardware/nfc-talisman/manufacturing/design-review-v3.md) | 仅记录单拼板阶段；双款当前状态以共同导出清单为准。 |
| 原生 EDA 与脚本边界 | [`eda/api-notes.md`](../hardware/nfc-talisman/eda/api-notes.md) | 活动文档、桥接操作和原生快照的边界。执行编号脚本前应先读此处及目标脚本。 |
| 历史导出版本 | [`manufacturing/draft/export-manifest.json`](../hardware/nfc-talisman/manufacturing/draft/export-manifest.json) | 单拼板旧制造草案；请勿与当前两款版混用。当前版见 `variants/common/export-manifest.json` 与各 variant 制造草案目录。 |

## 历史记录如何使用

详细评审、审计日志、几何数据、图片、生成物和源快照保留在各自目录，按其记录日期、输入哈希和适用版本查阅。当前入口与导航不覆盖旧记录的检查结论；交付 ZIP 同时保留这些过程资料。

遇到互相冲突的旧结论时，优先查看更晚、来源和版本明确的原生快照/导出清单及对应检查；把旧内容作为它当时的记录，不覆盖成当前状态。旧编号 `.js` 桥接脚本按特定阶段设计，可能写入活动 EDA；Python/SVG 生成脚本也会重建各自输出文件。不要不加辨别地整批运行脚本。先阅读其文档和代码，确认输入、目标、写入范围与阶段条件。
