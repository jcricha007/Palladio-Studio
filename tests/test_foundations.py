from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from palladio.store import Library
from palladio.scene import ValidationError
from palladio.placement import active_terrain
from palladio.foundations import pad_ground
from palladio.commands import preview_commands,placement_warnings
from palladio.transfer import snapshot

class FoundationTests(unittest.TestCase):
    def setUp(self):
        temp=TemporaryDirectory();self.addCleanup(temp.cleanup);self.library=Library(Path(temp.name)/'p.sqlite3')
        self.p=self.library.create('Slope',None,elevation=json.loads(Path('examples/elevation-grid.json').read_text()))
        self.edit({'action':'assembly','assembly':{'kind':'room','yaw':25}});self.host=self.p['scene']['assemblies'][0]['id']
    def edit(self,*commands):self.p=self.library.commit(self.p['id'],self.p['revision'],list(commands));return self.p
    def fit(self):self.edit({'action':'assembly_place','id':self.host,'offset_m':1.2},{'action':'foundation_fit','id':self.host,'foundation':{'columns_x':3,'columns_z':3}})
    def test_rotated_pads_follow_ground_and_top_meets_host_without_terrain_mutation(self):
        baseline=deepcopy(self.p['baseline']);self.fit();host,foundation=self.p['scene']['assemblies'];spec=foundation['spec']
        self.assertEqual(self.p['baseline'],baseline);self.assertAlmostEqual(spec['position'][1]+spec['height'],host['spec']['position'][1])
        for offset,ground in zip(spec['support_offsets'],pad_ground(spec,active_terrain(self.p['baseline'],self.p['scene']))):self.assertAlmostEqual(spec['position'][1]+offset,ground)
        self.assertEqual(len(foundation['members']),21);self.assertGreater(max(spec['support_offsets']),0)
        self.assertEqual(self.library.import_snapshot(snapshot(self.p))['scene'],self.p['scene'])
    def test_refit_after_lowering_keeps_top_ids_overrides_and_restore(self):
        self.fit();foundation=deepcopy(self.p['scene']['assemblies'][1]);top=foundation['spec']['position'][1]+foundation['spec']['height'];member=foundation['members']['pier 1.1']
        self.edit({'action':'update','id':member,'element':{'material':'stone'}},{'action':'terrain_layer','layer':{'mode':'lower','center':[0,0],'radius_m':15,'amount_m':.4}})
        self.assertTrue(any('Refit' in warning for warning in placement_warnings(self.p,self.p['scene'])))
        self.edit({'action':'foundation_refit','id':foundation['id']});updated=self.p['scene']['assemblies'][1]
        self.assertEqual(updated['members'],foundation['members']);self.assertAlmostEqual(updated['spec']['position'][1]+updated['spec']['height'],top)
        self.assertEqual(next(e for e in self.p['scene']['elements'] if e['id']==member)['material'],'stone')
        self.assertFalse(any('Refit' in warning for warning in placement_warnings(self.p,self.p['scene'])))
    def test_insufficient_clearance_bad_grid_and_outside_site_roll_back(self):
        before=self.p
        for command in [{'action':'foundation_fit','id':self.host},{'action':'foundation_fit','id':self.host,'foundation':{'columns_x':True}}]:
            with self.assertRaises(ValidationError):self.edit(command)
        with self.assertRaises(ValidationError):self.edit({'action':'assembly_update','id':self.host,'assembly':{'position':[200,5,0]}},{'action':'foundation_fit','id':self.host})
        self.assertEqual(self.library.get(self.p['id']),before)
    def test_raise_and_fit_is_a_single_unsaved_preview(self):
        before=self.p;plan=preview_commands(self.p,self.p['revision'],[{'action':'assembly_place','id':self.host,'offset_m':1.2},{'action':'foundation_fit','id':self.host}])
        self.assertEqual(len(plan['scene']['assemblies']),2);self.assertEqual(self.library.get(self.p['id']),before)
        self.edit(*plan['commands']);self.assertEqual(self.p['revision'],before['revision']+1)
