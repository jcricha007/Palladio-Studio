from collections import Counter
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from palladio.assemblies import generate_assembly
from palladio.roofs import ROOF_KINDS
from palladio.store import Library
from palladio.transfer import snapshot
from palladio.unreal import unreal_view

class RoofTests(unittest.TestCase):
    def test_roof_envelopes_are_closed_and_have_overhang(self):
        for kind in ROOF_KINDS:
            for w,d in [(6,8),(8,6),(6,6)]:
                spec,parts=generate_assembly({'kind':kind,'width':w,'depth':d,'height':2,'overhang':.4})
                mesh=parts[0]['mesh'];edges=Counter()
                for i in range(0,len(mesh['triangles']),3):
                    a,b,c=mesh['triangles'][i:i+3]
                    for edge in [(a,b),(b,c),(c,a)]:edges[tuple(sorted(edge))]+=1
                self.assertTrue(all(count==2 for count in edges.values()))
                self.assertEqual(parts[0]['size'],[w+.8,2,d+.8])
                self.assertEqual(parts[0]['role'],'roof envelope:1')
    def test_fit_resize_native_projection_and_portable_reopen(self):
        with TemporaryDirectory() as tmp:
            lib=Library(Path(tmp)/'data.db');p=lib.create('Roof','meadow')
            p=lib.commit(p['id'],1,[{'action':'assembly','assembly':{'kind':'garage','position':[3,2,4],'yaw':30}}]);host=p['scene']['assemblies'][0]
            p=lib.commit(p['id'],2,[{'action':'roof_fit','id':host['id'],'roof':{'kind':'gable_roof','height':2}}])
            roof=p['scene']['assemblies'][1];self.assertEqual(roof['spec']['width'],host['spec']['width'])
            self.assertAlmostEqual(roof['spec']['position'][1],5.55)
            key=next(iter(roof['members'].values()))
            p=lib.commit(p['id'],3,[{'action':'assembly_update','id':roof['id'],'assembly':{'height':3,'overhang':.7}}])
            self.assertEqual(next(iter(p['scene']['assemblies'][1]['members'].values())),key)
            self.assertIn('mesh_sections',unreal_view(p)['elements'][-1])
            self.assertEqual(lib.import_snapshot(snapshot(p))['scene'],p['scene'])
