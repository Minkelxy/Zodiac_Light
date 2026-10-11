# 2026-10-11 NFC 符咒评审归档

本包包含实际尺寸图案校样、马面光路候选、首件装配与测试空模板，以及 C1 / ERC 核对资料。它是现有工程的补充评审包，不是制造下单包，也不包含完整原生工程、全部历史素材或现有 Gerber。关联历史资料的链接需要在 `hardware/nfc-talisman` 工程目录中查看。

- [本轮推进报告](../improvement-review-2026-10-11.md)
- [十二款实际尺寸校样](../../artwork/production-study-v1/index.html)
- [首件装配与测试记录](../first-article-v1/README.md)
- [C1 与 ERC 核对](../bom-erc-closeout-v1/README.md)
- [材料与外观基线](../material-and-finish-baseline.md)

`manifest.json` 记录包内文件字节数和 SHA-256，以及 28 项现有制造基线的只读核对结果。ZIP CRC、成员完整性与磁盘字节一致性记录在同目录的 `validation.json`；该验证文件在 ZIP 外保存，避免对 ZIP 自身哈希形成循环。校样 SVG 内嵌源 PNG 字节，源图没有修改；打印后仍须量 10 mm 标尺。实物结果全部留空。
