# 马符咒与射手座图案导入

马头图案目前留给用户在嘉立创EDA中手动导入。本项目不再生成马形矢量，也没有把早先的探索稿放进制造板；旧稿已移到 `artwork/archive/exploratory-horse-v1/`，不可用于生产。

马面按用户参考图保持原构图：灰色八边形底座、深色内场、紫色马首侧面剪影，马口朝右；不增加鬃毛造型、符号、边饰或文字。`horse-import-guide.svg` 只显示底座与图像放置范围，是定位指南，不是可制造图案。原动画截图和宣传图可从 [Horse Talisman Gallery](https://jackiechanadventures.fandom.com/wiki/Horse_Talisman/Gallery) 对照；链接仅作视觉参考，图片版权仍归权利人。

## 手动导入位置

在 `ManufacturingPanel100` 拼板文档中导入图像：马盖板中心为 `(20.5, 23.5) mm`，板外形对边 37 mm。保持图像朝向与附件一致，不镜像；马首剪影落在内场中，四周保留原图的灰色八边框。若在独立子板文档中操作，则将图像中心放在原点 `(0, 0)`。

本工程准备采用嘉立创彩色丝印实现灰底与紫马：白色阻焊、沉金、双层 FR-4，并在 PCB 设置中启用彩色丝印。请将用户选定的原图/授权图作为原图导入顶层丝印，并在导出制造文件时一并导出嘉立创彩色丝印文件。彩印可能改变透光率；正式加工前需用预览及首件确认暖光能否透过马面。工艺限制与入口见[嘉立创EDA彩色丝印说明](https://prodocs.lceda.cn/cn/pcb/other-draw-colorful-silkscreen/index.html)。

射手座面不添加人马图案。现有八星孔与十一条连通光槽保留，新增顶层拉丁文 `AD ASTRA` 与 `FORTIS ET LIBER`，均从背面外侧左到右阅读。两片外盖图案都在各自 PCB Top；射手座 Top 在叠装时朝外（本文件夹具方向图会注明内侧视图变换）。

`art_data.json` 只保留射手座单线字形和马图导入约定，不含马图几何。`scripts/build_panel_import.py` 只导入板框、孔槽、器件和射手座文字，不会创建马图。
