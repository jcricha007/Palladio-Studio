export function download(name,content,type='application/json') {
  const url=URL.createObjectURL(new Blob([content],{type}));
  const link=document.createElement('a');link.href=url;link.download=name;link.click();
  setTimeout(()=>URL.revokeObjectURL(url),1000);
}
export class TransferTools {
  constructor(find,hooks) {
    this.find=find;this.hooks=hooks;
    find('property-export').addEventListener('click',()=>hooks.run(async()=>{
      const packet=await hooks.api('/api/properties/'+hooks.state().project.id+'/export');
      download('palladio-property-r'+packet.source_revision+'.json',JSON.stringify(packet));
    }));
    find('property-import').addEventListener('change',()=>hooks.run(async()=>{
      const file=find('property-import').files[0];if(!file)return;
      if(file.size>20000000)throw new Error('Choose a property snapshot up to 20 MB.');
      let packet;try{packet=JSON.parse(await file.text());}catch{throw new Error('This file is not valid JSON.');}
      const project=await hooks.api('/api/properties/import',{packet});
      hooks.open(project,true);await hooks.reloadLibrary();find('property-import').value='';
    }));
  }
  sync() {
    const {busy,project}=this.hooks.state();
    this.find('property-export').disabled=busy||!project;this.find('property-import').disabled=busy;
  }
}
