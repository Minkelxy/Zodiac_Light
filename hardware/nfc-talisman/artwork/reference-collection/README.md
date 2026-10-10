# 十二符咒与十二星座参考素材

2026-10-10。打开 [本地图片索引](index.html) 可看24张主图、逐项下载，亦可下载旁边的 `reference-collection.zip` 整包。原工程中的马图仍由用户手动导入，本轮只增添参考素材，没有改动 EDA 或制造文件。

## 十二符咒

`source-talisman/` 中有鼠、牛、虎、兔、龙、蛇、马、羊、猴、鸡、狗、猪十二枚独立 PNG，按原源字节保存。父 agent 逐张目视核对了动物、灰石底座和配色；马为紫色轮廓，左向侧面，源图细节、方向保持原样。

来源：[Jackie Chan Adventures Wiki 符咒页](https://jackiechanadventures.fandom.com/wiki/Talismans) 与 [Promotional images 图库](https://jackiechanadventures.fandom.com/wiki/Category:Promotional_images)。[原图清单](source-talisman/source_manifest.json) 记录每枚文件页、公开静态 CDN 地址、尺寸和 SHA-256。

这套源图为 **200×141 px、带轻微透视的正面参考插画**，可见侧面厚度。它们不是正投影矢量加工稿；未裁切、换色、镜像、放大或自由重绘，亦未把 PNG 包装成虚假的路径 SVG。符咒版权属于原作相关权利方，未从 Wiki 的文本 CC 许可推定图像许可。

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
