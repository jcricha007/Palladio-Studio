from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from palladio.assemblies import generate_assembly
from palladio.rooms import room_schedule
from palladio.scene import ValidationError
from palladio.store import Library
from palladio.transfer import snapshot

class RoomTests(unittest.TestCase):
    def test_shared_partition_openings_and_schedule(self):
        spec,parts=generate_assembly({'kind':'dwelling','width':10,'depth':8,'rooms_x':2,'rooms_z':2})
        walls=[p for p in parts if p['kind'] in ('wall','column')]
        def contains(p,point):
            return all(abs(point[i]-p['position'][i])<p['size'][i]/2 for i in (0,2)) and p['position'][1]<point[1]<p['position'][1]+p['size'][1]
        for point in ([0,1,-2],[0,1,2],[-2.5,1,0],[2.5,1,0],[-2.5,1,3.9]):
            self.assertFalse(any(contains(w,point) for w in walls),point)
        self.assertTrue(any(contains(w,[0,1,0]) for w in walls))
        rooms=room_schedule(spec);self.assertEqual(len(rooms),4)
        self.assertAlmostEqual(rooms[0]['area_m2'],4.725*3.725)
        self.assertEqual(len(set(p['role'] for p in parts)),len(parts))
    def test_grid_bounds_resize_override_and_snapshot(self):
        with self.assertRaises(ValidationError):generate_assembly({'kind':'dwelling','width':6,'rooms_x':4})
        with self.assertRaises(ValidationError):generate_assembly({'kind':'dwelling','rooms_z':True})
        with TemporaryDirectory() as tmp:
            lib=Library(Path(tmp)/'data.db');p=lib.create('Home','meadow')
            p=lib.commit(p['id'],1,[{'action':'assembly','assembly':{'kind':'dwelling'}}]);g=p['scene']['assemblies'][0]
            key=g['members']['room 1.1 slab:1']
            p=lib.commit(p['id'],2,[{'action':'update','id':key,'element':{'finish':{'color':'#bbbbbb'}}},
                {'action':'assembly_update','id':g['id'],'assembly':{'width':12,'depth':12,'rooms_x':3}}])
            self.assertEqual(p['scene']['assemblies'][0]['members']['room 1.1 slab:1'],key)
            self.assertEqual(next(e for e in p['scene']['elements'] if e['id']==key)['finish']['color'],'#bbbbbb')
            self.assertEqual(lib.import_snapshot(snapshot(p))['scene'],p['scene'])
