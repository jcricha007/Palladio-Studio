import copy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from palladio.assemblies import generate_assembly
from palladio.commands import preview_commands
from palladio.landscape_tools import design_landscape
from palladio.placement import height_at
from palladio.scene import ValidationError
from palladio.store import Library
from palladio.unreal import unreal_view

class LandscapeToolsTests(unittest.TestCase):
    def setUp(self):
        temp=TemporaryDirectory();self.addCleanup(temp.cleanup)
        self.lib=Library(Path(temp.name)/'test.sqlite3')
        self.p=self.lib.create('Garden','wooded hills',True)
    def commit(self,*commands):
        self.p=self.lib.commit(self.p['id'],self.p['revision'],list(commands));return self.p
    def test_layers_preview_toggle_remove_restore_and_reopen(self):
        original=copy.deepcopy(self.p)
        command={'action':'terrain_layer','layer':{'mode':'raise','center':[0,0],'radius_m':16,'amount_m':2}}
        plan=preview_commands(self.p,1,[command])
        self.assertEqual(self.lib.get(self.p['id']),original)
        self.assertEqual(height_at(plan['scene']['terrain'],0,0),2)
        self.commit(command)
        layer=self.p['scene']['terrain_layers'][0]['id']
        raised=copy.deepcopy(self.p['scene']['terrain'])
        self.commit({'action':'terrain_toggle','id':layer,'enabled':False})
        self.assertEqual(self.p['scene']['terrain'],original['baseline']['terrain'])
        self.commit({'action':'terrain_toggle','id':layer,'enabled':True})
        self.assertEqual(self.p['scene']['terrain'],raised)
        self.commit({'action':'terrain_remove','id':layer})
        self.assertEqual(self.p['scene']['terrain'],original['baseline']['terrain'])
        self.commit(command,{'action':'terrain_restore'})
        self.assertNotIn('terrain',self.p['scene'])
        self.assertEqual(self.p['scene']['elements'],original['scene']['elements'])
        self.assertEqual(self.p['baseline'],original['baseline'])
        self.assertEqual(Library(self.lib.path).get(self.p['id']),self.p)
    def test_layer_order_and_flat_core(self):
        self.commit({'action':'terrain_layer','layer':{'mode':'flatten','center':[0,0],'radius_m':16,'height_m':3}})
        self.assertEqual(height_at(self.p['scene']['terrain'],4,4),3)
        self.commit({'action':'terrain_layer','layer':{'mode':'lower','center':[0,0],'radius_m':8,'amount_m':1}})
        self.assertEqual(height_at(self.p['scene']['terrain'],0,0),2)
    def test_design_and_baseline_projection_and_tree_grounding(self):
        original=unreal_view(self.p)
        self.commit({'action':'terrain_layer','layer':{'mode':'raise','center':[16,16],'radius_m':64,'amount_m':3}})
        view=unreal_view(self.p)
        self.assertNotEqual(view['vertices_cm'],original['vertices_cm'])
        self.assertEqual(view['baseline_vertices_cm'],original['vertices_cm'])
        design=design_landscape(self.p['baseline'],self.p['scene'])
        for tree in design['vegetation']:
            x,y,z=tree['position'];self.assertAlmostEqual(y,height_at(design['terrain'],x,z))
        self.assertEqual(view['baseline_vegetation'],original['vegetation'])
    def test_invalid_layers_and_bad_batch_do_not_save(self):
        original=copy.deepcopy(self.p)
        for layer in ({'mode':'raise','center':[0,0],'radius_m':1,'amount_m':1},
                      {'mode':'flatten','center':[1000,0],'radius_m':16,'height_m':0},
                      {'mode':'lower','center':[0,0],'radius_m':16,'amount_m':float('nan')}):
            with self.assertRaises(ValidationError): self.commit({'action':'terrain_layer','layer':layer})
        self.assertEqual(self.lib.get(self.p['id']),original)
    def test_stairs_path_and_planter_are_linked_editable_geometry(self):
        for kind in ('stairs','path','planter'):
            spec,parts=generate_assembly({'kind':kind,'yaw':30,'position':[8,0,8]})
            self.assertTrue(parts)
            self.commit({'action':'assembly','assembly':spec})
            group=self.p['scene']['assemblies'][-1]
            self.assertEqual(len(parts),len(group['members']))
        stairs=generate_assembly({'kind':'stairs','steps':16})[1]
        self.assertTrue(all(a['size'][1]<b['size'][1] for a,b in zip(stairs,stairs[1:])))
        with self.assertRaises(ValidationError): generate_assembly({'kind':'stairs','steps':2})
