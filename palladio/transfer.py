"""Portable, self-contained property snapshots; imports always create a new property."""
from copy import deepcopy
import hashlib
import json
from uuid import UUID
from .scene import ValidationError, element, edit_scene, number, required_text, vector
from .groups import regenerate
from .landscape_tools import validated_layer, rebuild
from .references import details, image

MAX_BYTES = 20_000_000


def canonical(data):
    try: return json.dumps(data,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
    except (TypeError,ValueError,RecursionError) as error: raise ValidationError('Snapshot contains invalid JSON values.') from error


def identifier(value):
    try:
        if not isinstance(value,str) or str(UUID(value)) != value: raise ValueError()
    except ValueError as error: raise ValidationError('Snapshot IDs must be canonical UUIDs.') from error
    return value


def sequence(value,limit,label):
    if not isinstance(value,list) or len(value)>limit: raise ValidationError(f'{label} exceeds the supported snapshot limit.')
    return value


def snapshot(project):
    payload={key:deepcopy(project[key]) for key in ('name','baseline','scene')}
    result={'format':'palladio-property','version':1,'source_revision':project['revision'],
            'payload':payload,'sha256':hashlib.sha256(canonical(payload)).hexdigest()}
    if len(canonical(result))>MAX_BYTES: raise ValidationError('Snapshot exceeds the 20 MB transfer limit.')
    return result


def validate(packet):
    if not isinstance(packet,dict) or packet.get('format')!='palladio-property' or type(packet.get('version')) is not int or packet['version']!=1:
        raise ValidationError('Choose a version 1 Palladio property snapshot.')
    if len(canonical(packet))>MAX_BYTES: raise ValidationError('Snapshot exceeds the 20 MB transfer limit.')
    payload=packet.get('payload')
    if hashlib.sha256(canonical(payload)).hexdigest()!=packet.get('sha256'): raise ValidationError('Snapshot checksum failed. Export a new copy.')
    try:
        if set(payload)!={'name','baseline','scene'}: raise ValueError()
        name=required_text(payload['name'],'Property name',100)
        baseline=deepcopy(payload['baseline']);scene=deepcopy(payload['scene'])
        terrain=baseline['terrain'];n=terrain['size'];spacing=number(terrain['spacing'],'Sample spacing',.25,100)
        if type(n) is not int or n%2!=1 or not 3<=n<=129 or not 20<=(n-1)*spacing<=256: raise ValueError()
        heights=sequence(terrain['heights'],129**2,'Terrain')
        if len(heights)!=n*n: raise ValueError()
        for height in heights: number(height,'Ground height',-200,200)
        source=baseline['source']
        if source['kind'] not in ('procedural','elevation grid'): raise ValueError()
        required_text(source['profile'],'Site profile',100)
        if source['kind']=='elevation grid':
            for key,limit in [('dataset',200),('vertical_datum',120)]: required_text(source[key],key,limit)
            number(source['latitude'],'Latitude',-90,90);number(source['longitude'],'Longitude',-180,180)
            number(source['origin_elevation_m'],'Origin height',-12000,10000)
            if 'acquisition' in source:
                from .terrain import surveyed_landscape
                checked=surveyed_landscape({'version':1,'size':n,'spacing_m':spacing,
                    'latitude':source['latitude'],'longitude':source['longitude'],'dataset':source['dataset'],
                    'vertical_datum':source['vertical_datum'],'elevations_m':[h+source['origin_elevation_m'] for h in heights],
                    'acquisition':source['acquisition']})
                baseline['source']['acquisition']=checked['source']['acquisition']
        for tree in sequence(baseline['vegetation'],5000,'Vegetation'):
            vector(tree['position'],'Tree position',-1000,1000);number(tree['height'],'Tree height',.05,100)
            from .placement import height_at
            height_at(terrain,tree['position'][0],tree['position'][2])
        for environment in (baseline['environment'],scene['environment']):
            # A snapshot is a full scene, not a partial weather/time edit.
            if not isinstance(environment, dict) or set(environment) != {'hour', 'weather'}:
                raise ValueError()
            edit_scene({'environment':{'weather':'clear','hour':16}}, {'action':'environment','environment':environment})
        if not scene.keys() <= {'elements','environment','assemblies','terrain','terrain_layers','references','finishes','views'}: raise ValueError()
        view_ids=set();view_names=set()
        for view in sequence(scene.get('views',[]),24,'Views'):
            from .presentation import camera
            key=identifier(view['id']);label=required_text(view['name'],'View name',80)
            if key in view_ids or label.casefold() in view_names or set(view)!={'id','name','camera'} or camera(view['camera'])!=view['camera']:raise ValueError()
            view_ids.add(key);view_names.add(label.casefold())
        finish_ids=set();finish_names=set()
        for preset in sequence(scene.get('finishes',[]),32,'Finishes'):
            from .geometry import finish
            key=identifier(preset['id']);label=required_text(preset['name'],'Finish name',80)
            if key in finish_ids or label.casefold() in finish_names or set(preset)!={'id','name','finish'} or finish(preset['finish'])!=preset['finish']:raise ValueError()
            finish_ids.add(key);finish_names.add(label.casefold())
        ids=set();elements=[]
        for item in sequence(scene['elements'],5000,'Elements'):
            key=identifier(item['id'])
            if key in ids: raise ValueError()
            ids.add(key);checked={**element(item),'id':key}
            if 'role' in item: checked['role']=required_text(item['role'],'Part role',120)
            if checked!=item: raise ValueError()
            elements.append(checked)
        used=set();group_ids=set()
        for group in sequence(scene.get('assemblies',[]),500,'Assemblies'):
            if not group.keys()<={'id','members','spec','overrides','ground_anchor'}:raise ValueError()
            if 'ground_anchor' in group:
                from .planting import PLANTS
                from .placement import active_terrain,height_at
                if group['spec']['kind'] not in PLANTS or set(group['ground_anchor'])!={'offset_m'}:raise ValueError()
                offset=number(group['ground_anchor']['offset_m'],'Ground offset',-5,50)
                x,y,z=group['spec']['position']
                if abs(y-height_at(active_terrain(baseline,scene),x,z)-offset)>1e-8:raise ValueError()
            key=identifier(group['id'])
            if key in group_ids or key in ids: raise ValueError()
            group_ids.add(key)
            if not isinstance(group['members'],dict) or set(group['members'].values())-ids: raise ValueError()
            members=set(group['members'].values())
            if len(members)!=len(group['members']) or members & used: raise ValueError()
            used |= members
            for override in group.get('overrides',{}).values():
                if not isinstance(override,dict) or not override.keys()<={'name','material','finish'}: raise ValueError()
            check={'elements':[]};generated=deepcopy(group);regenerate(check,generated,group['spec'])
            if generated!=group or {p['id']:p for p in check['elements']}!={p['id']:p for p in elements if p['id'] in members}: raise ValueError()
        layers=[];layer_ids=set()
        for layer in sequence(scene.get('terrain_layers',[]),128,'Terrain layers'):
            key=identifier(layer['id'])
            if key in layer_ids or type(layer['enabled']) is not bool: raise ValueError()
            layer_ids.add(key)
            checked=validated_layer({k:v for k,v in layer.items() if k not in ('id','enabled')},terrain)
            checked.update(id=key,enabled=layer['enabled']);layers.append(checked)
            if checked!=layer: raise ValueError()
        if ('terrain' in scene)!=('terrain_layers' in scene): raise ValueError()
        if 'terrain' in scene and rebuild(baseline,layers)!=scene['terrain']: raise ValueError()
        ref_ids=set()
        for ref in sequence(scene.get('references',[]),6,'References'):
            key=identifier(ref['id'])
            if key in ref_ids: raise ValueError()
            ref_ids.add(key)
            checked={**details({k:ref[k] for k in ('name','cues')}),**image(ref['data']),'id':key}
            if checked!=ref: raise ValueError()
        return name,baseline,scene
    except (KeyError,TypeError,ValueError,AttributeError,RecursionError) as error:
        raise ValidationError('Snapshot structure or scene data is invalid; no property was imported.') from error
