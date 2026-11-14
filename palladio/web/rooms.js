export class RoomTools {
  constructor(find,hooks) {
    this.find=find;this.hooks=hooks;
    find('assembly-kind').addEventListener('change',()=>this.render());
    find('room-schedule').addEventListener('click',()=>hooks.run(async()=>{
      const {project}=hooks.state();const result=await hooks.api('/api/properties/'+project.id+'/schedule');
      find('room-schedule-text').textContent=result.buildings.map(b=>b.name+'\n'+b.rooms.map(r=>`${r.name}: ${r.clear_width_m.toFixed(2)} × ${r.clear_depth_m.toFixed(2)} m · ${r.area_m2.toFixed(2)} m²`).join('\n')).join('\n\n')||'No connected-room buildings in this property.';
    }));
  }
  render() {this.find('assembly-grid').hidden=this.find('assembly-kind').value!=='dwelling';this.find('room-schedule-text').textContent='';}
  sync() {const {project,busy}=this.hooks.state();this.find('room-schedule').disabled=busy||!project;}
}
