# 十二符咒严格单色候选 v1

2026-10-11：用户批准仅统一可见像素 RGB 为每张指定主色。处理顺序为原生 ImageGen 重绘 → 布局候选 → 固定 RGB。Python 仅替换 alpha > 0 像素的 RGB；alpha、轮廓、留白、排线和画布位置逐字节保留。这是色值归一化，不是程序重绘。

已逐张检查主体、朝向、主要分段与透明负形；造型仍是参考修复稿。牛脸、龙角、虎条纹、猴的笔画及其他局部差异见 [逐张复核](../talisman-monochrome-v1/visual-review.md)。颜色通过不代表图形已获最终视觉批准。原生绘制来源与完整提示词见 [候选清单](../talisman-monochrome-v1/manifest.json)、[提示词](../talisman-monochrome-v1/prompts.json)。

## PNG 下载

- [鼠 Rat（#595959）](rat-single-ink.png)
- [牛 Ox（#286DA8）](ox-single-ink.png)
- [虎 Tiger（#282828）](tiger-single-ink.png)
- [兔 Rabbit（#86278D）](rabbit-single-ink.png)
- [龙 Dragon（#CF3037）](dragon-single-ink.png)
- [蛇 Snake（#22964C）](snake-single-ink.png)
- [马 Horse（#7365B6）](horse-single-ink.png)
- [羊 Sheep（#80DDC2）](sheep-single-ink.png)
- [猴 Monkey（#9B594B）](monkey-single-ink.png)
- [鸡 Rooster（#B9313B）](rooster-single-ink.png)
- [狗 Dog（#DFBA32）](dog-single-ink.png)
- [猪 Pig（#DF819D）](pig-single-ink.png)

Contact sheet: [contact-sheet.jpg](contact-sheet.jpg)
