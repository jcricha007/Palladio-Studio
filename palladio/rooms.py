"""Connected rectangular room grids with shared partitions and clear door openings."""
import math
from .scene import ValidationError,element,number


def room_schedule(spec):
    cols,rows=spec['rooms_x'],spec['rooms_z'];w=spec['width']/cols;d=spec['depth']/rows
    result=[]
    for row in range(rows):
        for col in range(cols):
            width=w-(.2 if col==0 else .075)-(.2 if col==cols-1 else .075)
            depth=d-(.2 if row==0 else .075)-(.2 if row==rows-1 else .075)
            result.append({'name':f'Room {row+1}.{col+1}','clear_width_m':width,'clear_depth_m':depth,'area_m2':width*depth})
    return result


def dwelling(spec,data):
    for key in ('rooms_x','rooms_z'):
        value=data.get(key,2)
        if type(value) is not int or not 1<=value<=4: raise ValidationError('Choose one to four room columns/rows.')
        spec[key]=value
    if any(key in data for key in ('overhang','steps','window_width','window_height','window_sill')):
        raise ValidationError('Dwelling grids support door dimensions; roof, stair and window parameters use their own tools.')
    cols,rows=spec['rooms_x'],spec['rooms_z'];w,d,h=spec['width'],spec['depth'],spec['height'];cw,cd=w/cols,d/rows
    if min(cw,cd)<2.4: raise ValidationError('Each room cell must span at least 2.4 m before wall thickness.')
    spec['door_width']=number(data.get('door_width',.9),'Door width',.6,min(cw,cd)-.6)
    spec['door_height']=number(data.get('door_height',2.1),'Door height',1,h-.15)
    dw,dh=spec['door_width'],spec['door_height'];angle=math.radians(spec['yaw']);pieces=[]
    def add(role,pos,size,kind='wall',material=None):
        x,y,z=pos;px,py,pz=spec['position']
        pieces.append({**element({'kind':kind,'name':spec['name']+' · '+role,'material':material or spec['material'],
            'position':[px+x*math.cos(angle)+z*math.sin(angle),py+y,pz-x*math.sin(angle)+z*math.cos(angle)],
            'size':size,'yaw':spec['yaw']}),'role':role+':1'})
    for row in range(rows):
        for col in range(cols):add(f'room {row+1}.{col+1} slab',[-w/2+(col+.5)*cw,0,-d/2+(row+.5)*cd],[cw,.15,cd],'floor','concrete')
    add('roof',[0,h+.15,0],[w+.4,.2,d+.4],'roof')
    for sign,label in [(-1,'west'),(1,'east')]:add(label,[sign*(w/2-.1),.15,0],[.2,h,d])
    # The entry is centred on the front-left room, away from shared partitions.
    entry=-w/2+cw/2;left=-w/2+.2;right=w/2-.2
    for label,a,b in [('entry left',left,entry-dw/2),('entry right',entry+dw/2,right)]:add(label,[(a+b)/2,.15,d/2-.1],[b-a,h,.2])
    add('entry lintel',[entry,dh+.15,d/2-.1],[dw,h-dh,.2])
    for col in range(cols):
        x=-w/2+(col+.5)*cw;ww=min(2,cw*.5);low=-w/2+col*cw+(.2 if col==0 else 0);high=-w/2+(col+1)*cw-(.2 if col==cols-1 else 0)
        for label,a,b in [('left',low,x-ww/2),('right',x+ww/2,high)]:add(f'window {col+1} {label}',[(a+b)/2,.15,-d/2+.1],[b-a,h,.2])
        add(f'window {col+1} sill',[x,.15,-d/2+.1],[ww,.9,.2])
        add(f'window {col+1} header',[x,2.25,-d/2+.1],[ww,h-2.1,.2])
        add(f'window {col+1} glazing',[x,1.05,-d/2+.1],[ww,1.2,.06],'glazing','glass')
    # Each shared cell edge appears once; its doorway connects adjacent rooms.
    for col in range(1,cols):
        for row in range(1,rows):add(f'junction {col}.{row}',[-w/2+col*cw,.15,-d/2+row*cd],[.15,h,.15],'column')
    for col in range(1,cols):
        x=-w/2+col*cw
        for row in range(rows):
            z=-d/2+(row+.5)*cd
            lo=-d/2+row*cd+(.2 if row==0 else .075);hi=-d/2+(row+1)*cd-(.2 if row==rows-1 else .075)
            for label,a,b in [('a',lo,z-dw/2),('b',z+dw/2,hi)]:add(f'partition X{col}.{row+1} {label}',[x,.15,(a+b)/2],[.15,h,b-a])
            add(f'partition X{col}.{row+1} lintel',[x,.15+dh,z],[.15,h-dh,dw])
    for row in range(1,rows):
        z=-d/2+row*cd
        for col in range(cols):
            x=-w/2+(col+.5)*cw;lo=-w/2+col*cw+(.2 if col==0 else .075);hi=-w/2+(col+1)*cw-(.2 if col==cols-1 else .075)
            for label,a,b in [('a',lo,x-dw/2),('b',x+dw/2,hi)]:add(f'partition Z{row}.{col+1} {label}',[(a+b)/2,.15,z],[b-a,h,.15])
            add(f'partition Z{row}.{col+1} lintel',[x,.15+dh,z],[dw,h-dh,.15])
    return spec,pieces
