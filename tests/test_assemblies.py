import copy
import json
import math
from http.server import ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Thread
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from palladio.assemblies import ASSEMBLIES, assembly_preview, generate_assembly
from palladio.agent import preview
from palladio.__main__ import handler_for
from palladio.scene import ValidationError
from palladio.store import Library, RevisionConflict
from palladio.unreal import unreal_view


class AssemblyTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'property.sqlite3'
        self.library = Library(self.path)
        self.project = self.library.create('Test home', 'meadow')

    def test_every_preset_and_extreme_is_valid(self):
        for kind, catalog in ASSEMBLIES.items():
            for edge in (0, 1):
                data = {'kind': kind, **{key: bounds[edge] for key, bounds in catalog['limits'].items()}}
                spec, pieces = generate_assembly(data)
                self.assertTrue(pieces)
                self.assertLess(len(pieces), 100)
                for part in pieces:
                    self.assertTrue(all(math.isfinite(v) and v >= .05 for v in part['size']))
                    self.assertLessEqual(len(part['name']), 100)

    def test_invalid_values_rejected(self):
        bad = [None, [], {'kind': []}, {'kind': 'house'}, {'kind': 'room', 'extra': 1}]
        for field in ('width', 'depth', 'height', 'yaw'):
            bad.extend({'kind': 'room', field: value} for value in (None, True, float('nan'), float('inf'), '3'))
        bad.extend([{'kind': 'room', 'material': 'missing'}, {'kind': 'room', 'position': [0, 0]},
                    {'kind': 'garage', 'width': 3}, {'kind': 'room', 'height': 2.1}])
        for data in bad:
            with self.subTest(data=data), self.assertRaises(ValidationError):
                generate_assembly(data)

    def test_rotation_matches_scene_convention(self):
        _, before = generate_assembly({'kind': 'room'})
        _, after = generate_assembly({'kind': 'room', 'yaw': 90, 'position': [10, 2, -5]})
        for a, b in zip(before, after):
            x, y, z = a['position']
            for actual, expected in zip(b['position'], [10 + z, 2 + y, -5 - x]):
                self.assertAlmostEqual(actual, expected)
            self.assertEqual(b['yaw'], 90)
            self.assertEqual(b['size'], a['size'])

    def test_shell_entry_is_clear_and_window_is_not_solid_wall(self):
        for kind in ('room', 'garage'):
            spec, pieces = generate_assembly({'kind': kind})
            door_w, door_h = (2.8, 2.5) if kind == 'garage' else (1.2, 2.2)
            # Point in the doorway cannot intersect any wall, glazing or column.
            point = [0, .15 + door_h / 2, spec['depth'] / 2 - .1]
            walls = [part for part in pieces if part['kind'] in ('wall', 'glazing', 'column')]
            self.assertFalse(any(self.contains(part, point) for part in walls))
            point = [0, .15 + .9 + .6, -spec['depth'] / 2 + .1]
            self.assertFalse(any(self.contains(part, point) for part in walls if part['kind'] == 'wall'))
            self.assertTrue(any(self.contains(part, point) for part in walls if part['kind'] == 'glazing'))

    @staticmethod
    def contains(part, point):
        p, s = part['position'], part['size']
        return (abs(point[0] - p[0]) < s[0] / 2 and p[1] <= point[1] < p[1] + s[1]
                and abs(point[2] - p[2]) < s[2] / 2)

    def test_preview_commit_restore_and_reopen(self):
        original = copy.deepcopy(self.project)
        plan = assembly_preview(self.project, {'kind': 'room', 'position': [10, 0, 0]})
        self.assertEqual(self.project, original)
        self.assertEqual(self.library.get(original['id']), original)
        result = self.library.commit(original['id'], plan['revision'], [plan['command']])
        self.assertEqual(result['revision'], 2)
        self.assertEqual(result['baseline'], original['baseline'])
        self.assertEqual([{k: v for k, v in p.items() if k != 'id'} for p in result['scene']['elements']],
                         [{k: v for k, v in p.items() if k != 'id'} for p in plan['elements']])
        ids = [p['id'] for p in result['scene']['elements']]
        self.assertEqual(len(set(ids)), len(ids))
        self.assertFalse(any(id.startswith('preview-') for id in ids))
        self.assertEqual(Library(self.path).get(original['id']), result)
        with self.assertRaises(RevisionConflict):
            self.library.commit(original['id'], 1, [plan['command']])
        changed = self.library.commit(original['id'], 2, [{'action': 'update', 'id': ids[0],
                                                        'element': {'material': 'oak'}}])
        self.assertEqual(changed['scene']['elements'][0]['material'], 'oak')
        restored = self.library.commit(original['id'], 3, restore=1)
        self.assertEqual(restored['scene'], original['scene'])

    def test_bad_batch_does_not_leave_partial_assembly(self):
        with self.assertRaises(ValidationError):
            self.library.commit(self.project['id'], 1, [
                {'action': 'assembly', 'assembly': {'kind': 'dining'}},
                {'action': 'assembly', 'assembly': {'kind': 'garage', 'height': 0}},
            ])
        self.assertEqual(self.library.get(self.project['id']), self.project)

    def test_prompt_and_unreal_share_generated_geometry(self):
        for prompt in ('add a room', 'add a garage', 'add a dining set', 'add a lounge set'):
            plan = preview(self.project, prompt)
            result = self.library.commit(self.project['id'], self.project['revision'], [plan['command']])
            self.project = result
        projected = unreal_view(result)
        for source, native in zip(result['scene']['elements'], projected['elements']):
            self.assertEqual(source['id'], native['id'])
            x, y, z = source['position']
            self.assertEqual(native['center_cm'], [x * 100, z * 100, y * 100 + source['size'][1] * 50])

    def test_http_preview_apply_stale_and_bad_data(self):
        with ThreadingHTTPServer(('127.0.0.1', 0), handler_for(self.library)) as server:
            thread = Thread(target=server.serve_forever)
            thread.start()
            try:
                base = f'http://127.0.0.1:{server.server_port}'
                path = base + '/api/properties/' + self.project['id']
                def request(url, data=None):
                    req = Request(url, data=None if data is None else json.dumps(data).encode(),
                                  headers={'Content-Type': 'application/json'})
                    with urlopen(req, timeout=5) as reply:
                        return json.load(reply)
                self.assertEqual(set(request(base + '/api/catalog')['assemblies']), set(ASSEMBLIES))
                plan = request(path + '/assembly-preview', {'assembly': {'kind': 'garage'}})
                self.assertEqual(request(path)['revision'], 1)
                edit = {'revision': plan['revision'], 'commands': [plan['command']]}
                result = request(path + '/edit', edit)
                self.assertEqual(result['revision'], 2)
                with self.assertRaises(HTTPError) as stale:
                    request(path + '/edit', edit)
                self.assertEqual(stale.exception.code, 409)
                for data in ({'assembly': {'kind': 'room', 'width': 0}}, {'assembly': []}):
                    with self.assertRaises(HTTPError) as bad:
                        request(path + '/assembly-preview', data)
                    self.assertEqual(bad.exception.code, 400)
            finally:
                server.shutdown()
                thread.join()


if __name__ == '__main__':
    unittest.main()
