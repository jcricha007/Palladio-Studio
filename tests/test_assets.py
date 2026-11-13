import copy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Thread
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
import unittest

from palladio.__main__ import handler_for
from palladio.assets import AssetStore, import_obj
from palladio.geometry import surface_triangles, world_point
from palladio.scene import ValidationError
from palladio.store import Library
from palladio.unreal import unreal_view, unreal_vector
import test_unreal

OBJ = 'mtllib ../../private.mtl\nv 0 0 0\nv 100 0 0\nv 0 100 50\nf -3 -2 -1\n'


class AssetTests(unittest.TestCase):
    def setUp(self):
        temp=TemporaryDirectory();self.addCleanup(temp.cleanup)
        self.library=Library(Path(temp.name)/'properties.sqlite3')
        self.assets=AssetStore(Path(temp.name)/'properties-assets')
        self.p=self.library.create('Assets','meadow')
    def edit(self,*commands):
        self.p=self.library.commit(self.p['id'],self.p['revision'],list(commands));return self.p
    def test_obj_units_negative_indices_and_invalid_geometry(self):
        size,model=import_obj(OBJ,'cm')
        self.assertEqual(size,[1,1,.5]);self.assertEqual(model['triangles'],[0,1,2])
        self.assertEqual(model['vertices'][2],[-.5,1,.5])
        for bad in [OBJ.replace('-3 -2 -1','1 2 3 1'),OBJ.replace('-3 -2 -1','0 2 3'),
                    OBJ.replace('100 50','nan 50'),OBJ.replace('-3 -2 -1','1 1 2'),
                    OBJ+'call remote.obj\n']:
            with self.subTest(bad=bad),self.assertRaises(ValidationError): import_obj(bad,'cm')
        with self.assertRaises(ValidationError): import_obj(OBJ,'feet')
    def test_export_import_and_embedded_instances_survive_missing_cache(self):
        asset=self.assets.import_data('Chair','obj',OBJ,'cm')
        again=self.assets.import_data('Chair','palladio',json.dumps(asset))
        self.assertEqual(asset,again)
        item=self.assets.element(asset['id'],[4,2,6],30)
        self.edit({'action':'add','element':item})
        (self.assets.path/(asset['id']+'.json')).unlink()
        reopened=Library(self.library.path).get(self.p['id'])
        self.assertEqual(reopened,self.p)
        native=unreal_view(reopened)['elements'][0]
        self.assertEqual(native['center_cm'],[400,600,250])
        self.assertEqual(native['mesh_sections'][0]['vertices_cm'],[[-50,-25,0],[50,-25,0],[-50,25,100]])
        self.assertEqual(self.assets.list(),[])
    def test_finish_override_survives_resize_and_reset(self):
        self.edit({'action':'assembly','assembly':{'kind':'room'}})
        group=self.p['scene']['assemblies'][0];member=next(iter(group['members'].values()))
        finish={'color':'#ABCDEF','pattern':'wood','scale_m':.4,'rotation':90}
        self.edit({'action':'update','id':member,'element':{'finish':finish}},
                  {'action':'assembly_update','id':group['id'],'assembly':{'width':9}})
        item=next(e for e in self.p['scene']['elements'] if e['id']==member)
        self.assertEqual(item['finish']['color'],'#abcdef')
        native=next(e for e in unreal_view(self.p)['elements'] if e['id']==member)
        self.assertEqual(sum(len(s['triangles'])//3 for s in native['mesh_sections']),768)
        self.assertGreater(len(native['mesh_sections']),1)
        self.edit({'action':'update','id':member,'element':{'finish':None}},
                  {'action':'assembly_update','id':group['id'],'assembly':{'width':8}})
        self.assertNotIn('finish',next(e for e in self.p['scene']['elements'] if e['id']==member))
    def test_capture_whole_group_preserves_world_geometry_and_colors(self):
        self.edit({'action':'assembly','assembly':{'kind':'stairs','position':[4,2,-3],'yaw':25}})
        item=self.p['scene']['elements'][0]
        self.edit({'action':'update','id':item['id'],'element':{'finish':{'color':'#884422'}}})
        before=copy.deepcopy(self.p)
        asset=self.assets.capture(self.p,item['id'],'Custom terrace')
        self.assertEqual(self.library.get(self.p['id']),before)
        expected=[world_point(e,p) for e in self.p['scene']['elements'] for tri,_ in surface_triangles(e) for p in tri]
        actual=asset['mesh']['vertices'];self.assertEqual(len(actual),len(expected))
        low=[min(p[i] for p in expected) for i in range(3)];high=[max(p[i] for p in expected) for i in range(3)]
        origin=[(low[0]+high[0])/2,low[1],(low[2]+high[2])/2]
        for original,normalized in zip(expected,actual):
            for i in range(3): self.assertAlmostEqual(original[i],normalized[i]*asset['size'][i]+origin[i])
        self.assertIn('#884422',asset['mesh']['colors'])
    def test_invalid_packets_and_tampered_assets_do_not_modify_scene(self):
        for packet in [{'version':2},{'version':1,'size':[1,1,1],'mesh':{}},
                       {'version':1,'size':[1,1,1],'mesh':{'vertices':[[0,0,0]]*3,'triangles':[0,1,2]}}]:
            with self.assertRaises(ValidationError): self.assets.import_data('Bad','palladio',json.dumps(packet))
        self.assertEqual(self.assets.list(),[])
        asset=self.assets.import_data('Good','obj',OBJ,'cm')
        (self.assets.path/(asset['id']+'.json')).write_text('{}')
        with self.assertRaises(ValidationError): self.assets.get(asset['id'])
        self.assertEqual(self.assets.list(),[]);self.assertEqual(self.library.get(self.p['id']),self.p)
    def test_http_preview_and_stale_capture(self):
        with ThreadingHTTPServer(('127.0.0.1',0),handler_for(self.library)) as server:
            worker=Thread(target=server.serve_forever);worker.start()
            try:
                root=f'http://127.0.0.1:{server.server_port}';read=test_unreal.UnrealBridgeTest.read
                asset=read(root+'/api/assets/import',{'name':'Imported','format':'obj','units':'cm','data':OBJ})
                url=root+'/api/properties/'+self.p['id']
                plan=read(url+'/asset-preview',{'revision':1,'asset_id':asset['id'],'position':[0,0,0]})
                self.assertEqual(self.library.get(self.p['id']),self.p)
                saved=read(url+'/edit',{'revision':1,'commands':plan['commands']})
                with self.assertRaises(HTTPError) as stale:
                    read(url+'/asset-capture',{'revision':1,'selection':saved['scene']['elements'][0]['id'],'name':'Stale'})
                self.assertEqual(stale.exception.code,409);self.assertEqual(len(self.assets.list()),1)
                packet=read(root+'/api/assets/'+asset['id']);self.assertIn('mesh',packet)
            finally: server.shutdown();worker.join()
