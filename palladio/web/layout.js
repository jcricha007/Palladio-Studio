export class LayoutTools {
  constructor(find,hooks) {
    this.find=find;this.hooks=hooks;this.ids=[];this.key=null;
    find('layout-include').addEventListener('click',()=>{
      const id=hooks.state().selected;if(id&&!this.ids.includes(id))this.ids.push(id);hooks.invalidate();this.render();
    });
    find('layout-clear').addEventListener('click',()=>{this.ids=[];hooks.invalidate();this.render();});
    find('layout-form').addEventListener('input',hooks.invalidate);
    find('layout-form').addEventListener('change',hooks.invalidate);
    find('layout-form').addEventListener('submit',event=>{
      event.preventDefault();hooks.preview([{action:'layout',layout:{ids:this.ids.slice(),operation:find('layout-operation').value,
        offset:['x','y','z'].map(a=>Number(find('layout-'+a).value)),axis:find('layout-axis').value,
        angle:Number(find('layout-angle').value),spacing_m:Number(find('layout-spacing').value)}}]);
    });
    find('layout-measure').addEventListener('click',()=>hooks.run(async()=>{
      const {project}=hooks.state();const result=await hooks.api('/api/properties/'+project.id+'/measure',{revision:project.revision,ids:this.ids});
      find('layout-measurement').textContent=`${result.objects} objects · ${result.parts} parts · world extents ${result.size.map(n=>n.toFixed(3)).join(' × ')} m`+
        (result.origin_distance_m===null?'':` · origin distance ${result.origin_distance_m.toFixed(3)} m`);
    }));
  }
  render() {
    const {project}=this.hooks.state();if(this.key!==project?.id){this.ids=[];this.key=project?.id;}
    this.ids=this.ids.filter(id=>project?.scene.elements.some(e=>e.id===id));
    this.find('layout-selection').textContent=this.ids.map(id=>project.scene.elements.find(e=>e.id===id).name).join(' · ')||'Select parts and add them to the set. Linked parts resolve to one whole assembly.';
    this.find('layout-measurement').textContent='';this.sync();
  }
  sync() {
    const {busy,project,baselineView,selected}=this.hooks.state();const disabled=busy||!project||baselineView;
    for(const node of this.find('layout-form').querySelectorAll('input,select,button'))node.disabled=disabled;
    for(const id of ['layout-preview','layout-measure','layout-clear'])this.find(id).disabled=disabled||!this.ids.length;
    this.find('layout-include').disabled=disabled||!selected;
  }
}
