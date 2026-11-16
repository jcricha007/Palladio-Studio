import {download} from './transfer.js';
export class DiagnosticsTools {
  constructor(find,hooks){
    this.find=find;this.hooks=hooks;
    find('diagnostics-refresh').addEventListener('click',()=>hooks.run(async()=>{
      const report=await hooks.api('/api/health');this.report=report;
      find('diagnostics-result').textContent='Build '+report.build.slice(0,12)+'\nPython '+report.python+' · database schema '+report.database_schema+'\nLibrary: '+report.library_path;
      this.sync();
    }));
    find('diagnostics-download').addEventListener('click',()=>{if(this.report)download('palladio-diagnostics.json',JSON.stringify(this.report,null,2));});
  }
  sync(){this.find('diagnostics-refresh').disabled=this.hooks.state().busy;this.find('diagnostics-download').disabled=this.hooks.state().busy||!this.report;}
}
