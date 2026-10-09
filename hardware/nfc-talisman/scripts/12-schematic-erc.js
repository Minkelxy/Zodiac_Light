await eda.dmt_EditorControl.openDocument('293c7786afd689e8');await new Promise(r=>setTimeout(r,500));const errors=await eda.sch_Drc.check(true,false,true);return {errors};
