export class FinishTools {
  constructor(find,hooks) {
    this.find=find;this.hooks=hooks;this.key='';
    find('palette-save').addEventListener('click',()=>hooks.preview([{action:'finish_save',source_id:hooks.state().selected,name:find('palette-name').value}]));
    find('palette-apply').addEventListener('click',()=>hooks.preview([{action:'finish_apply',finish_id:find('palette-list').value,ids:[hooks.state().selected],scope:find('palette-scope').value}]));
    find('palette-remove').addEventListener('click',()=>hooks.preview([{action:'finish_remove',finish_id:find('palette-list').value}]));
    for(const event of ['input','change'])find('palette-panel').addEventListener(event,()=>{hooks.invalidate();this.sync();});
  }
  render() {
    const {project,catalog}=this.hooks.state(),key=[project?.id,project?.revision,Boolean(catalog)].join('|');if(key===this.key)return;this.key=key;
    const list=this.find('palette-list'),previous=list.value;
    const items=[...Object.entries(catalog?.finishes||{}).map(([id,p])=>({id:'builtin:'+id,name:p.name+' · built in'})),...(project?.scene.finishes||[])];
    list.replaceChildren(...items.map(p=>new Option(p.name,p.id)));if(items.some(p=>p.id===previous))list.value=previous;
  }
  sync() {
    const {project,selected,busy,baselineView}=this.hooks.state(),disabled=busy||!project||baselineView;
    for(const node of this.find('palette-panel').querySelectorAll('input,select,button'))node.disabled=disabled;
    this.find('palette-save').disabled=disabled||!selected;this.find('palette-apply').disabled=disabled||!selected||!this.find('palette-list').value;
    this.find('palette-remove').disabled=disabled||!this.find('palette-list').value||this.find('palette-list').value.startsWith('builtin:');
  }
}
