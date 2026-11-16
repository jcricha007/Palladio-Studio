"""Closed roof envelopes, not structural framing or construction drawings."""
from .geometry import normalize
from .scene import ValidationError, element, number

ROOF_KINDS=('gable_roof','hip_roof','shed_roof')


def polyhedron(vertices,faces):
    centre=[sum(p[i] for p in vertices)/len(vertices) for i in range(3)];triangles=[]
    for face in faces:
        for index in range(1,len(face)-1):
            a,b,c=face[0],face[index],face[index+1]
            u=[vertices[b][i]-vertices[a][i] for i in range(3)];v=[vertices[c][i]-vertices[a][i] for i in range(3)]
            normal=[u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0]]
            if sum(normal[i]*(vertices[a][i]-centre[i]) for i in range(3))<0: b,c=c,b
            triangles.extend((a,b,c))
    return normalize(vertices,triangles)


def roof_part(spec):
    w=spec['width']+2*spec['overhang'];d=spec['depth']+2*spec['overhang'];h=spec['height']
    vertices=[[-w/2,0,-d/2],[w/2,0,-d/2],[w/2,0,d/2],[-w/2,0,d/2]]
    faces=[[0,3,2,1]]
    if spec['kind']=='shed_roof':
        vertices += [[-w/2,.1,-d/2],[w/2,h,-d/2],[w/2,h,d/2],[-w/2,.1,d/2]]
        faces += [[4,5,6,7],[0,1,5,4],[1,2,6,5],[2,3,7,6],[3,0,4,7]]
    elif spec['kind']=='hip_roof' and abs(w-d)<.05:
        vertices.append([0,h,0]);faces += [[0,1,4],[1,2,4],[2,3,4],[3,0,4]]
    elif spec['kind']=='hip_roof' and w>d:
        vertices += [[-(w-d)/2,h,0],[(w-d)/2,h,0]]
        faces += [[0,1,5,4],[1,2,5],[2,3,4,5],[3,0,4]]
    else:
        ridge=d/2 if spec['kind']=='gable_roof' else (d-w)/2
        vertices += [[0,h,-ridge],[0,h,ridge]]
        faces += [[0,1,4],[1,2,5,4],[2,3,5],[3,0,4,5]]
    size,mesh=polyhedron(vertices,faces)
    return {**element({'kind':'roof','name':spec['name']+' · envelope','material':spec['material'],
        'position':spec['position'],'yaw':spec['yaw'],'size':size,'mesh':mesh}),'role':'roof envelope:1'}


def fit_roof(scene,command,baseline):
    from .groups import find_group,edit_group
    host=find_group(scene,command.get('id'));source=host['spec'];data=command.get('roof')
    if source['kind'] not in ('room','garage','dwelling'): raise ValidationError('Fit a roof to a room, garage or dwelling shell.')
    if not isinstance(data,dict) or not data.keys()<={'kind','name','height','material','overhang'} or data.get('kind') not in ROOF_KINDS:
        raise ValidationError('Choose gable, hip or shed roof parameters.')
    position=source['position'][:];position[1]+=source['height']+.35
    spec={**data,'width':source['width'],'depth':source['depth'],'position':position,'yaw':source['yaw']}
    return edit_group(scene,{'action':'assembly','assembly':spec},baseline)
