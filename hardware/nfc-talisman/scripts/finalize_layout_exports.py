import json
from pathlib import Path
from bridge import execute

root=Path(__file__).resolve().parents[1]
steps=['24-schematic-erc-current','25-core-pcb-drc-current','26-panel-pcb-drc-current','49-core-pad-snapshot','30-native-connectivity-snapshot','31-export-native-project','38-export-manufacturing-draft']
for name in steps:
    r=execute((root/'scripts'/f'{name}.js').read_text(encoding='utf-8-sig'),name)
    if not r.get('success'):raise RuntimeError(f'{name}: {r.get("error")}')
    v=r['result']
    if name.startswith('24-'):
        if any(x.get('type')=='error' for x in v['errors']):raise RuntimeError('Schematic ERC errors')
    if name.startswith(('25-','26-')) and v.get('errors',v.get('drc',[])):raise RuntimeError('PCB DRC findings')
    if name=='49-core-pad-snapshot':
        (root/'eda/core-pads.json').write_text(json.dumps(v['pads'],ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'step':name,'success':True,'size':v.get('size'),'rawCount':v.get('rawCount')},ensure_ascii=False),flush=True)
