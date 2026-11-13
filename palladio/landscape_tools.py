"""Reversible design terrain layers; source terrain stays immutable."""
from copy import deepcopy
import math
from uuid import uuid4
from .scene import ValidationError, number, required_text
from .placement import active_terrain, height_at


def validated_layer(data, terrain):
    if not isinstance(data, dict) or not data.keys() <= {'name','mode','center','radius_m','amount_m','height_m'}:
        raise ValidationError('Choose supported terrain layer fields.')
    mode=data.get('mode')
    if mode not in ('raise','lower','flatten'):
        raise ValidationError('Choose raise, lower or flatten.')
    center=data.get('center')
    if not isinstance(center,list) or len(center)!=2:
        raise ValidationError('Terrain centre needs X and Z coordinates.')
    center=[number(v,'Terrain centre',-1000,1000) for v in center]
    height_at(terrain,*center)
    layer={'id':str(uuid4()),'enabled':True,'name':required_text(data.get('name',mode.capitalize()+' ground'),'Terrain layer name',80),
           'mode':mode,'center':center,'radius_m':number(data.get('radius_m'),'Brush radius',terrain['spacing'],128)}
    if mode=='flatten': layer['height_m']=number(data.get('height_m'),'Target local height',-200,200)
    else: layer['amount_m']=number(data.get('amount_m'),'Height change',.01,20)
    return layer


def rebuild(baseline, layers):
    terrain=deepcopy(baseline['terrain'])
    n,spacing=terrain['size'],terrain['spacing']; edge=(n-1)*spacing/2
    for layer in layers:
        if not layer['enabled']: continue
        cx,cz=layer['center']; radius=layer['radius_m']
        for row in range(n):
            z=row*spacing-edge
            for col in range(n):
                x=col*spacing-edge; distance=math.hypot(x-cx,z-cz)
                if distance>=radius: continue
                weight=(1-distance/radius)**2
                i=row*n+col; old=terrain['heights'][i]
                if layer['mode']=='flatten':
                    weight=min(1,(1-distance/radius)/.35)**2
                    value=old+(layer['height_m']-old)*weight
                else: value=old+layer['amount_m']*weight*(1 if layer['mode']=='raise' else -1)
                terrain['heights'][i]=number(value,'Edited ground height',-500,500)
    return terrain


def edit_terrain(scene, command, baseline):
    if baseline is None: raise ValidationError('Terrain tools require a saved property.')
    layers=deepcopy(scene.get('terrain_layers',[]))
    action=command['action']
    if action=='terrain_layer':
        if len(layers)>=128: raise ValidationError('A design supports at most 128 terrain layers.')
        layers.append(validated_layer(command.get('layer'),baseline['terrain']))
        label='Added '+layers[-1]['name']
    elif action=='terrain_restore':
        scene.pop('terrain',None); scene.pop('terrain_layers',None)
        return 'Restored original ground; architecture retained'
    else:
        layer=next((x for x in layers if x['id']==command.get('id')),None)
        if layer is None: raise ValidationError('This terrain layer no longer exists.')
        if action=='terrain_remove': layers.remove(layer); label='Removed '+layer['name']
        elif action=='terrain_toggle':
            enabled=command.get('enabled')
            if type(enabled) is not bool: raise ValidationError('Layer visibility must be true or false.')
            layer['enabled']=enabled;label=('Enabled ' if enabled else 'Disabled ')+layer['name']
        else: raise ValidationError('Unknown terrain command.')
    scene['terrain']=rebuild(baseline,layers)
    scene['terrain_layers']=layers
    return label


def design_landscape(baseline, scene):
    terrain=active_terrain(baseline,scene)
    vegetation=deepcopy(baseline['vegetation'])
    for tree in vegetation:
        x,_,z=tree['position']; tree['position'][1]=height_at(terrain,x,z)
    return {**baseline,'terrain':terrain,'vegetation':vegetation}
