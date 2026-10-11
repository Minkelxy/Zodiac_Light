"""Import byte-exact cover candidates as locked 37 mm EasyEDA color objects."""
import base64
import hashlib
import json
from pathlib import Path
from bridge import execute

ROOT=Path(__file__).resolve().parents[1]
audit=json.loads((ROOT/'manufacturing/draft/star-face-audit.json').read_text(encoding='utf-8'))
old_silk=[s['native_id'] for s in audit['native_source']['silkscreen_art_matches']]
targets=[]
for variant,uuid,animal,sign in [('horse-sagittarius','4a4719695b24dc2b','horse','sagittarius'),('snake-leo','fe8ee4534ee0b941','snake','leo')]:
    images=[]
    folder=ROOT/'variants'/variant/'artwork'
    manifest=json.loads((folder/'manifest.json').read_text(encoding='utf-8'))
    for side,word,left,top in [('front',animal,2,95),('rear',sign,61,42)]:
        path=folder/(side+'-'+word+'-37mm.png')
        raw=path.read_bytes()
        assert hashlib.sha256(raw).hexdigest()==manifest['files'][path.name]['sha256']
        images.append({'side':side,'name':path.name,'x_mm':left,'y_mm':top,'sha256':hashlib.sha256(raw).hexdigest(),
                       'binary':'data:image/png;base64,'+base64.b64encode(raw).decode()})
    targets.append({'variant':variant,'uuid':uuid,'old_silk':old_silk if animal=='horse' else [],'images':images})
code=r"""
const TARGETS=__TARGETS__,PROJECT='c051e4069a83472198ecce7729fbd257',EPCB_LayerId={TOP_SILKSCREEN:3},MM=1/0.0254;
const backups=[],changes=[];
function parse(s){return s.split(/\r?\n/).filter(v=>v.includes('||')).map(v=>{const i=v.indexOf('||');return [JSON.parse(v.slice(0,i)),JSON.parse(v.slice(i+2).replace(/\|+$/,''))];});}
const stable=v=>Array.isArray(v)?v.map(stable):(v&&typeof v==='object'?Object.fromEntries(Object.keys(v).sort().map(k=>[k,stable(v[k])])):v);
const primitiveTypes=new Set(['LINE','VIA','FILL','COMPONENT','ATTR','PAD_NET','PAD','POLY','STRING','OBJ']);
const signature=(rows,exclude)=>rows.filter(r=>primitiveTypes.has(r[0].type)&&!exclude.has(r[0].id)).map(r=>JSON.stringify([r[0].type,r[0].id,stable(r[1])])).sort().join('\n');
try{
 for(const t of TARGETS){
  await eda.dmt_EditorControl.openDocument(t.uuid);
  const doc=await eda.dmt_SelectControl.getCurrentDocumentInfo();
  if(doc?.uuid!==t.uuid||doc.parentProjectUuid!==PROJECT)throw Error('Wrong artwork target');
  const objects=await eda.pcb_PrimitiveObject.getAll(),polys=await eda.pcb_PrimitivePolyline.getAll();
  if(objects.length!==1||objects[0].getState_FileName()!=='sagittarius-color-print-candidate.png'||objects[0].getState_Layer()!==EPCB_LayerId.TOP_SILKSCREEN)throw Error('Unexpected artwork; preserve user changes');
  if(polys.filter(p=>p.getState_Layer()===EPCB_LayerId.TOP_SILKSCREEN).length!==t.old_silk.length||t.old_silk.some(id=>!polys.some(p=>p.getState_PrimitiveId()===id)))throw Error('Unexpected managed vector art');
  const source=await eda.sys_FileManager.getDocumentSource();
  const removed=new Set([objects[0].getState_PrimitiveId(),...t.old_silk]),protectedBefore=signature(parse(source),removed);
  backups.push({uuid:t.uuid,source});
  if(t.old_silk.length&&!await eda.pcb_PrimitivePolyline.delete(t.old_silk))throw Error('Remove old vector art failed');
  if(!await eda.pcb_PrimitiveObject.delete(objects))throw Error('Remove old embedded art failed');
  const created=[];
  for(const im of t.images){
   const obj=await eda.pcb_PrimitiveObject.create(EPCB_LayerId.TOP_SILKSCREEN,im.x_mm*MM,im.y_mm*MM,im.binary,37*MM,37*MM,0,false,im.name,true);
   if(!obj)throw Error('Import new cover failed '+im.name);
   created.push({side:im.side,id:obj.getState_PrimitiveId(),fileName:im.name,inputSha256:im.sha256});
  }
  if(!await eda.pcb_Document.save())throw Error('Save artwork failed');
  if(!await eda.dmt_EditorControl.closeDocument(doc.tabId))throw Error('Close artwork failed');
  await eda.dmt_EditorControl.openDocument(t.uuid);await new Promise(r=>setTimeout(r,500));
  const sourceAfter=await eda.sys_FileManager.getDocumentSource(),exclude=new Set([...removed,...created.map(v=>v.id)]);
  if(signature(parse(sourceAfter),exclude)!==protectedBefore)throw Error('Protected geometry changed during artwork import');
  const actual=(await eda.pcb_PrimitiveObject.getAll()).map(o=>({id:o.getState_PrimitiveId(),fileName:o.getState_FileName(),layer:o.getState_Layer(),x:o.getState_TopLeftX(),y:o.getState_TopLeftY(),width:o.getState_Width(),height:o.getState_Height(),mirror:o.getState_Mirror(),rotation:o.getState_Rotation(),blob:o.getState_BinaryData()}));
  if(actual.length!==2||actual.some(o=>Math.abs(o.width-37*MM)>.002||Math.abs(o.height-37*MM)>.002||o.mirror||o.rotation!==0))throw Error('Cover state verification');
  const drc=await eda.pcb_Drc.check(true,false,true);
  if(!Array.isArray(drc)||drc.length)throw Error('Art panel DRC failed '+JSON.stringify(drc));
  changes.push({variant:t.variant,uuid:t.uuid,status:'covers_integrated_saved_reopened',protectedGeometryUnchanged:true,created,actual,drc,sourceAfter});
 }
 return {status:'two_variants_cover_candidates_integrated',changes};
}catch(error){
 const rollback=[];
 for(const b of backups.reverse()){
  await eda.dmt_EditorControl.openDocument(b.uuid);
  rollback.push({uuid:b.uuid,restored:await eda.sys_FileManager.setDocumentSource(b.source),saved:await eda.pcb_Document.save()});
 }
 return {status:'failed_rolled_back',error:String(error),rollback};
}
""".replace('__TARGETS__',json.dumps(targets,separators=(',',':')))
r=execute(code,'55-integrate-two-variant-cover-artwork')
v=r.get('result',{})
if r.get('success') and v.get('status')=='two_variants_cover_candidates_integrated':
    for item in v['changes']:
        stem=item['variant']+'-panel'
        (ROOT/'variants/common/eda/native'/(stem+'-source.jsonl')).write_text(item['sourceAfter'],encoding='utf-8',newline='\n')
        summary={k:x for k,x in item.items() if k!='sourceAfter'}
        (ROOT/'variants'/item['variant']/'artwork-eda-integration.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    summary={'status':v['status'],'changes':[{k:x for k,x in item.items() if k!='sourceAfter'} for item in v['changes']]}
else:summary=v or r
print(json.dumps(summary,ensure_ascii=False))
if v.get('status')!='two_variants_cover_candidates_integrated':raise SystemExit(1)
