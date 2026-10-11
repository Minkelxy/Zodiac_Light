const project=await eda.dmt_Project.getCurrentProjectInfo();
const current=await eda.dmt_SelectControl.getCurrentDocumentInfo();
const pcbs=await eda.dmt_Pcb.getAllPcbsInfo();
return {project,current,pcbs};
