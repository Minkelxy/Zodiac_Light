# 十二星座简化星图来源比较

## 结论

连线图形没有全球统一、由 IAU 规定的唯一版本。IAU 官方规定的是 88 个星座区域及边界。若目标是给灯具/图标使用一组简洁、能由实际恒星坐标复现的点线图，建议以项目已存档的 Stellarium Modern 连线作为主版本，使用本目录 IAU / Sky & Telescope 图页作对照与来源参考。

## 两类来源

| 来源 | 呈现方式 | 用途与许可 |
|---|---|---|
| IAU / Sky & Telescope | 绿色连线画在完整 J2000 天区图上，另有星点、星等、经纬网、边界、黄道、邻近星座和文字标注；线条有不同粗细。IAU 页面说明图案由 Alan MacRobert 绘制，受 H. A. Rey 影响并调整以保留早期传统。 | 有良好来源和上下文，适合研究不同星座图案和核对星点。12 份 GIF 与 A4 PDF 及其来源 URL、哈希在 `manifest.json`。IAU 页面声明 CC BY 4.0，转载/改编应保留署名与许可。它是 IAU/S&T 发布的图页版本，不代表唯一官方连线标准。 |
| Stellarium Modern | 软件天空文化中的现代西方星座表示，可从点坐标和线段数据还原为统一风格的简图；项目快照已含 88 星座数据及来源说明。 | 适合直接生成项目所需的纯点线 SVG，因为坐标和连线可分离排版，不必从地图截图裁剪。项目保存的原始来源在 `data/sources/20261008T150844925832Z/stellarium_modern_index.json` 和 `stellarium_modern_description.md`；说明记录数据采用 CC BY-SA 4.0，衍生连线数据须保持归属与相同许可。 |

两种图案会在选用哪些星星、是否补连线和图形细节上有差别。IAU/S&T 图页受 Rey 与既有星图传统影响；Stellarium Modern 属于软件星空文化版本。实际恒星锚点可用 HIP 编号及 J2000/ICRS 坐标核对，但连接方式属于星图习惯，不是天文学中的唯一答案。

## 项目十二个对象

按常用传统十二星座制作：白羊 Aries (Ari)、金牛 Taurus (Tau)、双子 Gemini (Gem)、巨蟹 Cancer (Cnc)、狮子 Leo (Leo)、处女 Virgo (Vir)、天秤 Libra (Lib)、天蝎 Scorpius (Sco)、射手 Sagittarius (Sgr)、摩羯 Capricornus (Cap)、水瓶 Aquarius (Aqr)、双鱼 Pisces (Psc)。这里采用天文学星座的拉丁标准名；黄道经过的蛇夫座 Ophiuchus 不属于这套传统十二位。

## 射手座的“茶壶”

射手座中央的茶壶是常见局部星群解释，取自 Sagittarius 的一部分恒星。项目可保留既有的 8 星、11 边茶壶图作为 Sagittarius 专属简化图，并在资料或图注中说明它是项目采用的局部方案。它不代表完整 Sagittarius，也不应标为 IAU 规定的官方图案或十二星座统一标准。

## 可追溯来源

- IAU 说明星座区域与星图连线的区别：[The Constellations](https://www.iau.org/IAU/IAU/Astronomy-FAQs/Constellations.aspx?hkey=bb9dc841-0618-41b5-ac70-149741062141)
- IAU / Sky & Telescope 星图及 CC BY 4.0 说明：[The Constellations chart archive](https://iauarchive.eso.org/public/themes/constellations/)
- Stellarium Modern 数据位置与许可说明：`data/sources/README.md`、`data/sources/20261008T150844925832Z/stellarium_modern_description.md`
- 可选的 IAU / Rey / 通用简化 HIP 连线对照集：[constellation-stick-figures](https://github.com/dcf21/constellation-stick-figures)。该仓库明确指出星座连线没有唯一标准；其 IAU 数据按 CC BY 4.0 发布，其作者自制 simplified 数据按 GPL-3.0 发布，若直接纳入项目须分别遵循对应许可。
