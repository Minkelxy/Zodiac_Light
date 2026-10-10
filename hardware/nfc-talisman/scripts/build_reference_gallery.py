"""Build an offline catalogue without modifying the downloaded images."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import html
import json
import zipfile
from html.parser import HTMLParser
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1] / 'artwork' / 'reference-collection'


def esc(value):
    return html.escape(str(value), quote=True)


def link(path, label):
    return f'<a href="{esc(path)}">{esc(label)}</a>'


class LocalLinks(HTMLParser):
    def __init__(self):
        super().__init__()
        self.paths = set()

    def handle_starttag(self, tag, attrs):
        for key, value in attrs:
            if key in ('href', 'src', 'data-original', 'data-pattern') and value:
                parsed = urlsplit(value)
                if not parsed.scheme and not parsed.netloc and parsed.path:
                    self.paths.add(unquote(parsed.path))


def main():
    talisman = json.loads((ROOT / 'source-talisman/source_manifest.json').read_text(encoding='utf-8-sig'))
    zodiac = json.loads((ROOT / 'zodiac-modern/manifest.json').read_text(encoding='utf-8-sig'))
    assert len(talisman['files']) == 12
    main_charts = [c for c in zodiac['charts'] if len(c['id']) == 3]
    assert len(main_charts) == 12
    pattern_file = ROOT / 'talisman-patterns/manifest.json'
    patterns = {}
    if pattern_file.is_file():
        pattern_manifest = json.loads(pattern_file.read_text(encoding='utf-8-sig'))
        patterns = {item['id']: item for item in pattern_manifest['files']}
        assert set(patterns) == {item['id'] for item in talisman['files']}
    fronts = []
    for item in talisman['files']:
        path = item.get('path') or item.get('local_path')
        if not item.get('downloaded') or not path:
            raise ValueError('Talisman image missing: ' + item['id'])
        actual = ROOT / path
        if not actual.is_file():
            raise FileNotFoundError(actual)
        if hashlib.sha256(actual.read_bytes()).hexdigest() != item['sha256']:
            raise ValueError('Talisman bytes changed: ' + item['id'])
        dims = item.get('dimensions')
        if isinstance(dims, dict):
            dims = [dims.get('width'), dims.get('height')]
        caption = f"{dims[0]} × {dims[1]} px" if dims else '原始尺寸'
        if patterns:
            pattern = patterns[item['id']]
            pattern_path = pattern['path']
            raw = (ROOT / pattern_path).read_bytes()
            if hashlib.sha256(raw).hexdigest() != pattern['output_sha256']:
                raise ValueError('Pattern bytes changed: ' + item['id'])
            fronts.append(f'''<article class="card pattern-card" data-original="{esc(path)}" data-pattern="{esc(pattern_path)}" data-caption="{esc(caption)}" data-name="{esc(item['animal_zh'])}">
<a class="image talisman-pattern" href="{esc(pattern_path)}"><img src="{esc(pattern_path)}" alt="{esc(item['animal_zh'])}透明动物图案" loading="lazy"></a>
<h3>{esc(item['animal_zh'])} · {esc(item['animal_en'])}</h3><p class="image-caption">透明 PNG · 独立动物图案</p>
<div class="links">{link(pattern_path, '透明图案 PNG')} {link(path, '完整符咒 PNG')} {link(item['file_page'], '图源页面')}</div></article>''')
            continue
        fronts.append(f'''<article class="card">
<a class="image talisman" href="{esc(path)}"><img src="{esc(path)}" alt="{esc(item['animal_zh'])}符咒正面" loading="lazy"></a>
<h3>{esc(item['animal_zh'])} · {esc(item['animal_en'])}</h3><p>{esc(caption)} · 保留源图字节</p>
<div class="links">{link(path, 'PNG 原图')} {link(item['file_page'], '图源页面')}</div></article>''')
    charts = []
    for item in main_charts:
        base = 'zodiac-modern/'
        for key in ('svg', 'png', 'import_svg'):
            if not (ROOT / base / item[key]).is_file():
                raise FileNotFoundError(item[key])
        iau_base = f"source-zodiac/iau-sky-and-telescope/{item['id']}"
        charts.append(f'''<article class="card">
<a class="image" href="{esc(base + item['svg'])}"><img src="{esc(base + item['png'])}" alt="{esc(item['chinese'])}现代点线星图" loading="lazy"></a>
<h3>{esc(item['chinese'])} · {esc(item['english'])}</h3><p>{item['star_count']} 星 · {item['edge_count']} 连线</p>
<div class="links">{link(base + item['png'], 'PNG')} {link(base + item['svg'], '深色 SVG')} {link(base + item['import_svg'], '透明线稿 SVG')} {link(iau_base + '.gif', 'IAU 对照图')} {link(iau_base + '.pdf', 'IAU PDF')}</div></article>''')
    body = '''<!doctype html><html lang="zh-CN"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>十二符咒与十二星座 · 素材索引</title>
<style>
:root{color-scheme:dark;font:16px/1.65 system-ui,"Microsoft YaHei",sans-serif;background:#101419;color:#e4e8ee}
body{margin:0}main{max-width:1440px;margin:auto;padding:40px 24px}h1{font-size:clamp(26px,3vw,42px);margin:0 0 12px}h2{margin:44px 0 10px}
p{color:#adb8c6;margin:5px 0 16px}a{color:#bbd6ff;text-decoration:none}a:hover{text-decoration:underline}nav,.links{display:flex;flex-wrap:wrap;gap:8px 14px}
nav a,.links a{padding:3px 8px;border:1px solid #384454;border-radius:6px;font-size:14px}.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:18px}
.card{border:1px solid #2c3644;border-radius:12px;overflow:hidden;background:#1a2029;padding:0 0 16px}.card h3,.card p,.card .links{margin-left:16px;margin-right:16px}.card h3{font-size:18px;margin-top:13px;margin-bottom:4px}.card p{font-size:13px}
.image{display:block;aspect-ratio:1;background:#0b1018}.image img{display:block;width:100%;height:100%;object-fit:contain}.talisman{background:#c2c7cc}
.talisman-pattern{background-color:#eee;background-image:conic-gradient(#ddd 25%,transparent 0 50%,#ddd 0 75%,transparent 0);background-size:24px 24px}
.mode-switch{display:flex;gap:10px;margin:18px 0}button{font:inherit;color:#bbd6ff;background:#1a2029;border:1px solid #384454;border-radius:6px;padding:6px 12px;cursor:pointer}button[aria-pressed="true"]{color:#101419;background:#bbd6ff;border-color:#bbd6ff}
.note{border-left:3px solid #bacfe9;padding:12px 18px;background:#1a2029;max-width:1100px}footer{margin-top:36px;border-top:1px solid #384454;padding-top:18px}
</style><main><h1>十二符咒与十二星座</h1><p>本地参考素材 · 点击图片查看原尺寸 · 图片与 SVG 可逐项下载</p>
<nav><a href="#talismans">十二符咒</a><a href="#zodiac">十二星座</a><a href="#sagittarius">射手座八星</a><a href="README.md">说明与来源</a><a href="../reference-collection.zip">完整 ZIP</a></nav>
<h2 id="talismans">十二符咒正面</h2><p>PNG 保留源文件，不改色、不镜像、不重画。来源图库中的插画用于核对动物轮廓、灰石底座和配色；动画不同镜头也可能存在画法差异。</p><div class="grid">'''
    if patterns:
        body = body.replace('<h2 id="talismans">十二符咒正面</h2><p>PNG 保留源文件，不改色、不镜像、不重画。来源图库中的插画用于核对动物轮廓、灰石底座和配色；动画不同镜头也可能存在画法差异。</p><div class="grid">',
                            '<h2 id="talismans">十二符咒 · 独立动物图案</h2><p>新增透明 PNG 去掉石质底座和边框；可切换完整符咒作对照。棋盘格只用于显示透明区域，不在图片里。</p><div class="mode-switch" role="group" aria-label="符咒图片显示方式"><button type="button" data-mode="pattern" aria-pressed="true">透明图案</button><button type="button" data-mode="original" aria-pressed="false">完整符咒</button></div><div class="grid">')
    body += '\n'.join(fronts) + '</div><h2 id="zodiac">十二星座 · Stellarium Modern</h2>'
    body += '<p>暗底浅线预览；透明 SVG 只含星点与连线。北上、东左，按实际星位等比投影。IAU / Sky &amp; Telescope 原星图作为另一种画法对照。</p><div class="grid">'
    body += '\n'.join(charts) + '</div><h2 id="sagittarius">射手座八星茶壶</h2>'
    extra_pngs = list((ROOT / 'zodiac-modern').rglob('*teapot*dark.png'))
    if extra_pngs:
        extra_png = extra_pngs[0].relative_to(ROOT).as_posix()
        extra_svg = extra_png.removesuffix('.png') + '.svg'
        body += f'<div class="card" style="max-width:430px"><a class="image" href="{esc(extra_svg)}"><img src="{esc(extra_png)}" alt="射手座八星茶壶"></a><h3>现有 PCB 选用方案</h3><p>8 星、11 连线；它是射手座中的局部星群。此参考没有修改当前 PCB 的孔槽。</p><div class="links">{link(extra_png,"PNG")} {link(extra_svg,"SVG")}</div></div>'
    else:
        body += '<p>现有项目保留八星、十一连线方案。参见 <a href="../sagittarius-face-review.png">当前 PCB 图案预览</a>。</p>'
    body += '''<footer><div class="note">IAU 标准化的是星座区域与边界，连线没有唯一官方画法。Stellarium 连线数据署名按 CC BY-SA 4.0；Hipparcos 星位 Credit: ESA，目录许可 CC BY-NC 3.0 IGO；IAU/S&amp;T 图为 CC BY 4.0。符咒图像权利未据图库文本许可推定。本集合用于本地设计参考，具体出处见各清单。</div></footer></main></html>'''
    if patterns:
        body = body.replace('</main></html>', '''</main><script>
document.querySelectorAll('[data-mode]').forEach(button=>button.addEventListener('click',()=>{
  const showPattern=button.dataset.mode==='pattern';
  document.querySelectorAll('[data-mode]').forEach(control=>control.setAttribute('aria-pressed',String(control===button)));
  document.querySelectorAll('.pattern-card').forEach(card=>{
    const anchor=card.querySelector('.image'), img=anchor.querySelector('img');
    const path=showPattern?card.dataset.pattern:card.dataset.original;
    anchor.href=path;img.src=path;img.alt=card.dataset.name+(showPattern?'透明动物图案':'完整符咒正面');
    anchor.classList.toggle('talisman-pattern',showPattern);anchor.classList.toggle('talisman',!showPattern);
    card.querySelector('.image-caption').textContent=showPattern?'透明 PNG · 独立动物图案':card.dataset.caption+' · 保留源图字节';
  });
}));
</script></html>''')
    (ROOT / 'index.html').write_bytes(body.encode('utf-8'))
    rows = []
    for path in sorted(ROOT.rglob('*')):
        if path.is_file() and path.name != 'collection-manifest.json':
            data = path.read_bytes()
            rows.append({'path':path.relative_to(ROOT).as_posix(),'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()})
    report = {'generated_utc':datetime.now(timezone.utc).isoformat(),'talisman_png_count':12,'talisman_pattern_png_count':len(patterns),'zodiac_main_chart_count':12,'files':rows}
    (ROOT / 'collection-manifest.json').write_bytes((json.dumps(report,ensure_ascii=False,indent=2)+'\n').encode('utf-8'))
    target = ROOT.parent / 'reference-collection.zip'
    with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED) as bundle:
        for path in sorted(ROOT.rglob('*')):
            if path.is_file():
                bundle.write(path, path.relative_to(ROOT).as_posix())
    with zipfile.ZipFile(target) as bundle:
        assert bundle.testzip() is None
        local_files = {p.relative_to(ROOT).as_posix(): p for p in ROOT.rglob('*') if p.is_file()}
        assert set(bundle.namelist()) == set(local_files)
        for name, path in local_files.items():
            if bundle.read(name) != path.read_bytes():
                raise ValueError('ZIP bytes differ: ' + name)
    links = LocalLinks()
    links.feed(body)
    for relative in links.paths:
        if not (ROOT / relative).is_file():
            raise FileNotFoundError('Broken gallery link: ' + relative)
    print(json.dumps({'gallery':str(ROOT/'index.html'),'files':len(rows)+1,
                      'talisman_patterns':len(patterns),'local_links_checked':len(links.paths),
                      'zip_matches_disk':True,'zip_bytes':target.stat().st_size},ensure_ascii=False))


if __name__ == '__main__':
    main()
