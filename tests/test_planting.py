from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from palladio.commands import preview_commands
from palladio.placement import height_at,active_terrain
from palladio.scene import ValidationError
from palladio.store import Library
from palladio.transfer import snapshot
from palladio.unreal import unreal_view

class PlantingTests(unittest.TestCase):
    def setUp(self):
        tmp=TemporaryDirectory();self.addCleanup(tmp.cleanup);self.lib=Library(Path(tmp.name)/'data.db');self.p=self.lib.create('Garden','wooded hillside')
        self.command={'action':'planting','planting':{'kind':'pine','center':[20,20],'count':4,'seed':17,'radius_m':6,'offset_m':.2}}
    def test_repeatable_preview_and_ground_following_preserve_original_site(self):
        a=preview_commands(self.p,1,[self.command]);b=preview_commands(self.p,1,[self.command])
        self.assertEqual([g['spec'] for g in a['scene']['assemblies']],[g['spec'] for g in b['scene']['assemblies']])
        p=self.lib.commit(self.p['id'],1,[self.command]);ids=[g['members'] for g in p['scene']['assemblies']]
        initial=deepcopy(p['scene']['elements'])
        p=self.lib.commit(p['id'],2,[{'action':'terrain_layer','layer':{'mode':'raise','center':[20,20],'radius_m':20,'amount_m':4}}])
        for g in p['scene']['assemblies']:
            x,y,z=g['spec']['position'];self.assertAlmostEqual(y,height_at(p['scene']['terrain'],x,z)+.2)
        self.assertEqual([g['members'] for g in p['scene']['assemblies']],ids);self.assertEqual(p['baseline'],self.p['baseline'])
        restored=self.lib.commit(p['id'],3,[{'action':'terrain_restore'}]);self.assertEqual(restored['scene']['elements'],initial)
        for g in restored['scene']['assemblies']:
            x,y,z=g['spec']['position'];self.assertAlmostEqual(y,height_at(restored['baseline']['terrain'],x,z)+.2)
        self.assertEqual(self.lib.import_snapshot(snapshot(restored))['scene'],restored['scene'])
    def test_move_copy_offset_detach_and_native_mesh(self):
        p=self.lib.commit(self.p['id'],1,[self.command]);g=p['scene']['assemblies'][0];old=g['spec']['position']
        p=self.lib.commit(p['id'],2,[{'action':'assembly_update','id':g['id'],'assembly':{'position':[25,old[1]+1,25]}},
            {'action':'assembly_duplicate','id':g['id'],'position':[30,old[1]+1,30]}])
        current=p['scene']['assemblies'][0];self.assertAlmostEqual(current['ground_anchor']['offset_m'],1.2)
        self.assertIn('mesh_sections',unreal_view(p)['elements'][1])
        key=next(iter(current['members'].values()));p=self.lib.commit(p['id'],3,[{'action':'assembly_detach','id':g['id']},{'action':'update','id':key,'element':{'position':[1,1,1]}}])
        self.assertEqual(next(e for e in p['scene']['elements'] if e['id']==key)['position'],[1,1,1])
    def test_outside_terrain_batch_is_atomic(self):
        bad=deepcopy(self.command);bad['planting']['center']=[900,900]
        with self.assertRaises(ValidationError):self.lib.commit(self.p['id'],1,[self.command,bad])
        self.assertEqual(self.lib.get(self.p['id']),self.p)
