"""Rebuild the source-backed electrical handoff for the NFC talisman.

The JSON is a connectivity contract, not an EasyEDA native netlist. Native
library pin numbers (especially LEDs) must be checked against the library.
Run with Python 3.11+: python scripts/build_electrical.py [--download-sources]
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from urllib.request import Request, urlopen
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "electrical"
SOURCES = ROOT / "sources" / "electrical"
VERIFIED_DATE = "2026-10-09"

SOURCE_PDFS = [
    ("NXP_NT3H2111_2211_rev3.6.pdf", "https://cache.nxp.com/docs/en/data-sheet/NT3H2111_2211.pdf", "NXP", "Rev. 3.6, 2023-07-21"),
    ("NXP_TN00042_rev1.0.pdf", "https://cache.nxp.com/docs/en/engineering-bulletin/TN00042.pdf", "NXP", "Rev. 1.0, 2018-07-10"),
    ("NXP_AN11578_rev1.0.pdf", "https://cache.nxp.com/docs/en/application-note/AN11578.pdf", "NXP", "Rev. 1.0, 2016-02-01"),
    ("NXP_ES_NT3H2111_2211_rev4.1.pdf", "https://cache.nxp.com/docs/en/errata/ES_NT3H2111_2211.pdf", "NXP", "Rev. 4.1, 2025-10-30"),
    ("Kingbright_APG1608SYKC-T.pdf", "https://www.kingbrightusa.com/images/catalog/SPEC/APG1608SYKC-T.pdf", "Kingbright", "V.15B, 2025-03-13"),
    ("Murata_GRM155R71C154KA12.pdf", "https://search.murata.co.jp/Ceramy/image/img/A01X/G101/ENG/GRM155R71C154KA12-01A.pdf", "Murata", "Reference sheet, 2024-12-25 specifications"),
    ("YAGEO_RC0603FR-072K2L.pdf", "https://yageogroup.com/component-documentation/download/specsheet/RC0603FR-072K2L", "YAGEO", "Online part-specific specification"),
    ("YAGEO_RC0603FR-0747KL.pdf", "https://yageogroup.com/component-documentation/download/specsheet/RC0603FR-0747KL", "YAGEO", "Online part-specific specification"),
    ("YAGEO_CC0402JRNPO9BN470.pdf", "https://yageogroup.com/download/specsheet/CC0402JRNPO9BN470", "YAGEO", "Online part-specific specification"),
]

PARTS = {
    "ic": {"manufacturer": "NXP", "mpn": "NT3H2111W0FHKH", "lcsc": "C710403", "package": "XQFN8 1.6x1.6 / SOT902-3", "height_max_mm": 0.5,
           "source": "https://www.lcsc.com/fr/product-detail/RFID-ICs_NXP-NT3H2111W0FHKH_C710403.html"},
    "led": {"manufacturer": "Kingbright", "mpn": "APG1608SYKC/T", "lcsc": "C5875720", "package": "0603 (1608 metric) LED", "height_max_mm": 0.35,
            "source": "https://www.lcsc.com/product-detail/LED-Indication-Discrete_Kingbright-APG1608SYKC-T_C5875720.html"},
    "r2200": {"manufacturer": "YAGEO", "mpn": "RC0603FR-072K2L", "lcsc": "C114662", "package": "0603 (1608 metric)", "height_max_mm": 0.55,
              "source": "https://www.lcsc.com/product-detail/C114662.html"},
    "r47000": {"manufacturer": "YAGEO", "mpn": "RC0603FR-0747KL", "lcsc": "C105579", "package": "0603 (1608 metric)", "height_max_mm": 0.55,
               "source": "https://lcsc.com/product-detail/Chip-Resistor-Surface-Mount_YAGEO-RC0603FR-0747KL_C105579.html"},
    "c150n": {"manufacturer": "Murata", "mpn": "GRM155R71C154KA12D", "lcsc": "C162182", "package": "0402 (1005 metric)", "height_max_mm": 0.55,
              "source": "https://www.lcsc.com/es/product-detail/Multilayer-Ceramic-Capacitors-MLCC-SMD-SMT_Murata-Electronics_C162182.html"},
    "c47p": {"manufacturer": "YAGEO", "mpn": "CC0402JRNPO9BN470", "lcsc": "C60137", "package": "0402 (1005 metric)", "height_max_mm": 0.55,
             "source": "https://www.lcsc.com/product-detail/C60137.html"},
}


def component(ref: str, part: str | None, value: str, pins: dict[str, str], *, side="Top", population="Fit", note="") -> dict:
    result = {"reference": ref, "value": value, "pins": pins, "pcb_side": side, "population": population, "notes": note}
    if part:
        result.update(PARTS[part])
    return result


def make_netlist() -> dict:
    comps = [
        component("U1", "ic", "NT3H2111W0FHKH", {"1": "ANT_LA", "2": "GND", "3": "SCL", "4": "FD", "5": "SDA", "6": "VOUT", "7": "VOUT", "8": "ANT_LB"}, note="Center metal area is not an electrical pin: no copper/paste exposed center pad."),
        component("L1", None, "PCB octagonal spiral", {"1": "ANT_LA", "2": "ANT_LB"}, note="34mm across flats, 4 turns, width/gap 0.25/0.25mm; inner end via bottom return. Physical inductance is unmeasured."),
        component("C1", "c150n", "150nF 16V X7R 10%", {"1": "VOUT", "2": "GND"}, note="The ONLY VOUT/VCC bypass/storage capacitor. Nominal total 150nF; 165nF with +10% initial tolerance, below 220nF ceiling."),
        component("CT1", "c47p", "47pF 50V C0G 5%", {"1": "ANT_LA", "2": "ANT_LB"}, note="Starting value only. Include internal IC 50pF plus antenna/assembly parasitics when tuning."),
        component("CT2", None, "TUNE C0G 0402", {"1": "ANT_LA", "2": "ANT_LB"}, population="DNP", note="Unpopulated additional parallel tuning capacitor. Selection follows complete stack measurement; no invented part number."),
        component("R5", "r47000", "47kOhm 1%", {"1": "VOUT", "2": "SCL"}, note="Unused I2C clock held high."),
        component("R6", "r47000", "47kOhm 1%", {"1": "VOUT", "2": "SDA"}, note="Unused I2C data held high."),
        component("R7", "r47000", "47kOhm 1%", {"1": "VOUT", "2": "FD"}, note="FD pull-up; about 64uA at 3V while FD sinks. No external host."),
        component("TP1", None, "VOUT test pad", {"1": "VOUT"}),
        component("TP2", None, "GND test pad", {"1": "GND"}),
    ]
    for n in range(1, 5):
        side = "Top" if n <= 2 else "Bottom"
        optional = n in (2, 4)
        net = f"LED{n}_A"
        comps += [component(f"R{n}", "r2200", "2.2kOhm 1%", {"1": "VOUT", "2": net}, side=side, note="Independent LED current limit; never short."),
                  component(f"D{n}", "led", "Yellow 590nm", {"A": net, "K": "GND"}, side=side, note="Optional DNP to reduce load." if optional else "Baseline light source on this face.")]
    nets: dict[str, list[dict[str, str]]] = {}
    for comp in comps:
        for pin, net in comp["pins"].items():
            nets.setdefault(net, []).append({"reference": comp["reference"], "pin": pin})
    return {
        "format": "nfc-talisman.connectivity.v1", "revision": "v1", "source_verified_date": VERIFIED_DATE,
        "description": "Connectivity handoff. This JSON is not an EasyEDA native project or imported native netlist.",
        "power": {"external_source": False, "vcc_tied_to_vout": True, "vout_storage_nominal_nF": 150, "vout_storage_limit_nF": 220},
        "pin_name_map_U1": {"1": "LA", "2": "VSS", "3": "SCL", "4": "FD", "5": "SDA", "6": "VCC", "7": "VOUT", "8": "LB"},
        "led_pin_policy": "A and K denote polarity, not native library pad numbers. Resolve the EasyEDA/LCSC device mapping before routing; library pad digits are not assumed.",
        "components": comps, "nets": nets,
        "assembly_profiles": {"full": {"DNP": ["CT2"]}, "low_load": {"DNP": ["CT2", "D2", "D4"]}, "rf_only_diagnostic": {"DNP": ["CT2", "D1", "D2", "D3", "D4"]}},
        "validation_status": "Source and connectivity reviewed; no fabricated PCB or phone validation performed.",
    }


def write_bom(netlist: dict) -> None:
    headers = ["Designator", "Quantity", "Value", "Manufacturer", "MPN", "LCSC", "Package", "Side", "Population", "Height_max_mm", "Source_URL", "Notes"]
    with (OUT / "BOM.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        for c in netlist["components"]:
            if c["reference"] in {"L1", "TP1", "TP2"}:
                continue
            writer.writerow({"Designator": c["reference"], "Quantity": 1, "Value": c["value"], "Manufacturer": c.get("manufacturer", ""), "MPN": c.get("mpn", ""), "LCSC": c.get("lcsc", ""), "Package": c.get("package", "0402 (1005 metric)"), "Side": c["pcb_side"], "Population": c["population"], "Height_max_mm": c.get("height_max_mm", ""), "Source_URL": c.get("source", ""), "Notes": c["notes"]})


def write_schematic_svg() -> None:
    # This drawing uses connected net labels to keep antenna and power paths clear.
    items = ['<svg xmlns="http://www.w3.org/2000/svg" width="1400" height="980" viewBox="0 0 1400 980">',
             '<rect width="1400" height="980" fill="#f8fafc"/>',
             '<style>text{font-family:Arial,Microsoft YaHei,sans-serif;fill:#102b42}.title{font-size:30px;font-weight:bold}.small{font-size:16px}.label{font-size:20px}.wire{stroke:#257381;stroke-width:3;fill:none}.part{stroke:#102b42;stroke-width:3;fill:white}.hint{fill:#f0d899;stroke:#997e35;stroke-width:1.5}</style>']
    def text(x, y, s, cls="label", anchor=None):
        a = f' text-anchor="{anchor}"' if anchor else ""
        items.append(f'<text x="{x}" y="{y}" class="{cls}"{a}>{escape(s)}</text>')
    def line(x1,y1,x2,y2):
        items.append(f'<path d="M{x1},{y1} L{x2},{y2}" class="wire"/>')
    def label(x,y,s):
        text(x,y,s,"small")
    def dot(x,y):
        items.append(f'<circle cx="{x}" cy="{y}" r="4" fill="#257381"/>')
    def resistor(x,y,ref,val):
        line(x,y,x,y+10)
        items.append(f'<rect x="{x-11}" y="{y+10}" width="22" height="48" class="part"/>')
        line(x,y+58,x,y+75)
        label(x+18,y+22,ref)
        label(x+18,y+47,val)
    def capacitor(x,y,ref,val):
        line(x,y,x,y+22)
        line(x-18,y+22,x+18,y+22)
        line(x-18,y+36,x+18,y+36)
        line(x,y+36,x,y+75)
        label(x+24,y+28,ref)
        label(x+24,y+50,val)
    text(45,55,"37 mm NFC talisman — core electrical v1","title")
    text(45,88,"Source-backed schematic overview · Connectivity contract: netlist.json · No battery / no MCU","small")
    items.append('<rect x="470" y="165" width="350" height="280" rx="5" class="part"/>')
    text(645,200,"U1  NT3H2111W0FHKH","label","middle")
    text(645,224,"XQFN8 · SOT902-3","small","middle")
    pinleft=[(1,"LA",260),(8,"LB",385)]
    for pin,name,y in pinleft:
        line(440,y,470,y); label(478,y-7,f"{pin}  {name}")
    for pin,name,y in [(6,"VCC",260),(7,"VOUT",295),(3,"SCL",330),(5,"SDA",365),(4,"FD",400)]:
        line(820,y,850,y); label(715,y-7,f"{name}  {pin}")
        label(855,y-5,"VOUT" if pin in (6,7) else name)
    line(645,445,645,475); label(657,463,"2 VSS / GND"); line(610,475,680,475)
    label(541,420,"Center metal: NO solder/paste")
    # Antenna coil and parallel tuning capacitors.
    line(130,260,440,260); line(130,385,440,385)
    items.append('<path d="M130,260 L130,274 C85,274 85,296 130,296 C85,296 85,318 130,318 C85,318 85,340 130,340 C85,340 85,362 130,362 L130,385" class="wire"/>')
    label(45,235,"L1 PCB coil");label(45,415,"4 turns · 34 mm AF");label(45,440,"0.25 / 0.25 mm")
    label(300,250,"ANT_LA"); label(300,408,"ANT_LB")
    for x,ref,val in [(250,"CT1","47 pF C0G"),(385,"CT2","DNP")]:
        dot(x,260);dot(x,385);line(x,260,x,290);capacitor(x,290,ref,val);line(x,365,x,385)
    # C1 and unused interface pullups use net labels instead of cross-page wires.
    text(1000,190,"Shared EH supply","label")
    label(945,219,"VOUT");line(945,230,945,265);capacitor(945,265,"C1","150 nF X7R");line(945,340,945,367);label(954,361,"GND")
    text(940,410,"TP1: VOUT   TP2: GND","small")
    line(1080,230,1320,230); label(1090,220,"VOUT")
    for x,ref,net in [(1090,"R5","SCL"),(1170,"R6","SDA"),(1250,"R7","FD")]:
        dot(x,230);resistor(x,230,ref,"47k");line(x,305,x,347);label(x-9,369,net)
    items.append('<rect x="40" y="510" width="1320" height="330" rx="8" fill="#ecf2f6" stroke="#c4d3dd"/>')
    text(65,548,"Independent LED branches — D2 and D4 may be omitted to reduce load","label")
    for n,x in enumerate([175,485,795,1105],1):
        label(x-25,580,"VOUT");line(x,587,x,600);resistor(x,600,f"R{n}","2.2k");label(x+15,699,f"LED{n}_A")
        line(x,675,x,704)
        items.append(f'<path d="M{x-17},704 L{x+17},704 L{x},732 Z" class="part"/>')
        line(x-19,736,x+19,736);line(x,736,x,776)
        items.append(f'<path d="M{x+22},711 l17,-13 m-6,0 l6,0 l-1,6 M{x+30},730 l17,-13 m-6,0 l6,0 l-1,6" class="wire"/>')
        label(x-42,797,"GND");label(x+62,735,f"D{n}");label(x+62,758,"590 nm yellow")
        label(x-55,821,"TOP / horse" if n<=2 else "BOTTOM / stars")
        label(x-37,722,"A");label(x-37,750,"K")
    items.append('<rect x="40" y="860" width="1320" height="82" rx="5" class="hint"/>')
    text(60,887,"VCC ties directly to VOUT. C1 is the entire bypass total; do not add another supply capacitor.","small")
    text(60,911,"CT1 is an initial tuning value. Four LEDs may dim at low NFC field; assess full stack resonance and read/write under load.","small")
    text(60,935,"A/K identify LED polarity; map actual EasyEDA library pad numbers before manufacture. This SVG is not a native EDA schematic.","small")
    items.append('</svg>')
    (OUT / "schematic.svg").write_text("\n".join(items),encoding="utf-8")


ASSEMBLY = r"""# NFC 符咒核心板 v1 电气装配与调试

本目录提供电气连接契约和阅读用原理图；`netlist.json`、`schematic.svg`不替代立创 EDA 原生工程或 EDA 的 ERC/DRC。所有实物、谐振、手机和光学验收目前均为待执行。

## 固定接线及首版补充

U1 数字脚为 **1 LA、2 VSS、3 SCL、4 FD、5 SDA、6 VCC、7 VOUT、8 LB**。中心金属区不焊接，不能当作接地散热焊盘，也不能开中心钢网。VCC 直连 VOUT；唯一 C1 为 150 nF / 16 V / X7R / 0402，共享 VCC 去耦和 VOUT 储能。外加 VCC 电容会计入 VOUT 总量，首版不加。

SCL、SDA、FD 各由一颗 47 kΩ 上拉 VOUT，无 MCU、无外接 I²C 主机。该补充采用 NXP 的 EH 接法，避免悬浮接口；47 kΩ 大于 5 kΩ，FD 有场下沉约 43–64 µA。不能把 VOUT 或 VCC 接地。依据：[NXP 数据手册 §7、§8.6](https://cache.nxp.com/docs/en/data-sheet/NT3H2111_2211.pdf)、[TN00042 §4.4.1](https://www.nxp.com/docs/en/engineering-bulletin/TN00042.pdf)。

CT1 = 47 pF / 50 V / C0G，CT2 为未焊的并联调谐位；均跨 LA/LB。天线是 PCB 结构，不是采购电感。芯片内部约 50 pF，47 pF 不表示成品已调谐，叠装寄生和铜图案都须包含在测量中。增加并联电容通常降低谐振频率；频率过低时减小/去掉 CT1，而不是继续加 CT2。[AN11578](https://www.nxp.com/docs/en/application-note/AN11578.pdf)

R1→D1、R2→D2 在核心板正面；R3→D3、R4→D4 在背面。每路 VOUT→2.2 kΩ→LED 阳极 A，LED 阴极 K→GND。D2、D4 可不焊；对应电阻保留也不会有闭合负载。标准 BOM 四灯均焊、CT2 不焊。LED 型号为 **590 nm 黄色**，暖金是外观描述，并非暖白色温规格。LED 的 A/K 必须通过 EDA 库核对为实际焊盘编号，图上 A/K 不假定为 1/2。[Kingbright 原厂](https://www.kingbrightusa.com/images/catalog/SPEC/APG1608SYKC-T.pdf)

## 采购与净高

|功能|固定型号|立创编号|封装|器件本体最大高度|
|---|---|---|---|---|
|U1|NT3H2111W0FHKH|C710403|XQFN8 / 1.6×1.6 mm|0.50 mm|
|D1–D4|APG1608SYKC/T|C5875720|0603 LED|0.35 mm（0.25±0.10）|
|R1–R4|RC0603FR-072K2L|C114662|0603|0.55 mm|
|R5–R7|RC0603FR-0747KL|C105579|0603|0.55 mm|
|C1|GRM155R71C154KA12D|C162182|0402|0.55 mm|
|CT1|CC0402JRNPO9BN470|C60137|0402|0.55 mm|

型号、参数和 LCSC 编号已按官方产品页核验；来源 URL 在 `BOM.csv`。未记录实时价格或库存保证。最大本体高度不含焊锡浮高；1 mm 垫环内窗应覆盖所有元件、丝印标记和测量点，试装时检查盖板不压元件。

## 两面回流与组装

1. 装配前核对 U1 pin-1、LED 阴极标记和 CT2 DNP，测量 VOUT/GND 没有焊接短路。线圈直流连通是正常的，不能把 LA/LB 间蜂鸣误判为短路。
2. 先贴底面 D3/D4、R3/R4，后贴顶面 U1、C1、CT1、R1/R2/R5/R6/R7、D1/D2。使用平整的回流支撑，检查第一次回流器件在第二次过程中不移动。也可店铺两面回流。
3. APG1608 不超过两次回流；以其原厂 profile 和焊膏工艺共同限定峰值及时间。不要根据普通厚 LED 封装随意延长保温；检查 MSL 3 的开封/烘烤要求。
4. 先测裸核心，再干装五层。临时定位夹具仅放外围，试验非金属扩散片；所有金属、胶和扩散片保持与最终样件一致再调谐。天线附近不放金属夹具。
5. 确认双面图案、光路、读写后再在两垫环外围胶合，胶不能流入元件、星孔、槽或马形光窗。

## 首次 NFC / NDEF 格式化

适用对象是 GET_VERSION 为 NTAG I²C **plus 1k** 的新芯片。CC 初值为零，用户区出厂数据不定。优先使用支持该型号的 NFC 工具；普通 NDEF 写入可能无法识别零 CC。可用支持原始 NFC-A 收发的 Android 手机应用或 Type 2 Tag 读写器初始化。命令表不含 CRC_A：Android `NfcA.transceive()` 由系统附加 CRC；读写器按自身 API 决定是否附加。[NXP 数据手册 Table 8、Fig.11、§10](https://cache.nxp.com/docs/en/data-sheet/NT3H2111_2211.pdf)

|顺序|RF 命令（十六进制）|作用与预期|
|---|---|---|
|1|`60`|GET_VERSION，确认 `00 04 04 05 02 02 13 03`；不匹配时停止此流程。|
|2|`30 00`|读 page 00–03；保存 UID、page02 和 CC page03（最后四字节）。|
|3|`30 E2`|读 E2–E5，保存动态锁字节和 AUTH0；新片 E2 前三字节为零、E3 第四字节通常 FF。|
|4|`30 04`|先保存用户区。仅对已确认新片且 CC=`00 00 00 00` 执行下面写入。|
|5|`A2 04 03 00 FE 00`|WRITE page04，建立空 NDEF TLV 和终止符；检查 ACK。|
|6|`30 04`|回读确认 page04 的四字节。|
|7|`A2 03 E1 10 6D 00`|WRITE page03，按原厂 plus 1k 示例设置读写 CC；检查 ACK。|
|8|`30 03`|回读 page03–06，确认 CC 与空 NDEF，移离 RF 再重新扫描。|

WRITE 成功响应为四位 ACK `Ah`（API 常以 byte `0A` 表示）。每次写后等待至少 10 ms 再回读；失去 RF 场时重新扫描、回读状态，不盲目重写。若 CC 已为 `E1 10 6D 00` 且含有效 NDEF，则保留内容并直接进行标准 NDEF 改写；其他 CC/锁位/保护状态需要另行分析，不能覆盖。

**禁止使用“一键永久锁定/只读”。** 首版不写 page02、E2–E9、密码/访问配置或 CC 访问字节 0F；RF 侧 CC 和锁位的一些设置不可通过 RF 清零。仅在上述确认条件下初始化 page03/page04；不使用 I²C block00 的批量写法，避免触及地址和静态锁位。

格式化后先写一个 HTTPS 链接，再用标准 NDEF 工具改写为文本并回读。Android 与 iPhone 都用支持 NDEF 写入的应用验证；iPhone 对 URL 的后台读取与在应用内读取普通文本属于不同界面，不以“文本无后台弹窗”判定标签坏。未在本任务中操作真实手机或写入真实标签。

## 调试与验收记录

- 开始用四灯 BOM 测试。如果通信边缘不稳定，移除 D2、D4 后重复测量；不降低四个限流电阻来强行增加亮度。用高阻探头测 TP1–TP2 的 VOUT；使用长探头接地会改变 RF 环境。
- 分别测 RF 诊断（所有 LED DNP）、四灯与两灯，以及裸板/完整叠装。记录 CT1/CT2、谐振频率、最小/最大 VOUT、可读写摆位。VOUT 来自手机场，LED 亮度与连续点亮时间不是恒定电源规格。
- 每台手机、每一面连续读十次，至少改写两次，记录成功次数、型号、系统、NFC 天线位置和图案遮光效果。只有实测达到目标后才能称通过手机/光学验收。
- 开槽两盖板可能漏光、透明 FR-4 会衰减且散射黄色光；试装先评估，再决定薄扩散片厚度。不能依据 SVG 预览声称达到了柔光。

最新已查 NXP errata Rev.4.1（2025-10-30）主要处理 I²C/RF 同时访问的竞态和数据损坏；本版无 I²C 主机，SCL/SDA 固定高，不进行 I²C 事务。如果以后添加主机，必须执行其中的时序与回读要求。[原厂 errata](https://www.nxp.com/docs/en/errata/ES_NT3H2111_2211.pdf)
"""


def validation(netlist: dict) -> dict:
    c = {x["reference"]: x for x in netlist["components"]}
    results = []
    def check(name, passed, detail):
        results.append({"check": name, "passed": bool(passed), "detail": detail})
    check("U1 pinning", c["U1"]["pins"] == {"1":"ANT_LA","2":"GND","3":"SCL","4":"FD","5":"SDA","6":"VOUT","7":"VOUT","8":"ANT_LB"}, "NXP datasheet Table3; center pad is absent.")
    check("EH supply capacitance", netlist["power"]["vout_storage_nominal_nF"] == 150 and 150*1.1 < 220, "Single C1; max initial tolerance 165nF.")
    check("LED individual resistors and polarity", all(c[f"R{n}"]["pins"] == {"1":"VOUT","2":f"LED{n}_A"} and c[f"D{n}"]["pins"] == {"A":f"LED{n}_A","K":"GND"} for n in range(1,5)), "Four independent 2.2k branches.")
    check("SCL/SDA/FD pullups", all(c[ref]["pins"] == {"1":"VOUT","2":net} for ref,net in [("R5","SCL"),("R6","SDA"),("R7","FD")]), "Three 47k >5k pullups.")
    check("RF tuning only LA/LB", all(c[ref]["pins"] == {"1":"ANT_LA","2":"ANT_LB"} for ref in ["L1","CT1","CT2"]), "Both tuning caps across antenna; CT2 DNP.")
    check("Parts under 0.6mm body height", all(x.get("height_max_mm",0)<=0.6 for x in c.values()), "Based on selected manufacturer specifications; solder height excluded.")
    check("Net membership covers all pins", sum(len(x) for x in netlist["nets"].values()) == sum(len(x["pins"]) for x in c.values()), "Connectivity consistency; does not test PCB copper.")
    return {"status": "passed" if all(r["passed"] for r in results) else "failed", "scope": "Source-backed logical connectivity only. Not native EDA ERC/DRC or prototype validation.", "checks": results, "pending": ["Native EasyEDA library LED polarity mapping", "Native EDA ERC and PCB DRC", "Full-stack resonance and VOUT measurement", "Android/iPhone and optical tests"]}


def download_sources() -> None:
    SOURCES.mkdir(parents=True,exist_ok=True)
    entries=[]
    for name,url,publisher,revision in SOURCE_PDFS:
        path=SOURCES/name
        try:
            if not path.exists():
                with urlopen(Request(url,headers={"User-Agent":"Mozilla/5.0"}),timeout=45) as response:
                    content=response.read()
                if not content.startswith(b"%PDF"):
                    raise ValueError("Source returned non-PDF; not archived as PDF")
                path.write_bytes(content)
            entries.append({"file":name,"url":url,"publisher":publisher,"revision":revision,"retrieved_date":VERIFIED_DATE,"sha256":hashlib.sha256(path.read_bytes()).hexdigest(),"size_bytes":path.stat().st_size,"status":"archived"})
        except Exception as exc:
            entries.append({"file":name,"url":url,"publisher":publisher,"revision":revision,"status":"download_failed","error":str(exc)})
    (SOURCES/"manifest.json").write_text(json.dumps(entries,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"sources_archived":sum(x["status"]=="archived" for x in entries),"sources_failed":[x["file"] for x in entries if x["status"]!="archived"]}))


def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--download-sources",action="store_true")
    args=parser.parse_args()
    OUT.mkdir(parents=True,exist_ok=True)
    netlist=make_netlist()
    (OUT/"netlist.json").write_text(json.dumps(netlist,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    write_bom(netlist)
    write_schematic_svg()
    (OUT/"assembly.md").write_text(ASSEMBLY.replace("https://www.nxp.com/docs/", "https://cache.nxp.com/docs/"),encoding="utf-8")
    report=validation(netlist)
    (OUT/"connectivity-validation.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    phone_record = OUT/"phone-test-record.csv"
    if not phone_record.exists():
        phone_record.write_text("Date,Phone,OS,Side,Assembly,CT1_pF,CT2_pF,LED_profile,Read_success_out_of_10,URL_write_ok,Text_rewrite_ok,VOUT_min_V,VOUT_max_V,Resonance_MHz,Light_observation,Notes\n",encoding="utf-8-sig")
    (OUT/"source-index.md").write_text("# 电气来源索引\n\n"+"\n".join(f"- [{publisher} {revision}]({url}) — `{name}`" for name,url,publisher,revision in SOURCE_PDFS)+"\n\n采购页按 2026-10-09 核验，见 BOM.csv；来源文件哈希见 ../sources/electrical/manifest.json。\n",encoding="utf-8")
    if args.download_sources:
        download_sources()
    print(json.dumps({"electrical_output":str(OUT),"connectivity_validation":report["status"],"components":len(netlist["components"]),"nets":len(netlist["nets"])}))
    if report["status"]!="passed":
        raise SystemExit(1)


if __name__=="__main__":
    main()
