# NFC 符咒当前项目说明

此页是两款 NFC 符咒的当前目标和状态入口。当前原生集成、保存重开 DRC 与新版导出已同步；实体验收和制造放行仍未完成。

星图美观和 LED 布局的结论见[双款设计审阅](../hardware/nfc-talisman/variants/common/design-review.md)。

## 当前目标

- 两款产品：**马 + 射手座**、**蛇 + 狮子座**。
- 每款都是独立的 37 mm 双面 NFC 符咒，使用各自的 **100×100 mm、五片拼板**；两款不合并为十片同板。
- 两款已集成在同一个嘉立创EDA工程，共用核心板 PCB1，并各有独立拼板 PCB。
- LED 按每面相对中心成对对称：Top D1=(-6,0)、D2=(+6,0) mm；Bottom D3=(-6,0)、D4=(+6,0) mm，坐标以核心板原生局部坐标为准。对称要求只针对 LED，R1–R4 保持原布局。保留首件光效验收待办与记录模板，但不把复杂光学优化作为对称布局的前提。

## 盘点得到的状态

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

旧版光学候选、BOM、单拼板 Gerber 与检查摘要仍对应各自历史版本。当前两款原生工程与导出以 `variants/common/export-manifest.json` 及各自 variant 草案目录为准。保存重开 DRC 和离线几何审计已通过；光效、RF/NFC、正式 CAM、C1 选料及实物首件仍未验收。查看分类入口请到[文档地图](document-map.md)。

更新本页时，应写入实际文件路径、原生板名或导出清单版本，并区分离线几何检查、原生 ERC/DRC、官方 CAM 与实体测试。未找到同步证据时继续标为“待同步”。
