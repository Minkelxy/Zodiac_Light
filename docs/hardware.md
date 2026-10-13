# ESP32 / WS2812 参考驱动

当前灯带主工程是 [firmware-idf](../firmware-idf)，开发构建使用 **ESP-IDF 5.5.1** 原生 RMT/UART 驱动，目标为经典 ESP32 DevKit。GPIO18 输出灯带数据，板载 USB 转串口连接 UART0（GPIO1 TX / GPIO3 RX），电脑可生成九种灯效的 RGB 帧，Mode 4 也可由 ESP32 原生计算并脱机播放。实际开发板、灯珠和供电尚未实测，工程没有执行刷板。ESP32-C3/S3 等型号需要重新核对目标和引脚。37 mm NFC 的硬件另见[当前项目状态](current-project.md#nfc-双款)。

固件默认上电发送全黑，只有完整有效帧才能更新显示；距上一有效帧达到 1000 ms 后发全黑，断流不会切到本地灯效。原生工程不依赖 Arduino、FastLED 或需要下载的组件。`firmware/` 保留 Arduino / PlatformIO 备选实现，当前没有完成它的框架下载和板端构建验证。

## 接线

灯带按实际规格使用独立 5 V 电源，ESP32 由 USB 供电；两者 GND 相连。下面的数据线只有一条串行链，空间上的星座分叉和闭环不意味着数据线也分叉。

```text
电脑 USB ── ESP32
               GPIO18 ── AHCT125 输入
独立 +5 V ────────────── AHCT125 VCC ─────────────── 灯带 +5 V
                  AHCT125 输出 ── 330 Ω ── 首段 DIN
独立 GND ───────── ESP32 GND ── AHCT125 GND ─────── 灯带 GND

首段 DOUT ── 导线 ── 下一段 DIN ── … ── 最后一段
```

采用 **SN74AHCT125** 这类 5 V 供电、TTL 输入的缓冲器把 ESP32 的 3.3 V 信号升到 5 V。TI 规定 AHCT125 的推荐供电范围为 4.5–5.5 V，输入高电平门槛为 2 V。对常见 14 脚封装，VCC=14、GND=7、1OE=1 接低、1A=2 接 GPIO、1Y=3 接 DIN；其他封装须按其引脚图连接。VCC/GND 就近放 0.1 µF 去耦，未用通道的输入和使能脚也要固定电平。[TI 原厂数据表](https://www.ti.com/lit/ds/symlink/sn74ahct125.pdf)

Worldsemi 的新版 V6 公告修改了逻辑门槛和待机电流，市售条带可能使用更早版本。因此，在未确认灯珠版本前保留上述电平转换；不能从“WS2812”名称推断 3.3 V 直驱可靠或每灯恒定 60 mA。[Worldsemi 升级公告](https://www.world-semi.com/web/index.php?classid=19&id=587&lanstr=en&topclassid=19)

数据串联电阻放在首颗 DIN 附近。灯带供电入口可放 500–1000 µF、耐压高于供电电压的电容；数据线与 GND 配对布线，先连接公共地，再连接供电和数据。以上是 NeoPixel 厂商给出的通用接线建议。[Adafruit 接线建议](https://learn.adafruit.com/adafruit-neopixel-uberguide/best-practices)

各灯段的电源可从公共电源母线补电，数据则按导出的 `piece_order` 逐段串接。段间导线不占 LED 地址。按实际电流与线材承载能力设置电源和支路保护；不能让全部灯带电流经过 ESP32 USB 或板载稳压器。首次验收用受控限流的电源、低亮度模式，并测量远端电压和电流。

## 时序、颜色与帧率

每颗灯发送 24 位，默认线序 **GRB、每通道最高位先发**；电脑协议始终存 **RGB**。`output_transform.h` 限流并换序到独立 GRB 缓冲，RMT 硬件生成脉宽；应用等待 RMT 完成后才 ACK，也不会提前改写该缓冲。[Espressif RMT 驱动](https://docs.espressif.com/projects/esp-idf/en/v5.5.1/esp32/api-reference/peripherals/rmt.html)

原生编码器以 40 MHz（25 ns/tick）组合 SDK bytes/copy 编码器：0 位高 14 tick（350 ns）、低 36 tick（900 ns）；1 位高 36 tick、低 14 tick。每位总长 1.25 µs，即 800 kbit/s，末尾显式发送 **300 µs 低电平复位**。具体条带的芯片版本仍需按其数据表和逻辑分析仪确认。代码改编自 Espressif 原生 led_strip encoder 示例，保留 Apache-2.0 SPDX 信息。[官方编码器示例](https://github.com/espressif/esp-idf/blob/v5.5.1/examples/peripherals/rmt/led_strip/main/led_strip_encoder.c)

默认 268 灯的 RGB 数据为 804 B，协议帧为 820 B。460800 baud、8N1 下单帧纯串口传输约 17.80 ms；灯带输出约 `268×30 µs + 300 µs = 8.34 ms`。主机等待显示后的 ACK，因此还需考虑两者之和及调度、USB 延迟：默认 30 FPS 的周期为 33.33 ms，留有约 7 ms 的名义余量。灯数或波特率改变后重新计算，不能仅根据 WS2812 的速率宣称整套系统帧率。

## CLP1 帧协议

| 字节偏移 | 长度 | 内容 |
| --- | ---: | --- |
| 0 | 4 | ASCII `CLP1` |
| 4 | 4 | `sequence`，uint32，小端 |
| 8 | 2 | `led_count`，uint16，小端 |
| 10 | 2 | `payload_len`，uint16，小端 |
| 12 | 4 | RGB 载荷的 CRC32，uint32，小端 |
| 16 | `led_count×3` | 按电气 LED 地址排列的 RGB 字节 |

CRC 与 Python `zlib.crc32(payload)` 一致：反射多项式 `0xEDB88320`，初值和最终异或均为 `0xFFFFFFFF`，不包含头部。完整帧长 `16 + 3N`。固件只接受 `led_count == CLP_LED_COUNT` 且 `payload_len == 3×CLP_LED_COUNT` 的帧；不会根据收到的头部动态分配内存或更改灯数。

`frame_protocol.h` 逐字节寻找 magic，在错误头部内保留可能的新 magic 或其前缀；RGB 内出现 `CLP1` 按正常载荷处理。未完成包超过 250 ms 总时间或字节间隔会丢弃。CRC 错包、错误长度和截包只写后缓冲，完整校验后才交换前后缓冲。解析器和应用 RGB/GRB 缓冲静态分配；SDK UART/RMT 驱动内部仍会申请内存。

RMT 数据及复位发送完成后，固件尝试返回 `OK <sequence>\n`。UART 队列空间不足时丢弃 ACK，主机有超时；它不能证明实灯发光或供电稳定。原生 UART 缓冲为 RX4096 B、TX256 B；TX 环形缓冲须大于经典 ESP32 的 128 B FIFO。应用 console 和日志关闭，ACK 直接写 UART driver；ROM 启动噪声由主机黑屏握手处理。[Espressif UART 驱动](https://docs.espressif.com/projects/esp-idf/en/v5.5.1/esp32/api-reference/peripherals/uart.html)

## 亮度和电流估算

电脑先完成灯效、亮度、gamma 和限流。原生固件使用相同电流模型进行整数复核，按微安校准系数与统一比例向下取整；已满足板端预算的 RGB 原样换序，不再次乘用户亮度或 gamma。主机测试实际编译运行这个变换，验证 RGB/GRB、预算、边界和没有第二次缩放。

`data/hardware.json` 的电脑估算为：

```text
estimated_ma = N × idle_led_ma + sum(R + G + B) / 255 × channel_ma
默认 idle_led_ma=1、channel_ma=20、current_limit_ma=2000
```

这些是可替换的估计初值，不能替代电流测量或硬件过流保护。测出实际芯片电流后调整系数与预算。构建脚本以 `data/hardware.json` 为参数来源，同步 GPIO、灯数、电流系数、波特率和超时到 Kconfig；整数微安系数的量化值也写入输出配置，使电脑与固件采用同一模型。Arduino 备选的 FastLED 使用自己的功率估算。

## 编译与使用

接收者需先安装 ESP-IDF、对应 Python 环境、ESP32 工具链、CMake 与 Ninja。开发记录使用 ESP-IDF 5.5.1；源码 ZIP 不包含 SDK、工具或 `build/` 中的固件。工具齐备后，Windows 构建脚本可从 Espressif 安装器记录选择当前 SDK、Python 和工具：

```powershell
.\scripts\build_idf.ps1 -Mode 0
```

自动检测失败时，使用脚本的 `-IdfPath`、`-IdfPython` 和 `-ToolsPath` 指定本机实际安装位置。构建脚本只编译和归档，不执行刷板；检查报告及交付流程见[复现与交付指南](delivery.md)。

脚本先验证并从 `data/catalog.json`、`constellation.json`、`layout.json` 生成紧凑映射，同时从 `data/effects.json` 生成原生灯效预设。生成头、派生 Kconfig 和来源指纹保存到 ASCII 构建缓存；原始 JSON 是可编辑来源。脚本按当前项目根目录建立 junction，再使用 CMake 处理中文源码路径；临时目录路径须为 ASCII，不修改 SDK 或系统配置。

硬件配置从 `data/hardware.json` 同步；灯数由布局派生，错误 GPIO、无法满足的超时/带宽、电流低于待机估算等配置会在编译前拒绝。脚本保留其他 SDK 设置。`-Menuconfig` 可调其他 SDK 设置和模式；硬件来源字段会在构建前再次与 JSON 同步。显式 `-Mode` 优先于已有缓存，省略则保留当前缓存模式。

成功后复制 BIN/ELF/MAP、bootloader、分区、flash_args、生成映射/预设、来源校验记录和 `hardware.json` 到输出目录。默认/Mode 0 输出在 `build/esp-idf/`；其他模式在 `build/esp-idf/mode-N/`。输出硬件快照绑定当前场景 SHA256，主机 FPS 会按 UART + WS2812 + ACK 预算自动下调，例如 268 灯、115200 baud 导出 10.5 FPS。

```powershell
.\scripts\build_idf.ps1 -Mode 1         # 单灯追逐
.\scripts\build_idf.ps1 -Mode 2         # 红绿蓝色序
.\scripts\build_idf.ps1 -Mode 3         # 星/线分色
.\scripts\build_idf.ps1 -Effect twinkle # Mode 4，暖星微闪
.\scripts\build_idf.ps1 -Effect aurora  # Mode 4，极光
```

九种 `-Effect` ID 与 Python 相同。脱机模式在编译时选择；公共亮度/速度/gamma/种子、自定义路径、源星及专属参数都从 `effects.json` 导出。PC 串流版本失去有效帧时仍清屏。无论来源是电脑还是本地，最终 RGB 通过同一个 GRB/限流/RMT 输出路径。

默认 268 灯的双 RGB 缓冲为 1608 B，GRB 缓冲为 804 B，共 2412 B。原生灯效上下文固定分配，主机编译测得 12008 B、参数 360 B；目标编译器对齐和 SDK/RMT/UART/栈另计。循环周期用全精度几何导出，0.1 mm 空间量化不累积为长期循环相位偏移。原生渲染没有动态分配；实际芯片上的刷新速率仍需测量。

电脑发送应使用该次构建的硬件快照，例如 `--hardware build/esp-idf/hardware.json`。握手核对 `INFO CLP1 <N> <scene_sha256> <mode>`；Mode 0 和映射一致后才允许彩色帧。SHA 用来检查配置一致，不证明实物布线或发光状态。

自行确认板型和端口后，可在已激活 ESP-IDF 的终端进入输出目录，按生成的地址烧录。示例 COM3 应换成真实端口；此命令写入设备，本文档中的构建脚本不会执行它：

```powershell
Set-Location -LiteralPath '.\build\esp-idf'
python -m esptool --chip esp32 --port COM3 --baud 460800 write_flash '@flash_args'
```

## Arduino / PlatformIO 备选

局部安装与编译（首次需要联网获取固定依赖）：

```powershell
python -m venv firmware/.venv-pio
firmware/.venv-pio/Scripts/python.exe -m pip install platformio==6.1.18
$env:PYTHONUTF8 = '1'
$env:PLATFORMIO_CORE_DIR = Join-Path (Resolve-Path firmware).Path '.pio-core'
firmware/.venv-pio/Scripts/python.exe -m platformio run --project-dir firmware -e esp32dev
```

编译参数集中在 `firmware/include/config.h` 和 `platformio.ini`。默认 GPIO18、460800 baud、2000 mA 估算上限、1000 ms 断流、250 ms 包超时；确认板型后再决定实际 DATA_PIN。`platformio run` 仅编译；这里未执行上传或刷板。

三个验线环境均为编译时明确选择，亮度默认 16/255：

| 编译环境 | 模式 | 用途 |
| --- | ---: | --- |
| `esp32dev` | 0 | 电脑发送帧，断流黑屏 |
| `local_chase` | 1 | 逐 LED 白点，核对串行地址、焊接方向和断点 |
| `local_rgb` | 2 | 每 1.5 s 轮换红绿蓝，确认 RGB/GRB 配置 |
| `local_parts` | 3 | 用紧凑头映射：星为暖黄、连线为蓝，隐藏 LED 黑；缺头时仅显示低亮白光 |

例如把上述编译命令的 `-e esp32dev` 改成 `-e local_parts`。Arduino 备选的三种本地模式用于装配验收；九种完整脱机灯效在原生 ESP-IDF 工程中实现。

未连接设备时先保存协议回放文件：

```powershell
python -m constellation_lamp stream --dry-run build/twinkle.clp --hardware data/hardware.json --effect twinkle --duration 2
```

确认板型、完成自行刷板和接线验收后，再安装串口依赖并查看端口列表；端口名称须按实际列表选择：

```powershell
python -m pip install 'pyserial>=3.5'
python -m constellation_lamp ports
python -m constellation_lamp stream --port COM3 --hardware data/hardware.json --effect twinkle --duration 10
```

关闭占用同一端口的串口监视器。主机打开串口可能使开发板复位，因此主机先核对全黑帧的场景身份及 ACK 再播放；结束时也发送全黑帧并等待 ACK，断线情况下由固件看门狗清屏。

## 验证记录

`tests/test_firmware.py` 编译并运行实际 C++ 包解析器，使用独立 Python `zlib` 包做输入，验证 13 项协议、缓冲边界和看门狗行为。Windows 可运行 `scripts/run_checks.cmd` 初始化 MSVC；仅运行 Python 而缺少主机 C++ 编译器时，这组测试明确跳过。

2026-10-09：本机 ESP-IDF 5.5.1 + Xtensa GCC 14.2.0 构建成功，生成 `constellation_lamp_idf.bin`，固件大小见当前输出目录的构建记录和 BIN 文件；Mode 4 另外包含九种原生渲染逻辑。源 SDK 已有的修改保留。主机测试还覆盖原生 GRB/限流变换，与 Python 帧模型一致。Arduino 备选下载中断，未完成板端构建。

本轮最终验证：163 项测试全部通过，包含实际 MSVC C11/C++14 编译和运行。串流版 BIN 为 201936 B，极光脱机版为 230400 B；两个版本的布局、预设、二进制 SHA256 和硬件快照已核对。12008 B 原生工作区放入 `.bss`，较带非零初始化的版本减少 12016 B 固件文件。主机与原生默认短时 RGB 差异最多 1，保留权威周期后 24 小时、7 天的长时比较也最多 1。

尚未刷板，未做真实串口往返、逻辑分析仪、电流或光学实测。上电黑屏、色序、断流时间、供电压降仍需在实际成品上验收。当前原生工程只运行 UART/RMT 任务；若以后加入 Wi-Fi 或运行中写 Flash，需按官方 RMT cache-safe 说明复核 ISR/encoder 的 IRAM 配置和输出时序。
