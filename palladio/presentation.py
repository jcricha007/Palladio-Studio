"""Saved browser cameras and bounded, metre/Y-up geometry exports."""
from uuid import uuid4
import math
from .scene import ValidationError,number,vector,required_text
from .geometry import raw_triangles,world_point
from .placement import active_terrain


def camera(data):
    fields={'target','azimuth','pitch','distance'}
    if not isinstance(data,dict) or not fields <= set(data) or set(data)-fields-{'fov_degrees'}:
        raise ValidationError('Provide a complete orbit camera.')
    return {'target':vector(data['target'],'View target',-2000,2000),
            'azimuth':number(data['azimuth'],'Orbit angle',-100000,100000),
            'pitch':number(data['pitch'],'View pitch',.06,1.51),
            'distance':number(data['distance'],'View distance',2,3000),
            **({'fov_degrees':number(data['fov_degrees'],'Vertical field of view',15,100)} if 'fov_degrees' in data else {})}


def camera_pose(data):
    view=camera(data);angle=view['azimuth'];pitch=view['pitch'];distance=view['distance']
    offset=[math.sin(angle)*math.cos(pitch),math.sin(pitch),math.cos(angle)*math.cos(pitch)]
    return {'eye':[t+distance*d for t,d in zip(view['target'],offset)],
            'target':view['target'],'fov_degrees':view.get('fov_degrees',45)}


def camera_from_pose(data):
    if not isinstance(data,dict) or set(data)!={'eye','target','fov_degrees'}:
        raise ValidationError('Provide an eye, orbit target and vertical field of view.')
    eye=vector(data['eye'],'Camera eye',-6000,6000);target=vector(data['target'],'View target',-2000,2000)
    x,y,z=[a-b for a,b in zip(eye,target)];distance=math.sqrt(x*x+y*y+z*z)
    pitch=math.atan2(y,math.hypot(x,z))
    if not .06-1e-9 <= pitch <= 1.51+1e-9:
        raise ValidationError('Save an orbit looking downward toward its target (3.5 to 86.5 degrees).')
    # Native centimetres and JSON round trips can drift at an allowed endpoint.
    pitch=max(.06,min(1.51,pitch))
    if 2-1e-7 <= distance <= 3000+1e-7:distance=max(2,min(3000,distance))
    return camera({'target':target,'azimuth':math.atan2(x,z),'pitch':pitch,
                   'distance':distance,'fov_degrees':data['fov_degrees']})


def edit_view(scene,command):
    views=scene.setdefault('views',[]);action=command['action'];key=command.get('id')
    existing=next((v for v in views if v['id']==key),None)
    if action=='view_remove':
        if existing is None:raise ValidationError('Choose a saved view.')
        views.remove(existing);return 'Removed view '+existing['name']
    name=required_text(command.get('name'),'View name',80)
    view=camera_from_pose(command.get('pose')) if action=='view_capture' else camera(command.get('camera'))
    if any(v['name'].casefold()==name.casefold() and v is not existing for v in views):raise ValidationError('Use a unique view name.')
    if action=='view_update':
        if existing is None:raise ValidationError('Choose a saved view.')
        existing.update(name=name,camera=view)
    elif action in ('view_save','view_capture'):
        if len(views)>=24:raise ValidationError('Keep at most 24 saved views.')
        views.append({'id':str(uuid4()),'name':name,'camera':view})
    else:raise ValidationError('Unknown view operation.')
    return 'Saved view '+name


def scene_obj(project,include_terrain=True):
    if type(include_terrain) is not bool:raise ValidationError('Terrain inclusion must be true or false.')
    # Finishes do not change geometry. Avoid exporting color-sampling subdivisions.
    items=[{k:v for k,v in item.items() if k!='finish'} for item in project['scene']['elements']]
    count=sum(len(e['mesh']['triangles'])//3 if 'mesh' in e else 12 for e in items)
    terrain=active_terrain(project['baseline'],project['scene']);n=terrain['size']
    if include_terrain:count+=2*(n-1)**2
    if count>100000:raise ValidationError('Geometry export supports at most 100,000 triangles. Export a smaller design.')
    lines=['# Palladio geometry snapshot','# Units: metres; Y up',f'# Property {project["id"]}; revision {project["revision"]}'];index=1
    def triangle(points):
        nonlocal index
        lines.extend('v '+' '.join(format(value,'.12g') for value in point) for point in points)
        lines.append(f'f {index} {index+1} {index+2}');index+=3
    for item in items:
        label=''.join(c if c.isascii() and c.isalnum() else '_' for c in item['name'])
        lines.append('o '+label+'_'+item['id'])
        for points,_ in raw_triangles(item):triangle([world_point(item,p) for p in points])
    if include_terrain:
        lines.append('o terrain');spacing=terrain['spacing'];edge=(n-1)*spacing/2
        def point(row,col):return [col*spacing-edge,terrain['heights'][row*n+col],row*spacing-edge]
        for row in range(n-1):
            for col in range(n-1):
                a,b,c,d=point(row,col),point(row+1,col),point(row+1,col+1),point(row,col+1)
                triangle([a,b,c]);triangle([a,c,d])
    return {'revision':project['revision'],'triangles':count,'obj':'\n'.join(lines)+'\n'}
