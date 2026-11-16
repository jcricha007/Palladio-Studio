"""Shared local-to-world construction of named, stable assembly parts."""
import math
from .scene import element


def box_part(spec, role, position, size, material=None, kind='block', **extra):
    x,y,z=position;px,py,pz=spec['position'];angle=math.radians(spec['yaw'])
    return {**element({'kind':kind,'name':f"{spec['name']} · {role}"[:100],
        'material':material or spec['material'],'position':[px+x*math.cos(angle)+z*math.sin(angle),py+y,pz-x*math.sin(angle)+z*math.cos(angle)],
        'size':size,'yaw':spec['yaw'],**extra}),'role':role}


def mesh_part(spec,role,vertices,faces,material=None,**extra):
    from .roofs import polyhedron
    low=[min(p[i] for p in vertices) for i in range(3)];high=[max(p[i] for p in vertices) for i in range(3)]
    size,mesh=polyhedron(vertices,faces)
    return box_part(spec,role,[(low[0]+high[0])/2,low[1],(low[2]+high[2])/2],size,material,mesh=mesh,**extra)
