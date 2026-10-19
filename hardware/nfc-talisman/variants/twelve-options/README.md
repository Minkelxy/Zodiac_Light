# 十二星座与十二生肖：四块五片盖板拼板

新增 **4 块独立的 100 × 100 mm PCB**，每块包含 5 个不同的 **37 mm AF 八边形盖板**。沿用用户选定的绿色阻焊、白色丝印；星座后盖与生肖前盖分别成组，共用现有 NFC 核心设计。加上原有的射手座、狮子座，以及马、蛇，分别得到完整的 12 个星座与 12 个生肖选项。

本轮已优化新增十款星座的开槽，并将十款新增生肖改为项目已归档的严格单色符咒图。四块 PCB 的原生工程与普通 Gerber 已同步导出，保存重开后 DRC 均为 0；检查结论由清单中的源文件哈希绑定。

2026-10-20 边框修订：四块选项拼板与马/蛇两块绿白整套拼板同步增加白色纹理边框、内外分界线；十二星座与十二生肖使用同一边缘语言。核心板和原彩色两板完整保留，两块既有绿白板有意更新丝印，电路、铜、天线、孔槽与阻焊保持保护基线。六板已保存重开且 DRC 均为 0；原生工程和普通 Gerber 已重新导出，旧版检查不替代本轮源文件哈希绑定的结果。

| 拼板 | 五个选项 | PCB 名称 | 预览 |
|---|---|---|---|
| 星座 A | 白羊、金牛、双子、巨蟹、处女 | `Constellations-A-5x37-GreenWhite-100` | [图](artwork/constellations-a-100mm.png) |
| 星座 B | 天秤、天蝎、摩羯、水瓶、双鱼 | `Constellations-B-5x37-GreenWhite-100` | [图](artwork/constellations-b-100mm.png) |
| 生肖 A | 鼠、牛、虎、兔、龙 | `Zodiac-A-5x37-GreenWhite-100` | [图](artwork/zodiac-a-100mm.png) |
| 生肖 B | 羊、猴、鸡、狗、猪 | `Zodiac-B-5x37-GreenWhite-100` | [图](artwork/zodiac-b-100mm.png) |

四块都是无元件的可替换盖板拼板，不重复放置 NFC 电路。每片通过四个连接桥与框架相连，拆下后与现有核心及另一面盖板叠装。生肖图案选用项目[既有单色符咒图](../../artwork/reference-collection/talisman-single-ink-v1/README.md)，按源图透明轮廓转换为可编辑的白色丝印；动物图案不做去绿油开窗，也不新增装饰铜。原图、转换参数和每款来源由几何记录绑定，造型不由本脚本另行重绘。

## 文件入口

- [全部九份 PCB 的集成原生工程](eda/native/nfc-twelve-options.epro2)：包含共用核心、两份原彩色拼板、两份绿白双款拼板及四份新盖板拼板。
- [五页拼板展示 PDF](../../../../output/pdf/十二星座与生肖_拼板展示.pdf)：用于分享与投屏，非 1:1 加工模板。
- [导出清单](export-manifest.json)、[图案与来源清单](design-manifest.json)、[交付检查](delivery-audit.json)、[Gerber 几何与连接性检查](gerber-geometry-audit.json)、[离线孔槽与连板几何审计](slot-layout-geometry-audit.json)、[六板边框独立审计](border-artwork-audit.json)。
- 四份独立 Gerber：[星座 A](manufacturing-draft/constellations-a-green-white-gerber.zip)、[星座 B](manufacturing-draft/constellations-b-green-white-gerber.zip)、[生肖 A](manufacturing-draft/zodiac-a-green-white-gerber.zip)、[生肖 B](manufacturing-draft/zodiac-b-green-white-gerber.zip)。
- SVG 与 PNG 在 [artwork](artwork/)；原生导入几何在 [geometry](geometry/)；数据快照与请求参数在 [sources](sources/)。

本轮四份选项 PCB 已保存、关闭、重开，DRC 返回空数组；两份整套绿白 PCB 也已保存重开且 DRC 为 0。核心板及两份原彩色设计/彩色对象严格保留，两份既有绿白板仅允许受控白色丝印更新，保护其电气和孔槽基线。保存重开及实际导出检查由两套当前清单共同绑定统一九板工程。集成工程与 Gerber 仍保持 **`HOLD_CAM_PHYSICAL_VALIDATION_PENDING`**；盖板加工、拆板手感、叠装、NFC 与光效需要供应商 CAM 和首件确认。

## 图案与加工参数

新增边框由普通白色丝印形成：边缘纹理框区分外侧装饰带与内部符咒/星图，内外分界线建立统一轮廓。边框不成为装饰铜或透光槽，不新增去绿油开窗。线宽、位置及对板边、文字、原图和孔槽的避让以冻结后的几何与审计为准，展示图不是雕刻或铣槽路径。

边框采用冻结模块 [`pcb_cover_border.py`](../../scripts/pcb_cover_border.py) 的 `af37-double-contour-ticks-v1`：

| 丝印元素 | 名义位置与尺寸 |
|---|---|
| 外轮廓 | 中心线距外形内缩 0.70 mm，线宽 0.22 mm |
| 内分界轮廓 | 中心线内缩 2.10 mm，线宽 0.24 mm |
| 边缘短刻纹 | 中心线内缩 1.35 mm，刻纹中心线长 0.42 mm、宽 0.22 mm、节距 2.40 mm |
| 八角点纹 | 名义直径 0.28 mm |

这些是丝印几何参数，不是加工刀路。边框按现有主体、阻焊开窗及四向连接桥让位；图案/开窗避让目标不小于 0.20 mm，并加数值余量。实际保留的纹理数量、最小间距与局部修剪由每款 `border` 元数据和最终导出审计记录，不能把示例图的最小间距替代全部 24 个图案的检查。

四块选项板的每片记录位于 `geometry/*.json` 的 `covers[].details.border`，包含模块版本、参数、各类纹理的提议/保留数量、几何 SHA-256、原图与开窗几何指纹及实际间距。边框图元以 `<款式>:border:<序号>` 独立归属，方便与原符咒/星图图元分别核对；同一几何文件受设计清单哈希绑定。

[六板边框独立审计](border-artwork-audit.json)通过，覆盖 24 个图案、1,059 个独立边框丝印多边形；新增边框实算最小板边间距约 0.59 mm、主体间距约 0.336829 mm、开窗间距约 0.253552 mm，独立边框片之间约 0.22 mm。审计确认仅受控顶层丝印变化，孔槽、阻焊、铜、板框与拆板几何保留；这些检查不替代供应商 CAM 和实物验收。

星图采用 [Stellarium Modern 连线](https://github.com/Stellarium/stellarium/tree/master/skycultures/modern)和 [ESA Hipparcos I/239 恒星坐标](https://cdsarc.cds.unistra.fr/viz-bin/cat/I/239)。保留十个星座的所有选用 HIP 星点及连线，共 113 个不同 HIP 编号；按北向上、东向左投影后适配 37 mm 盖板。过近星点作有记录的间距调整，具体偏移和仅印刷的连线见各款几何 JSON，不作为等角度天文测量图使用。

星点为直径 0.8 mm 非金属孔；开槽按孔槽间实材、星点距离和盖板连通要求优化，不能仅按连线长短决定。槽宽、端点退让、仅印刷边、最窄实材与孔位移动以冻结后的各款几何及审计记录为准，其余连线保持白色丝印。孔槽周围阻焊开窗名义外扩 0.20 mm，丝印让开 0.16 mm。单片盖板间最小距离约 4.01 mm，外围铣槽宽 1.0 mm；连接桥宽 4.0 mm，每桥 5 个直径 0.4 mm 邮票孔，孔距 0.72 mm、孔边间距 0.32 mm。最小外框余料为 1.5 mm，盖板与框架的连接由实际导出审计确认。

冻结的[开槽优化报告](sources/slot-optimization.json)保留全部 **113 个 HIP 星点、109 条逻辑连线**：实体槽从 **37 条增至 51 条**，槽中心线总长由 **159.153 mm 增至 211.083 mm（+32.6%）**。未开槽的连接仍以白色丝印保留。离线几何的最小星孔到槽实材约 **1.005 mm**，槽间实材约 **0.80463 mm**，最短槽整体长度约 **1.50350 mm**；十款基材都保持单个连通部分。报告绑定冻结星图、星表与优化模块的 SHA-256；独立[孔槽几何审计](slot-layout-geometry-audit.json)绑定同一设计及优化报告，逐项核对 113 个 HIP 孔与 51 个实体槽。原生/实际 Gerber 一致性仍需对应本轮导出审计确认，不能将这些离线数值当作供应商刀补与实物结果。

生肖源图来自 `talisman-single-ink-v1`，羊在拼板中使用 `goat` 标识，对应原图 `sheep-single-ink.png`。几何记录保存源 PNG、候选/原始参考和来源清单的路径及 SHA-256，并记录透明度阈值、简化和版面适配参数。转换产生的是丝印多边形，不把位图文件直接当作原生彩图导入；原图的视觉复核状态继续保留，来源完整性校验不代表重新批准所有原图细节。

Gerber 不编码绿色油墨的具体色号，下单时应选绿色阻焊、白色丝印并确认板厚。现有装配设计的名义板厚与 EDA 默认叠层显示并不完全一致，须按叠装试样确认；本轮没有替原工程作板厚制造放行。孔槽内角、铣刀处理、五图混拼计费及邮票孔拆分由供应商确认。

## 再生成与核对

普通接收者可直接打开原生工程与 PDF。需要重新生成图案时，在仓库根目录安装 `numpy matplotlib pillow opencv-python shapely`，运行：

```powershell
python hardware/nfc-talisman/scripts/build_twelve_option_panels.py
python hardware/nfc-talisman/scripts/audit_twelve_slot_layout.py
python hardware/nfc-talisman/scripts/audit_twelve_options_geometry.py
python hardware/nfc-talisman/scripts/check_twelve_options.py
```

图案生成只读冻结数据并写本目录，不连接 EDA。修改图案后必须先同步活动 PCB、保存重开并重新导出，随后才运行审计和展示 PDF 生成；旧导出不能验证新几何。`create_twelve_option_pcbs.py` 是会创建、导入和保存活动工程的桥接脚本，不应在接收项目时批量重跑；现有 `pcb-state.json` 用来防止重复创建。

星座连线与其衍生星图按 **CC BY-SA 4.0** 署名 Stellarium 团队；修改包括投影、尺寸适配、孔位间距调整和 PCB 图案转换。原始许可证说明已保存在 [Stellarium 描述快照](sources/stellarium-modern-description.md)。Hipparcos 来源与使用条款沿用项目 [数据来源记录](../../../../data/catalog.json)，坐标快照来自 VizieR 的 ESA 1997 星表。生肖符咒的 ImageGen 候选、单色归一化和参考图来源沿用[既有符咒清单](../../artwork/reference-collection/talisman-single-ink-v1/manifest.json)，不再描述为本次生成器原创线稿；以上来源声明与仓库代码的许可证分别适用。
