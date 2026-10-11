# NFC 符咒文档地图

从[当前项目说明](current-project.md)查看两款产品目标和已同步状态。硬件目录的短入口是 [`hardware/nfc-talisman/README.md`](../hardware/nfc-talisman/README.md)。

## 按工作主题查阅

| 主题 | 入口 | 用途与边界 |
|---|---|---|
| 项目状态 | [`docs/current-project.md`](current-project.md) | 当前两款目标；未同步状态明确标注。 |
| 星图与 LED 审阅 | [双款设计审阅](../hardware/nfc-talisman/variants/common/design-review.md) | 美观判断、槽与星孔的视觉取舍、对称 LED 布局及实物光效验证边界。 |
| 两款共用工程与清单 | [`variants/common/export-manifest.json`](../hardware/nfc-talisman/variants/common/export-manifest.json)、[`variants/common/native-archive-validation.json`](../hardware/nfc-talisman/variants/common/native-archive-validation.json) | 共用核心和两拼板 UUID、保存重开 DRC、原生归档及当前版本文件清单。 |
| 共用铜/面板几何审计 | [`native-copper-audit.json`](../hardware/nfc-talisman/variants/common/native-copper-audit.json)、[`face-geometry-audit.json`](../hardware/nfc-talisman/variants/common/face-geometry-audit.json)、[对称核心布局图](../hardware/nfc-talisman/variants/common/layout-review/symmetric-core-layout-review.png) | 当前两面、两拼板审计和 LED 对称布局图。 |
| Horse + Sagittarius 当前包 | [`Horse–Sagittarius Gerber 与 BOM/PnP`](../hardware/nfc-talisman/variants/horse-sagittarius/manufacturing-draft/README.md)、[盖板预览](../hardware/nfc-talisman/variants/horse-sagittarius/artwork/cover-review-preview.png) | 当前候选盖板及该版本制造草案；仍待 CAM、C1 与实体验证。 |
| Snake + Leo 当前包 | [`Snake–Leo Gerber 与 BOM/PnP`](../hardware/nfc-talisman/variants/snake-leo/manufacturing-draft/README.md)、[盖板预览](../hardware/nfc-talisman/variants/snake-leo/artwork/cover-review-preview.png) | 9 星/10 图案边、8 物理槽、2 短印线；当前候选盖板及该版本制造草案。 |
| 电路与装配 | [`electrical/source-index.md`](../hardware/nfc-talisman/electrical/source-index.md)、[`electrical/assembly.md`](../hardware/nfc-talisman/electrical/assembly.md) | 电路来源、元件和既有装配说明。 |
| 机械和板框 | [`geometry/README.md`](../hardware/nfc-talisman/geometry/README.md)、[`geometry/layout-review-v3.md`](../hardware/nfc-talisman/geometry/layout-review-v3.md) | 既有 37 mm 外形、五片拼板和布局依据。 |
| 图案 | [`artwork/README.md`](../hardware/nfc-talisman/artwork/README.md)、[`artwork/production-study-v1/README.md`](../hardware/nfc-talisman/artwork/production-study-v1/README.md) | 图案源数据、校样和历史候选。 |
| LED 与光效历史 | [`manufacturing/star-led-review-v1/README.md`](../hardware/nfc-talisman/manufacturing/star-led-review-v1/README.md) | 首件 LED/星孔位置与光路推演。旧坐标不代表当前灯位；当前坐标见共同导出清单。点源模型不是实物光效验证，首件光效验收仍待完成。 |
| 制造草案与风险 | [`manufacturing/README.md`](../hardware/nfc-talisman/manufacturing/README.md)、[`manufacturing/validation-status.md`](../hardware/nfc-talisman/manufacturing/validation-status.md) | 材料、拼板和版本化草案状态；旧报告保留其检查边界。 |
| 历史推进记录 | [`manufacturing/improvement-review-2026-10-11.md`](../hardware/nfc-talisman/manufacturing/improvement-review-2026-10-11.md)、[`manufacturing/design-review-v3.md`](../hardware/nfc-talisman/manufacturing/design-review-v3.md) | 仅记录单拼板阶段；双款当前状态以共同导出清单为准。 |
| 原生 EDA 与脚本边界 | [`eda/api-notes.md`](../hardware/nfc-talisman/eda/api-notes.md) | 活动文档、桥接操作和原生快照的边界。执行编号脚本前应先读此处及目标脚本。 |
| 历史导出版本 | [`manufacturing/draft/export-manifest.json`](../hardware/nfc-talisman/manufacturing/draft/export-manifest.json) | 单拼板旧制造草案；请勿与当前两款版混用。当前版见 `variants/common/export-manifest.json` 与各 variant 制造草案目录。 |

## 历史记录如何使用

详细评审、审计日志、几何数据、图片、生成物和源快照继续留在各自目录，按其记录日期、输入哈希和适用版本查阅。本次整理只增加当前入口与导航，没有移动、删除或重写旧记录。

遇到互相冲突的旧结论时，优先查看更晚、来源和版本明确的原生快照/导出清单及对应检查；把旧内容作为它当时的记录，不覆盖成当前状态。旧编号 `.js` 桥接脚本按特定阶段设计，可能写入活动 EDA；Python/SVG 生成脚本也会重建各自输出文件。不要不加辨别地整批运行脚本。先阅读其文档和代码，确认输入、目标、写入范围与阶段条件。
