"""Schematic basin geometry and analytic water capacity; no fluid simulation."""
import math
from .scene import ValidationError,number
from .parts import box_part,mesh_part

KINDS=('pool','pond')
SEGMENTS=32


def ring(width,depth,y,factor=1):
    return [[math.cos(i*2*math.pi/SEGMENTS)*width/2*factor,y,math.sin(i*2*math.pi/SEGMENTS)*depth/2*factor] for i in range(SEGMENTS)]


def ellipse(spec,role,width,depth,bottom,top,material,**extra):
    vertices=ring(width,depth,bottom)+ring(width,depth,top)
    faces=[list(reversed(range(SEGMENTS))),list(range(SEGMENTS,2*SEGMENTS))]
    faces += [[i,(i+1)%SEGMENTS,(i+1)%SEGMENTS+SEGMENTS,i+SEGMENTS] for i in range(SEGMENTS)]
    return mesh_part(spec,role,vertices,faces,material,**extra)


def water_parts(spec,data):
    h,w,d=spec['height'],spec['width'],spec['depth']
    spec['water_level']=number(data.get('water_level',max(.2,h-.2)),'Water height above basin bottom',.2,h-.1)
    level=spec['water_level'];parts=[]
    if spec['kind']=='pool':
        t=.15
        parts.append(box_part(spec,'basin floor',[0,0,0],[w,t,d]))
        for sign,label in [(-1,'west'),(1,'east')]:parts.append(box_part(spec,label+' wall',[sign*(w-t)/2,t,0],[t,h-t,d]))
        for sign,label in [(-1,'north'),(1,'south')]:parts.append(box_part(spec,label+' wall',[0,t,sign*(d-t)/2],[w-2*t,h-t,t]))
        for sign,label in [(-1,'west'),(1,'east')]:parts.append(box_part(spec,label+' coping',[sign*(w-t)/2,h,0],[t+.2,.1,d+.2]))
        for sign,label in [(-1,'north'),(1,'south')]:parts.append(box_part(spec,label+' coping',[0,h,sign*(d-t)/2],[w-2*t-.2,.1,t+.2]))
        parts.append(box_part(spec,'water surface',[0,level-.05,0],[w-2*t,.05,d-2*t],'water',collision=False))
    else:
        parts.append(ellipse(spec,'pond bed',w*.65,d*.65,0,.1,spec['material']))
        outer=ring(w,d,h);outer_base=ring(w,d,0);inner=ring(w,d,.1,.65);inner_base=ring(w,d,0,.65)
        for i in range(SEGMENTS):
            j=(i+1)%SEGMENTS
            vertices=[outer_base[i],outer_base[j],inner_base[j],inner_base[i],outer[i],outer[j],inner[j],inner[i]]
            faces=[[0,3,2,1],[4,5,6,7],[0,1,5,4],[1,2,6,5],[2,3,7,6],[3,0,4,7]]
            parts.append(mesh_part(spec,f'bank {i+1}',vertices,faces))
        factor=.65+.35*(level-.1)/(h-.1)
        parts.append(ellipse(spec,'water surface',w*factor,d*factor,level-.05,level,'water',collision=False))
    return spec,parts


def capacity(spec):
    w,d,h,level=spec['width'],spec['depth'],spec['height'],spec['water_level']
    if spec['kind']=='pool':area=(w-.3)*(d-.3);volume=area*(level-.15)
    elif spec['kind']=='pond':
        # The rendered basin uses a 32-sided ellipse, so use its polygon area factor.
        base=SEGMENTS/2*math.sin(2*math.pi/SEGMENTS)*w*d/4
        factor=.65+.35*(level-.1)/(h-.1);area=base*factor**2
        volume=base*(level-.1)/3*(.65**2+.65*factor+factor**2)
    else:raise ValidationError('Choose a pool or pond.')
    return {'surface_area_m2':area,'water_volume_m3':volume,'litres':volume*1000,'water_depth_m':level-(.15 if spec['kind']=='pool' else .1)}
