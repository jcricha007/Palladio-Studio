"""Local immutable asset packets. Import never follows OBJ material paths or URLs."""
import hashlib
import json
from pathlib import Path
import re
from uuid import uuid4
from .geometry import MAX_TRIANGLES, MAX_VERTICES, mesh, normalize, surface_triangles, world_point
from .groups import owner
from .scene import ValidationError, number, required_text, vector


def import_obj(text, units):
    factors={'m':1,'cm':.01,'mm':.001,'in':.0254}
    if units not in factors: raise ValidationError('Choose OBJ units: m, cm, mm or in.')
    text=required_text(text,'OBJ contents',750000)
    points=[];triangles=[]
    for line in text.splitlines():
        tokens=line.split('#',1)[0].split()
        if not tokens: continue
        if tokens[0]=='v':
            if len(tokens)!=4: raise ValidationError('OBJ vertices need three coordinates.')
            try: points.append([number(float(v)*factors[units],'OBJ coordinate (m)',-10000,10000) for v in tokens[1:]])
            except ValueError as error: raise ValidationError('Invalid OBJ vertex.') from error
            if len(points)>MAX_VERTICES: raise ValidationError('Simplify this OBJ before importing it.')
        elif tokens[0]=='f':
            if len(tokens)!=4: raise ValidationError('Triangulate OBJ faces before importing.')
            try:
                face=[int(token.split('/')[0]) for token in tokens[1:]]
                if any(i==0 or i>len(points) or i < -len(points) for i in face): raise ValueError()
                triangles.extend(i-1 if i>0 else len(points)+i for i in face)
            except ValueError as error: raise ValidationError('Invalid OBJ face index.') from error
            if len(triangles)>MAX_TRIANGLES*3: raise ValidationError('Simplify this OBJ to at most 4096 triangles.')
        elif tokens[0] not in ('vn','vt','o','g','s','usemtl','mtllib'):
            raise ValidationError('Unsupported OBJ record. Export a triangulated mesh.')
    if not points or not triangles: raise ValidationError('OBJ contains no triangle geometry.')
    return normalize(points,triangles)


class AssetStore:
    def __init__(self,directory): self.path=Path(directory)
    def save(self,name,size,model,source):
        packet={'version':1,'name':required_text(name,'Asset name',80),'size':vector(size,'Asset size',.05,300),
                'mesh':mesh(model),'source':required_text(source,'Asset source',400)}
        raw=json.dumps(packet,sort_keys=True,separators=(',',':'),allow_nan=False)
        key=hashlib.sha256(raw.encode()).hexdigest()
        self.path.mkdir(parents=True,exist_ok=True)
        temporary=self.path/(uuid4().hex+'.tmp')
        try:
            temporary.write_text(raw,encoding='utf-8');temporary.replace(self.path/(key+'.json'))
        finally: temporary.unlink(missing_ok=True)
        return {**packet,'id':key}
    def get(self,key):
        if not isinstance(key,str) or not re.fullmatch('[a-f0-9]{64}',key): raise ValidationError('Choose a saved asset.')
        try:
            raw=(self.path/(key+'.json')).read_text(encoding='utf-8')
            if hashlib.sha256(raw.encode()).hexdigest()!=key: raise ValueError()
            data=json.loads(raw)
            if data['version']!=1: raise ValueError()
            mesh(data['mesh']);vector(data['size'],'Asset size',.05,300)
            return {**data,'id':key}
        except (OSError,ValueError,KeyError,TypeError) as error: raise ValidationError('Asset is missing or damaged. Import it again.') from error
    def list(self):
        items=[]
        for path in sorted(self.path.glob('*.json')):
            try:
                item=self.get(path.stem)
                items.append({k:v for k,v in item.items() if k!='mesh'} | {'triangles':len(item['mesh']['triangles'])//3})
            except ValidationError: continue
        return items
    def import_data(self,name,format,data,units='m'):
        if format=='obj':
            size,model=import_obj(data,units)
            return self.save(name,size,model,'Imported OBJ ('+units+'); material files not loaded')
        if format=='palladio':
            try: packet=json.loads(required_text(data,'Asset packet',900000))
            except (ValueError,RecursionError) as error: raise ValidationError('Invalid asset JSON.') from error
            if not isinstance(packet,dict) or packet.get('version')!=1: raise ValidationError('Use a version 1 Palladio asset packet.')
            return self.save(name,packet.get('size'),packet.get('mesh'),packet.get('source','Imported Palladio asset'))
        raise ValidationError('Choose OBJ or Palladio asset JSON.')
    def capture(self,project,selection,name):
        target=next((e for e in project['scene']['elements'] if e['id']==selection),None)
        if target is None: raise ValidationError('Select a scene element to capture.')
        group=owner(project['scene'],selection)
        parts=[e for e in project['scene']['elements'] if not group and e['id']==selection or group and e['id'] in group['members'].values()]
        vertices=[];triangles=[];colors=[]
        for part in parts:
            for points,tint in surface_triangles(part):
                triangles.extend(range(len(vertices),len(vertices)+3))
                vertices.extend(world_point(part,p) for p in points);colors.append(tint)
                if len(triangles)>MAX_TRIANGLES*3 or len(vertices)>MAX_VERTICES: raise ValidationError('This selection is too detailed to capture as one asset.')
        size,model=normalize(vertices,triangles,colors)
        return self.save(name,size,model,'Captured from '+project['name']+' revision '+str(project['revision']))
    def element(self,key,position,yaw=0):
        item=self.get(key)
        return {'kind':'block','name':item['name'],'material':'concrete','position':vector(position,'Asset position',-1000,1000),
                'yaw':number(yaw,'Asset rotation',-360,360),'size':item['size'],'mesh':item['mesh']}
