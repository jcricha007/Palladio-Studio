"""Editable wall runs with multiple rectangular rough openings and explicit frames."""
import re
from .scene import ValidationError,number
from .geometry import finish
from .parts import box_part

KEY=re.compile(r'[A-Za-z0-9_-]{1,24}')


def openings(data,width,height):
    if not isinstance(data,list) or len(data)>16:raise ValidationError('Use at most 16 openings per wall.')
    result=[];keys=set()
    for value in data:
        if not isinstance(value,dict) or not value.keys()<={'key','kind','center','width','height','sill','frame'}:raise ValidationError('Choose supported opening fields.')
        key=value.get('key');kind=value.get('kind')
        if not isinstance(key,str) or not KEY.fullmatch(key) or key in keys:raise ValidationError('Use a unique opening key of 1–24 letters, numbers, underscores or dashes.')
        if kind not in ('door','window'):raise ValidationError('Choose a door or window.')
        keys.add(key)
        item={'key':key,'kind':kind,'center':number(value.get('center',0),'Opening centre',-width/2,width/2),
              'width':number(value.get('width',1.2),'Rough opening width',.5,width-.2),
              'height':number(value.get('height',2.1 if kind=='door' else 1.2),'Rough opening height',.5,height-.1),
              'sill':number(value.get('sill',0 if kind=='door' else .9),'Opening sill',0,height-.6),
              'frame':number(value.get('frame',.06),'Frame width',.05,.2)}
        if kind=='door' and item['sill']!=0:raise ValidationError('Door openings start at the wall base.')
        if kind=='window' and item['sill']<.1:raise ValidationError('Window sills must be at least 0.1 m above the wall base.')
        if item['height']+item['sill']>height-.1+1e-9:raise ValidationError('Leave at least 0.1 m of wall above every opening.')
        if min(item['width'],item['height'])-2*item['frame']<.2:raise ValidationError('Frames must leave at least 0.2 m clear inside the opening.')
        result.append(item)
    result.sort(key=lambda item:(item['center'],item['key']))
    edge=-width/2
    for item in result:
        left=item['center']-item['width']/2
        if left-edge<.1-1e-9:raise ValidationError('Leave at least 0.1 m of wall beside and between openings.')
        edge=item['center']+item['width']/2
    if width/2-edge<.1-1e-9:raise ValidationError('Leave at least 0.1 m of wall at the end.')
    return result


def wall_parts(spec,data):
    spec['openings']=openings(data.get('openings',[]),spec['width'],spec['height'])
    if 'wall_finish' in data:spec['wall_finish']=finish(data['wall_finish'])
    pieces=[];w,h,d=spec['width'],spec['height'],spec['depth']
    def add(role,pos,size,material=None,kind='wall'):
        extra={'finish':spec['wall_finish']} if 'wall_finish' in spec and material is None else {}
        pieces.append(box_part(spec,role,pos,size,material,kind,**extra))
    edge=-w/2;previous='start'
    for opening in spec['openings']:
        key=opening['key'];x=opening['center'];ow=opening['width'];oh=opening['height'];sill=opening['sill'];f=opening['frame'];left=x-ow/2;right=x+ow/2
        add(f'span {previous}-{key}',[(edge+left)/2,0,0],[left-edge,h,d])
        if sill:add(f'{key} sill wall',[x,0,0],[ow,sill,d])
        add(f'{key} lintel',[x,sill+oh,0],[ow,h-sill-oh,d])
        for sign,label in [(-1,'left'),(1,'right')]:add(f'{key} {label} frame',[x+sign*(ow-f)/2,sill,0],[f,oh,d],'oak','block')
        add(f'{key} top frame',[x,sill+oh-f,0],[ow-2*f,f,d],'oak','block')
        if opening['kind']=='window':
            add(f'{key} bottom frame',[x,sill,0],[ow-2*f,f,d],'oak','block')
            add(f'{key} glazing',[x,sill+f,0],[ow-2*f,oh-2*f,.05],'glass','glazing')
        edge=right;previous=key
    add(f'span {previous}-end',[(edge+w/2)/2,0,0],[w/2-edge,h,d])
    return spec,pieces


def edit_opening(scene,command,baseline):
    from .groups import edit_group,find_group,owner
    action=command['action']
    if action=='wall_convert':
        item=next((e for e in scene['elements'] if e['id']==command.get('id')),None)
        if item is None or item['kind']!='wall' or 'mesh' in item or owner(scene,item['id']):raise ValidationError('Select an independent box wall. Detach its assembly first if needed.')
        spec={'kind':'wall_run','name':item['name'][:60],'material':item['material'],'position':item['position'],'yaw':item['yaw'],
              'width':item['size'][0],'height':item['size'][1],'depth':item['size'][2]}
        if 'finish' in item:spec['wall_finish']=item['finish']
        # Validate/generate before removing the source; transaction rollback protects both.
        result=edit_group(scene,{'action':'assembly','assembly':spec},baseline)
        scene['elements']=[e for e in scene['elements'] if e['id']!=item['id']]
        return 'Converted wall to linked openings · '+result
    group=find_group(scene,command.get('id'))
    if group['spec']['kind']!='wall_run':raise ValidationError('Select a wall-run assembly to edit its openings.')
    values=group['spec']['openings'][:]
    if action=='opening_set':
        value=command.get('opening')
        if not isinstance(value,dict):raise ValidationError('Provide an opening specification.')
        values=[x for x in values if x['key']!=value.get('key')]+[value]
    elif action=='opening_remove':
        key=command.get('key')
        if not any(x['key']==key for x in values):raise ValidationError('Choose an opening to remove.')
        values=[x for x in values if x['key']!=key]
    else:raise ValidationError('Unknown opening operation.')
    return edit_group(scene,{'action':'assembly_update','id':group['id'],'assembly':{'openings':values}},baseline)
