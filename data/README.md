# 人马座灯的设计数据

- `catalog.json`：21 颗恒星的 HIP 身份、SIMBAD 名称、ICRS 赤经/赤纬及 Johnson V 视星等。坐标观测历元为 J1991.25；赤经和赤纬统一使用度。
- `constellation.json`：参考图上的 21 个星点及 24 条逻辑边。边由已缓存的 Stellarium `CON modern Sgr` 多条折线逐段拆出，顺序为 `e01` 至 `e24`。星点顺序从图片左上开始，逻辑星图与灯带接线顺序独立。
- `reference.png`：本地用户附件，453 × 375 px；未随公开仓库分发，运行不依赖该文件。保持图片朝向与比例；原点在左上，x 向右，y 向下。`reference_px` 是人工核对的星点中心近似值，单位为像素，不是制作尺寸。
- `layout.json`：另行维护的制作尺寸、LED 分配和灯带接线，不由星表获取脚本修改。
- `sources/`：原始响应与许可证据；具体 URL、抓取日期、SHA-256 和引用信息记录在 `catalog.json.sources`。

参考图中星点经过 HIP 坐标投影与二维仿射拟合核对，匹配误差约 1.5 px。顶部旁边一条灰细线可能属于插画弓弦，当前没有将其添加为额外逻辑边。本地附件供继续核对，不以插画自动生成额外连线；仓库保存全部参考坐标和连接关系。

刷新方式：

```powershell
python scripts/fetch_catalog.py            # 仅离线验证，不联网
python scripts/fetch_catalog.py --refresh  # 显式联网刷新星表与来源快照
```

刷新成功后仅替换 `catalog.json`，保留所有既有版本快照。获取失败、字段改变、恒星缺失或许可证据无法核实都会保留原有完整数据。脚本不会更改 `constellation.json`、`reference.png` 或 `layout.json`。

SIMBAD 的 `name` 保留其原始 `main_id`，例如 `* rho01 Sgr`、`V* X Sgr`。恒星主键使用 `hip_<编号>`，避免将名称显示形式当作身份。X Sgr 是变星；当前只采用目录 V 星等作为静态参考，不模拟其真实变化周期。
