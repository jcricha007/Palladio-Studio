export class WallTools {
  constructor(find,hooks){
    this.find=find;this.hooks=hooks;this.key='';
    find('opening-list').addEventListener('change',()=>{hooks.invalidate();this.show();});
    find('opening-new').addEventListener('click',()=>{hooks.invalidate();this.show(true);});
    find('opening-kind').addEventListener('change',()=>{if(find('opening-kind').value==='door')find('opening-sill').value=0;});
    for(const event of ['input','change'])find('opening-form').addEventListener(event,hooks.invalidate);
    find('opening-form').addEventListener('submit',event=>{
      event.preventDefault();const group=this.group();if(!group)return;
      const opening={key:find('opening-key').value,kind:find('opening-kind').value};
      for(const key of ['center','width','height','sill','frame'])opening[key]=Number(find('opening-'+key).value);
      hooks.preview([{action:'opening_set',id:group.id,opening}]);
    });
    find('opening-remove').addEventListener('click',()=>{const group=this.group();if(group)hooks.preview([{action:'opening_remove',id:group.id,key:find('opening-list').value}]);});
    find('wall-convert').addEventListener('click',()=>hooks.preview([{action:'wall_convert',id:hooks.state().selected}]));
  }
  group(){const {project,selected}=this.hooks.state();return project?.scene.assemblies?.find(g=>g.spec.kind==='wall_run'&&Object.values(g.members).includes(selected));}
  show(fresh=false){
    const openings=this.group()?.spec.openings||[];let n=1;while(openings.some(o=>o.key==='opening-'+n))n++;
    const value=(!fresh&&openings.find(o=>o.key===this.find('opening-list').value))||{key:'opening-'+n,kind:'window',center:0,width:1.2,height:1.2,sill:.9,frame:.06};
    for(const key of ['key','kind','center','width','height','sill','frame'])this.find('opening-'+key).value=value[key];
  }
  render(){
    const {project,selected}=this.hooks.state(),key=[project?.id,project?.revision,selected].join('|');if(key===this.key)return;this.key=key;
    const list=this.find('opening-list'),previous=list.value,openings=this.group()?.spec.openings||[];
    list.replaceChildren(...openings.map(o=>new Option(o.key+' · '+o.kind,o.key)));if(openings.some(o=>o.key===previous))list.value=previous;
    this.show();
  }
  sync(){
    const {project,selected,busy,baselineView}=this.hooks.state(),group=this.group(),disabled=busy||!project||baselineView;
    for(const node of this.find('wall-tools').querySelectorAll('input,select,button'))node.disabled=disabled||!group;
    this.find('opening-remove').disabled=disabled||!group||!this.find('opening-list').value;
    const item=project?.scene.elements.find(e=>e.id===selected),owned=project?.scene.assemblies?.some(g=>Object.values(g.members).includes(selected));
    this.find('wall-convert').disabled=disabled||item?.kind!=='wall'||Boolean(item?.mesh)||owned;
  }
}
