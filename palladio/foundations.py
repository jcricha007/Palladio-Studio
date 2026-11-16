"""Schematic isolated pads, piers and beams fitted to saved terrain under a level top."""
from .scene import ValidationError,number
from .parts import box_part
from .placement import active_terrain,footprint_range

HOSTS=('room','garage','dwelling','path')


def grid(spec,data):
    result={}
    for key in ('columns_x','columns_z'):
        value=data.get(key,3)
        if type(value) is not int or not 2<=value<=6:raise ValidationError('Choose 2–6 pier columns and rows.')
        result[key]=value
    result['pier_width']=number(data.get('pier_width',.25),'Pier width',.15,.6)
    pad=max(.5,result['pier_width']*2)
    if min((spec['width']-pad)/(result['columns_x']-1),(spec['depth']-pad)/(result['columns_z']-1))<pad+.1:raise ValidationError('The support grid is too dense for this footprint.')
    return result


def locations(spec):
    pad=max(.5,spec['pier_width']*2)
    for row in range(spec['columns_z']):
        for col in range(spec['columns_x']):
            x=-spec['width']/2+pad/2+col*(spec['width']-pad)/(spec['columns_x']-1)
            z=-spec['depth']/2+pad/2+row*(spec['depth']-pad)/(spec['columns_z']-1)
            yield row,col,x,z,pad


def pad_ground(spec,terrain):
    for row,col,x,z,pad in locations(spec):
        part=box_part(spec,'probe',[x,0,z],[pad,.2,pad])
        low,high=footprint_range(terrain,{'width':pad,'depth':pad,'yaw':spec['yaw'],'position':part['position']})
        yield high


def foundation_parts(spec,data):
    spec.update(grid(spec,data));count=spec['columns_x']*spec['columns_z']
    offsets=data.get('support_offsets',[0]*count)
    if not isinstance(offsets,list) or len(offsets)!=count:raise ValidationError('Refit the foundation after changing its grid size.')
    spec['support_offsets']=[number(v,'Support base offset',0,spec['height']-.5) for v in offsets]
    pieces=[];pier=spec['pier_width'];h=spec['height']
    for index,(row,col,x,z,pad) in enumerate(locations(spec)):
        y=spec['support_offsets'][index];role=f'{row+1}.{col+1}'
        pieces.append(box_part(spec,'pad '+role,[x,y,z],[pad,.2,pad],'concrete'))
        pieces.append(box_part(spec,'pier '+role,[x,y+.2,z],[pier,h-y-.4,pier],kind='column'))
    for row in range(spec['columns_z']):
        pad=max(.5,pier*2);z=-spec['depth']/2+pad/2+row*(spec['depth']-pad)/(spec['columns_z']-1)
        pieces.append(box_part(spec,f'beam {row+1}',[0,h-.2,z],[spec['width'],.2,pier]))
    return spec,pieces


def fitted_spec(scene,baseline,source,parameters,top):
    if baseline is None:raise ValidationError('Foundation fitting requires saved terrain.')
    spec={**source,**grid(source,parameters)}
    heights=list(pad_ground(spec,active_terrain(baseline,scene)));low=min(heights)
    if top-max(heights)<.6-1e-8:raise ValidationError('Raise the structure to leave at least 0.6 m for pads, piers and beams.')
    spec['position']=[source['position'][0],low,source['position'][2]]
    spec['height']=top-low;spec['support_offsets']=[height-low for height in heights]
    return spec


def edit_foundation(scene,command,baseline):
    from .groups import edit_group,find_group
    group=find_group(scene,command.get('id'));source=group['spec'];parameters=command.get('foundation',{})
    if not isinstance(parameters,dict) or not parameters.keys()<={'columns_x','columns_z','pier_width'}:raise ValidationError('Choose foundation grid counts and pier width.')
    if command['action']=='foundation_fit':
        if source['kind'] not in HOSTS:raise ValidationError('Fit foundations to a room, garage, dwelling or terrace.')
        spec={k:source[k] for k in ('width','depth','position','yaw')}
        spec.update(kind='foundation',name=(source['name']+' foundations')[:60],height=1,material='concrete')
        spec=fitted_spec(scene,baseline,spec,parameters,source['position'][1])
        return edit_group(scene,{'action':'assembly','assembly':spec},baseline)
    if source['kind']!='foundation':raise ValidationError('Select a foundation to refit its pads to the current terrain.')
    spec=fitted_spec(scene,baseline,source,{**source,**parameters},source['position'][1]+source['height'])
    return edit_group(scene,{'action':'assembly_update','id':group['id'],'assembly':{k:v for k,v in spec.items() if k!='kind'}},baseline)


def foundation_warnings(spec,terrain):
    heights=list(pad_ground(spec,terrain));difference=max(abs(spec['position'][1]+offset-ground) for offset,ground in zip(spec['support_offsets'],heights))
    return [f"{spec['name']}: ground differs from fitted pad bases by up to {difference:.2f} m. Refit after terrain or placement changes."] if difference>.05 else []
