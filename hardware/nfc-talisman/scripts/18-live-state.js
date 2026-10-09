const project = await eda.dmt_Project.getCurrentProjectInfo();
const document = await eda.dmt_SelectControl.getCurrentDocumentInfo();
return {project, document};
