# NFC 工艺与盖板选项导航

产品主题为 **马 + 射手座**、**蛇 + 狮子座**。两款各使用独立的 100 × 100 mm 五片拼板，共用 37 mm 核心板设计；工艺版本分别保存，避免混用图案、原生 PCB 与制造数据。

| 工艺版本 | 入口 | 文件与检查边界 |
|---|---|---|
| 十二星座 / 十二生肖盖板 | [四块五片拼板](twelve-options/README.md)、[全九 PCB 工程](twelve-options/eda/native/nfc-twelve-options.epro2)、[清单](twelve-options/export-manifest.json) | 新增十星座与十生肖，绿色阻焊、白色丝印；四板保存重开 DRC 均为 0，归档、Gerber 实际区域和连板几何检查通过；正式 CAM 与首件待确认。 |
| 原彩色双款 | [原生工程](common/eda/native/nfc-two-variants.epro2)、[导出清单](common/export-manifest.json)、[设计审阅](common/design-review.md) | 原彩色图案与原生归档保留。已保存/重开检查和当前审计属于该版本；正式 CAM、C1 与实物验收待完成。 |
| 绿色阻焊 + 白色丝印 | [绿白普通工艺版](standard-green-white/README.md)、[全 5 PCB 原生工程](standard-green-white/eda/native/nfc-color-and-green-white.epro2)、[导出清单](standard-green-white/export-manifest.json) | 两款新 PCB 已保存重开，DRC 均为 0；无彩色喷印、无装饰铜，孔槽周围阻焊开窗。全工程与普通 Gerber 已导出，文件与实际图案区域检查通过。 |

原彩色各款资料分别见 [Horse + Sagittarius](horse-sagittarius/manufacturing-draft/README.md)、[Snake + Leo](snake-leo/manufacturing-draft/README.md)。`snake-leo/README.md` 是独立几何候选阶段记录，当前彩色集成以共同清单为准。

当前两种工艺均未制造放行，保持 **`HOLD_CAM_C1_PHYSICAL_VALIDATION_PENDING`**。图案预览表示设计，不是实物照片；供应商阻焊/丝印色差、套准、槽加工与实物 RF/NFC、透光效果须另行确认。
