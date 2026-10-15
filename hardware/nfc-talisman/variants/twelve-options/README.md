# 十二星座与十二生肖：四块五片盖板拼板

新增 **4 块独立的 100 × 100 mm PCB**，每块包含 5 个不同的 **37 mm AF 八边形盖板**。沿用用户选定的绿色阻焊、白色丝印；星座后盖与生肖前盖分别成组，共用现有 NFC 核心设计。加上原有的射手座、狮子座，以及马、蛇，分别得到完整的 12 个星座与 12 个生肖选项。

| 拼板 | 五个选项 | PCB 名称 | 预览 |
|---|---|---|---|
| 星座 A | 白羊、金牛、双子、巨蟹、处女 | `Constellations-A-5x37-GreenWhite-100` | [图](artwork/constellations-a-100mm.png) |
| 星座 B | 天秤、天蝎、摩羯、水瓶、双鱼 | `Constellations-B-5x37-GreenWhite-100` | [图](artwork/constellations-b-100mm.png) |
| 生肖 A | 鼠、牛、虎、兔、龙 | `Zodiac-A-5x37-GreenWhite-100` | [图](artwork/zodiac-a-100mm.png) |
| 生肖 B | 羊、猴、鸡、狗、猪 | `Zodiac-B-5x37-GreenWhite-100` | [图](artwork/zodiac-b-100mm.png) |

四块都是无元件的可替换盖板拼板，不重复放置 NFC 电路。每片通过四个连接桥与框架相连，拆下后与现有核心及另一面盖板叠装。生肖图案采用本项目原创的矢量线稿，便于后续修改轮廓；动物图案由白色丝印形成，不做去绿油开窗，也不新增装饰铜。

## 文件入口

- [全部九份 PCB 的集成原生工程](eda/native/nfc-twelve-options.epro2)：包含共用核心、两份原彩色拼板、两份绿白双款拼板及四份新盖板拼板。
- [五页拼板展示 PDF](../../../../output/pdf/十二星座与生肖_拼板展示.pdf)：用于分享与投屏，非 1:1 加工模板。
- [导出清单](export-manifest.json)、[图案与来源清单](design-manifest.json)、[交付检查](delivery-audit.json)、[Gerber 几何与连接性检查](gerber-geometry-audit.json)。
- 四份独立 Gerber：[星座 A](manufacturing-draft/constellations-a-green-white-gerber.zip)、[星座 B](manufacturing-draft/constellations-b-green-white-gerber.zip)、[生肖 A](manufacturing-draft/zodiac-a-green-white-gerber.zip)、[生肖 B](manufacturing-draft/zodiac-b-green-white-gerber.zip)。
- SVG 与 PNG 在 [artwork](artwork/)；原生导入几何在 [geometry](geometry/)；数据快照与请求参数在 [sources](sources/)。

四份 PCB 均已保存、关闭、重开，重新运行的 DRC 返回空数组。原有五份 PCB 的设计几何与彩色对象已逐份比对保留。集成工程与 Gerber 仍保持 **`HOLD_CAM_PHYSICAL_VALIDATION_PENDING`**；盖板加工、拆板手感、叠装、NFC 与光效需要供应商 CAM 和首件确认。

## 图案与加工参数

星图采用 [Stellarium Modern 连线](https://github.com/Stellarium/stellarium/tree/master/skycultures/modern)和 [ESA Hipparcos I/239 恒星坐标](https://cdsarc.cds.unistra.fr/viz-bin/cat/I/239)。保留十个星座的所有选用 HIP 星点及连线，共 113 个不同 HIP 编号；按北向上、东向左投影后适配 37 mm 盖板。过近星点作有记录的间距调整，具体偏移和仅印刷的连线见各款几何 JSON，不作为等角度天文测量图使用。

星点为直径 0.8 mm 非金属孔；较长、间隔足够的连线为宽 1.0 mm 透光槽，其余连线保持白色丝印。孔槽周围阻焊开窗名义外扩 0.20 mm，丝印让开 0.16 mm。单片盖板间最小距离约 4.01 mm，外围铣槽宽 1.0 mm；连接桥宽 4.0 mm，每桥 5 个直径 0.4 mm 邮票孔，孔距 0.72 mm、孔边间距 0.32 mm。最小外框余料为 1.5 mm，所有盖板仍与框架连接。

Gerber 不编码绿色油墨的具体色号，下单时应选绿色阻焊、白色丝印并确认板厚。现有装配设计的名义板厚与 EDA 默认叠层显示并不完全一致，须按叠装试样确认；本轮没有替原工程作板厚制造放行。孔槽内角、铣刀处理、五图混拼计费及邮票孔拆分由供应商确认。

## 再生成与核对

普通接收者可直接打开原生工程与 PDF。需要重新生成图案时，在仓库根目录安装 `numpy matplotlib pillow opencv-python shapely`，运行：

```powershell
python hardware/nfc-talisman/scripts/build_twelve_option_panels.py
python hardware/nfc-talisman/scripts/audit_twelve_options_geometry.py
python hardware/nfc-talisman/scripts/check_twelve_options.py
```

图案生成只读冻结数据并写本目录，不连接 EDA。`create_twelve_option_pcbs.py` 是会创建、导入和保存活动工程的桥接脚本，不应在接收项目时批量重跑；现有 `pcb-state.json` 用来防止重复创建。

星座连线与其衍生星图按 **CC BY-SA 4.0** 署名 Stellarium 团队；修改包括投影、尺寸适配、孔位间距调整和 PCB 图案转换。原始许可证说明已保存在 [Stellarium 描述快照](sources/stellarium-modern-description.md)。Hipparcos 来源与使用条款沿用项目 [数据来源记录](../../../../data/catalog.json)，坐标快照来自 VizieR 的 ESA 1997 星表。原创生肖矢量路径包含在生成脚本中；以上第三方数据声明与仓库其他代码的许可证分别适用。
