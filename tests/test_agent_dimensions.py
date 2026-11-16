"""Building dimension and default regressions from a real local-model reply."""
from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from palladio.assemblies import ASSEMBLIES, generate_assembly
from palladio.local_agent import (AgentError, AgentService, OllamaPlanner,
                                  assembly_catalog, plan_schema, validated_plan)
from palladio.model_check import check_design, design_signature
from palladio.scene import ValidationError
from palladio.store import Library
from test_agent_assembly_schema import action_variants


REPORTED_BUILDING = {'action': 'building', 'building': {
    'shell': {'kind': 'garage', 'name': 'Workshop', 'material': 'concrete',
              'position': [0, 0, 0], 'yaw': 0, 'width': 8, 'depth': 6,
              'door_width': 2.5, 'door_height': 2.5, 'window_width': 2.5,
              'window_height': 1.5, 'window_sill': .5},
    'ground_offset_m': .8,
    'roof': {'kind': 'gable_roof', 'name': 'Workshop roof', 'height': 1.8,
             'material': 'charred timber', 'overhang': .5},
    'foundation': {'columns_x': 3, 'columns_z': 2}}}


class DimensionTests(unittest.TestCase):
    def setUp(self):
        temp = TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.library = Library(Path(temp.name) / 'dimensions.sqlite3')
        self.project = self.library.create('Dimensions', 'open meadow')

    def test_creation_grammar_requires_dimensions_without_expanding_update_scope(self):
        schema = plan_schema({'assemblies': [{'id': 'garage-id', 'spec': {'kind': 'garage'}}]})
        branches = action_variants(schema, 'assembly')[0]['properties']['assembly']['oneOf']
        branches += action_variants(schema, 'building')[0]['properties']['building']['properties']['shell']['oneOf']
        for branch in branches:
            with self.subTest(kinds=branch['properties']['kind']['enum']):
                self.assertTrue({'kind', 'width', 'depth', 'height'} <= set(branch['required']))
                self.assertTrue(set(branch['required']).isdisjoint({'door_width', 'window_width'}))
        update = action_variants(schema, 'assembly_update')[0]['properties']['assembly']
        self.assertEqual(update['required'], [])
        self.assertIn('window_width', update['properties'])

    def test_opening_defaults_match_generator_for_every_supported_shell_width(self):
        catalog = assembly_catalog()
        for kind in ('room', 'garage'):
            for width in ASSEMBLIES[kind]['limits']['width']:
                spec, _ = generate_assembly({'kind': kind, 'width': width})
                for key, default in catalog[kind]['opening_defaults'].items():
                    self.assertEqual(spec[key], default, (kind, width, key))
        self.assertEqual(catalog['garage']['opening_defaults']['door_width'], 2.8)
        self.assertEqual(catalog['room']['opening_defaults']['door_width'], 1.2)
        catalog['garage']['opening_defaults']['door_width'] = 99
        self.assertEqual(assembly_catalog()['garage']['opening_defaults']['door_width'], 2.8)
        self.assertNotIn('opening_defaults', ASSEMBLIES['garage'])

    def test_missing_dimension_cannot_silently_fall_back_or_partially_save(self):
        for missing in ('width', 'depth', 'height'):
            command = deepcopy(REPORTED_BUILDING)
            command['building']['shell']['height'] = 3
            del command['building']['shell'][missing]
            with self.subTest(missing=missing), self.assertRaisesRegex(ValidationError, 'explicitly include shell'):
                validated_plan(self.project, {'summary': 'An 8 by 6 by 3 metre garage', 'commands': [
                    {'action': 'environment', 'environment': {'weather': 'fog'}}, command]}, set())
            self.assertEqual(self.library.get(self.project['id']), self.project)
            self.assertEqual(self.project['scene']['elements'], [])

    def test_actual_model_path_receives_defaults_and_rejects_reported_missing_height(self):
        calls = []
        def request(path, payload=None, **kwargs):
            if path == '/api/tags': return {'models': [{'name': 'test:local', 'size': 100}]}
            if path == '/api/show': return {'model_info': {'general.architecture': 'gptoss'}}
            calls.append(payload)
            return {'done': True, 'message': {'content': json.dumps({
                'summary': 'An 8 by 6 by 3 metre garage', 'commands': [REPORTED_BUILDING]})}}
        planner = OllamaPlanner()
        with patch.object(planner, '_request', side_effect=request):
            with self.assertRaisesRegex(AgentError, 'explicitly include shell'):
                AgentService(planner).preview(self.project, 'Create a garage 8 m wide, 6 m deep and 3 m high.',
                    provider='ollama', model='test:local', revision=self.project['revision'])
        context = json.loads(calls[0]['messages'][1]['content'])['scene_context']
        self.assertEqual(context['catalog']['assemblies']['garage']['opening_defaults'], {
            'door_width': 2.8, 'door_height': 2.5, 'window_width': 2,
            'window_height': 1.2, 'window_sill': .9})
        self.assertEqual(len(calls), 1)  # A valid JSON proposal is never silently rewritten.
        self.assertEqual(self.library.get(self.project['id']), self.project)

    def test_explicit_shell_dimensions_and_omitted_openings_preview_apply_exactly(self):
        command = deepcopy(REPORTED_BUILDING)
        shell = command['building']['shell']
        shell['height'] = 3
        for key in list(shell):
            if key.startswith(('door_', 'window_')): del shell[key]
        plan = validated_plan(self.project, {'summary': 'Review garage', 'commands': [command]}, set())
        actual = plan['scene']['assemblies'][0]['spec']
        self.assertEqual([actual[key] for key in ('width', 'depth', 'height')], [8, 6, 3])
        for key, default in assembly_catalog()['garage']['opening_defaults'].items():
            self.assertEqual(actual[key], default)
        roof = plan['scene']['assemblies'][1]['spec']
        self.assertAlmostEqual(roof['position'][1], actual['position'][1] + 3 + .35)
        self.assertEqual(self.library.get(self.project['id']), self.project)
        saved = self.library.commit(self.project['id'], plan['revision'], plan['commands'])
        self.assertEqual(design_signature(saved['scene']), design_signature(plan['scene']))

    def test_acceptance_still_rejects_invented_openings_with_explicit_height(self):
        command = deepcopy(REPORTED_BUILDING)
        command['building']['shell']['height'] = 3
        with patch.object(OllamaPlanner, 'propose', return_value={
                'summary': 'Review garage', 'commands': [command]}):
            report = check_design('test:local', 11435)
        building = next(case for case in report['cases'] if case['case'] == 'complete-building')
        self.assertFalse(building['passed'])
        self.assertIn({'path': 'scene.assemblies[0].spec.door_width',
                       'expected': 2.8, 'actual': 2.5}, building['differences'])
        self.assertTrue(building['preview_unchanged'])


if __name__ == '__main__': unittest.main()
