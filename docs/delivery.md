# 复现、打包与交付

本指南适用于仓库中的灯带软件、40 cm U1 制作资料和当前 NFC 双款设计草案。当前状态见[项目状态](current-project.md)，资料分类见[文档地图](document-map.md)。上传或下载源码包不会改变 NFC 的制造 HOLD，也不会补齐实物验收。

## 接收项目

可从 [GitHub 仓库](https://github.com/Minkelxy/Zodiac_Light)克隆，或从[版本下载页](https://github.com/Minkelxy/Zodiac_Light/releases)取得交付 ZIP 与同名 `.sha256`。交付 ZIP 包含 Git 跟踪文件和 `delivery-manifest.json`；本机 `build/`、虚拟环境、工具缓存及忽略的 `data/reference.png` 不在包内。运行和灯条定位使用保存的恒星/布局 JSON，无需该原始参考图片。

对下载的包，先按实际文件名核对外部 SHA-256，再解压。PowerShell 示例：

```powershell
Get-FileHash -LiteralPath .\Zodiac_Light-<commit12>.zip -Algorithm SHA256
Get-Content -LiteralPath .\Zodiac_Light-<commit12>.zip.sha256
Expand-Archive -LiteralPath .\Zodiac_Light-<commit12>.zip -DestinationPath .\received
```

`<commit12>` 应换成下载文件中的真实提交前缀；将输出的 SHA-256 与校验文件逐字对照。解压后可用包内脚本核对 `delivery-manifest.json` 中的每个文件及 ZIP 成员：

```powershell
Set-Location .\received\Zodiac_Light
python scripts/package_project.py --verify ..\..\Zodiac_Light-<commit12>.zip
```

外部 SHA-256 用于核对下载文件；包内清单记录提交和逐文件哈希，用于核对内容完整性。它们不证明硬件已经生产或验收。ZIP 解压目录没有 `.git`，可运行检查和预览；如需生成新的按提交交付包，应使用 Git 克隆的工作区。

## 安装与全项目检查

使用 Python 3.11 或更高版本。在项目根目录运行：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python scripts/check_project.py --output build/project-check.json
```

若当前 PowerShell 策略不允许激活脚本，可直接用 `.\.venv\Scripts\python.exe` 替换后续命令中的 `python`。GUI 预览需要 Matplotlib 的可用桌面后端；静态渲染和布局构建不需要打开窗口。串口实播另需 `python -m pip install "pyserial>=3.5"`。

[check_project.py](../scripts/check_project.py)运行全部 unittest、CLI 布局/硬件预算验证、NFC 原彩色与普通绿白的保存快照/导出审计、U1/灯条定位模板的源文件与 PDF 哈希检查，以及入口文档的本地链接检查。报告记录各步骤结果；任一步骤失败即返回失败。可用 `--skip-tests` 跳过 unittest 进行资料复核，该结果应注明未运行软件测试。

有主机 C/C++ 编译器时，软件测试会编译并运行协议、导出表和原生灯效比较。Windows 的 [run_checks.cmd](../scripts/run_checks.cmd)可初始化默认路径的 Visual Studio 2022 Community 后运行 unittest；其他编译器可在已配置的终端中运行检查。缺少编译器造成的跳过属于检查范围限制。全项目检查不会启动嘉立创EDA、运行新的原生 ERC/DRC、刷板或进行实体测试；其 NFC 结果核对的是已保存归档与导出证据。

## 使用与再生成

| 工作 | 命令或入口 | 产生或使用的资料 |
|---|---|---|
| NFC 十二选项完整工程 | [nfc-twelve-options.epro2](../hardware/nfc-talisman/variants/twelve-options/eda/native/nfc-twelve-options.epro2)、[四块盖板说明](../hardware/nfc-talisman/variants/twelve-options/README.md) | 统一九 PCB 当前档；六块绿白板同步纹理边框，核心板与原彩色两板保留，两块整套绿白板保护电气/星孔光槽/阻焊，拆板孔外移 0.40 mm 并闭合内框 |
| 灯带交互预览 | `python -m constellation_lamp preview` | 已保存的 21 星、24 边、268 灯布局与九种灯效 |
| 灯带构建 | `python -m constellation_lamp build` | `build/` 内运行表、裁切/接线 CSV、C 头文件、静态图 |
| 静态灯效 | `python -m constellation_lamp render --effect ripple --time-ms 2400 --output build/ripple.png` | 指定时刻的 PNG |
| U1 与灯条打印 | [40 cm 制作资料](../output/README.md) | U1 PDF 第 2–7 页与定位 PDF 第 2–7 页；先实测 100 mm 校准尺 |
| ESP32 构建 | [固件说明](hardware.md) | 安装 ESP-IDF/工具后运行 `scripts/build_idf.ps1`；固件输出到 `build/esp-idf/` |
| NFC 原彩色原生工程 | [nfc-two-variants.epro2](../hardware/nfc-talisman/variants/common/eda/native/nfc-two-variants.epro2) | 原彩色 3 PCB 归档，含共用核心和两款独立拼板 |
| NFC 普通绿白与全工程 | [绿白双款入口](../hardware/nfc-talisman/variants/standard-green-white/README.md)、[统一九 PCB 原生工程](../hardware/nfc-talisman/variants/twelve-options/eda/native/nfc-twelve-options.epro2)、[独立导出清单](../hardware/nfc-talisman/variants/standard-green-white/export-manifest.json) | 当前普通绿白版与十二选项共用九板归档；制造导出状态以对应独立清单为准 |
| NFC 绿白历史五板档 | [nfc-color-and-green-white.epro2](../hardware/nfc-talisman/variants/standard-green-white/eda/native/nfc-color-and-green-white.epro2) | 加边框前的五板工程快照保留，不能代替当前九板归档 |
| NFC 制造审阅 | [原彩色导出清单](../hardware/nfc-talisman/variants/common/export-manifest.json)、[原彩色装配审阅清单](../hardware/nfc-talisman/variants/common/assembly-review-manifest.json)、[普通绿白入口](../hardware/nfc-talisman/variants/standard-green-white/README.md) | 按工艺版本选择原生快照、Gerber 和四灯/两灯审阅表，原彩色清单不覆盖为绿白版 |

打印资料的再生成需要 ReportLab 和 Windows 黑体字体；具体依赖、输出覆盖范围见[制作资料的再生成说明](../output/README.md#重新生成)。现有 PDF 可直接下载打印。PDF 生成会包含生成时的元数据，重新生成后应使用本次同步更新的清单核对，不能要求它与旧 PDF 的字节哈希相同。

`build` 编译保存布局；`layout` 会重新计算实体路径和初始串接顺序，使用前应保留手工接线修改。历史图案生成脚本和编号桥接脚本分别针对各阶段，其中有些会覆盖文件或写入活动 EDA；先查[脚本边界](../hardware/nfc-talisman/eda/api-notes.md)。NFC 当前装配文件为各 variant 的 `four-led-*-review.csv` 或 `two-led-*-review.csv`，原始 `bom-all.csv`/`pnp-all.csv` 含 DNP 占位且实际为制表符分隔，不应直接用于装配。C1 采购 HOLD、CT1 调谐与实体测试待办仍适用。

## 生成新的交付包

先完成改动、检查并提交，使 Git 工作区干净，再运行：

```powershell
python scripts/package_project.py
```

[package_project.py](../scripts/package_project.py)默认重新运行全项目检查，只打包 Git 跟踪文件，默认输出 `build/releases/Zodiac_Light-<commit12>.zip` 和同名 `.sha256`。`delivery-manifest.json`记录提交、文件哈希与制造 HOLD；有未提交改动或检查失败时停止打包。`--output` 可指定输出 ZIP 路径；`--skip-tests` 可跳过 unittest，但仍运行其他检查并记录此限制。

上传版本时同时附上 ZIP 和 `.sha256`，并注明对应提交和检查范围。接收者从总 README 进入 U1 制作资料或 NFC 双款清单。当前包包含历史评审文件，使用时按[文档地图](document-map.md)区分适用版本；发布源码交付包不等于允许按制造草案下单。
