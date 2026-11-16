import copy
import math
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from urllib.error import HTTPError
from palladio.presentation import camera, camera_pose, camera_from_pose
from palladio.scene import ValidationError
from palladio.store import Library
from palladio.transfer import snapshot
from palladio.unreal import unreal_view, unreal_vector
from palladio.__main__ import handler_for
from test_local_agent import running_server
import test_unreal


class SharedViewTests(unittest.TestCase):
    def test_pose_round_trip_preserves_eye_target_and_vertical_fov(self):
        for angle in [-math.pi, -.6, 0, math.pi/2, 13]:
            for pitch in [.06, .8, 1.51]:
                for distance in [2, 34, 3000]:
                    original={'target':[14,-1,28],'azimuth':angle,'pitch':pitch,'distance':distance,'fov_degrees':67}
                    pose=camera_pose(original);restored=camera_pose(camera_from_pose(pose))
                    self.assertEqual(restored['target'],pose['target']);self.assertEqual(restored['fov_degrees'],67)
                    for a,b in zip(restored['eye'],pose['eye']):self.assertAlmostEqual(a,b,places=8)
        old={'target':[0,0,0],'azimuth':0,'pitch':.4,'distance':10}
        self.assertEqual(camera(old),old);self.assertEqual(camera_pose(old)['fov_degrees'],45)

    def test_capture_validation_rejects_unrepresentable_or_invalid_poses(self):
        valid={'eye':[0,10,10],'target':[0,0,0],'fov_degrees':45}
        for patch in [{'eye':[0,0,0]},{'eye':[0,-10,10]},{'eye':[0,10,0]},
                      {'eye':[0,0,100]},{'eye':[0,4000,4000]},{'fov_degrees':0},
                      {'fov_degrees':True},{'target':[float('nan'),0,0]},{'extra':1}]:
            with self.assertRaises(ValidationError):camera_from_pose({**valid,**patch})

    def test_native_capture_is_revisioned_persistent_and_transferable(self):
        with TemporaryDirectory() as tmp:
            library=Library(Path(tmp)/'views.sqlite3');project=library.create('Shared views','meadow')
            pose={'eye':[12,14,18],'target':[2,3,-4],'fov_degrees':56}
            with running_server(handler_for(library)) as server:
                url=f'http://127.0.0.1:{server.server_port}/api/properties/{project["id"]}'
                body={'revision':1,'commands':[{'action':'view_capture','name':'Native approach','pose':pose}]}
                test_unreal.UnrealBridgeTest.read(url+'/edit',body)
                saved=library.get(project['id']);native=test_unreal.UnrealBridgeTest.read(url+'/unreal');view=native['views'][0]
                self.assertEqual(view['id'],saved['scene']['views'][0]['id']);self.assertEqual(view['target_cm'],[200,-400,300])
                for a,b in zip(view['eye_cm'],unreal_vector(pose['eye'])):self.assertAlmostEqual(a,b)
                self.assertEqual(view['vertical_fov_degrees'],56);self.assertEqual(saved['scene']['elements'],[])
                with self.assertRaises(HTTPError) as stale:test_unreal.UnrealBridgeTest.read(url+'/edit',body)
                self.assertEqual(stale.exception.code,409)
                bad=copy.deepcopy(body);bad['revision']=2;bad['commands'][0]['pose']['eye']=[0,-10,0]
                with self.assertRaises(HTTPError) as invalid:test_unreal.UnrealBridgeTest.read(url+'/edit',bad)
                self.assertEqual(invalid.exception.code,400);self.assertEqual(library.get(project['id']),saved)
                imported=library.import_snapshot(snapshot(saved));self.assertEqual(imported['scene'],saved['scene'])
                self.assertEqual(unreal_view(imported)['views'],native['views'])
