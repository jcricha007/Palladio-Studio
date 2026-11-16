"""Shared local-to-world construction of named, stable assembly parts."""
import math
from .scene import element


def box_part(spec, role, position, size, material=None, kind='block', **extra):
    x,y,z=position;px,py,pz=spec['position'];angle=math.radians(spec['yaw'])
    return {**element({'kind':kind,'name':f"{spec['name']} · {role}"[:100],
        'material':material or spec['material'],'position':[px+x*math.cos(angle)+z*math.sin(angle),py+y,pz-x*math.sin(angle)+z*math.cos(angle)],
        'size':size,'yaw':spec['yaw'],**extra}),'role':role}
