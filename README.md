# 星座灯与 NFC 符咒

本仓库包含 **40 cm 射手座 WS2812 星座灯**、其 **U1 亚克力刻线与灯条定位模板**，以及 **马 + 射手座 / 蛇 + 狮子座两款 37 mm NFC 符咒**的原生工程、制造草案和审计记录。

新增绿色阻焊、白色丝印版，以及四块各含五片的 100 × 100 mm 盖板拼板，补齐 **12 星座与 12 生肖**选项，复用现有 NFC 核心。新增星座已优化为 51 条透光槽；生肖采用项目既有严格单色符咒图。

| 从这里开始 | 当前交付内容 |
|---|---|
| [十二星座与十二生肖](hardware/nfc-talisman/variants/twelve-options/README.md) | 新增两块五星座、两块五生肖拼板；[全九 PCB 工程](hardware/nfc-talisman/variants/twelve-options/eda/native/nfc-twelve-options.epro2)、[五页展示 PDF](output/pdf/十二星座与生肖_拼板展示.pdf)；四板保存重开 DRC 均为 0 |
| [项目状态](docs/current-project.md) | 灯带与双款 NFC 的状态、证据和待验收事项 |
| [40 cm 制作资料](output/README.md) | U1 刻线 PDF/SVG、六张 A4 拼接纸、灯条定位与裁切表 |
| [NFC 原彩色双款工程](hardware/nfc-talisman/variants/common/eda/native/nfc-two-variants.epro2) | 共用核心板及两款各自 100 × 100 mm 五片拼板；[原彩色文件清单](hardware/nfc-talisman/variants/common/export-manifest.json) |
| [NFC 绿白普通工艺双款](hardware/nfc-talisman/variants/standard-green-white/README.md) | 独立马/蛇 PCB：绿色阻焊、白色丝印，无彩色喷印与装饰铜；两款保存重开 DRC 为 0，全 5 PCB 工程与普通 Gerber 已导出 |
| [NFC 版本导航](hardware/nfc-talisman/variants/README.md) | 原彩色与普通绿白分别保存，按版本选择工程、图案和制造草案 |
| [文档地图](docs/document-map.md) | 当前资料、历史候选、单拼板旧输出的分类导航 |
| [复现与交付指南](docs/delivery.md) | 安装、全项目检查、打包、校验与接收步骤 |
| [GitHub 版本下载](https://github.com/Minkelxy/Zodiac_Light/releases) | 按提交归档的交付 ZIP 和 SHA-256 校验文件 |

NFC 当前制造状态保持 **`HOLD_CAM_C1_PHYSICAL_VALIDATION_PENDING`**。原生归档、文件完整性、离线铜/孔槽审计与保存重开 DRC 的通过结果属于设计检查；正式 CAM、C1 选料、RF/NFC、点亮和实物首件验收仍待完成。灯带固件也尚未刷板或实物验收。

## 40 cm WS2812 星座灯

本项目按参考图建立 **21 颗恒星、24 条连线**，保存真实恒星资料、实际灯带布局和串接映射，并用 Python 播放灯效。默认采用 **200 灯/m、每 2 灯一个裁切单位**，每颗星共 **4 灯**，由两段各 2 灯的灯带组成两排。

默认面板为 **400 × 400 mm（40 × 40 cm）**，四周留 **5 mm**；尺寸校验包含灯带 PCB 的宽度和裁切边界。灯带 PCB 实际宽度为 **5 mm**；两排之间留 2 mm，所以单颗星的 PCB 包围框为 **10 × 12 mm**。当前得到 **268 灯、66 个裁切段、1.340 m 灯带**，PCB 外形包围框约 **330.34 × 384.38 mm**。单个 RGB 帧为 **804 字节**，不含运行表、灯效或驱动缓存。修改参数后的结果以 `validate` 或 `build` 输出为准。

40 cm 亚克力的 **A4 拼接刻线稿、灯条定位模板与打印说明**见 [制作资料入口](output/README.md)。当前刻线稿采用选定的 U1 紧凑短发与肩胸造型，保留 R1 棱角和短尾，六张 A4 按 100% 实际大小打印后拼成 400 × 400 mm；历轮方案对比和生成脚本也已归档。

保留参考图的 21 颗星和全部连接关系。受四灯星点与最短 10 mm 连线段的实体尺寸限制，先等比例缩放参考图，再微调相邻星点的制作位置，当前最大移动约 **4.67 mm**，作者布局最大允许移动 10 mm；原始图片坐标和天文坐标保持原值。实际偏移量记在布局的 `generation` 中。换用其他宽度的灯带时，修改制作参数后重新生成布局，核对裁切表和预览。

## 启动

在 PowerShell 中进入本目录，使用 Python 3.11 或更高版本：

```powershell
git clone https://github.com/Minkelxy/Zodiac_Light.git
Set-Location Zodiac_Light
python -m pip install -r requirements.txt
python -m constellation_lamp preview
```

如果当前 Python 已安装 NumPy 和 Matplotlib，可直接运行最后一条命令。预览采用 Matplotlib 桌面窗口，需要可用的图形界面后端；无桌面环境可以使用后文的 `render` 和 `build` 导出静态图。

安装完成后，在项目根目录运行全项目检查：

```powershell
python scripts/check_project.py --output build/project-check.json
```

检查包含软件测试、灯带数据和硬件预算验证、当前 NFC 快照审计、打印模板的来源与 PDF 哈希，以及入口文档链接。完整交付流程见[复现与交付指南](docs/delivery.md)。

窗口提供播放/暂停（也可按空格）、九种灯效、速度和亮度调节，以及星名、灯珠编号、连线方向、背面导线的显示开关。鼠标移到灯珠上可以查看它的编号、归属、毫米位置、限流后的 RGB 值和边内进度。切换效果时载入该效果的完整预设，并同步亮度和速度滑杆；手动调参保留到下一次切换。预览按硬件预算计算电流和缩放比例，可用 `--hardware` 或 `--current-limit-ma` 调整。

```powershell
python -m constellation_lamp preview --effect flow
python -m constellation_lamp preview --effect ripple
python -m constellation_lamp preview --effect flow --route 95168,94820,93683,93085,92855
```

| 灯效 ID | 效果 |
|---|---|
| `twinkle` | 暖色星点独立微闪、蓝色连线微光 |
| `flow` | 青色光脉冲沿指定路径流动 |
| `ripple` | 按实际二维位置传播的蓝紫波纹 |
| `breath` | 暖金色整体呼吸 |
| `aurora` | 绿、青、紫色极光帘幕 |
| `sparkle` | 各星点按固定种子产生短暂闪耀 |
| `graph_wave` | 从某颗星出发，按图距离沿各分支传播 |
| `draw` | 依次勾勒全部 24 条边，保持，再渐暗 |
| `meteor` | 带蓝色拖尾的流星扫过二维空间 |

`python -m constellation_lamp effects` 列出全部灯效。没有指定 `--route` 时，`flow` 自动选择一条较长的有效星座路径。显式路由必须由相邻恒星组成。`graph_wave`、`draw` 的 `source_star` 可设为 `hip_95168` 等星 ID；默认从最亮星开始。

公共亮度、速度、gamma、种子以及每种效果的参数保存在 [data/effects.json](data/effects.json)。例如修改 `breath_period_s` 控制呼吸周期，`meteor_angle_deg` 控制流星方向，`aurora_velocity_mm_s` 控制极光移动速度。所有效果仍由 `render(runtime, time_ms, params, state, frame)` 输出固定长度 RGB 帧；同一时间、配置和种子不受调用顺序影响。CLI 的 `--brightness`、`--speed`、`--gamma`、`--seed` 覆盖配置文件，`--effect-config` 可以选择另一份参数文件。

`--brightness` 默认 0.2，会改变实际 RGB 帧。屏幕预览另有 `--exposure`，默认 3，用于增强较暗的灯光显示，**不改变输出 RGB 数据**。光晕用于帮助观察布局，预览不测算扩散罩、光通量和环境照度。

## 数据与制作布局

| 文件 | 编辑或查看内容 |
|---|---|
| [data/catalog.json](data/catalog.json) | HIP 编号、SIMBAD 名称、ICRS 坐标、V 视星等及来源快照 |
| [data/constellation.json](data/constellation.json) | 21 个星点的图片位置和 24 条连接关系 |
| [data/layout.json](data/layout.json) | 实体灯带段、裁切数量、毫米位置及真实串接顺序 |
| [docs/data-model.md](docs/data-model.md) | 完整字段说明、最小 JSON 例子和单片机移植接口 |

天文坐标、图片坐标、制作坐标分别保存；星座连线与 WS2812 电气串接顺序也分别保存。灯珠按每段裁切边界向内半个间距取样：2 灯段的名义裁切长度是 10 mm，灯珠中心跨度是 5 mm。

面板、灯带宽度和星点形状在 `layout.json` 的生成设置中配置：

```json
"panel": {"width_mm": 400, "height_mm": 400, "margin_mm": 5},
"strip_width_mm": 5,
"star_defaults": {
  "led_count": 4,
  "shape": "grid_2x2",
  "row_gap_mm": 2,
  "angle_deg": 0
},
"adjust_nearby_stars": true,
"max_star_shift_mm": 10,
"star_overrides": {}
```

`grid_2x2` 仅支持 4 灯，每排仍按 5 mm 固定间距；排间中心距离为灯带宽度加 `row_gap_mm`，不会把 PCB 当作零宽的灯珠。`straight` 可以使用 2、4、6……灯的单一直段；逐星修改 `star_overrides` 时可显式选择形状和角度。

修改生成设置或面板尺寸后，需要重新生成布局。先在 `build/` 中试验，检查结果后再覆盖作者布局：

```powershell
python -m constellation_lamp layout --output build/layout.json
python -m constellation_lamp preview --layout build/layout.json
```

想将检查后的新布局保存为作者数据时，可生成到指定路径：

```powershell
python -m constellation_lamp layout --output data/layout.json
```

`--width-mm` 指星点中心包围框的宽度；面板配置仍约束整个 PCB 外形。当前 400 × 400 mm 面板下指定 `--width-mm 700` 会报告尺寸冲突，不会扩大面板。要修改外形尺寸，应编辑 `panel` 后重生成；要保持 40 cm 限制，只修改星点或制作参数即可。

重生成保留面板、星点默认设置和逐星覆盖，重新计算物理路径、灯珠数和初始串接顺序。它会重置手工修改的路径和接线顺序。已制作的实物应直接编译其保存的布局，不再通过尺寸参数重新生成。

每个实体段必须包含正偶数颗灯，每颗星或连线可以由多个段组成。手工调整 `pieces` 和 `wiring.order` 后，运行下面命令检查：

```powershell
python -m constellation_lamp validate
```

初始串接采用最近邻启发式，允许手工修改顺序和 `reverse`。星间分支通过背面导线串接；它们不是数据总线上的电气分叉。反接段只影响编号顺序，空间位置和灯效逻辑方向保持一致。接线表的导线长度是端点直线距离，实际制作应根据背面走线留余量。

## 构建与导出

```powershell
python -m constellation_lamp build
python -m constellation_lamp export --output build/constellation_data.h
python -m constellation_lamp render --effect ripple --time-ms 2400 --output build/ripple.png
```

`build` 将已保存布局编译到 `build/`，生成：

- `layout.json`：本次构建使用的实体布局快照。
- `runtime.json`：逐灯珠映射、星/连线成员、几何和数量。
- `cutting.csv`：按串接顺序排列的裁切表、编号范围、DIN/DOUT 和方向。
- `wiring.csv`：相邻裁切段之间的导线连接表。
- `constellation_data.h`：完整浮点 C99/C++ 常量数组。
- `constellation_compact.h`、`compact.json`：量化整数 SoA 表、成员列表及 CSR 图邻接表，当前数组占 3718 字节。
- `preview_<effect>.png`：全部九种灯效的静态预览。
- `effects_gallery.png`：九种灯效总览。

CSV 使用带 BOM 的 UTF-8。`runtime.json` 和 C 头文件是派生结果，应从源 JSON 重新生成。

单片机加载头文件中的星、边、逐灯珠及明确成员索引表，并准备 `uint8_t frame[CONSTELLATION_LED_COUNT][3]`。Python 灯效统一接口：

```python
render(runtime, time_ms, params, state, frame)
```

时间和随机种子显式传入；缓存不影响指定时刻的输出。星闪烁按 HIP 身份计算，流光按边内进度 `u` 计算，空间效果按毫米位置计算。WS2812 的 GRB 物理色序由硬件驱动适配，运行帧统一使用 RGB。项目另有 [firmware-idf](firmware-idf) 中的原生 ESP-IDF 参考驱动，支持电脑实时播放、三种脱机验线模式，以及九种原生脱机灯效。

## 实际 WS2812 调试

硬件参数和电流估算在 [data/hardware.json](data/hardware.json)。参考板型为 ESP32 DevKit，GPIO18，460800 baud，默认 30 FPS；构建脚本自动从当前布局、灯效及硬件 JSON 生成本次固件的映射和配置：

```powershell
.\scripts\build_idf.ps1 -Mode 0
python -m pip install "pyserial>=3.5"
python -m constellation_lamp ports
python -m constellation_lamp stream --dry-run build/demo.clp --effect aurora --duration 2
```

`--dry-run` 生成可复现的二进制 RGB 包，不打开串口，并附加最终黑屏包。固件输出目录的 `hardware.json` 绑定灯珠映射指纹、实际波特率、电流系数和可用帧率。实际接好并烧录参考固件后，用显式端口播放，例如：

```powershell
python -m constellation_lamp stream --port COM3 --hardware build/esp-idf/hardware.json --effect aurora --duration 20
```

COM3 只是示例，应使用设备的真实端口。驱动先握手发送黑屏，核对固件灯数、映射 SHA256 和串流模式，再逐帧等待固件 ACK；停止或异常退出会尝试确认黑屏并关闭端口，断流由固件超时关灯。校验包括 CRC、灯数、长度、串口带宽、WS2812 发帧时间和超时预算。协议不重复应用 gamma 或用户亮度。

默认估算每灯待机 1 mA、每色通道满值 20 mA，RGB 会按 **2000 mA** 预算限幅。这些是可替换的计算参数，实际芯片版本的电流应实测；软件限幅不替代供电与布线设计。原生固件用同模型整数复核，满足预算的 RGB 保持原值。电源、共地、电平转换、注电位置、编译和烧录步骤见 [docs/hardware.md](docs/hardware.md)。开发阶段已用 ESP-IDF 5.5.1 编译成功；接收者需安装 SDK 后重新构建，产物在 `build/esp-idf/`，此目录不包含在源码交付 ZIP 中。未刷板或实物验收。Arduino / PlatformIO 实现保留于 `firmware/` 作为备选。

## ESP32 脱机播放

```powershell
.\scripts\build_idf.ps1 -Effect twinkle
.\scripts\build_idf.ps1 -Effect aurora
```

`-Effect` 自动选择 Mode 4，九种 ID 与 Python 相同；参数从 `data/effects.json` 编译到生成头，输出在 `build/esp-idf/mode-4/`。烧录该固件后无需电脑发送 RGB。改变预设后重新构建并烧录；Mode 0 断流仍按超时关灯。`-Mode 0` 可明确构建回串流版本。没有指定模式时保留当前构建缓存的模式。

原生实现使用静态上下文和明确的时间、种子；缓存不改变指定时刻的输出。空间位置采用 0.1 mm 整数表，循环周期从原始几何导出，避免长期积累相位偏移。主机 C++ 与 Python 的比较包含自定义参数、反接、隐藏灯、24 小时和 7 天时刻。实际板端帧率、色序和供电仍需实测。

## 来源与验证

原始星表、名称响应和 Stellarium 数据都已缓存到 `data/sources/`，并记录 URL、获取时间、SHA-256、引用和来源许可。仿真和构建不联网。默认验证缓存；只有显式刷新命令访问网络：

```powershell
python scripts/fetch_catalog.py
python scripts/fetch_catalog.py --refresh
python -m unittest discover -s tests -v
```

刷新失败会保留旧的完整星表和来源快照。具体来源及许可见 [data/README.md](data/README.md)。测试覆盖四灯星点、PCB 面板边界、近邻位置微调、裁切量化、尺寸冲突、引用及归属检查、多段对象、反接、确定性灯效、预览控件和 C 导出一致性。没有 `panel` 的旧式模板继续支持原先按星点中心宽度生成的 2 灯直段布局。

运行 `scripts/run_checks.cmd` 会在检测到默认安装路径的 Visual Studio 2022 Community 时初始化其编译环境，再执行软件测试，包括 C11/C++14 头文件编译与紧凑表的运行验证。其他安装可先进入编译器开发终端再运行 unittest；没有编译器时相应测试会明确跳过，检查报告应连同这些限制一起查阅。全项目交付检查使用 `scripts/check_project.py`。
