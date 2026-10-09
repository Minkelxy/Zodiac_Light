# 星座灯数据模型与单片机移植

本项目把天文身份、星座图和实物接线分开保存。`HIP` 标识真实恒星，逻辑星/边 ID 标识图上的对象，`LED index` 标识 WS2812 数据链中的地址。这三个编号各有用途，连线动画的方向不依赖接线编号。

## 三份作者数据

三份 JSON 都使用 `schema_version: 1`，坐标数组写作 `[x, y]`。

| 文件 | 主要字段 | 用途 |
|---|---|---|
| `data/catalog.json` | `stars`、`sources` | 星表身份、天球坐标、星等和来源 |
| `data/constellation.json` | `stars`、`edges` | 选定哪些星、参考图位置、连接关系 |
| `data/layout.json` | 密度、裁切单位、物理坐标、`pieces`、`wiring.order` | 实物几何、灯带切段和串接顺序 |

### 星表：catalog.json

`stars` 的每条记录有必填正整数 `hip`、角度单位的 `ra_deg`（0 到 360 之间，不含 360）和 `dec_deg`（−90 到 90）。`mag_v` 可以为 `null`，表示未知；较小的星等对应较亮的恒星，但实际灯光亮度由灯效决定。`id`、`name`、坐标系、历元和 `source_ids` 保留身份和来源信息。

`sources` 保存 URL、引用、获取时间、快照路径和校验值等来源元数据。验证器不限定其内部结构。现有数据的原始响应保存在 `data/sources/`，更新脚本更新星表时应同时保留来源快照。天球坐标不能直接当作面板上的毫米坐标。

### 逻辑图：constellation.json

`stars` 保存 `id`、`hip`、`reference_px`。`id` 在本场景中唯一，`hip` 对应星表，`reference_px` 保存参考图中的位置。额外的图像核对信息可以留在元数据里；图像位置和天文身份分别核对。

`edges` 保存唯一 `id` 和端点 `start`、`end`，端点是星的逻辑 ID。每条边必须连接不同的已有星，同一对星不能重复建边。这里的方向定义灯效进度的起点和终点；它不要求 WS2812 沿同样的方向接线。两条线在图上交叉不会自动形成节点，灰色背景剪影也不属于发光图。

### 实物布局：layout.json

| 字段 | 含义 |
|---|---|
| `density_leds_per_m` | 每米 LED 数，目前为 200，得到 5 mm 的灯间距 |
| `cut_unit_leds` | 每次允许裁切的灯数，目前为 2 |
| `width_mm`、`height_mm` | 实际星点中心包围框尺度，不能代替面板外形尺寸 |
| `panel` | 可选实体面板限制，包含 `width_mm`、`height_mm`、`margin_mm`；默认作者布局为 400 × 400 mm、5 mm 边距 |
| `strip_width_mm` | 灯带 PCB 的实际宽度；当前作者布局为用户确认的 5 mm |
| `star_defaults` | 生成星段的默认 `led_count`、`shape`、`row_gap_mm` 和 `angle_deg` |
| `star_overrides` | 按星 ID 覆盖生成参数；默认每星 4 灯、`grid_2x2` 两排 |
| `star_clearance_mm` | 生成星与连线灯段时预留的几何间隔 |
| `adjust_nearby_stars` | 是否为实体裁切间距微调相邻星点制作位置；带面板的布局默认开启 |
| `max_star_shift_mm` | 相对等比例参考图位置的最大允许移动，当前作者布局为 10 mm，生成器未指定时为 20 mm；超过时报告尺寸冲突 |
| `star_positions_mm` | 每个选定星的实体坐标，必须完整覆盖星 ID |
| `edge_paths_mm` | 按边 ID 指定逻辑折线路径；不提供时使用两颗星之间的直线 |
| `pieces` | 实际裁切的发光灯带段 |
| `wiring.order` | 全部灯带段的串接顺序及每段是否反接 |
| `generation` | 生成方式、尺寸及相关参数等记录 |

毫米坐标采用 **x 向右、y 向下**。逻辑边路径的第一个点必须是 `start` 星，最后一个点必须是 `end` 星。折线的总长是各段长度之和，灯效进度也按这个总长计算。

`panel` 约束实体 PCB 外形，不只检查 LED 中心。编译时将每个裁切路径按 `strip_width_mm` 向两侧扩展，检查完整灯带是否位于面板边距内。当前默认 `grid_2x2` 星由两段 10 mm 长的 2 灯条组成，两排中心间距为 `strip_width_mm + row_gap_mm`。按用户确认的 5 mm 条宽和 2 mm 排间隙，每星 PCB 包围框为 10 × 12 mm；四颗 LED 的横向间距为 5 mm，纵向间距为 7 mm。它是两排四灯星点，并非把 PCB 重叠拼成等距 5 mm 方阵。

`grid_2x2` 必须配置 `led_count: 4`。`shape: "straight"` 表示一个单一直段，允许 2、4、6……灯；`angle_deg` 旋转星段或整个两排星点。默认作者数据保留 21 星和 24 边，因此两排星点共有 42 段，连线另有 24 段，共 66 段。运行时仍以星的统一 `indices` 控制四灯，无需把星拆成两个逻辑对象。

带面板的生成器先按照完整星点包络和边距计算等比例缩放上限，再投影调整距离不足的近邻星点，为星点包络、端部间隔和最小 10 mm 连线裁切段留足空间。移动只作用于 `star_positions_mm`，不改 `constellation.json` 中的 `reference_px` 或星表天文坐标。`generation.original_scaled_positions_mm` 记录微调前的等比例位置，`generation.star_shift_mm` 保存逐星位移，`generation.max_star_shift_mm` 是实际最大位移；顶层同名字段为允许上限。当前最大实际位移约 4.67 mm，任何位移都不能超出设置上限或面板边界。换用其他 PCB 宽度时须修改 `strip_width_mm` 并重新生成，沿灯带方向的 5 mm 灯间距保持不变。

每个 `piece` 有 `id`、`owner_type`、`owner_id`、`led_count`、`path_mm`。`owner_type` 为 `star`、`edge` 或 `hidden`；隐藏段的 `owner_id` 必须为 `null`。一颗星可以拥有多个物理段，一条边也可以由多个段组成。LED 默认只能属于一个对象，星段和边段的灯不会重复计入。每颗星、每条边都必须拥有 LED。

`path_mm` 描述灯带**裁切边界**，而不是首末 LED 的中心。200 灯/m 时，一段 n 灯的裁切长度是 **n × 5 mm**，首末 LED 中心的跨度是 **(n−1) × 5 mm**。LED 在路径的 2.5、7.5、12.5… mm 处取样。每个物理段的 `led_count` 必须是正偶数，路径长度必须等于 `led_count × pitch_mm`；验证器允许 0.001 mm 数值误差。例如 2 灯段长 10 mm，两颗灯的中心相距 5 mm。

`wiring.order` 必须把每个 `piece_id` 写且只写一次。`reverse: true` 表示这段的串行输入位于 `path_mm` 末端，因此 LED 编号沿路径反向增加。**反接只改变编号，不改变空间位置上的边内进度 u**。相邻段之间的导线从上一段输出端连接到下一段输入端，编译器据此生成 `wire_links`；导线不占 LED 地址，也不成为逻辑连线。

修改尺寸需要重新生成 LED 数量、裁切长度、物理路径与串接计划。已经制作好的灯带不能仅通过修改 `width_mm` 就改变密度或外形。若只是调整预览窗口大小，应使用预览缩放。

命令 `python -m constellation_lamp build` 编译已保存的实物布局；`layout --output build/layout.json` 按其生成设置重新生成而不覆盖 `data/layout.json`，检查后再用 `layout --output data/layout.json` 保存。显式 `--width-mm` 仍指定星点中心包围框宽度，不能绕过 `panel`；当前面板下 `--width-mm 700` 会报尺寸冲突。没有 `panel` 的旧式模板保留原先按中心宽度缩放并加边距的行为。重生成保留默认星参数和逐星覆盖，重新计算段、路径和接线，因此不会保留手工修改的路径或串接顺序。首次自动串接使用确定性的最近邻启发式选择下一段及方向，不保证导线总长最短；实物制作前可以人工编辑 `wiring.order`。

## 可运行的最小例子

下面三份文档组成一个两星一边的布局例子，不替代项目现有人马座选点。两颗星各 2 灯，连线 8 灯，共 12 灯。连线方向为 `hip_95168 → hip_94820`。

`catalog.json`：

```json
{
  "schema_version": 1,
  "sources": [{"id": "hipparcos_i239", "citation": "ESA 1997, Hipparcos Catalogue"}],
  "stars": [
    {"hip": 95168, "id": "hip_95168", "name": "rho01 Sgr", "ra_deg": 290.41823037, "dec_deg": -17.84725155, "mag_v": 3.92, "source_ids": ["hipparcos_i239"]},
    {"hip": 94820, "id": "hip_94820", "name": "d Sgr", "ra_deg": 289.40868994, "dec_deg": -18.95288215, "mag_v": 4.88, "source_ids": ["hipparcos_i239"]}
  ]
}
```

`constellation.json`：

```json
{
  "schema_version": 1,
  "stars": [
    {"id": "hip_95168", "hip": 95168, "reference_px": [116, 78]},
    {"id": "hip_94820", "hip": 94820, "reference_px": [131, 84]}
  ],
  "edges": [{"id": "e01", "start": "hip_95168", "end": "hip_94820"}]
}
```

`layout.json`：

```json
{
  "schema_version": 1,
  "density_leds_per_m": 200,
  "cut_unit_leds": 2,
  "width_mm": 30,
  "height_mm": 40,
  "star_defaults": {"led_count": 2, "angle_deg": 0},
  "star_overrides": {},
  "star_clearance_mm": 1,
  "star_positions_mm": {"hip_95168": [10, 10], "hip_94820": [40, 50]},
  "edge_paths_mm": {"e01": [[10, 10], [40, 50]]},
  "pieces": [
    {"id": "star_a", "owner_type": "star", "owner_id": "hip_95168", "led_count": 2, "path_mm": [[5, 10], [15, 10]]},
    {"id": "edge_ab", "owner_type": "edge", "owner_id": "e01", "led_count": 8, "path_mm": [[13, 14], [37, 46]]},
    {"id": "star_b", "owner_type": "star", "owner_id": "hip_94820", "led_count": 2, "path_mm": [[35, 50], [45, 50]]}
  ],
  "wiring": {"order": [
    {"piece_id": "star_a", "reverse": false},
    {"piece_id": "edge_ab", "reverse": false},
    {"piece_id": "star_b", "reverse": false}
  ]},
  "generation": {"method": "manual-example"}
}
```

连线的逻辑长度为 50 mm，但发光段长 40 mm；两端剩余区域用于星灯段和间隔。把 `edge_ab` 的 `reverse` 改成 `true` 后，编号 2 的灯会移至原编号 9 的位置，其 u 仍表示同一个空间位置距离 `start` 星的比例。

## 编译后运行数据

`load_runtime(data_dir, layout_path=None)` 读取三份 JSON，验证后返回 `Runtime`。其中 `leds[index]` 对应物理灯带地址，记录物理位置、所属类型、所属星/边的数组下标和 `u`。非边 LED 的 `u` 为 `None`；隐藏段的 `owner_index` 为 −1。

每颗星、每条边的 `indices` 是明确的 LED 编号列表，不能把它简化成一个连续的起止区间。即使单个裁切段在串行链中连续，同一对象的多个段也可能隔着其他对象接线。反接的边还可能出现编号递增、u 递减。位置效果使用 x/y，连线流动使用 u，星闪烁使用星的逻辑身份。

JSON 是可编辑的源数据；编译后的运行表和 C 头文件是派生结果。修改星表或物理接线后应重新编译，避免手工修改派生表造成两个版本不一致。

## C99 / C++ 导出和移植

调用 `export_c(runtime, path)` 生成一个包含 `<stdint.h>` 的自包含头文件，单片机不需要解析 JSON。头文件有 include guard，表使用 `static const`，可以在 C99 或 C++ 中包含；多个翻译单元可能各自保留副本，因此嵌入式项目宜在负责灯效的一个翻译单元内包含它。当前头文件表示一个场景。

命令行导出已保存的布局：`python -m constellation_lamp export --output build/constellation_data.h`。完整 `build` 还生成运行 JSON、裁切表、接线表和预览 PNG。用 `--layout build/layout.json` 可以编译检查另一个布局版本，避免把预览中试验的尺寸与实际布线混淆。

导出接口包含：

- `constellation_leds`：每颗 LED 的 x/y、类型、所属对象下标、边内 u。
- `constellation_stars`：HIP、位置、星等、`mag_v_valid` 和成员列表的偏移/数量。
- `constellation_edges`：起点/终点星下标、逻辑路径总长和成员列表的偏移/数量。
- `constellation_star_led_indices`、`constellation_edge_led_indices`：明确的成员 LED 编号，按运行表顺序保存。
- `CONSTELLATION_*_COUNT`：各表的逻辑数量。空表使用一个存储占位元素，逻辑数量仍为 0，不能遍历这个占位元素。

成员偏移、数量、LED 索引和对象下标使用 `uint32_t`，超出范围会拒绝导出。隐藏 LED 的对象下标为 `UINT32_MAX`。未知星等导出 `mag_v = 0.0f` 和 `mag_v_valid = 0`；不能将它当作零等星。非边 LED 的 u 导出为 0.0f，必须结合类型解释。几何量导出为 `float`，数值须有限且能由 float32 表示。

通过成员表驱动某颗星的例子：

```c
const ConstellationStarInfo *star = &constellation_stars[star_index];
for (uint32_t k = 0; k < star->led_count; ++k) {
    uint32_t led = constellation_star_led_indices[star->led_offset + k];
    rgb[led][0] = red;
    rgb[led][1] = green;
    rgb[led][2] = blue;
}
```

帧缓冲的接口是 `uint8_t rgb[N][3]`，每个元素依次为 **R、G、B**。单个 RGB 帧缓冲占 **3N 字节 RAM**；这不包括灯效状态、驱动缓冲或双缓冲。灯效已经完成用户亮度处理，硬件驱动应把结果发送出去，避免无意中再乘一次用户亮度。WS2812 所需的实际色序由硬件驱动转换。

常量表的实际 Flash / RAM 位置取决于芯片、编译器和链接配置，不能仅凭 `const` 保证。某些目标需要额外的存储属性或访问方式。先选择单片机和 WS2812 驱动，再核对表、帧缓冲及驱动的内存需求。

Python 和单片机共享几何、索引、u、时间单位及 RGB 输出含义。Python 的预览库和 JSON 读取器不用移植；需要移植的是选定灯效的数学计算和状态更新，再用驱动层发送帧。对相同时间和参数比较逐 LED RGB，可以检查迁移是否保持效果。

## 紧凑 MCU 运行表

`pack_runtime(runtime)` 生成独立的 `constellation_compact_soa_v1` 派生格式，`export_compact_c(runtime, path)` 导出整数 C 表。完整浮点 Runtime 继续用于制作和仿真；量化仅发生在导出时。所有表采用 SoA（每个字段一个数组），避免结构体填充，同时保留原始电气 LED 编号。CLI：

```powershell
python -m constellation_lamp export --compact --output build/constellation_compact.h
```

| 字段 | 类型与含义 |
|---|---|
| `led_x_dm / led_y_dm` | `int16_t`，单位 0.1 mm，允许负坐标 |
| `led_owner_type` | `uint8_t`，0 隐藏、1 星、2 边 |
| `led_owner_index` | `uint16_t`，逻辑对象下标；隐藏为 65535 |
| `led_u16` | `uint16_t`，边内进度等于值除以 **65535**，两端精确为 0/1；非边为 0 |
| `star_hip` | `uint32_t`，HIP 编号不能缩成 16 位 |
| `star_mag_centi` | `int16_t`，星等×100；−32768 表示缺失 |
| `star_led_* / edge_led_*` | `uint16_t` 偏移、数量和明确 LED 成员索引，支持不连续的多段对象 |
| `edge_start_star / edge_end_star` | `uint16_t` 起终点星下标 |
| `edge_length_dm` | `uint16_t`，逻辑边长，单位 0.1 mm |
| `adjacency_offsets` | `uint16_t`，S+1 项，CSR 邻接区间边界 |
| `adjacency_neighbor_star / adjacency_edge_index` | `uint16_t`，无向图的邻星及所经边下标，每条边记录两次 |

数组符号统一带 `constellation_compact_` 前缀，宏带 `CONSTELLATION_COMPACT_` 前缀，可以与浮点头文件共存。量化舍入为最接近整数，中点向远离零方向舍入。坐标单轴理论误差不超过 0.05 mm；当前默认场景实测最大 0.049977 mm。u 的最大误差不超过 0.5/65535。

超范围会报错，禁止静默溢出或截断。支持最多 65535 个 LED，成员编号范围 0…65534；星/边对象不能占用隐藏索引哨兵。CSR 记录数为 2E，并且不得超过 65535。坐标、边长及星等也必须落在各自量化类型的范围内。

当前 **268 LED、21 星、24 边、48 邻接项** 的全部整数数组数据为 **3718 字节**，另需 804 字节单帧 RGB。`compact.json` 的 metadata 给出每张表的字节数和实际误差；这些是数组数据大小，程序、驱动、栈和缓存另外计算。空表有存储占位，逻辑数量仍为 0。ESP32 编译器可以淘汰未使用的常量数组，实际固件 Flash 占用以构建报告为准。

遍历一颗星的邻接关系：

```c
for (uint16_t k = constellation_compact_adjacency_offsets[star_index];
     k < constellation_compact_adjacency_offsets[star_index + 1]; ++k) {
    uint16_t neighbor = constellation_compact_adjacency_neighbor_star[k];
    uint16_t edge = constellation_compact_adjacency_edge_index[k];
    /* 用 neighbor / edge 进行图波传播；边的 u 仍按逻辑起终点定义。 */
}
```

## 灯效配置与驱动边界

`data/effects.json` 存公共默认参数和九种效果的命名预设，含 `schema_version: 1`；它不改变三份制作源文件。`state` 只用于派生缓存，输出不依赖上一次的帧。图传播和勾勒由连接关系计算距离及遍历顺序；空间波纹、极光、流星由物理毫米坐标计算。随机闪耀使用明确种子与逻辑恒星身份。

ESP32 参考固件可以接收电脑渲染的 RGB 帧，也支持九种原生脱机灯效和三个验线模式。`native_effects.h/.cpp` 使用定长 `RenderContext`、`NativeParams` 和 RGB 输出接口；星表查询、JSON 解析和 Matplotlib 留在电脑端。Mode 4 的预设由构建脚本生成，自定义路径和源星在编译前验证。

串口协议和电流估算见 [protocol.md](protocol.md)，参考硬件与固件构建见 [hardware.md](hardware.md)。`data/hardware.json` 保存硬件源参数，构建脚本同步到 `firmware-idf/main/Kconfig.projbuild` 对应的 sdkconfig 字段，并导出与固件绑定的配置快照。`firmware/include/config.h` 和 `platformio.ini` 属于 Arduino 备选实现。

紧凑导出还包含 `metadata.scene_sha256` 和 C 宏 `CONSTELLATION_COMPACT_SCENE_SHA256`。SHA256 对格式、数量、量化参数和全部数组的规范 JSON 计算，包含电气顺序，忽略显示名称及量化前的微小精度差异。指纹字符串和灯效/程序代码不计入 3718 B 数组数据。固件构建和串流握手以这个指纹检查当前映射。

`data/effects.json` 与 `data/hardware.json` 仍是源配置，`native_presets.h`、Kconfig、输出 `hardware.json` 都是派生结果。原生预设保留全精度的自动循环周期，仅空间查表量化；Python 和 C++ 都按绝对时间与种子渲染。修改路线/源星/种子时，C++ 调用方重新初始化 `RenderContext`；不变参数的帧可乱序请求。
