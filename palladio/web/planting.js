export class PlantingTools {
  constructor(find,hooks) {
    this.find=find;this.hooks=hooks;
    find('planting-form').addEventListener('input',hooks.invalidate);find('planting-form').addEventListener('change',hooks.invalidate);
    find('planting-form').addEventListener('submit',event=>{
      event.preventDefault();const planting={kind:find('plant-kind').value,name:find('plant-name').value,center:['x','z'].map(a=>Number(find('plant-'+a).value))};
      for(const key of ['width','depth','height','radius_m','count','seed','offset_m'])planting[key]=Number(find('plant-'+key).value);
      hooks.preview([{action:'planting',planting}]);
    });
  }
  sync() {const {busy,project,baselineView}=this.hooks.state();for(const node of this.find('planting-form').querySelectorAll('input,select,button'))node.disabled=busy||!project||baselineView;}
}
