"""Designed vegetation is separate from the immutable generated/source landscape."""
from copy import deepcopy
import math
import random
from .scene import ValidationError,element,number,required_text
from .placement import active_terrain,height_at
from .roofs import polyhedron

PLANTS=('pine','broadleaf','hedge')


def plant_parts(spec):
    w,d,h=spec['width'],spec['depth'],spec['height'];px,py,pz=spec['position'];parts=[]
    def add(role,offset,size,material,mesh=None):
        data={'kind':'block','name':spec['name']+' · '+role,'size':size,'position':[px,py+offset,pz],
              'yaw':spec['yaw'],'material':material}
        if mesh is not None:data['mesh']=mesh
        parts.append({**element(data),'role':role+':1'})
    if spec['kind']=='hedge':
        add('hedge',0,[w,h,d],spec['material']);return parts
    trunk=max(.08,min(w,d)*.12);add('trunk',0,[trunk,h*.6,trunk],'oak')
    if spec['kind']=='pine':
        vertices=[[math.cos(i*math.tau/12)*w/2,0,math.sin(i*math.tau/12)*d/2] for i in range(12)]+[[0,h*.65,0]]
        faces=[list(range(12))]+[[i,(i+1)%12,12] for i in range(12)]
    else:
        vertices=[[-w/2,h*.35,0],[0,h*.35,-d/2],[w/2,h*.35,0],[0,h*.35,d/2],[0,0,0],[0,h*.7,0]]
        faces=[[i,(i+1)%4,top] for top in (4,5) for i in range(4)]
    size,mesh=polyhedron(vertices,faces);add('crown',h*.35 if spec['kind']=='pine' else h*.3,size,spec['material'],mesh)
    return parts


def anchored_spec(scene,group,spec,baseline,vertical_delta=0):
    if baseline is None:raise ValidationError('Planted objects need their property terrain.')
    offset=number(group['ground_anchor']['offset_m']+vertical_delta,'Ground offset',-5,50)
    group['ground_anchor']={'offset_m':offset}
    position=spec['position'][:];position[1]=height_at(active_terrain(baseline,scene),position[0],position[2])+offset
    return {**spec,'position':position}


def reanchor(scene,baseline):
    from .groups import regenerate
    for group in scene.get('assemblies',[]):
        if 'ground_anchor' in group:regenerate(scene,group,anchored_spec(scene,group,group['spec'],baseline))


def plant(scene,command,baseline):
    from .groups import edit_group
    data=command.get('planting')
    if not isinstance(data,dict) or not data.keys()<={'kind','name','width','depth','height','center','radius_m','count','seed','offset_m'}:
        raise ValidationError('Choose supported planting fields.')
    kind=data.get('kind')
    if not isinstance(kind,str) or kind not in PLANTS:raise ValidationError('Choose pine, broadleaf or hedge.')
    name=required_text(data.get('name',kind.capitalize()),'Planting name',50)
    count=data.get('count',1);seed=data.get('seed',1);center=data.get('center')
    if type(count) is not int or not 1<=count<=64 or len(scene.get('assemblies',[]))+count>500:raise ValidationError('Plant 1–64 objects within a 500-assembly property.')
    if type(seed) is not int or not 0<=seed<2**31:raise ValidationError('Choose a whole-number seed between 0 and 2147483647.')
    if not isinstance(center,list) or len(center)!=2:raise ValidationError('Planting centre needs X and Z.')
    center=[number(v,'Planting centre',-900,900) for v in center]
    radius=number(data.get('radius_m',5),'Planting radius',0,100);offset=number(data.get('offset_m',0),'Ground offset',-5,50)
    if count>1 and radius<.1:raise ValidationError('A planting set needs a nonzero area.')
    randomizer=random.Random(seed);terrain=active_terrain(baseline,scene);positions=[]
    for index in range(count):
        if count==1:x,z=center
        else:
            angle=randomizer.random()*math.tau;r=radius*math.sqrt(randomizer.random());x,z=center[0]+math.cos(angle)*r,center[1]+math.sin(angle)*r
        positions.append([x,height_at(terrain,x,z)+offset,z])
    for index,position in enumerate(positions):
        spec={k:data[k] for k in ('kind','width','depth','height') if k in data}
        spec.update(position=position,name=(name+' '+str(index+1)) if count>1 else name)
        edit_group(scene,{'action':'assembly','assembly':spec},baseline)
        scene['assemblies'][-1]['ground_anchor']={'offset_m':offset}
    return f'Planted {count} {kind} objects; bases follow design ground'
