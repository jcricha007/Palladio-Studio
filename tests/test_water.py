from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from palladio.store import Library
from palladio.scene import ValidationError
from palladio.water import capacity
from palladio.assemblies import generate_assembly
from palladio.transfer import snapshot
from palladio.unreal import unreal_view
from palladio.assets import AssetStore
from palladio.__main__ import handler_for
from test_local_agent import running_server
import test_unreal

class WaterTests(unittest.TestCase):
    def setUp(self):
        temp=TemporaryDirectory();self.addCleanup(temp.cleanup);self.library=Library(Path(temp.name)/'p.sqlite3');self.p=self.library.create('Water','meadow')
    def edit(self,*commands):self.p=self.library.commit(self.p['id'],self.p['revision'],list(commands));return self.p
    def test_pool_volume_and_pond_mesh_are_bounded_and_water_is_non_solid(self):
        for kind in ('pool','pond'):
            spec,parts=generate_assembly({'kind':kind,'water_level':1.2});water=next(p for p in parts if p['role']=='water surface')
            self.assertFalse(water['collision']);self.assertTrue(all(p.get('collision',True) for p in parts if p is not water))
            self.assertAlmostEqual(water['position'][1]+water['size'][1],1.2)
            result=capacity(spec);self.assertGreater(result['litres'],0)
            if kind=='pool':self.assertAlmostEqual(result['water_volume_m3'],5.7*9.7*1.05)
            else:self.assertLess(result['surface_area_m2'],6*10);self.assertLess(len(water['mesh']['triangles'])//3,4096)
    def test_water_level_keeps_identity_and_roundtrips_through_native_and_transfer(self):
        self.edit({'action':'assembly','assembly':{'kind':'pond','position':[4,2,5],'yaw':42}});before=deepcopy(self.p);group=self.p['scene']['assemblies'][0];ids=group['members'].copy()
        self.edit({'action':'assembly_update','id':group['id'],'assembly':{'water_level':.8,'width':8}})
        self.assertEqual(self.p['scene']['assemblies'][0]['members'],ids)
        native=next(e for e in unreal_view(self.p)['elements'] if e['id']==ids['water surface']);self.assertFalse(native['collision']);self.assertIn('mesh_sections',native)
        self.assertEqual(self.library.import_snapshot(snapshot(self.p))['scene'],self.p['scene'])
        self.assertEqual(self.library.commit(self.p['id'],self.p['revision'],restore=before['revision'])['scene'],before['scene'])
    def test_invalid_levels_rollback_and_asset_capture_keeps_collision_semantics(self):
        for level in (0,1.5,float('nan'),True):
            with self.assertRaises(ValidationError):self.edit({'action':'assembly','assembly':{'kind':'pool','water_level':level}})
        self.assertEqual(self.p['revision'],1)
        self.edit({'action':'assembly','assembly':{'kind':'pool'}});group=self.p['scene']['assemblies'][0];key=group['members']['water surface'];assets=AssetStore(self.library.path.parent/'assets')
        with self.assertRaises(ValidationError):assets.capture(self.p,key,'Mixed')
        self.edit({'action':'assembly_detach','id':group['id']});asset=assets.capture(self.p,key,'Water only');self.assertFalse(asset['collision']);self.assertFalse(assets.element(asset['id'],[0,0,0])['collision'])
        import json
        self.assertFalse(assets.import_data('Water copy','palladio',json.dumps(asset))['collision'])
    def test_capacity_http_uses_saved_state(self):
        self.edit({'action':'assembly','assembly':{'kind':'pool'}})
        with running_server(handler_for(self.library)) as server:
            result=test_unreal.UnrealBridgeTest.read(f'http://127.0.0.1:{server.server_port}/api/properties/{self.p["id"]}/water-schedule')
            self.assertEqual(result['revision'],2);self.assertEqual(result['features'][0]['name'],'Swimming pool');self.assertGreater(result['features'][0]['litres'],0)
