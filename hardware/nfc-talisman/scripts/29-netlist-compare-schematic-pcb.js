const PROJECT='c051e4069a83472198ecce7729fbd257';
const SCHEMATIC='293c7786afd689e8';
const CORE='eb14b9eaec4f920c';
const differences=await eda.sys_Tool.netlistComparison(
  SCHEMATIC,
  CORE
);
return {project:PROJECT,schematic:SCHEMATIC,pcb:CORE,differences};
