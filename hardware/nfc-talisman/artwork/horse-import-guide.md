# 手动导入马符咒图像

参考 [Horse Talisman Gallery](https://jackiechanadventures.fandom.com/wiki/Horse_Talisman/Gallery) 核对原图形态。请选取你有权使用的图像；本工程不复制或重绘剧照。

在嘉立创EDA `ManufacturingPanel100` 中用“放置 → 图片”导入图片并勾选“放置原图”。图像中心对齐拼板坐标 `(20.5, 23.5) mm`，水平/垂直外形按 37 mm 对边距八边形校准，保持附件朝向（马首朝右）且不镜像。只保留原图的灰色八边底座、暗色内场、紫色马首，不加新装饰。`horse-import-guide.svg` 是空白定位预览，不能作为最终印刷图导入。

要用彩色丝印输出：PCB 设置中开启嘉立创彩色丝印；按嘉立创说明选择白色阻焊和沉金。彩色图层单独导出，Gerber 调整后需重新检查色彩图与板框是否对齐。图片导入和制造层设置见[嘉立创EDA彩色丝印指南](https://prodocs.lceda.cn/cn/pcb/other-draw-colorful-silkscreen/index.html)。暖光透过紫色区域的亮度没有依据屏幕预览判断，首板试做前确认彩印是否影响出光。
