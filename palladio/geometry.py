"""Bounded triangle assets and matching procedural finish geometry."""
import math
import re
from .scene import ValidationError, number, vector, MATERIALS
MAX_TRIANGLES=4096
MAX_VERTICES=8192
COLOR=re.compile(r'#[0-9a-fA-F]{6}')
PATTERNS=('solid','wood','stone','tile','brick')


def color(value):
    if not isinstance(value,str) or not COLOR.fullmatch(value): raise ValidationError('Choose a six-digit hex colour.')
    return value.lower()


def finish(data):
    if not isinstance(data,dict) or not data.keys() <= {'color','pattern','scale_m','rotation','source_colors','accent_color'}:
        raise ValidationError('Choose supported finish fields.')
    pattern=data.get('pattern','solid')
    if pattern not in PATTERNS: raise ValidationError('Choose a supported surface pattern.')
    source=data.get('source_colors',False)
    if type(source) is not bool: raise ValidationError('Source colours must be true or false.')
    return {'color':color(data.get('color','#b78554')),'pattern':pattern,
            'scale_m':number(data.get('scale_m',.25),'Grain spacing (m)',.02,10),
            'rotation':number(data.get('rotation',0),'Pattern direction',-360,360),'source_colors':source,
            **({'accent_color':color(data['accent_color'])} if 'accent_color' in data else {})}


def mesh(data):
    if not isinstance(data,dict) or not data.keys() <= {'vertices','triangles','colors'}:
        raise ValidationError('Invalid triangle mesh.')
    vertices=data.get('vertices'); triangles=data.get('triangles')
    if not isinstance(vertices,list) or not 3<=len(vertices)<=MAX_VERTICES:
        raise ValidationError(f'Use 3–{MAX_VERTICES} mesh vertices.')
    vertices=[vector(p,'Normalized vertex',-1,1) for p in vertices]
    if any(not -.500001<=p[0]<=.500001 or not 0<=p[1]<=1.000001 or not -.500001<=p[2]<=.500001 for p in vertices):
        raise ValidationError('Mesh coordinates must fit the normalized bottom-centred box.')
    if not isinstance(triangles,list) or not 3<=len(triangles)<=MAX_TRIANGLES*3 or len(triangles)%3:
        raise ValidationError(f'Use 1–{MAX_TRIANGLES} triangles.')
    if any(type(i) is not int or not 0<=i<len(vertices) for i in triangles): raise ValidationError('Invalid mesh triangle index.')
    for i in range(0,len(triangles),3):
        a,b,c=(vertices[triangles[i+j]] for j in range(3))
        u=[b[j]-a[j] for j in range(3)];v=[c[j]-a[j] for j in range(3)]
        cross=[u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0]]
        if sum(x*x for x in cross)<1e-20: raise ValidationError('Remove degenerate mesh triangles before import.')
    result={'vertices':vertices,'triangles':triangles[:]}
    if 'colors' in data:
        colors=data['colors']
        if not isinstance(colors,list) or len(colors)!=len(triangles)//3: raise ValidationError('Provide one colour per triangle.')
        result['colors']=[color(c) for c in colors]
        if len(set(result['colors']))>64: raise ValidationError('Use at most 64 asset colours.')
    return result


def normalize(vertices, triangles, colors=None):
    low=[min(p[i] for p in vertices) for i in range(3)]
    high=[max(p[i] for p in vertices) for i in range(3)]
    size=[max(.05,high[i]-low[i]) for i in range(3)]
    if any(v>300 for v in size): raise ValidationError('Asset dimensions must not exceed 300 m.')
    origin=[(low[0]+high[0])/2,low[1],(low[2]+high[2])/2]
    normalized=[[max(0,(p[1]-origin[1])/size[1]) if i==1 else (p[i]-origin[i])/size[i] for i in range(3)] for p in vertices]
    return size,mesh({'vertices':normalized,'triangles':triangles,**({'colors':colors} if colors is not None else {})})


def raw_triangles(item):
    w,h,d=item['size']; appearance=item.get('finish',{})
    if 'mesh' in item:
        model=item['mesh'];points=[[p[0]*w,p[1]*h,p[2]*d] for p in model['vertices']]
        colors=model.get('colors')
        for i in range(0,len(model['triangles']),3):
            yield [points[j] for j in model['triangles'][i:i+3]],colors[i//3] if colors else None
        return
    corners=[[-w/2,0,-d/2],[w/2,0,-d/2],[w/2,0,d/2],[-w/2,0,d/2],
             [-w/2,h,-d/2],[w/2,h,-d/2],[w/2,h,d/2],[-w/2,h,d/2]]
    n=8 if appearance.get('pattern')=='wood' else 16 if appearance.get('pattern','solid')!='solid' else 1
    for a,b,c,d1 in [(0,1,2,3),(4,7,6,5),(0,4,5,1),(1,5,6,2),(2,6,7,3),(3,7,4,0)]:
        a,b,d1=corners[a],corners[b],corners[d1]
        def at(u,v): return [a[i]+(b[i]-a[i])*u+(d1[i]-a[i])*v for i in range(3)]
        for row in range(n):
            for col in range(n):
                p,q,r,s=at(col/n,row/n),at((col+1)/n,row/n),at((col+1)/n,(row+1)/n),at(col/n,(row+1)/n)
                yield [p,q,r],None
                yield [p,r,s],None


def surface_triangles(item):
    appearance=item.get('finish',{})
    base=appearance.get('color',MATERIALS[item['material']])
    for points,source in raw_triangles(item):
        shade=1
        chosen=source if source and appearance.get('source_colors',not appearance) else base
        pattern=appearance.get('pattern','solid')
        if pattern!='solid':
            centre=[sum(p[i] for p in points)/3 for i in range(3)]
            a,b,c=points;u=[b[i]-a[i] for i in range(3)];v=[c[i]-a[i] for i in range(3)]
            normal=[u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0]]
            axis=max(range(3),key=lambda i:abs(normal[i]));u,v=(centre[2],centre[1]) if axis==0 else (centre[0],centre[2]) if axis==1 else (centre[0],centre[1])
            angle=math.radians(appearance.get('rotation',0))
            u,v=u*math.cos(angle)-v*math.sin(angle),u*math.sin(angle)+v*math.cos(angle)
            scale=appearance.get('scale_m',.25)
            if pattern=='wood':
                phase=(u+.02*math.sin(v*7))/scale;shade=.72+.28*math.floor((math.sin(phase*2*math.pi)*.5+.5)*7+.5)/7
            elif pattern=='stone':shade=.65+.35*((math.floor(u/scale)*73856093 ^ math.floor(v/scale)*19349663)&7)/7
            else:
                row=math.floor(v/scale*(2 if pattern=='brick' else 1));x=u/scale+(row%2)*.5 if pattern=='brick' else u/scale
                y=v/scale*(2 if pattern=='brick' else 1)
                grout=min(x-math.floor(x),1-(x-math.floor(x)),y-math.floor(y),1-(y-math.floor(y)))<.07
                if grout:chosen=appearance.get('accent_color','#c8c1b7')
                elif pattern=='brick':shade=.88+.12*((math.floor(x)^row)&3)/3
        rgb=[int(chosen[i:i+2],16) for i in (1,3,5)]
        tint='#'+''.join(f'{min(255,max(0,math.floor(c*shade+.5))):02x}' for c in rgb)
        yield points,tint


def world_point(item,p):
    a=math.radians(item['yaw']);x,y,z=p;px,py,pz=item['position']
    return [px+x*math.cos(a)+z*math.sin(a),py+y,pz-x*math.sin(a)+z*math.cos(a)]
