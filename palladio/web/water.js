export class WaterTools {
  constructor(find,hooks){
    this.find=find;this.hooks=hooks;this.key='';
    for(const event of ['input','change'])find('water-form').addEventListener(event,()=>{hooks.invalidate();this.sync();});
    const spec=()=>({kind:find('water-kind').value,name:find('water-name').value,material:find('water-material').value,
      position:['x','y','z'].map(a=>Number(find('water-'+a).value)),...Object.fromEntries(['width','height','depth','yaw','water_level'].map(k=>[k,Number(find('water-'+k).value)]))});
    find('water-form').addEventListener('submit',event=>{event.preventDefault();hooks.preview([{action:'assembly',assembly:spec()}]);});
    find('water-update').addEventListener('click',()=>{const group=this.group();if(!group)return;const {kind,...assembly}=spec();hooks.preview([{action:'assembly_update',id:group.id,assembly}]);});
    find('water-schedule').addEventListener('click',()=>hooks.run(async()=>{
      const {project}=hooks.state();const result=await hooks.api('/api/properties/'+project.id+'/water-schedule');
      find('water-result').textContent=result.features.map(f=>f.name+': '+f.litres.toFixed(0)+' L · '+f.surface_area_m2.toFixed(2)+' m² · depth '+f.water_depth_m.toFixed(2)+' m').join('\n')||'No saved pools or ponds.';
    }));
  }
  group(){const {project,selected}=this.hooks.state();return project?.scene.assemblies?.find(g=>['pool','pond'].includes(g.spec.kind)&&Object.values(g.members).includes(selected));}
  render(){
    const {project,selected}=this.hooks.state(),key=[project?.id,project?.revision,selected].join('|');if(key===this.key)return;this.key=key;this.find('water-result').textContent='';const spec=this.group()?.spec;if(!spec)return;
    for(const k of ['kind','name','material','width','height','depth','yaw','water_level'])this.find('water-'+k).value=spec[k];
    ['x','y','z'].forEach((a,i)=>this.find('water-'+a).value=spec.position[i]);
  }
  sync(){const {project,busy,baselineView}=this.hooks.state(),disabled=busy||!project||baselineView;
    for(const node of this.find('water-panel').querySelectorAll('input,select,button'))node.disabled=disabled;
    this.find('water-update').disabled=disabled||!this.group()||this.group().spec.kind!==this.find('water-kind').value;
  }
}
