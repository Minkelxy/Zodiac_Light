# 原理图、板框、布局及 BOM 复核 v3

2026-10-10：已应用到嘉立创EDA项目 `37mm双面NFC符咒首版`，保存重开后检查，并重新导出原生工程、Gerber、BOM 和贴片坐标。文件版本见 [导出清单](draft/export-manifest.json)。当前仍是样件草案，实物与制造放行未完成。

## 已完成

| 项目 | 结果与证据 |
|---|---|
| 接线 | 原理图、核心、拼板均 15 器件、36 引脚、11 网络，全部连接一致。见 [网表审计](../electrical/native-netlist-audit.json)。 |
| 原理图 | 按天线调谐、NTAG 供能、上拉电阻、四路 LED 分区，整理位号、数值、网标；LED 按 VOUT→R→A→K→GND 直接连线。见 [实际导出预览](../eda/schematic-review.png)、[SVG](../eda/schematic-review.svg)。 |
| ERC | 0 错误，保留原有 1 个 ATTRMATCHCODE 属性警告，涉及 U1、C1、CT1、CT2、R1–R7；具体触发属性尚未确认，未关闭规则。 |
| PCB | 四颗限流电阻向中心约 0.20 mm；核心和拼板各修正 10 条局部走线，射频区、LED、天线和过孔位置保留。见 [应用记录](../eda/layout-application-v3.json)、[两面实际布局](../geometry/core-layout-review-v3.png)。 |
| 铜距 | 目标焊盘间距约 0.387–0.392 mm，全板最小异网铜距由约 0.18669 mm 提升至 0.20140041 mm；连通、板框内收、钻孔、天线桥接及拼板平移均通过。见 [铜审计](../electrical/native-copper-audit.json)。 |
| DRC | 核心与拼板保存重开后均 0 项。见 [检查摘要](../eda/check-summary.json)。 |
| 制造导出 | 22 条闭合 GKO 轮廓、100×100 mm 包围盒（含取整误差）、10 PTH、108 NPTH；贴片位置与实际器件匹配。见 [CAM 审计](draft/cam-audit.json)。 |

## 合理性与实际限制

纯 RF 收能时 VCC 接 VOUT 符合 NXP 应用说明；C1 是唯一储能/去耦电容，150 nF、±10% 上限约 165 nF，低于 220 nF。LA/LB 接线圈两端，CT1/CT2 跨 LA–LB，CT2 保持 DNP。芯片输入电容典型约 50 pF，外接 47 pF 仅作起始值，最终需整机调谐。[NXP 数据手册 §8.6、表 30](https://www.nxp.com/docs/en/data-sheet/NT3H2111_2211.pdf)

R5/R6/R7 将 SCL/SDA/开漏 FD 上拉到 VOUT。当前无外部 I2C 主机，未来接主机需复核上升时间。每颗 LED 独立串联 2.2 kΩ，库映射 **1=K、2=A**。以 3.3 V、典型 Vf≈2.05 V 粗估四路合计约 2.27 mA，不能保证实际收能或亮度；须测弱场、启动、写入时的 VOUT，并比较两灯减载方案。

37 mm 对边距八边形、30 mm 内窗和五片位置保留。上下 3 mm 支撑条、骨架、tab、邮票孔连接通过，板间净距最小约 2.598 mm。八星/十一槽的实材桥约 1.03 mm，光口均在镜像后的垫环窗口内。见 [机械复核](../geometry/layout-review-v3.md)、[孔槽审计](draft/star-face-audit.json)。

最高器件约 0.55 mm，在 1 mm 腔内名义余量约 0.45 mm，须计焊料/板厚/胶层公差做干装。TP1/TP2 供裸板测量，胶合后无法外部接触。背面星孔距最近 LED 中心约 2.78–19.75 mm，不能单凭几何证明均匀透光；需比较非金属扩散片，逐孔槽验收后胶合。

## BOM 与待办

[汇总 BOM](bom-ready.csv) 和 [供应复核](bom-review.md) 已准备：四灯 14 件，两灯 12 件；两灯仅不装 D2/D4，R2/R4 保留。装配 BOM 与坐标在 `draft/four-led-*`、`draft/two-led-*`。CT2 不采购，原生全器件导出的 47 pF/C60137 只是占位；L1、TP1/TP2 是铜结构，不采购。

C1 当前 Murata `GRM155R71C154KA12D / C162182` 在原生库描述中标为 NRND，选料暂缓。同规格 CCTC `TCC0402X7R154K160AT / C7393865` 为非叠加备选，数量 0，尚未替换工程中的 C1；切换前需确认尺寸并同步原生器件和 BOM。库存只是当日快照。

待办：用户手动导入忠于参考的灰底紫马图及光窗；官方加工预览确认彩印/线稿叠放、透明区、刀补和分板；C1 选料同步；裸核心及五层调谐、VOUT/LED 负载、Android/iPhone 两面格式化与读写、逐孔槽光学验收。未下单、送厂、发布或联系第三方。
