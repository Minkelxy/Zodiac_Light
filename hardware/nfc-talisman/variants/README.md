# NFC 工艺与盖板选项导航

产品主题为 **马 + 射手座**、**蛇 + 狮子座**。两款各使用独立的 100 × 100 mm 五片拼板，共用 37 mm 核心板设计；工艺版本分别保存，避免混用图案、原生 PCB 与制造数据。

2026-10-20 边框修订覆盖全部六块绿白 PCB：四块选项拼板与两块整套拼板。新版统一使用九 PCB 集成工程；核心板与原彩色两板严格保留，两块既有绿白板更新受控丝印，并将全部拆板孔心外移 0.40 mm，旧五板归档及历史 release 保留。

| 工艺版本 | 入口 | 文件与检查边界 |
|---|---|---|
| 十二星座 / 十二生肖盖板 | [四块五片拼板](twelve-options/README.md)、[统一九 PCB 工程](twelve-options/eda/native/nfc-twelve-options.epro2)、[清单](twelve-options/export-manifest.json) | 新增十星座与十生肖，绿色阻焊、白色丝印；纹理边框版已保存重开，DRC 均为 0，原生与普通 Gerber 已导出，正式 CAM 与首件待确认。 |
| 原彩色双款 | [原生工程](common/eda/native/nfc-two-variants.epro2)、[导出清单](common/export-manifest.json)、[设计审阅](common/design-review.md) | 原彩色图案与原生归档保留。已保存/重开检查和当前审计属于该版本；正式 CAM、C1 与实物验收待完成。 |
| 绿色阻焊 + 白色丝印 | [绿白普通工艺版](standard-green-white/README.md)、[统一九 PCB 工程](twelve-options/eda/native/nfc-twelve-options.epro2)、[导出清单](standard-green-white/export-manifest.json) | 两款整套拼板同步纹理边框，保护铜/电路/星孔光槽/阻焊，拆板孔心外移 0.40 mm；保存重开 DRC 均为 0，普通 Gerber 实际图案审计通过，旧五板快照保留。 |
| 绿白历史五板快照 | [nfc-color-and-green-white.epro2](standard-green-white/eda/native/nfc-color-and-green-white.epro2) | 边框修订前的共用核心、两款原彩色与两款绿白拼板；作为历史版本查阅。 |

原彩色各款资料分别见 [Horse + Sagittarius](horse-sagittarius/manufacturing-draft/README.md)、[Snake + Leo](snake-leo/manufacturing-draft/README.md)。`snake-leo/README.md` 是独立几何候选阶段记录，当前彩色集成以共同清单为准。

当前两种工艺均未制造放行，保持 **`HOLD_CAM_C1_PHYSICAL_VALIDATION_PENDING`**。图案预览表示设计，不是实物照片；供应商阻焊/丝印色差、套准、槽加工与实物 RF/NFC、透光效果须另行确认。
