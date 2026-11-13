export class AssetTools {
  constructor(find, hooks) {
    this.find=find;this.hooks=hooks;this.items=[];this.key='';
    find('asset-refresh').addEventListener('click',()=>hooks.run(()=>this.refresh()));
    find('asset-import-form').addEventListener('submit',event=>{event.preventDefault();hooks.run(async()=>{
      const file=find('asset-file').files[0];
      if(!file||file.size>750000)throw new Error('Choose an OBJ or asset JSON file up to 750 KB.');
      const item=await hooks.api('/api/assets/import',{name:find('asset-name').value,format:file.name.toLowerCase().endsWith('.obj')?'obj':'palladio',data:await file.text(),units:find('asset-units').value});
      await this.refresh(item.id);find('asset-status').textContent='Asset saved locally. Preview placement to add it to a property.';
    });});
    find('asset-capture').addEventListener('click',()=>hooks.run(async()=>{
      const {project,selected}=hooks.state();
      const item=await hooks.api('/api/properties/'+project.id+'/asset-capture',{revision:project.revision,selection:selected,name:find('asset-name').value});
      await this.refresh(item.id);find('asset-status').textContent='Captured the selected object or its owning assembly as a reusable mesh.';
    }));
    find('asset-place').addEventListener('click',()=>hooks.run(async()=>{
      const {project}=hooks.state();
      const plan=await hooks.api('/api/properties/'+project.id+'/asset-preview',{revision:project.revision,asset_id:find('asset-list').value,position:['x','y','z'].map(a=>Number(find('asset-'+a).value)),yaw:Number(find('asset-yaw').value)});
      if(hooks.state().project?.id!==project.id||hooks.state().project.revision!==plan.revision)throw new Error('Property changed. Preview again.');
      hooks.showPlan(plan);
    }));
    find('asset-export').addEventListener('click',()=>hooks.run(async()=>{
      const packet=await hooks.api('/api/assets/'+find('asset-list').value);
      const url=URL.createObjectURL(new Blob([JSON.stringify(packet,null,2)],{type:'application/json'}));
      const link=document.createElement('a');link.href=url;link.download='palladio-asset-'+packet.id.slice(0,8)+'.json';link.click();
      setTimeout(()=>URL.revokeObjectURL(url),1000);
    }));
    find('finish-form').addEventListener('submit',event=>{
      event.preventDefault();const {selected}=hooks.state();if(!selected)return;
      hooks.preview([{action:'update',id:selected,element:{finish:{color:find('finish-color').value,pattern:find('finish-pattern').value,scale_m:Number(find('finish-scale').value),rotation:Number(find('finish-rotation').value),source_colors:find('finish-source').checked}}}]);
    });
    find('finish-reset').addEventListener('click',()=>{const {selected}=hooks.state();if(selected)hooks.preview([{action:'update',id:selected,element:{finish:null}}]);});
    for(const form of ['asset-import-form','asset-placement','finish-form'])for(const event of ['input','change'])find(form).addEventListener(event,hooks.invalidate);
  }
  async refresh(preferred) {
    this.items=await this.hooks.api('/api/assets');
    const select=this.find('asset-list'), previous=preferred||select.value;
    select.replaceChildren(...this.items.map(item=>new Option(item.name+' · '+item.triangles+' triangles',item.id)));
    if(this.items.some(item=>item.id===previous))select.value=previous;
  }
  render(project,selected,materials) {
    const key=[project?.id,project?.revision,selected].join('|');if(this.key===key)return;this.key=key;
    const item=project?.scene.elements.find(item=>item.id===selected);
    this.find('finish-panel').hidden=!item;if(!item)return;
    const finish=item.finish||{};
    this.find('finish-color').value=finish.color||materials[item.material];this.find('finish-pattern').value=finish.pattern||'solid';
    this.find('finish-scale').value=finish.scale_m||.25;this.find('finish-rotation').value=finish.rotation||0;
    this.find('finish-source').checked=finish.source_colors??Boolean(item.mesh?.colors);
  }
  sync(disabled,selected) {
    for(const id of ['asset-import-form','asset-placement','finish-form'])for(const control of this.find(id).querySelectorAll('input,select,button'))control.disabled=disabled;
    this.find('asset-capture').disabled=disabled||!selected;
    this.find('asset-place').disabled=disabled||!this.items.length;
    this.find('asset-export').disabled=disabled||!this.items.length;
  }
}
