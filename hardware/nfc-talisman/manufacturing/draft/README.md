# 当前制造与装配草案

`nfc-talisman-panel-cam-review.zip` 用于本地 CAM 评审。它保留原始导出的铜层、丝印、阻焊、锡膏、板框，以及一份 PTH 和一份 NPTH 钻孔程序，文件内容未重写。原始 `nfc-talisman-panel-draft.zip` 同时包含两个完全重复的 PTH 程序，需避免将它们重复作为钻孔输入。处理依据、SHA-256 和文件清单分别见 `cam-package-manifest.json` 与 `export-manifest.json`。

初检确认 22 条板框路径显式闭合，100×100 mm 外尺寸、100 个邮票孔、8 个星孔和 10 个金属化过孔符合当前源数据；顶层线圈和底层引出与原生工程一致。详见 `cam-audit.json`。刀补、孔槽公差、最短光槽与 3 mm 支撑条仍须加工评审。

TP1/TP2 的顶面 Ø0.8 mm 铜面及 Ø0.9 mm 阻焊开窗已在 Gerber 中核对，锡膏层没有对应开窗；两点分别连接 VOUT/GND，不是采购器件，不进入 BOM/PnP。铜审计覆盖两点与引线、11 个网络连通性以及核心板/拼板平移一致性，见 `../../electrical/native-copper-audit.json`。归档脚本会拒绝与 ZIP 不匹配或有关键检查失败的 CAM 报告。

| 装配选择 | BOM | 拼板坐标 | 不焊器件 |
|---|---|---|---|
| 默认四灯，14 件 | `four-led-bom.csv` | `four-led-panel-pnp.csv` | CT2 |
| 两灯减载，12 件 | `two-led-bom.csv` | `two-led-panel-pnp.csv` | CT2、D2、D4 |

两灯方案保留 R2、R4，开路 LED 支路不消耗电流。坐标沿用嘉立创EDA的毫米数据与底面旋转值；贴装前仍须核对 LED 实物阴极标记及底面旋转约定。`*-all.csv` 是原始全量导出，实际以制表符分隔，含 CT2 的 47 pF 库占位信息，不能直接用作装配清单。工程 BOM 已将 CT2 定义为未选值的 DNP 调谐位，两种装配清单都已剔除。

马图和彩色丝印尚未导入，马盖板透光开窗尚未定义。当前草案不满足制造放行条件；继续完成图案与光路、ERC 库警告复核、CAM 与装配检查，再进行裸核心/叠装调谐、手机和光学验收。最终粘接须等实物测试完成。
