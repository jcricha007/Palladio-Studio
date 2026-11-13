import copy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from palladio.commands import preview_commands
from palladio.groups import owner
from palladio.placement import footprint_range, height_at
from palladio.scene import ValidationError
from palladio.store import Library, RevisionConflict
from palladio.unreal import unreal_view


class GroupTests(unittest.TestCase):
    def setUp(self):
        temp = TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.library = Library(Path(temp.name) / 'library.sqlite3')
        self.p = self.library.create('Groups', 'meadow')
    def edit(self, *commands):
        self.p = self.library.commit(self.p['id'], self.p['revision'], list(commands))
        return self.p
    def add(self):
        self.edit({'action':'assembly','assembly':{'kind':'garage'}})
        return self.p['scene']['assemblies'][0]
    def test_resize_preserves_members_overrides_and_history(self):
        g = self.add(); ids = g['members'].copy(); member = next(iter(ids.values()))
        self.edit({'action':'update','id':member,'element':{'material':'oak','name':'Custom slab'}})
        before = copy.deepcopy(self.p)
        command = {'action':'assembly_update','id':g['id'],'assembly':{'width':8,'door_width':3.2,'yaw':25}}
        plan = preview_commands(self.p,self.p['revision'],[command])
        self.assertEqual(self.library.get(self.p['id']), before)
        self.edit(command)
        self.assertEqual(self.p['scene']['assemblies'][0]['members'], ids)
        slab = next(e for e in self.p['scene']['elements'] if e['id']==member)
        self.assertEqual((slab['name'], slab['material'], slab['size'][0]), ('Custom slab','oak',8))
        self.assertEqual(self.p['scene'], plan['scene'])
        self.p = self.library.commit(self.p['id'],self.p['revision'],restore=before['revision'])
        self.assertEqual(self.p['scene'],before['scene'])
        self.assertEqual(Library(self.library.path).get(self.p['id']),self.p)
    def test_detach_is_explicit_and_duplicate_has_independent_ids(self):
        g = self.add(); member = next(iter(g['members'].values()))
        with self.assertRaises(ValidationError): self.edit({'action':'update','id':member,'element':{'size':[2,2,2]}})
        self.edit({'action':'assembly_duplicate','id':g['id'],'position':[12,0,0]})
        groups=self.p['scene']['assemblies']
        self.assertTrue(set(groups[0]['members'].values()).isdisjoint(groups[1]['members'].values()))
        self.edit({'action':'assembly_detach','id':g['id']}, {'action':'update','id':member,'element':{'size':[2,2,2]}})
        self.assertIsNone(owner(self.p['scene'],member))
        self.assertEqual(len(self.p['scene']['assemblies']),1)
    def test_bad_batch_and_stale_preview_never_save(self):
        g=self.add(); before=copy.deepcopy(self.p)
        with self.assertRaises(ValidationError): self.edit(
            {'action':'assembly_update','id':g['id'],'assembly':{'width':8}},
            {'action':'assembly_update','id':g['id'],'assembly':{'door_width':100}})
        self.assertEqual(self.library.get(self.p['id']),before)
        with self.assertRaises(RevisionConflict): preview_commands(self.p,1,[{'action':'assembly_remove','id':g['id']}])
    def test_triangle_height_and_footprint_capture_interior_peak(self):
        terrain={'size':3,'spacing':10,'heights':[0,0,0,0,10,0,0,0,0]}
        self.assertAlmostEqual(height_at(terrain,-5,-2),5)
        low,high=footprint_range(terrain,{'width':12,'depth':12,'position':[0,0,0],'yaw':35})
        self.assertEqual(high,10)
        self.assertLess(low,high)
        with self.assertRaises(ValidationError): footprint_range(terrain,{'width':30,'depth':10,'position':[0,0,0],'yaw':0})
    def test_ground_placement_and_unreal_movement_contract(self):
        g=self.add()
        self.edit({'action':'assembly_update','id':g['id'],'assembly':{'position':[18,0,18],'yaw':35}})
        spec=self.p['scene']['assemblies'][0]['spec']
        low,high=footprint_range(self.p['baseline']['terrain'],spec)
        plan=preview_commands(self.p,self.p['revision'],[{'action':'assembly_place','id':g['id'],'offset_m':.2}])
        self.assertTrue(plan['warnings'])
        self.edit(*plan['commands'])
        self.assertAlmostEqual(self.p['scene']['assemblies'][0]['spec']['position'][1],high+.2)
        native=unreal_view(self.p)['elements'][0]
        self.assertEqual(native['edit_id'],g['id'])
        position=native['edit_position']; position[0]+=.5
        self.edit({'action':native['edit_action'],'id':native['edit_id'],'assembly':{'position':position}})
        self.assertAlmostEqual(self.p['scene']['assemblies'][0]['spec']['position'][0],18.5)
    def test_old_properties_and_unlinked_elements_still_work(self):
        old=self.library.create('Old','meadow',True)
        element=old['scene']['elements'][0]
        result=self.library.commit(old['id'],1,[{'action':'update','id':element['id'],'element':{'position':[1,2,3]}}])
        self.assertNotIn('assemblies',result['scene'])
        self.assertNotIn('edit_id',unreal_view(result)['elements'][0])
