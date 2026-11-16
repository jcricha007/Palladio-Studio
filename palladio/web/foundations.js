export class FoundationTools {
  constructor(find,hooks){
    this.find=find;this.hooks=hooks;
    for(const event of ['input','change'])find('foundation-panel').addEventListener(event,hooks.invalidate);
    for(const action of ['fit','raise','refit'])find('foundation-'+action).addEventListener('click',()=>{
      const group=this.group();if(!group)return;
      const foundation=Object.fromEntries(['columns_x','columns_z','pier_width'].map(k=>[k,Number(find('foundation-'+k).value)]));
      const commands=action==='raise'?[{action:'assembly_place',id:group.id,offset_m:Number(find('foundation-clearance').value)}]:[];
      commands.push({action:action==='refit'?'foundation_refit':'foundation_fit',id:group.id,foundation});hooks.preview(commands);
    });
  }
  group(){const {project,selected}=this.hooks.state();return project?.scene.assemblies?.find(g=>Object.values(g.members).includes(selected));}
  sync(){
    const {project,busy,baselineView}=this.hooks.state(),disabled=busy||!project||baselineView,kind=this.group()?.spec.kind;
    for(const node of this.find('foundation-panel').querySelectorAll('input,button'))node.disabled=disabled;
    for(const action of ['fit','raise'])this.find('foundation-'+action).disabled=disabled||!['room','garage','dwelling','path'].includes(kind);
    this.find('foundation-refit').disabled=disabled||kind!=='foundation';
  }
}
