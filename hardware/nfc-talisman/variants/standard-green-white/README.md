# 绿色阻焊 + 白色丝印普通工艺双款

本版为两款 37 mm 双面 NFC 符咒新增独立普通 PCB：**马 + 射手座**与**蛇 + 狮子座**。用户选定绿色阻焊、白色丝印；原彩色 PCB、图案和归档继续保留。本页记录图案输入与工程交付状态，当前保持 **`HOLD_CAM_C1_PHYSICAL_VALIDATION_PENDING`**。

## 两款独立 PCB

| 款式 | 原生 PCB 名称 | 拼板 | 外观预览 |
|---|---|---|---|
| 马 + 射手座 | `Horse-Sagittarius-GreenWhite-100-v1` | 独立 100 × 100 mm，五片 | [正反面预览](artwork/horse-sagittarius-standard-green-white-two-face-preview.png) |
| 蛇 + 狮子座 | `Snake-Leo-GreenWhite-100-v1` | 独立 100 × 100 mm，五片 | [正反面预览](artwork/snake-leo-standard-green-white-two-face-preview.png) |

两款不合并成十片同板。共用核心设计的两面 LED 分别位于 x=±6 mm、y=0，R1–R4 保持原布局。本轮变更限于盖板图案工艺：导出清单记录两款原板框、星孔/光槽、铜、天线与电路保护基线保持，原彩色 PCB 与核心板保留。原生 UUID 分别为 `7b9104396cd59877`、`8bb2139a68d10671`；两款均已保存重开，DRC 返回空数组。

## 普通工艺如何形成外观

- **绿色底色**：未开窗的绿色阻焊，不能用阻焊层的整版填充代表绿底；阻焊开窗表示去绿油。
- **白色图案**：前盖马/蛇轮廓，后盖星图、星孔白环和文字，均为普通白色丝印。
- **孔槽周围开窗**：沿用原物理孔槽，外扩名义 0.20 mm 去绿油；丝印让开开窗名义 0.16 mm。动物轮廓不做阻焊开窗。
- **无彩色喷印、无装饰铜**：装饰图案不写入铜层。棕色预览仅示意去绿油后露出的基材，不表示铜色或金属图案。

射手座保留 8 个星孔、11 条光槽；狮子座保留 9 个星孔、8 条光槽，另有 2 条只印刷的短连线。预览中的空白孔槽是实际开孔/开槽位置，白色印线本身不是透光槽。

## 资料入口与检查结果

| 内容 | 路径或入口 | 当前状态 |
|---|---|---|
| 图案源、导入几何和预览 | [artwork/README.md](artwork/README.md)、[图案清单](artwork/manifest.json) | SVG/PNG 与丝印/阻焊多边形已生成；详细处理参数和图形边界见技术说明。 |
| 彩色与绿白展示 | [绿白普通工艺展示 PDF](../../../../output/pdf/NFC符咒_绿白普通工艺展示.pdf) | 外观对比与工艺说明，效果示意不是实物。 |
| 含原彩色和绿白的原生工程 | [nfc-color-and-green-white.epro2](eda/native/nfc-color-and-green-white.epro2) | 全 5 PCB 归档已导出：1 共用核心、2 原彩色拼板、2 绿白拼板；1,121,683 bytes。独立归档检查已通过。 |
| 保存重开 DRC | [export-manifest.json](export-manifest.json) | 本版两款均为 `saved_reopened=true`、`drc=[]`；对应本版原生 PCB，不借用原彩色检查。 |
| Gerber 与制造草案 | [马 + 射手 Gerber](manufacturing-draft/horse-sagittarius-green-white-gerber.zip)、[蛇 + 狮子 Gerber](manufacturing-draft/snake-leo-green-white-gerber.zip) | 普通工艺数据已导出，`color_silkscreen_export=false`；文件检查与实际 Gerber 图案区域审计通过，未送厂或下单。 |
| 制造放行 | `HOLD_CAM_C1_PHYSICAL_VALIDATION_PENDING` | C1 采购/适配、正式 CAM 与实物 RF/NFC/光效验收未完成。 |

原彩色版本的源工程见 [nfc-two-variants.epro2](../common/eda/native/nfc-two-variants.epro2)，对应 [原彩色导出清单](../common/export-manifest.json)；它们不由本版图案生成脚本覆盖。所有版本入口见[版本导航](../README.md)。

本版[导出清单](export-manifest.json)记录 13 项文件及大小、SHA-256、两款 PCB 的保存重开/DRC 状态。图案来源与处理记录由独立 [artwork/manifest.json](artwork/manifest.json)维护。原彩色历史清单仍保留其三块 PCB 对应版本。

## 制造与展示边界

绿白 SVG/PNG 由最终丝印/开窗多边形绘制，适合核对外观与工艺位置。白色边线不小于 0.22 mm，但动物锐尖局部仍可小于 0.15 mm，不能声称全图达到统一最小线宽；供应商须确认实际可印细节、阻焊/丝印套准与星孔/光槽加工。

预览颜色不保证最终阻焊或基材色。LED 明亮程度、读写距离、叠装谐振与点亮效果仍须实物测量。原生 DRC 和离线文件审计即使通过，也不等于 CAM 或实体样件通过，不改变制造 HOLD。

独立检查：[21 项交付检查](delivery-audit.json)、[Gerber 实际图案审计](gerber-artwork-audit.json)。实际丝印与开窗最小间距约 0.15991 mm；图案边界与源几何误差不超过 0.000003 mm，蛇图 12 处负形与星环空心均保留。旧彩印派生的底层 Image 阻焊代理已随彩色对象移除，原有焊盘开窗保持。
