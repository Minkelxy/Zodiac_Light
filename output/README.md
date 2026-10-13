# 40 cm 射手座亚克力制作资料

2026-10-14 定稿：选用 **U1 紧凑短发与肩胸造型**，保留 R1 棱角、四腿和短尾；下方原星链作为星轨延伸。面部留白，手部、颈根与腰侧的细碎线已整理为直线刻画路径。

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

当前脚本使用 Windows 的 `C:/Windows/Fonts/simhei.ttf` 字体。在项目根目录运行：

```powershell
python -m pip install -r requirements.txt reportlab Pillow
python scripts/make_a4_placement_pdf.py
python scripts/make_u1_engraving_pdf.py
```

重新生成会覆盖对应 PDF、SVG 和清单。先保存对这些文件的手工修改。源布局变更后应重新核对打印比例与刻线、灯条的配合关系。历史清单中的本机路径记录制作来源；实际文件位置按本页的仓库相对链接查找。
