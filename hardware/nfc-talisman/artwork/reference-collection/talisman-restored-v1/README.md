# 十二符咒 · 修复正视透明图案 v1

本组 `*-restored.png` 为十二张独立透明 PNG **v1 修复稿**。以 `source-talisman/` 原始插画为造型依据，使用原生 ImageGen 逐张重建低分辨率轮廓与可辨认细节，并将八边形符咒承载平面校正为正视。目标是保留动物自身姿态、朝向、配色、分段笔画和负空间；正视化不代表把所有动物转成正脸。

**龙、虎、猴仍有细节偏差，待精修。** 龙的尖端/片段、虎的黑白碎笔、猴的线宽未达到与源图准确一致；其他图也存在曲率和描线的重建解释。不要把本版视为已经全部准确还原完成。逐张结果见 [目视复核](visual-review.md)。

每张为 **1024×1024 RGBA**，图案最长边约 **820 px**，等比缩放、居中放置，四周至少约 100 px 透明留白。只含动物图案，不含石质底座、边框、阴影、文字或棋盘格。预览用棋盘格另见 [总览 JPG](restored-contact-sheet.jpg)，它不属于透明图案文件。

2026-10-10 羊图修订：恢复源图连续的薄荷绿头部和两道空心耳线，纠正上一版误拆头部为散点的问题；身体中央仍透明。两步原生 ImageGen 修复的输入、原稿及完整提示词见 [修订记录](raw/sheep-revision.json)，其他十一张成品保持原文件内容。

| 生肖 | 文件 | 主要保留特征 |
|---|---|---|
| 鼠 | [rat-restored.png](rat-restored.png) | 灰色右向奔跑、长回弯尾与分段肢体 |
| 牛 | [ox-restored.png](ox-restored.png) | 蓝色正面牛头、成对牛角及耳部 |
| 虎 | [tiger-restored.png](tiger-restored.png) | 黑白双虎回旋、条纹与留白 |
| 兔 | [rabbit-restored.png](rabbit-restored.png) | 紫色右向单兔、长耳与分段腿脚 |
| 龙 | [dragon-restored.png](dragon-restored.png) | 红色左向东方龙、弯身与分段爪尾 |
| 蛇 | [snake-restored.png](snake-restored.png) | 绿色左向蛇头、盘绕曲线及原有断口 |
| 马 | [horse-restored.png](horse-restored.png) | 紫色左向马头、六块主分段及锯齿鬃毛 |
| 羊 | [sheep-restored.png](sheep-restored.png) | 薄荷绿右向羊头、空心耳线、背/尾与四腿笔画，躯干中央透明 |
| 猴 | [monkey-restored.png](monkey-restored.png) | 赭色坐姿猴、左侧大卷尾 |
| 鸡 | [rooster-restored.png](rooster-restored.png) | 红色右向单鸡、左侧尾羽及分段脚 |
| 狗 | [dog-restored.png](dog-restored.png) | 黄色右向站姿狗、上卷尾与分段腿 |
| 猪 | [pig-restored.png](pig-restored.png) | 粉色左向猪头、弧形轮廓及内部留白 |

`raw/` 保存选用的原生生成图和每张的完整提示词。[prompts.json](prompts.json) 汇总提示词；[manifest.json](manifest.json) 记录原图、生成图、成品哈希、尺寸、裁切位置、等比缩放比例与放置位置；[validation.json](validation.json) 记录文件与布局检查。[修复版 ZIP](../../talisman-restored-v1.zip) 提供十二张成品和检查元数据；生成原稿在完整素材 ZIP 内。

尺寸整理脚本只裁去透明边缘、等比缩放和居中，不承担形体重绘。以 alpha≥8/255 确定有效边界并外扩 2 px；该范围外极淡的生成残留不纳入画布，范围内的透明层级和所有分段保留。按此前已授权的 Python 图片整理流程生成统一画布。

```powershell
python hardware/nfc-talisman/scripts/normalize_talisman_restorations.py
python hardware/nfc-talisman/scripts/build_reference_gallery.py
```

这是基于 **200×141** 参考图的修复版本，缺失信息不能被精确反推，细节仍需与参考图并排审阅；不声称是动画官方原始生产稿。完整源图和原像素透明版均保留在索引中，便于比较。PNG 不是 PCB 加工路径，马图仍由用户手动导入，尚未将本组图案写入 EDA 或制造文件。原作图像的来源及权利说明见 [集合说明](../README.md)。
