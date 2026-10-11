# BOM 与 ERC 收尾评审包 v1（评审资料，非生产放行）

**日期：2026-10-11。未修改 EasyEDA 原生设计。** 本包记录 C1 候选料的规格/焊盘评估、当前 ERC 归因证据和后续安全切换条件；不构成装配放行或采购授权。

## 当前结论

- 原生 C1 继续使用 Murata GRM155R71C154KA12D / C162182；未改原理图、核心板或拼板。CCTC TCC0402X7R154K160AT / C7393865 仅是 Qty 0 / HOLD 候选，尚未证明适配。
- CCTC 原厂 DRAAW108K/1-2022 第16页对 ≥100 nF 的 0402*2 给出最大本体尺寸 **1.20 × 0.70 × 0.70 mm**；原生 C1 land 的间距/轴向长度与推荐范围略有偏差，最大净高也增加 0.15 mm。见 `c1-alternative-comparison.md`。
- 最新只读 ERC 为 0 errors、1 个 `ATTRMATCHCODE` warning group，涉及 11 个器件。API 未给出具体比较字段或值，因此精确触发项仍未知；没有改匹配码或隐藏检查。见 `erc-attribution.md` 与 `fresh-live-erc.json`。
- 当前核心板和拼板 DRC 记录均为 0 groups。此次未改铜/几何，所以没有重复运行 DRC，也没有保存或导出原生工程。CT2 仍 DNP，且不进入四灯/两灯 BOM；C1 是唯一 150 nF 电容。

## 文件

- [current-bom-ready.csv](current-bom-ready.csv)、[current-bom-review.md](current-bom-review.md)：本轮更新后的汇总 BOM 与采购/适配评审，CCTC 候选为 Qty 0 / HOLD。原目录的 `manufacturing/bom-ready.csv` / `bom-review.md` 已被 2026-10-10 manifest 冻结，保留旧字节；最新结论以本目录为准。
- `c1-alternative-comparison.md`：原厂规格、实际 C1 land 测量、几何交叠计算及待核实的盖板净高/制程项。
- `erc-attribution.md`：ERC 结果、只读属性比较观察与归因边界。
- `fresh-live-erc.json`：本次只读 live ERC 结果摘要和已有持久化响应来源。
- `c1-candidate-register.csv`：Qty 0、未批准候选行。
- `candidate-pnp-gate.csv`：保留原生 C1 坐标作为上下文；明确未生成候选料 PnP，因为候选未同步且未通过适配评审。
- `legacy-four-led-bom.csv`、`legacy-two-led-bom.csv`、`legacy-four-led-panel-pnp.csv`、`legacy-two-led-panel-pnp.csv`：从 `manufacturing/draft` 复制的历史参考文件；BOM 副本标出 C1 HOLD，PnP 仍对应原生 Murata。它们不是 fresh export，也不能直接用于生产。
- `validation.json`、`baseline-manifest.json`：检查状态、live C1几何和原生/draft文件哈希核对。

## 后续切换条件

先核实 0.70 mm 本体高度与最终盖板、垫环、胶层的净空，再由装配/制程评审 0.3404 mm pad 间隙和 0.5004 mm pad 轴向长度是否可接受。完成后才考虑同步 EasyEDA C1 采购属性和装配 BOM；保持符号、封装、网络、位置、旋转及铜几何不变。之后须保存、关闭重开、确认 C1 数量/CT2 DNP，并重跑 fresh ERC、两块板 DRC，将新原生导出放入新的 dated closeout。不要覆盖 `manufacturing/draft`；旧 draft manifest 仍描述历史快照。
