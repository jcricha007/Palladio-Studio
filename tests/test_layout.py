from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from palladio.commands import preview_commands
from palladio.layout import measure
from palladio.store import Library
from palladio.scene import ValidationError

class LayoutTests(unittest.TestCase):
    def setUp(self):
        temp=TemporaryDirectory();self.addCleanup(temp.cleanup);self.library=Library(Path(temp.name)/'data.db')
        self.p=self.library.create('Layout','meadow')
        self.p=self.library.commit(self.p['id'],1,[{'action':'assembly','assembly':{'kind':'room'}},
            *[{'action':'add','element':{'kind':'block','name':str(x),'material':'oak','position':[x,0,0],'size':[1,1,1]}} for x in (10,12,20)]])
    def layout(self,ids,operation,**data): return {'action':'layout','layout':{'ids':ids,'operation':operation,**data}}
    def test_linked_selection_moves_once_and_preserves_identity(self):
        g=self.p['scene']['assemblies'][0];ids=list(g['members'].values())[:2]
        command=self.layout(ids,'move',offset=[3,2,4]);before=deepcopy(self.p)
        plan=preview_commands(self.p,2,[command]);self.assertEqual(self.library.get(self.p['id']),before)
        saved=self.library.commit(self.p['id'],2,[command]);group=saved['scene']['assemblies'][0]
        self.assertEqual(group['spec']['position'],[3,2,4]);self.assertEqual(group['members'],g['members'])
        self.assertEqual(plan['scene'],saved['scene'])
    def test_distribution_alignment_and_rotation(self):
        ids=[e['id'] for e in self.p['scene']['elements'][-3:]]
        plan=preview_commands(self.p,2,[self.layout(ids,'distribute',axis='x')])
        self.assertEqual([e['position'][0] for e in plan['scene']['elements'][-3:]],[10,15,20])
        plan=preview_commands(self.p,2,[self.layout(ids,'rotate',angle=90)])
        last=plan['scene']['elements'][-1];self.assertAlmostEqual(last['position'][0],10);self.assertAlmostEqual(last['position'][2],-10)
        plan=preview_commands(self.p,2,[self.layout(ids,'align',axis='x')])
        self.assertEqual([e['position'][0] for e in plan['scene']['elements'][-3:]],[10]*3)
    def test_copy_grid_measurement_and_atomic_failure(self):
        ids=[e['id'] for e in self.p['scene']['elements'][-2:]]
        result=measure(self.p['scene'],ids);self.assertEqual(result['size'],[9,1,1]);self.assertEqual(result['origin_distance_m'],8)
        plan=preview_commands(self.p,2,[self.layout(ids,'copy',offset=[0,0,4])])
        self.assertEqual(len(plan['scene']['elements']),len(self.p['scene']['elements'])+2)
        self.assertTrue(set(ids).isdisjoint(e['id'] for e in plan['scene']['elements'][-2:]))
        plan=preview_commands(self.p,2,[self.layout(ids,'grid',spacing_m=3)])
        self.assertEqual([e['position'][0] for e in plan['scene']['elements'][-2:]],[12,21])
        with self.assertRaises(ValidationError): self.library.commit(self.p['id'],2,[self.layout(ids,'move',offset=[999,0,0])])
        self.assertEqual(self.library.get(self.p['id']),self.p)
