"""Selection-level layout tools respect linked assembly ownership."""
from copy import deepcopy
import math
from .scene import ValidationError, edit_scene, number, vector
from .geometry import raw_triangles, world_point


def targets(scene,ids):
    if not isinstance(ids,list) or not 1<=len(ids)<=100 or any(not isinstance(i,str) for i in ids):
        raise ValidationError('Choose between one and 100 scene parts.')
    groups=scene.get('assemblies',[])
    owners={member:g for g in groups for member in g['members'].values()}
    elements={p['id']:p for p in scene['elements']};result={}
    for key in ids:
        if key not in elements: raise ValidationError('A selected part is no longer in this property.')
        group=owners.get(key)
        if group: result[group['id']]={'group':True,'id':group['id'],'data':group['spec'],'members':set(group['members'].values())}
        else: result[key]={'group':False,'id':key,'data':elements[key],'members':{key}}
    return list(result.values())


def measure(scene,ids):
    chosen=targets(scene,ids);members=set().union(*(t['members'] for t in chosen))
    low=[math.inf]*3;high=[-math.inf]*3
    for item in scene['elements']:
        if item['id'] not in members: continue
        for points,_ in raw_triangles(item):
            for p in points:
                p=world_point(item,p)
                low=[min(a,b) for a,b in zip(low,p)];high=[max(a,b) for a,b in zip(high,p)]
    return {'objects':len(chosen),'parts':len(members),'minimum':low,'maximum':high,
            'size':[b-a for a,b in zip(low,high)],
            'origin_distance_m':math.dist(chosen[0]['data']['position'],chosen[1]['data']['position']) if len(chosen)==2 else None}


def edit_layout(scene,command,baseline):
    data=command.get('layout')
    if not isinstance(data,dict) or not data.keys()<={'ids','operation','offset','axis','spacing_m','angle'}:
        raise ValidationError('Choose supported layout fields.')
    chosen=targets(scene,data.get('ids'));operation=data.get('operation')
    if operation not in ('move','copy','rotate','align','distribute','grid'): raise ValidationError('Choose a supported layout operation.')
    axis=data.get('axis','x')
    if axis not in ('x','y','z'): raise ValidationError('Choose the X, Y or Z axis.')
    axis='xyz'.index(axis);pivot=chosen[0]['data']['position'][:]
    offset=vector(data.get('offset',[0,0,0]),'Layout offset',-1000,1000)
    angle=number(data.get('angle',0),'Layout rotation',-360,360);radians=math.radians(angle)
    spacing=number(data.get('spacing_m',1),'Grid spacing',.01,100)
    if operation=='distribute':
        if len(chosen)<3: raise ValidationError('Choose at least three independent objects to distribute.')
        chosen.sort(key=lambda t:t['data']['position'][axis])
    changes=[]
    for index,target in enumerate(chosen):
        source=target['data'];position=source['position'][:];yaw=source['yaw']
        if operation in ('move','copy'): position=[a+b for a,b in zip(position,offset)]
        elif operation=='grid': position=[math.floor(value/spacing+.5)*spacing for value in position]
        elif operation=='align': position[axis]=pivot[axis]
        elif operation=='distribute': position[axis]=chosen[0]['data']['position'][axis]+index*(chosen[-1]['data']['position'][axis]-chosen[0]['data']['position'][axis])/(len(chosen)-1)
        elif operation=='rotate':
            x,z=position[0]-pivot[0],position[2]-pivot[2]
            position[0]=pivot[0]+x*math.cos(radians)+z*math.sin(radians)
            position[2]=pivot[2]-x*math.sin(radians)+z*math.cos(radians)
            yaw=(yaw+angle+180)%360-180
        if operation=='copy':
            if target['group']: edit={'action':'assembly_duplicate','id':target['id'],'position':position}
            else: edit={'action':'add','element':{**deepcopy(source),'position':position}}
        elif target['group']: edit={'action':'assembly_update','id':target['id'],'assembly':{'position':position,'yaw':yaw}}
        else: edit={'action':'update','id':target['id'],'element':{'position':position,'yaw':yaw}}
        changes.append(edit)
    # Resolve all transforms before mutation so distribution is order-independent.
    for edit in changes: edit_scene(scene,edit,baseline)
    return f'{operation.capitalize()} {len(chosen)} objects ({sum(len(t["members"]) for t in chosen)} linked/independent parts)'
