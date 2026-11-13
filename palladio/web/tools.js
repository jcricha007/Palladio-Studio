// Inspector tools produce unsaved command previews through the common Apply flow.
export class DesignTools {
  constructor(find, preview, invalidate) {
    this.find = find;
    this.preview = preview;
    this.group = null;
    this.key = '';
    find('group-form').addEventListener('submit', event => {
      event.preventDefault();
      if (!this.group) return;
      const assembly = Object.fromEntries(['width','depth','height','yaw'].map(key => [key, Number(find('group-' + key).value)]));
      if (this.group.spec.kind === 'stairs') assembly.steps = Number(find('group-steps').value);
      assembly.position = ['x','y','z'].map(axis => Number(find('group-' + axis).value));
      if (['room','garage'].includes(this.group.spec.kind)) {
        for (const key of ['door_width','door_height','window_width','window_height','window_sill']) assembly[key] = Number(find('group-' + key).value);
      }
      preview([{action:'assembly_update', id:this.group.id, assembly}]);
    });
    for (const event of ['input','change']) find('group-form').addEventListener(event, invalidate);
    for (const event of ['input','change']) find('terrain-form').addEventListener(event, invalidate);
    find('terrain-form').addEventListener('submit', event => {
      event.preventDefault();
      const mode=find('terrain-mode').value;
      const layer={name:find('terrain-name').value,mode,center:[Number(find('terrain-x').value),Number(find('terrain-z').value)],radius_m:Number(find('terrain-radius').value)};
      layer[mode==='flatten'?'height_m':'amount_m']=Number(find(mode==='flatten'?'terrain-height':'terrain-amount').value);
      preview([{action:'terrain_layer',layer}]);
    });
    for (const action of ['toggle','remove','restore']) find('terrain-'+action).addEventListener('click',()=>{
      if (action==='restore') {preview([{action:'terrain_restore'}]);return;}
      const layer=this.project?.scene.terrain_layers?.find(x=>x.id===find('terrain-layers').value);
      if (layer) preview([{action:'terrain_'+action,id:layer.id,...(action==='toggle'?{enabled:!layer.enabled}:{})}]);
    });
    for (const action of ['place','duplicate','detach','remove']) find('group-' + action).addEventListener('click', () => {
      if (!this.group) return;
      const command = {action:'assembly_' + action, id:this.group.id};
      if (action === 'place') command.offset_m = Number(find('group-offset').value);
      if (action === 'duplicate') command.position = ['x','y','z'].map(axis => Number(find('group-' + axis).value));
      preview([command]);
    });
  }

  render(project, selected) {
    this.project = project;
    this.group = project?.scene.assemblies?.find(g => Object.values(g.members).includes(selected)) || null;
    this.find('group-panel').hidden = !this.group;
    const key = [project?.id,project?.revision,selected].join('|');
    if (this.key === key) return;
    this.key = key;
    const layers=project?.scene.terrain_layers || [];
    const selectedLayer=this.find('terrain-layers').value;
    this.find('terrain-layers').replaceChildren(...layers.map(layer=>new Option((layer.enabled?'On · ':'Off · ')+layer.name,layer.id)));
    if (layers.some(x=>x.id===selectedLayer)) this.find('terrain-layers').value=selectedLayer;
    if (!this.group) return;
    const spec = this.group.spec;
    this.find('group-title').textContent = spec.name + ' · ' + Object.keys(this.group.members).length + ' linked parts';
    for (const field of ['width','depth','height','yaw','door_width','door_height','window_width','window_height','window_sill']) this.find('group-' + field).value = spec[field] ?? '';
    for (const [i,axis] of ['x','y','z'].entries()) this.find('group-' + axis).value = spec.position[i];
    this.find('group-offset').value = 0;
    this.find('group-steps').value=spec.steps ?? '';
    this.find('group-steps-label').hidden=spec.kind!=='stairs';
    this.find('group-steps').required=spec.kind==='stairs';
    const shell = ['room','garage'].includes(spec.kind);
    this.find('group-openings').hidden = !shell;
    for (const field of ['door_width','door_height','window_width','window_height','window_sill']) this.find('group-' + field).required = shell;
  }

  sync(disabled) {
    for (const control of this.find('terrain-form').querySelectorAll('input, select, button')) control.disabled = disabled;
    for (const control of this.find('group-form').querySelectorAll('input, button')) control.disabled = disabled || !this.group;
  }
}
