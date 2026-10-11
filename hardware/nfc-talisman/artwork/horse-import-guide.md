# 手动导入马符咒图像

当前导入基准是 [单色正视马图](reference-collection/talisman-single-ink-v1/horse-single-ink.png)：马首朝左，六块紫色区域与头颈留白保持现有稿，不镜像、不增添装饰。原图和重绘记录见 [素材索引](reference-collection/index.html#talismans)；[Horse Talisman Gallery](https://jackiechanadventures.fandom.com/wiki/Horse_Talisman/Gallery) 用于核对原作构图。当前稿仍需在实际尺寸下人工确认细节。

在嘉立创EDA `ManufacturingPanel100` 中用“放置 → 图片”导入图片并勾选“放置原图”。1024×1024 的整幅透明 PNG 画布设置为 **37×37 mm**，中心对齐拼板坐标 `(20.5, 23.5) mm`；独立盖板中心为 `(0,0)`。可见马图的 alpha 包围框为 820×712 px，对应约 **29.63×25.73 mm**，不能把可见马图单独放大到 37 mm。保留整幅画布与透明边距，不裁切、不旋转、不镜像。

紫色透明 PNG 只有马图，没有灰色底座和暗色内场。背景须作为独立印刷分区与光路设计核对，不能用整片不透明深色背景覆盖计划出光区。完整外形为 37 mm 对边距八边形，两片垫环内窗为 30 mm 对边距；外侧观看马首朝左。`horse-import-guide.svg` 是空白定位预览，不能作为最终印刷图导入；[37 mm 校样与光路候选](production-study-v1/README.md) 是评审资料，也不替代 PCB 制造层。

校样另有 [十二款共用光腔适配候选](production-study-v1/light-window-candidate/index.html)：将整幅画布统一放置为 28.17×28.17 mm，不裁切、不改变 PNG。它为 30 mm 内窗留出名义余量，可与上面的 37 mm 基线比较；候选还未被选为最终马图尺寸，导入后必须核对实际图案、光路和板框，不能混用两套放置尺寸。

要用彩色丝印输出：PCB 设置中开启嘉立创彩色丝印；按嘉立创说明选择白色阻焊和沉金。两片外盖都在各自 Top 放图，装配后 Top 朝外，不因射手座位于背面而再次镜像。彩色图层单独导出，Gerber 调整后需重新检查色彩图、板框与开口是否对齐。图片导入和制造层设置见[嘉立创EDA彩色丝印指南](https://prodocs.lceda.cn/cn/pcb/other-draw-colorful-silkscreen/index.html)。

现有制造草案还没有马图，也没有马形光窗。PNG 的透明像素不等于 PCB 已去铜、去阻焊或开孔；保留 FR-4 的窗口与实际铣孔是不同工艺。确定出光区后须分别落实制造层、核查材料连通和天线投影，再保存重开检查及重新导出。暖金 LED 经 FR-4、油墨、扩散片后的亮度和颜色须用实物比较，不能由屏幕颜色判定。
