"""Revisioned property finish palettes; applying a preset stores a copy on each part."""
from copy import deepcopy
from uuid import uuid4
from .geometry import finish
from .scene import ValidationError,MATERIALS,required_text,edit_scene
from .layout import targets

PRESETS={
 'warm-oak':{'name':'Warm oak','finish':{'color':'#b78554','pattern':'wood','scale_m':.3,'rotation':0}},
 'limestone':{'name':'Limestone','finish':{'color':'#b6b0a0','pattern':'stone','scale_m':.45}},
 'clay-brick':{'name':'Clay brick','finish':{'color':'#ad654c','pattern':'brick','scale_m':.6,'accent_color':'#c8bca3'}},
 'light-tile':{'name':'Light tile','finish':{'color':'#d5d3c9','pattern':'tile','scale_m':.6,'accent_color':'#777772'}},
}


def edit_finish(scene,command,baseline):
    action=command['action'];palettes=scene.setdefault('finishes',[])
    if action=='finish_save':
        if len(palettes)>=32:raise ValidationError('Keep at most 32 property finishes.')
        source=next((e for e in scene['elements'] if e['id']==command.get('source_id')),None)
        if source is None:raise ValidationError('Select a part to capture its finish.')
        name=required_text(command.get('name'),'Finish name',80)
        if any(p['name'].casefold()==name.casefold() for p in palettes):raise ValidationError('Use a unique finish name, or remove the earlier preset.')
        palettes.append({'id':str(uuid4()),'name':name,'finish':finish(source.get('finish',{'color':MATERIALS[source['material']],'source_colors':bool(source.get('mesh',{}).get('colors'))}))})
        return 'Saved finish '+name
    key=command.get('finish_id');preset=PRESETS.get(key.removeprefix('builtin:')) if isinstance(key,str) and key.startswith('builtin:') else next((p for p in palettes if p['id']==key),None)
    if preset is None:raise ValidationError('Choose a saved finish.')
    if action=='finish_remove':
        if preset not in palettes:raise ValidationError('Built-in finishes cannot be removed.')
        palettes.remove(preset);return 'Removed preset; applied surfaces retained'
    if action!='finish_apply':raise ValidationError('Unknown finish operation.')
    ids=command.get('ids');chosen=targets(scene,ids);scope=command.get('scope','part')
    if scope not in ('part','assembly'):raise ValidationError('Choose selected parts or whole assemblies.')
    members=set().union(*(t['members'] for t in chosen)) if scope=='assembly' else set(ids)
    for key in sorted(members):edit_scene(scene,{'action':'update','id':key,'element':{'finish':deepcopy(preset['finish'])}},baseline)
    return f'Applied {preset["name"]} to {len(members)} parts'
