import copy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from urllib.error import HTTPError
from palladio.store import Library
from palladio.scene import ValidationError
from palladio.presentation import scene_obj
from palladio.transfer import snapshot
from palladio.__main__ import handler_for
from test_local_agent import running_server
import test_unreal

CAMERA={'target':[2,3,4],'azimuth':-.5,'pitch':.8,'distance':40}
class PresentationTests(unittest.TestCase):
    def setUp(self):
        temp=TemporaryDirectory();self.addCleanup(temp.cleanup);self.library=Library(Path(temp.name)/'p.sqlite3');self.p=self.library.create('Views','meadow')
    def edit(self,*commands):self.p=self.library.commit(self.p['id'],self.p['revision'],list(commands));return self.p
    def test_views_persist_update_restore_and_transfer_without_geometry_changes(self):
        self.edit({'action':'view_save','name':'Front','camera':CAMERA});view=self.p['scene']['views'][0]
        self.edit({'action':'view_update','id':view['id'],'name':'Approach','camera':{**CAMERA,'distance':80}})
        self.assertEqual(self.p['scene']['views'][0]['id'],view['id']);self.assertEqual(self.p['scene']['elements'],[])
        self.assertEqual(Library(self.library.path).get(self.p['id']),self.p)
        self.assertEqual(self.library.import_snapshot(snapshot(self.p))['scene'],self.p['scene'])
        self.edit({'action':'view_remove','id':view['id']});self.assertFalse(self.p['scene']['views'])
        restored=self.library.commit(self.p['id'],self.p['revision'],restore=2);self.assertEqual(restored['scene']['views'],[view])
    def test_invalid_camera_and_duplicate_names_are_atomic(self):
        for bad in [{**CAMERA,'pitch':4},{**CAMERA,'distance':float('nan')},{**CAMERA,'target':[0,0]}]:
            with self.assertRaises(ValidationError):self.edit({'action':'view_save','name':'Bad','camera':bad})
        with self.assertRaises(ValidationError):self.edit({'action':'view_save','name':'Front','camera':CAMERA},{'action':'view_save','name':'front','camera':CAMERA})
        self.assertEqual(self.library.get(self.p['id'])['revision'],1)
    def test_geometry_export_is_world_space_bounded_and_revision_checked(self):
        self.edit({'action':'add','element':{'name':'Box','kind':'block','material':'stone','size':[2,3,4],'position':[10,2,20],'yaw':90}})
        before=copy.deepcopy(self.p);result=scene_obj(self.p,False);self.assertEqual(result['triangles'],12)
        vertices=[list(map(float,line.split()[1:])) for line in result['obj'].splitlines() if line.startswith('v ')]
        self.assertEqual([min(p[i] for p in vertices) for i in range(3)],[8,2,19]);self.assertEqual([max(p[i] for p in vertices) for i in range(3)],[12,5,21])
        faces=[list(map(int,line.split()[1:])) for line in result['obj'].splitlines() if line.startswith('f ')];self.assertEqual(faces[-1],[34,35,36])
        self.assertGreater(scene_obj(self.p)['triangles'],12);self.assertEqual(self.library.get(self.p['id']),before)
        big=copy.deepcopy(self.p);big['scene']['elements']*=8334
        with self.assertRaises(ValidationError):scene_obj(big,False)
        with running_server(handler_for(self.library)) as server:
            url=f'http://127.0.0.1:{server.server_port}/api/properties/{self.p["id"]}/geometry-export'
            self.assertEqual(test_unreal.UnrealBridgeTest.read(url,{'revision':2,'terrain':False}),result)
            with self.assertRaises(HTTPError) as stale:test_unreal.UnrealBridgeTest.read(url,{'revision':1})
            self.assertEqual(stale.exception.code,409)
