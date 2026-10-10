# 十二符咒与十二星座参考素材

2026-10-10。打开 [本地图片索引](index.html) 可看十二符咒与十二星座、逐项下载，亦可下载旁边的 `reference-collection.zip` 整包。符咒可切换「修复正视版」「原像素透明版」「完整符咒」作对照。原工程中的马图仍由用户手动导入，本轮整理参考素材，没有改动 EDA 或制造文件。

## 十二符咒

`source-talisman/` 中有鼠、牛、虎、兔、龙、蛇、马、羊、猴、鸡、狗、猪十二枚独立 PNG，按原源字节保存。父 agent 逐张目视核对了动物、灰石底座和配色；马为紫色轮廓，左向侧面，源图细节、方向保持原样。

来源：[Jackie Chan Adventures Wiki 符咒页](https://jackiechanadventures.fandom.com/wiki/Talismans) 与 [Promotional images 图库](https://jackiechanadventures.fandom.com/wiki/Category:Promotional_images)。[原图清单](source-talisman/source_manifest.json) 记录每枚文件页、公开静态 CDN 地址、尺寸和 SHA-256。

这套源图为 **200×141 px、带轻微透视的正面参考插画**，可见侧面厚度。它们不是正投影矢量加工稿；未裁切、换色、镜像、放大或自由重绘，亦未把 PNG 包装成虚假的路径 SVG。符咒版权属于原作相关权利方，未从 Wiki 的文本 CC 许可推定图像许可。

### 修复正视透明图案

`talisman-restored-v1/` 提供十二张 `*-restored.png` **v1 修复稿**。依据原图修复轮廓及可辨认细节、校正符咒正面平面的透视，以保留动物自身姿态、朝向、分段笔画和留白为约束。统一为 **1024×1024 RGBA**，图案最长边约 **820 px**、等比居中。图像重建由原生 ImageGen 逐张完成，Python/Pillow 仅整理透明边界、尺寸和画布；不是对源图扣取放大。**龙、虎、猴仍有细节偏差，已标注待精修**，不视为十二张均已准确还原；见 [逐张复核](talisman-restored-v1/visual-review.md)。

[修复版说明与十二张下载](talisman-restored-v1/README.md)、[总览 JPG](talisman-restored-v1/restored-contact-sheet.jpg)、[完整提示词](talisman-restored-v1/prompts.json)、[清单](talisman-restored-v1/manifest.json)、[文件/布局检查](talisman-restored-v1/validation.json)。生成原稿和提示词均归档在 `raw/`。这属于低分辨率参考图的修复重建，不能保证精确恢复原图中已丢失的细节；可用索引三种显示方式并排核对。

### 原像素透明图案（对照版）

`talisman-patterns/` 保留十二张 `*-pattern.png`，只保留动物图案，石质底座、侧面厚度和八边形外框设为透明。源图的原始画布、颜色和朝向均保留；马图仍为左向紫色图案。索引中的棋盘格仅是网页预览背景，不包含在 PNG 中。

采用 Python/Pillow 对原始像素应用人工复核的二值透明蒙版。每个像素的 RGB 与同坐标源像素完全相同，alpha 只保留源值或置零；没有生成重绘、插值放大、镜像或透视矫正。边缘的原始抗锯齿颜色一并保留，低分辨率原图在大倍率下仍会显像素。

[图案清单](talisman-patterns/manifest.json) 记录每张源图与输出哈希、可见区域和像素数；[行程蒙版](talisman-patterns/pixel-masks.json) 精确记录选取位置，格式为 `[y, x起点（含）, x终点（不含）]`；[像素验证结果](talisman-patterns/validation.json) 检查源哈希、原尺寸、RGB 不变、alpha 取值及蒙版一致性，并确认源图 RGB 通道差值至少 40 的明显彩色像素全部保留。该色差检查不适用于灰白色鼠、虎，二者另做轮廓和细节对照。十二张已与原图逐张目视对照，保留动物的分段构成与内部细节。该验证不将参考 PNG 认定为 PCB 加工矢量稿。

在仓库根目录重建和检查：

```powershell
python hardware/nfc-talisman/scripts/build_talisman_patterns.py
python hardware/nfc-talisman/scripts/build_talisman_patterns.py --check
python hardware/nfc-talisman/scripts/build_reference_gallery.py
```

`--freeze-reviewed-masks` 仅用于首次归档已目视复核的候选 PNG 的透明选区，日常重建无需使用。最终 PNG 按归档蒙版从未修改的源图重建；蒙版文件改变后应重新做目视对照。

## 十二星座

`zodiac-modern/` 内每个星座提供：1024×1024 暗底浅线 PNG、相同图案的可编辑 SVG、透明暗线无标题 SVG，以及带英文标题的透明 SVG。透明无标题版只有星点和连线，方便后续图案导入；它仍是参考形状，尚未设计 PCB 孔槽和实材桥。

连线采用 **Stellarium Modern** 的原始 HIP 边表，保留该版本所有相邻星的连接，不混用其他画法。143颗恒星坐标来自 CDS VizieR `I/239/hip_main` 的 `RAICRS/DEICRS/Vmag`；以球面均值为中心作切平面投影，北上、东左，等比缩放，不套用占星符号。[数据与坐标清单](zodiac-modern/manifest.json)、[生成说明](zodiac-modern/README.md)。

| 星座 | 拉丁名 | 星点 | 独立连线 |
|---|---|---:|---:|
| 白羊座 | Aries | 4 | 3 |
| 金牛座 | Taurus | 12 | 12 |
| 双子座 | Gemini | 17 | 16 |
| 巨蟹座 | Cancer | 6 | 5 |
| 狮子座 | Leo | 9 | 10 |
| 处女座 | Virgo | 12 | 12 |
| 天秤座 | Libra | 5 | 5 |
| 天蝎座 | Scorpius | 13 | 12 |
| 射手座 | Sagittarius | 21 | 24 |
| 摩羯座 | Capricornus | 9 | 9 |
| 水瓶座 | Aquarius | 15 | 14 |
| 双鱼座 | Pisces | 20 | 21 |

另存 **射手座八星、十一边茶壶版**，沿用本项目既有选星与连接；完整 Modern 射手座仍作为十二张主图之一。八星参考版没有转换为新的孔槽，也没有替换当前 PCB 设计。

## 主流画法对照

本次选择两套可核查、广泛使用的画法作参考，不把检索结果当成全网流行度排名：

- **Stellarium Modern**：干净的星点连线，边表可复现，适合作本项目的简化图案起点。
- **IAU / Sky & Telescope 星图**：已保存十二张原始 GIF 和 A4 PDF，图中绿色连线为 Alan MacRobert 的画法，用于核对另一种常见连线轮廓、星名及邻区。[下载清单](source-zodiac/iau-sky-and-telescope/manifest.json)、[比较记录](source-zodiac/zodiac-study.md)。

[IAU 说明](https://www.iau.org/IAU/IAU/Astronomy-FAQs/Constellations.aspx?hkey=bb9dc841-0618-41b5-ac70-149741062141) 标准化的是星座区域及边界，**连线没有唯一官方标准**。十二张星图当前保留参考版本；37mm板上的开孔数量、间距、连槽及光路需按各图另做机械设计，不从这些参考图直接下单。

## 署名与原始数据

- Stellarium team, Modern sky culture；连线与文本数据 CC BY-SA 4.0。源快照固定于本项目 `data/sources/20261008T150844925832Z/`，在 SVG metadata 中保留署名与许可。
- **Credit: ESA**。ESA 1997, *The Hipparcos and Tycho Catalogues*, ESA SP-1200；目录许可 CC BY-NC 3.0 IGO。143星的原始联网响应为 `source-zodiac/hipparcos-zodiac.tsv`，原始响应内保存了完整抓取 URL。未推定商业许可。
- IAU and Sky & Telescope；Alan MacRobert constellation patterns, Roger Sinnott and Rick Fienberg charts；原星图 CC BY 4.0，坐标历元 J2000。它与新绘图所用的 Hipparcos ICRS J1991.25 数据不是同一历元。

[整体文件清单](collection-manifest.json) 提供本集合每个文件的字节数和 SHA-256。`build_zodiac_reference_collection.py` 可从缓存重建新绘星图，`build_reference_gallery.py` 重建本地索引和 ZIP。
