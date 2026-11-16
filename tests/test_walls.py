from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from palladio.store import Library
from palladio.scene import ValidationError
from palladio.assemblies import generate_assembly
from palladio.transfer import snapshot
from palladio.unreal import unreal_view
from palladio.commands import preview_commands
import test_assemblies

DOOR={'key':'entry','kind':'door','center':-1.5,'width':1.2,'height':2.2,'sill':0,'frame':.06}
WINDOW={'key':'view','kind':'window','center':1.3,'width':1.6,'height':1.2,'sill':1,'frame':.08}
class WallTests(unittest.TestCase):
    def setUp(self):
        temp=TemporaryDirectory();self.addCleanup(temp.cleanup);self.library=Library(Path(temp.name)/'p.sqlite3');self.p=self.library.create('Walls','meadow')
    def edit(self,*commands):self.p=self.library.commit(self.p['id'],self.p['revision'],list(commands));return self.p
    def test_door_is_clear_window_is_glazed_and_volume_matches_openings(self):
        spec,parts=generate_assembly({'kind':'wall_run','openings':[DOOR,WINDOW]})
        contains=test_assemblies.AssemblyTests.contains
        self.assertFalse(any(contains(p,[-1.5,1,0]) for p in parts))
        self.assertTrue(any(contains(p,[1.3,1.6,0]) and p['kind']=='glazing' for p in parts))
        volume=sum(p['size'][0]*p['size'][1]*p['size'][2] for p in parts if p['kind']=='wall')
        self.assertAlmostEqual(volume,(6*3-1.2*2.2-1.6*1.2)*.2)
    def test_opening_edits_keep_ids_overrides_and_round_trip(self):
        self.edit({'action':'assembly','assembly':{'kind':'wall_run','yaw':35,'position':[4,2,3],'openings':[DOOR,WINDOW]}})
        group=deepcopy(self.p['scene']['assemblies'][0]);glazing=group['members']['view glazing']
        self.edit({'action':'update','id':glazing,'element':{'finish':{'color':'#aaccdd'}}},
                  {'action':'opening_set','id':group['id'],'opening':{**WINDOW,'center':1.5,'width':1.8}})
        self.assertEqual(self.p['scene']['assemblies'][0]['members'],group['members'])
        self.assertEqual(next(e for e in self.p['scene']['elements'] if e['id']==glazing)['finish']['color'],'#aaccdd')
        self.assertEqual(self.library.import_snapshot(snapshot(self.p))['scene'],self.p['scene'])
        self.assertEqual(len(unreal_view(self.p)['elements']),len(self.p['scene']['elements']))
        before=self.p
        with self.assertRaises(ValidationError):self.edit({'action':'opening_remove','id':group['id'],'key':'view'})
        self.assertEqual(self.library.get(self.p['id']),before)
    def test_overlap_bad_keys_and_height_fail_without_partial_save(self):
        for bad in [[DOOR,{**WINDOW,'center':-1}], [DOOR,DOOR], [{**WINDOW,'key':'x'*25}], [{**DOOR,'sill':1}], [{**WINDOW,'height':2.5}]]:
            with self.subTest(bad=bad),self.assertRaises(ValidationError):self.edit({'action':'assembly','assembly':{'kind':'wall_run','openings':bad}})
        self.assertEqual(self.library.get(self.p['id'])['revision'],1)
    def test_conversion_preview_preserves_appearance_and_restore(self):
        self.edit({'action':'add','element':{'kind':'wall','name':'Independent','material':'plaster','position':[2,1,3],'size':[6,3,.2],'yaw':20,'finish':{'color':'#123456'}}})
        before=self.p;key=self.p['scene']['elements'][0]['id'];command={'action':'wall_convert','id':key}
        plan=preview_commands(self.p,self.p['revision'],[command]);self.assertEqual(self.library.get(self.p['id']),before)
        self.assertEqual(plan['scene']['elements'][0]['finish']['color'],'#123456')
        self.edit(command);group=self.p['scene']['assemblies'][0];self.edit({'action':'opening_set','id':group['id'],'opening':WINDOW})
        self.assertTrue(all(e['finish']['color']=='#123456' for e in self.p['scene']['elements'] if e['kind']=='wall'))
        self.assertEqual(self.library.commit(self.p['id'],self.p['revision'],restore=2)['scene'],before['scene'])
