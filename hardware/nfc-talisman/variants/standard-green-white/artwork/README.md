# 普通绿色阻焊与白色丝印图案

本目录为两款独立普通 PCB 版的图案输入和预览。前盖为白色马/蛇轮廓，后盖为白色星图、星孔环与文字；绿色来自未开窗的阻焊。没有彩色喷印、动物形状阻焊开窗或装饰铜。

## 导入几何

- `horse-sagittarius-standard-layer-artwork.json`：前盖 6 个丝印填充；后盖 49 个丝印填充、19 个阻焊开窗（8 孔、11 槽）。
- `snake-leo-standard-layer-artwork.json`：前盖 5 个丝印填充；后盖 37 个丝印填充、17 个阻焊开窗（9 孔、8 槽）。
- `faces.front/rear.silk_polygons` 与 `mask_opening_polygons` 每项的 `path_mil` 是 EasyEDA complex polygon；外环顺时针、孔环逆时针，请求填充线宽为 `native_fill_width_mil=0`；当前客户端保存时归一化为 0.2 mil。实际 Gerber 区域已独立核对，没有额外描边或图形外扩。
- 两面都为原拼板的外侧 Top：白丝印层 3、阻焊开窗层 5。阻焊填充表示**去除绿油**，不能用全版绿色 FILL 代表绿底。
- 原图为 37 mm 页、x 向右/y 向下，不镜像；原生 mil 映射为前盖 `x=(2+sx)/0.0254, y=(95-sy)/0.0254`，后盖 `x=(61+sx)/0.0254, y=(42-sy)/0.0254`。

生成器只产生图案，不创建或修改孔槽、原生板框、电路、铜层和原版工程。孔槽沿用已有审核几何，后盖开窗为原物理孔槽外 nominal 0.20 mm；普通丝印再让开开窗 nominal 0.16 mm，导出 mil 多边形重建后的最小间距约 0.159914 mm。

## 与原彩印图的差别

动物来自当前 `front-*-37mm.svg` 的嵌入 single-ink PNG，并核对与已有批准 PNG 字节完全一致。本目录 `source-*-single-ink.png` 是相同源字节的副本。使用 alpha≥128、0.02 mm 保拓扑简化，去除面积小于 0.04 mm² 的微点/微洞；没有形态学整体加粗或腐蚀。保留马的 6 个、蛇的 5 个主要白色主体及蛇的 12 处主要负形。

原后盖极细 serif 文字改为同文字、同基线的 DejaVu Sans Bold 1.7 mm 原生填充轮廓；白色边线不小于 0.22 mm，原星孔中心外补可见 0.22 mm 白环。动物锐尖局部仍可小于 0.15 mm，需供应商 CAM 确认，不能据此声称全图都达到最小线宽。

SVG 与 PNG 从最终送出的丝印/开窗多边形绘制；棕色仅表示去绿油后露出的基材，透明区域表示实际孔槽。预览为设计示意，不是样件照片。每款 JSON 记录原 SVG/物理几何 SHA-256、源 PNG、字型、处理参数、坐标映射与导出重建校验；`manifest.json` 对本目录交付文件记录大小和 SHA-256。

重生成：`python -X utf8 hardware/nfc-talisman/scripts/build_standard_layer_artwork.py`。需 NumPy、Pillow、OpenCV、Shapely 与 Matplotlib，版本记入 JSON。原彩印图案及原版工程保持独立。
