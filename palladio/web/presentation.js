import {download} from './transfer.js';
export class PresentationTools {
  constructor(find,hooks) {
    this.find=find;this.hooks=hooks;this.key='';
    for(const action of ['save','update'])find('view-'+action).addEventListener('click',()=>{
      const {viewport}=hooks.state();if(!viewport)return;
      hooks.preview([{action:'view_'+action,id:find('view-list').value,name:find('view-name').value,camera:viewport.captureCamera()}]);
    });
    find('view-remove').addEventListener('click',()=>hooks.preview([{action:'view_remove',id:find('view-list').value}]));
    find('view-open').addEventListener('click',()=>{const view=this.chosen();if(view){hooks.state().viewport?.applyCamera(view.camera);find('view-fov').value=view.camera.fov_degrees??45;}});
    find('view-fov').addEventListener('change',()=>hooks.run(async()=>{
      hooks.state().viewport?.setFieldOfView(Number(find('view-fov').value));hooks.invalidate();
    }));
    find('view-list').addEventListener('change',()=>{const view=this.chosen();if(view)find('view-name').value=view.name;hooks.invalidate();this.sync();});
    find('view-name').addEventListener('input',hooks.invalidate);
    find('view-png').addEventListener('click',()=>hooks.run(async()=>{
      const {project,viewport}=hooks.state();const blob=await viewport.capturePng();download('palladio-r'+project.revision+'.png',blob,'image/png');
    }));
    find('view-obj').addEventListener('click',()=>hooks.run(async()=>{
      const {project}=hooks.state();const result=await hooks.api('/api/properties/'+project.id+'/geometry-export',{revision:project.revision,terrain:find('view-terrain').checked});
      download('palladio-r'+result.revision+'.obj',result.obj,'text/plain');find('view-status').textContent='Exported '+result.triangles+' triangles in metres, Y up.';
    }));
  }
  chosen(){return this.hooks.state().project?.scene.views?.find(v=>v.id===this.find('view-list').value);}
  render(){
    const {project}=this.hooks.state(),key=[project?.id,project?.revision].join('|');if(key===this.key)return;this.key=key;
    this.find('view-fov').value=this.hooks.state().viewport?.captureCamera?.().fov_degrees??45;
    const list=this.find('view-list'),previous=list.value,views=project?.scene.views||[];list.replaceChildren(...views.map(v=>new Option(v.name,v.id)));
    if(views.some(v=>v.id===previous))list.value=previous;
  }
  sync(){
    const {project,viewport,busy,baselineView}=this.hooks.state(),disabled=busy||!project||baselineView;
    for(const node of this.find('presentation-panel').querySelectorAll('input,select,button'))node.disabled=disabled;
    for(const id of ['view-save','view-png','view-fov'])this.find(id).disabled=disabled||!viewport;
    for(const id of ['view-update','view-open'])this.find(id).disabled=disabled||!viewport||!this.chosen();
    this.find('view-remove').disabled=disabled||!this.chosen();
  }
}
