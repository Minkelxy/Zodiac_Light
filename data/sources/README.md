# 原始来源、快照及许可

本目录中的时间戳子目录保存实际联网获取的原始响应字节，未对内容进行补写或替换。`catalog.json.sources` 中的 `snapshot_path` 指向当前版本；每项包含抓取时间（UTC）、完整 URL、SHA-256、来源引用和许可说明。SIMBAD 的 POST 请求参数及 ADQL 也保存在元数据中。

## 恒星位置与视星等

来源：[CDS VizieR I/239](https://cdsarc.cds.unistra.fr/viz-bin/cat/I/239)，下载使用 CDS 的 Harvard 镜像，表 `I/239/hip_main`。

原始文件：`hipparcos_i239.tsv`。字段为 `HIP, RAICRS, DEICRS, Vmag`；源响应明确坐标为 ICRS、观测历元 J1991.25，视星等为 Johnson V。

引用：ESA 1997, *The Hipparcos and Tycho Catalogues*, ESA SP-1200，bibcode `1997HIP...C......0E`。**Credit: ESA**。

[ESA 原始许可说明](https://www.cosmos.esa.int/web/hipparcos/catalogues)声明目录按 **CC BY-NC 3.0 IGO** 分发，并要求 `Credit: ESA`。`esa_hipparcos_catalogues.html` 是许可说明页面的原始快照。该项目没有据此推定商业许可；联网刷新会检查该声明是否仍能识别。

## 恒星名称

来源：[SIMBAD TAP](https://simbad.cds.unistra.fr/simbad/sim-tap/sync)，通过 HIP ID 批量查询 `ident` 与 `basic` 表，返回 `id, main_id`。

原始文件：`simbad_names.tsv`。归属/引用：SIMBAD astronomical database, CDS, Strasbourg, France。参考其[引用与致谢说明](https://cds.unistra.fr/cgi-bin/SimbadBib)。本项目没有核实出适用于数据再分发的明确许可，因此不为 SIMBAD 数据自行指定开源或商业许可。

## 星座连线

来源：[Stellarium Modern sky culture](https://github.com/Stellarium/stellarium/tree/master/skycultures/modern)，对象 `CON modern Sgr`。

原始文件：`stellarium_modern_index.json`、`stellarium_modern_description.md`。归属：Stellarium team。该文化的原始说明声明 **Text and data: CC BY-SA 4.0**；参考本项目的 `constellation.json` 是由此数据转换的星座连线数据，保留归属并按同一 **CC BY-SA 4.0** 许可提供。来源使用 `master` URL，实际内容以本地快照及 SHA-256 固定；未编造不可核实的 commit SHA。

Stellarium 说明将插画列为 **Free Art License**。本项目只下载文字和连线数据，没有下载 Stellarium 插画。`data/reference.png` 是用户提供的本地附件，原始外部出处与许可未核实，不将它重新指定为项目原创或推定可再分发。该文件已从公开提交中排除，仅作为本地布局参考；仿真和固件使用已保存的星点坐标，无需附件。

IAU 统一的是星座区域与边界，星座连线图不存在唯一官方版本：[IAU 说明](https://www.iau.org/IAU/IAU/Astronomy-FAQs/Constellations.aspx?hkey=bb9dc841-0618-41b5-ac70-149741062141)。本项目的选星及连线仍可由使用者明确修改。

## 完整性与刷新

`python scripts/fetch_catalog.py` 默认仅读取本地缓存，核对每个源文件的 SHA-256、21 个 HIP 的完整性以及目录与原始响应的一致性。仅 `--refresh` 发出网络请求；全部下载、解析和许可证据检查成功后，先写入新快照目录，最后原子替换 `catalog.json`。旧目录始终保留，因此失败或中断不会使已有目录引用半份星表。应用仿真和单片机导出均可离线使用数据。
