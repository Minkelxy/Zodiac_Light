# 绿色阻焊 + 白色丝印普通工艺双款

本版为两款 37 mm 双面 NFC 符咒新增独立普通 PCB：**马 + 射手座**与**蛇 + 狮子座**。用户选定绿色阻焊、白色丝印；原彩色 PCB、图案和归档继续保留。本页记录图案输入与工程交付状态，当前保持 **`HOLD_CAM_C1_PHYSICAL_VALIDATION_PENDING`**。

2026-10-20 修订：两款绿白整套拼板与四块星座/生肖选项拼板同步增加白色纹理边框及内外分界线。核心板与原彩色两板完整保留；绿白两板有意更新丝印，铜、天线、电路、孔槽及原阻焊开窗为保护基线。六板均已保存重开且 DRC 为 0，两套当前清单共同绑定重新导出的统一九板归档；上一版检查仅适用于其历史快照。

## 两款独立 PCB

| 款式 | 原生 PCB 名称 | 拼板 | 外观预览 |
|---|---|---|---|
| 马 + 射手座 | `Horse-Sagittarius-GreenWhite-100-v1` | 独立 100 × 100 mm，五片 | [正反面预览](artwork/horse-sagittarius-standard-green-white-two-face-preview.png) |
| 蛇 + 狮子座 | `Snake-Leo-GreenWhite-100-v1` | 独立 100 × 100 mm，五片 | [正反面预览](artwork/snake-leo-standard-green-white-two-face-preview.png) |

两款不合并成十片同板。共用核心设计的两面 LED 分别位于 x=±6 mm、y=0，R1–R4 保持原布局。本轮变更限于受控的盖板丝印图案；原生 UUID 分别为 `7b9104396cd59877`、`8bb2139a68d10671`。两款均已保存重开，DRC 返回空数组；丝印差异和电气/机械保护检查共同绑定本轮源文件与导出清单。

## 普通工艺如何形成外观

- **绿色底色**：未开窗的绿色阻焊，不能用阻焊层的整版填充代表绿底；阻焊开窗表示去绿油。
- **白色图案**：前盖马/蛇轮廓，后盖星图、星孔白环、文字与新增边缘纹理框、内外分界线，均为普通白色丝印。边框不写入铜层，也不新增阻焊开窗。
- **孔槽周围开窗**：沿用原物理孔槽，外扩名义 0.20 mm 去绿油；丝印让开开窗名义 0.16 mm。动物轮廓不做阻焊开窗。
- **无彩色喷印、无装饰铜**：装饰图案不写入铜层。棕色预览仅示意去绿油后露出的基材，不表示铜色或金属图案。

边框与四块选项拼板共用 [`pcb_cover_border.py`](../../scripts/pcb_cover_border.py) 的 `af37-double-contour-ticks-v1`。外/内轮廓中心线内缩 0.70/2.10 mm，线宽 0.22/0.24 mm；短刻纹名义长 0.42 mm、宽 0.22 mm、节距 2.40 mm，角点名义直径 0.28 mm。各面按原图、开窗与连接桥让位，实际特征数量及最小间距以本轮每面 `border` 元数据和 Gerber 审计为准；完整参数见[十二选项的边框说明](../twelve-options/README.md#图案与加工参数)。

每面边框记录位于本款 `*-standard-layer-artwork.json` 的 `faces.front/rear.source_metadata.border`。边框分类为 `textured_octagonal_border_and_inner_divider`，图元使用 `cover_border_XX` 标识；记录的几何 SHA-256、原图/开窗指纹、数量与实际间距随图案清单绑定，不靠展示 PNG 推断检查结果。

共同的[六板边框独立审计](../twelve-options/border-artwork-audit.json)已通过，覆盖全部 24 个图案；新增边框的最小板边/主体/开窗间距分别约 0.59/0.336829/0.253552 mm。两块整套绿白板的原孔槽、阻焊、电气与铜基线保留，原核心及彩色两板完整保留。

射手座保留 8 个星孔、11 条光槽；狮子座保留 9 个星孔、8 条光槽，另有 2 条只印刷的短连线。预览中的空白孔槽是实际开孔/开槽位置，白色印线本身不是透光槽。

## 资料入口与检查结果

| 内容 | 路径或入口 | 当前状态 |
|---|---|---|
| 图案源、导入几何和预览 | [artwork/README.md](artwork/README.md)、[图案清单](artwork/manifest.json) | SVG/PNG 与丝印/阻焊多边形已生成；详细处理参数和图形边界见技术说明。 |
| 彩色与绿白展示 | [绿白普通工艺展示 PDF](../../../../output/pdf/NFC符咒_绿白普通工艺展示.pdf) | 外观对比与工艺说明，效果示意不是实物。 |
| 当前统一原生工程 | [nfc-twelve-options.epro2](../twelve-options/eda/native/nfc-twelve-options.epro2) | 9 PCB：共用核心、2 原彩色、2 绿白整套拼板与 4 选项拼板；本轮边框归档已导出，实际版本由两套清单绑定。 |
| 绿白历史五板快照 | [nfc-color-and-green-white.epro2](eda/native/nfc-color-and-green-white.epro2) | 2026-10-15 的 5 PCB 快照保留，1,121,683 bytes；它是加边框前版本，不覆盖为本轮新工程。 |
| 保存重开 DRC | [export-manifest.json](export-manifest.json) | 本轮两款 PCB 均为 `saved_reopened=true`、`drc=[]`；不借用原彩色或旧边框前快照的结果。 |
| Gerber 与制造草案 | [马 + 射手 Gerber](manufacturing-draft/horse-sagittarius-green-white-gerber.zip)、[蛇 + 狮子 Gerber](manufacturing-draft/snake-leo-green-white-gerber.zip) | 普通工艺、关闭彩色喷印；边框版已重新导出，实际 Gerber 图案区域审计通过，未送厂或下单。 |
| 制造放行 | `HOLD_CAM_C1_PHYSICAL_VALIDATION_PENDING` | C1 采购/适配、正式 CAM 与实物 RF/NFC/光效验收未完成。 |

原彩色版本的源工程见 [nfc-two-variants.epro2](../common/eda/native/nfc-two-variants.epro2)，对应 [原彩色导出清单](../common/export-manifest.json)；它们不由本版图案生成脚本覆盖。所有版本入口见[版本导航](../README.md)。

本版[导出清单](export-manifest.json)记录文件大小、SHA-256、两款 PCB 的保存重开/DRC 状态，并与十二选项清单共同绑定统一九板工程。图案来源与处理记录由独立 [artwork/manifest.json](artwork/manifest.json)维护。边框参数及板边、图案、孔槽的避让以本轮几何记录为准；旧五板工程与原彩色三板清单继续保留历史角色。

## 制造与展示边界

绿白 SVG/PNG 由最终丝印/开窗多边形绘制，适合核对外观与工艺位置。白色边线不小于 0.22 mm，但动物锐尖局部仍可小于 0.15 mm，不能声称全图达到统一最小线宽；供应商须确认实际可印细节、阻焊/丝印套准与星孔/光槽加工。

预览颜色不保证最终阻焊或基材色。LED 明亮程度、读写距离、叠装谐振与点亮效果仍须实物测量。原生 DRC 和离线文件审计即使通过，也不等于 CAM 或实体样件通过，不改变制造 HOLD。

独立检查：[交付检查](delivery-audit.json)、[Gerber 实际图案审计](gerber-artwork-audit.json)。本轮纹理边框的检查项数、丝印/开窗最小间距及图案误差由重新导出的审计记录；源几何和导出区域核对包括蛇图负形与星环空心。旧彩印派生的底层 Image 阻焊代理仍移除，原有焊盘开窗保持。
