import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
r = json.loads((root/'eda/logs/46-organize-schematic.json').read_text(encoding='utf-8'))['result']
assert r['status'] == 'applied_saved_reopened' and r['netlistContractUnchanged']
style_path=root/'eda/logs/47-clean-schematic-appearance.json'
if style_path.exists():
    style=json.loads(style_path.read_text(encoding='utf-8'))['result']
    assert style['status']=='applied_saved_reopened' and style['netlistContractUnchanged']
    r.update(style)
(root/'eda/schematic-review.svg').write_text(r['svg'],encoding='utf-8',newline='\n')
(root/'eda/layout-review-v3.json').write_text(json.dumps({k:r[k] for k in ['status','netlistContractUnchanged','positions','pins','erc']},ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps({'status':r['status'],'erc':r['erc'],'svg_prefix':r['svg'][:100],'svg_bytes':len(r['svg'].encode())},ensure_ascii=False))
