const PROJECT='c051e4069a83472198ecce7729fbd257';
const file=await eda.sys_FileManager.getProjectFileByProjectUuid(PROJECT,'nfc-talisman-draft',undefined,'epro2');
if(!file||file.size===0)throw Error('Native project export unavailable');
const bytes=new Uint8Array(await file.arrayBuffer());
let binary='';
for(let offset=0;offset<bytes.length;offset+=16384)binary+=String.fromCharCode(...bytes.subarray(offset,offset+16384));
return {project:PROJECT,name:file.name,size:file.size,base64:btoa(binary)};
