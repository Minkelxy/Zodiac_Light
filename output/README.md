# 40 cm 射手座亚克力制作资料

## 对外展示成果

以下五份为 A4 横版展示 PDF，适合发送或投屏；2026-10-14 的原三份配有项目下载二维码。图中的灯效为软件仿真，NFC 外观为设计预览。实际加工仍使用下方的 1:1 制作模板。

两份绿白展示资料覆盖 2026-10-20 的纹理边框、闭合内框及拆板孔心外移 0.40 mm 修订，来源清单绑定六块绿白 PCB 的本轮源文件和导出版本。原三份展示 PDF 与历史 release 保留对应版本。

| 资料 | 页数 | 展示内容 |
| --- | --- | --- |
| [十二星座与生肖拼板展示](pdf/十二星座与生肖_拼板展示.pdf) | 5 | 四块五片绿白拼板总览、十星座与十生肖、统一白色纹理边框与分界线 |
| [项目一页成果速览](pdf/星座灯项目_一页成果速览.pdf) | 1 | 星座灯与 NFC 双款的整体进展，适合快速分享 |
| [40 cm 星座灯成果展示册](pdf/星座灯_40cm成果展示册.pdf) | 6 | U1 造型、恒星资料、灯珠布局、九种灯效与制作交付 |
| [NFC 双款设计展示册](pdf/NFC符咒_双款设计展示册.pdf) | 4 | 两款正反面、分层结构、核心布局、归档成果与实物待办 |
| [NFC 绿白普通工艺展示](pdf/NFC符咒_绿白普通工艺展示.pdf) | 3 | 马/蛇绿白正反面与原彩色对照、白色纹理边框、普通工艺边界 |

生成脚本为 [`make_showcase_pdfs.py`](../scripts/make_showcase_pdfs.py)，依赖 NumPy、ReportLab 和 Windows 微软雅黑字体；清单为 [`showcase-manifest.json`](pdf/showcase-manifest.json)。展示内容依据 2026-10-14 的保存资料，不能将设计图当成样件照片或制造放行证明。三份 PDF 也作为附件发布在[项目交付版本页](https://github.com/Minkelxy/Zodiac_Light/releases/tag/project-2026-10-14)。

绿白普通工艺展示由 [`make_green_white_showcase_pdf.py`](../scripts/make_green_white_showcase_pdf.py)生成，复用同一 PDF 排版与字体环境；对应[来源清单](pdf/green-white-showcase-manifest.json)。它保留原彩色对照，说明绿色阻焊、白色丝印、孔槽周围开窗与本轮纹理边框；原生工程入口统一为九 PCB，独立检查进度见[普通绿白版入口](../hardware/nfc-talisman/variants/standard-green-white/README.md)。五页拼板展示由 [`make_twelve_options_pdf.py`](../scripts/make_twelve_options_pdf.py)生成，对应[来源清单](pdf/twelve-options-showcase-manifest.json)。两份脚本均先核对当前来源和交付检查，再保存 PDF；旧三份展示 PDF 与清单保持原版本。

## 制作稿定稿

2026-10-14 定稿：选用 **U1 紧凑短发与肩胸造型**，保留 R1 棱角、四腿和短尾；下方原星链作为星轨延伸。面部留白，手部、颈根与腰侧的细碎线已整理为直线刻画路径。

本页属于 400 × 400 mm WS2812 亚克力灯的制作稿。37 mm NFC 双款的原生工程与制造草案见[项目状态](../docs/current-project.md#nfc-双款)；全仓库下载、检查及打包见[复现与交付指南](../docs/delivery.md)。U1 为当前选定打印稿，下面的 E/R/T/U 比较图和上一轮 T4 文件用于过程归档。

## 下载与打印

| 资料 | 用途 | 打印页码 |
| --- | --- | --- |
| [U1 最终刻线模板 PDF](pdf/星座灯_U1短发_400mm_A4刻线模板.pdf) | 黑色为亚克力刻线，浅灰为原星图和灯条位置参考 | 共 7 页；第 2-7 页是六张 1:1 拼接纸 |
| [灯条定位与裁切 PDF](pdf/星座灯_400mm_A4拼接定位模板.pdf) | 灯条轮廓、灯珠中心、数据方向、段号和裁切表 | 共 9 页；第 2-7 页拼接，第 8-9 页为裁切表 |
| [U1 刻线母图 SVG](engraving-final-u1/engraving-master.svg) | 400 × 400 mm 的纯黑刻线矢量，用于查看或继续修改 | 原尺寸为 400 × 400 mm；A4 拼接请使用上面的 PDF |
| [U1 刻线制作清单](engraving-final-u1/fabrication-manifest.json) | 290 条直线、源文件哈希、拼接范围和校准数据 | 数据文件 |
| [灯条定位清单](pdf/placement-template-manifest.json) | 灯条、页码、定位十字和源布局哈希 | 数据文件 |

1. 选择 A4 纵向、单面、**实际大小 / 100%**；关闭适合页面与多页合一。
2. 先试印第 2 页，实测横、纵两把校准尺都为 **100 mm**，再打印其余页。
3. 上排按 A1、A2、A3 排列，下排按 B1、B2、B3 排列。沿外框实线裁纸，保留各页标明的 10 mm 搭接带。
4. 右页盖住左页搭接带，下排盖住上排搭接带。同编号十字重合、图案连续后固定。
5. 拼好后外框为 **400 × 400 mm**。纸张放在透明亚克力下方，上边对齐板上边。从当前操作面看，箭指向左上，本模板无镜像。

刻画时只沿黑线轻划；浅灰线用于核对原星图和灯条位置，不划线。灯条的段号、DIN/DOUT 方向和裁切长度以灯条定位 PDF 为准。

## 设计过程

| 阶段 | 原图与数据 | 评审入口 |
| --- | --- | --- |
| A-D 初版直线方案 | [engraving-review](engraving-review/) | [设计总览](engraving-review/review-designs.png) |
| E/F 动作与星图配合 | [engraving-review-v2](engraving-review-v2/) | [E 动作](engraving-review-v2/concept-e-left-arrow.png)、[固定星图](engraving-review-v2/star-map-exact.png) |
| E1-E6 简化与抽象 | [engraving-review-v3](engraving-review-v3/) | [E 动作对比 PDF](pdf/星座灯_E动作_划线方案对比.pdf) |
| R1-R3 大切面优化 | [engraving-review-v4](engraving-review-v4/) | [R1-R3 对比 PDF](pdf/星座灯_E动作_优化对比_v4.pdf) |
| T1-T4 尾部优化 | [engraving-review-v5-tail](engraving-review-v5-tail/) | [尾部对比 PDF](pdf/星座灯_R1_马尾优化对比.pdf) |
| 上一轮 T4 打印稿 | [engraving-final](engraving-final/) | [T4 刻线 PDF](pdf/星座灯_R1短尾星轨_400mm_A4刻线模板.pdf) |
| 上半身与头发重构 | [engraving-review-v6-upper](engraving-review-v6-upper/) | [U1 / U2 / U4 对比 PDF](pdf/星座灯_上半身与头发重构对比_v6.pdf) |
| U1 最终直线矢量稿 | [engraving-final-u1](engraving-final-u1/) | [刻线母图](engraving-final-u1/engraving-master.svg)、[矢量构图预览](engraving-final-u1/U1-vector-preview.png) |

评审图和评审 PDF 用于比较构图。打印制作使用本页最上方的两个正式拼接模板。最终刻线采用人工整理的白色笔划中心线，没有把笔划两侧边缘重复描成加工线。

星点、连接关系和物理灯条参考直接来自项目保存的 [catalog.json](../data/catalog.json)、[constellation.json](../data/constellation.json) 和 [layout.json](../data/layout.json)。最终模板保留原 21 星、24 条连线、66 段灯条和 268 灯布局。

## 重新生成

两个正式模板由以下脚本生成：

- [make_a4_placement_pdf.py](../scripts/make_a4_placement_pdf.py)：灯条拼接、定位与裁切表。
- [make_u1_engraving_pdf.py](../scripts/make_u1_engraving_pdf.py)：U1 刻线母图、六张 A4 拼接页和制作清单，复用已有拼接框架。
- [make_final_engraving_pdf.py](../scripts/make_final_engraving_pdf.py)：共用打印框架与上一轮 T4 母图；单独运行会重建上一轮 T4 文件。

当前 PDF 脚本使用 ReportLab 和 Windows 的 `C:/Windows/Fonts/simhei.ttf` 字体；非 Windows 环境须先在脚本中配置等效中文字体。已有 PDF 可直接打印。生成 U1 的脚本还会写入 `tmp/pdfs/u1-vector-preview.pdf`，归档的 `U1-vector-preview.png` 是对此矢量页的渲染，未由该脚本自动重建。在项目根目录运行：

```powershell
python -m pip install -r requirements.txt reportlab
python scripts/make_a4_placement_pdf.py
python scripts/make_u1_engraving_pdf.py
```

重新生成会覆盖对应 PDF、SVG 和清单。先保存对这些文件的手工修改。源布局变更后应重新核对打印比例与刻线、灯条的配合关系，实际打印仍需重新测量校准尺。PDF 生成时的元数据可能变化，哈希以本次对应清单为准。历史清单中的本机路径记录制作来源；实际文件位置按本页的仓库相对链接查找。

可用以下命令核对当前归档的布局来源、U1/定位 PDF 哈希及全项目资料；它不会覆盖制作稿：

```powershell
python scripts/check_project.py --output build/project-check.json
```
