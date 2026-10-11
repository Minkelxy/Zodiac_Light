"""Build assembly review tables from fresh exports, excluding CT2 and optional LEDs."""
import csv
import hashlib
import io
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
COMMON=ROOT/'variants/common'
raw=json.loads((COMMON/'eda/native/core-netlist.json').read_text(encoding='utf-8'))
net=json.loads(raw[0] if isinstance(raw,list) else raw) if not isinstance(raw,dict) else raw
profiles=json.loads((ROOT/'manufacturing/draft/assembly-variants.json').read_text(encoding='utf-8'))['variants']
rows=[]
for ref in sorted(net['components']):
    props=net['components'][ref]['props']
    rows.append({'Designator':ref,'Value':props.get('Value',''),'Manufacturer Part':props.get('Manufacturer Part',''),
                 'Supplier Part':props.get('Supplier Part',''),'Footprint':props.get('FootprintName',''),
                 'Population':props.get('Population',''),'Sourcing': 'HOLD - existing NRND Murata; alternate needs fit review' if ref=='C1' else ('DNP - tuning placeholder, never procure' if ref=='CT2' else 'Designated; stock not rechecked'),
                 'Quantity':1})
def write(path,fields,data):
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(data)
fields=list(rows[0])
written=[]
for variant in ['horse-sagittarius','snake-leo']:
    out=ROOT/'variants'/variant/'manufacturing-draft'
    pnp=list(csv.DictReader(io.StringIO((out/'pnp-all.csv').read_text(encoding='utf-8-sig')),delimiter='\t'))
    assert len(pnp)==15 and {r['Designator'] for r in pnp}=={r['Designator'] for r in rows}
    for name,profile in profiles.items():
        fit=set(profile['fit_designators'])
        bom_rows=[r for r in rows if r['Designator'] in fit]
        pnp_rows=[r for r in pnp if r['Designator'] in fit]
        assert len(bom_rows)==len(pnp_rows)==profile['fit_count']
        assert 'CT2' not in fit and all(r['Manufacturer Part'] for r in bom_rows)
        bom=out/(name+'-bom-review.csv');coords=out/(name+'-pnp-review.csv')
        write(bom,fields,bom_rows);write(coords,list(pnp[0]),pnp_rows)
        written.extend([bom,coords])
    readme=out/'README.md'
    readme.write_text('''# 独立拼板制造草稿

本目录是本轮保存、重开后从嘉立创EDA导出的独立100×100 mm拼板；仅用于设计/CAM审阅，未送厂或下单。

`*-gerber.zip` 内含铜、阻焊、丝印、板框、PTH/NPTH钻孔和嘉立创EDA彩色丝印文件。彩印对象的对位、透明孔槽和印刷/白阻焊叠印效果仍需CAM复核；彩印外观不能由普通黑白Gerber代替。

`bom-all.csv` / `pnp-all.csv` 是原始API输出（扩展名为csv，实际为制表符分隔），含15个footprint和CT2库占位。不要直接用它们采购或贴装。

`four-led-*-review.csv` 是14个拟装器件；`two-led-*-review.csv` 是12个拟装器件，D2/D4不装，R2/R4保留。两者都排除CT2。坐标保持原生未镜像的拼板数据，单位mm，原点在左下；Bottom器件旋转值保持导出值。D1/D3=(44,50)、D2/D4=(56,50)mm。

C1保留原生Murata GRM155R71C154KA12D/C162182并明确采购HOLD；候选CCTC尚未完成适配评审，不能把它加成第二颗150nF。CT1的47pF是调谐起始值。最终装配、RF和手机读写结果以实际样件为准。

详见共同的原生工程、`export-manifest.json`、铜连接和盖板几何审计。\n''',encoding='utf-8')
    written.append(readme)
summary={'status':'assembly_review_tables_prepared','releaseStatus':'HOLD_C1_CAM_PHYSICAL_VALIDATION',
         'source': 'variants/common/eda/native/core-netlist.json','coordinate_convention':'native unmirrored panel mm, lower-left origin, bottom rotations as exported',
         'profiles':profiles,'files':{str(p.relative_to(ROOT)):{'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'size':p.stat().st_size} for p in written}}
(COMMON/'assembly-review-manifest.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'status':summary['status'],'fourLedFit':14,'twoLedFit':12,'fileCount':len(written)}))
