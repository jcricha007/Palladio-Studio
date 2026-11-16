"""Explicit planting proposals preserve requested names, sizes and generator defaults."""
from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from palladio.commands import preview_commands
from palladio.local_agent import (AgentError, AgentService, OllamaPlanner,
                                  scene_context, validated_plan)
from palladio.model_check import check_design, design_signature
from palladio.scene import ValidationError
from palladio.store import Library
from test_agent_assembly_schema import action_variants


PROMPT = ('Use planting to scatter 4 pine trees named Courtyard pine, height 5 m, within a 3 m radius '
          'around X 12, Z 12 using seed 17. Use default width, depth and ground offset. Make no other edits.')
REPORTED = {'summary': 'Scatter 4 pine trees named Courtyard pine, each 5 m tall, within a 3 m radius around (12, 12) using seed 17.',
            'commands': [{'action': 'planting', 'planting': {'kind': 'pine', 'center': [12, 12],
                          'radius_m': 3, 'count': 4, 'seed': 17, 'offset_m': 0}}]}
COMPLETE = {'action': 'planting', 'planting': {'kind': 'pine', 'name': 'Courtyard pine',
            'width': 3, 'depth': 3, 'height': 5, 'center': [12, 12], 'radius_m': 3,
            'count': 4, 'seed': 17, 'offset_m': 0}}


class PlantingContractTests(unittest.TestCase):
    def setUp(self):
        temp = TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.library = Library(Path(temp.name) / 'planting.sqlite3')
        self.project = self.library.create('Planting contract', 'open meadow')
        self.calls = []

    def transport(self, output):
        def request(path, payload=None, **kwargs):
            if path == '/api/tags': return {'models': [{'name': 'test:local', 'size': 100}]}
            if path == '/api/show': return {'model_info': {'general.architecture': 'gptoss'}}
            self.calls.append(deepcopy(payload))
            return {'done': True, 'done_reason': 'stop', 'message': {'content': json.dumps(output)}}
        return request

    def preview(self, service):
        return service.preview(self.project, PROMPT, provider='ollama', model='test:local', revision=self.project['revision'])

    def test_real_adapter_requires_complete_planting_and_applies_exact_named_geometry(self):
        planner = OllamaPlanner()
        with patch.object(planner, '_request', side_effect=self.transport({
                'summary': 'Review named planting', 'commands': [COMPLETE]})):
            plan = self.preview(AgentService(planner))
        grammar = action_variants(self.calls[0]['format'], 'planting')[0]['properties']['planting']
        self.assertEqual(set(grammar['required']), set(COMPLETE['planting']))
        self.assertEqual(grammar['properties']['name']['maxLength'], 50)
        self.assertFalse(grammar['additionalProperties'])
        for index, group in enumerate(plan['scene']['assemblies'], 1):
            self.assertEqual(group['spec']['name'], f'Courtyard pine {index}')
            self.assertEqual(group['spec']['height'], 5)
            self.assertEqual([group['spec']['width'], group['spec']['depth']], [3, 3])
        self.assertEqual(len(plan['scene']['assemblies']), 4)
        self.assertEqual(self.library.get(self.project['id']), self.project)
        saved = self.library.commit(self.project['id'], plan['revision'], plan['commands'])
        self.assertEqual(design_signature(saved['scene']), design_signature(plan['scene']))
        self.assertEqual(Library(self.library.path).get(saved['id']), saved)

    def test_reported_summary_only_name_and_height_are_rejected_without_rewrite(self):
        records = []; planner = OllamaPlanner(diagnostics=records)
        with patch.object(planner, '_request', side_effect=self.transport(REPORTED)):
            with self.assertRaisesRegex(AgentError, 'explicitly include depth, height, name, width'):
                self.preview(AgentService(planner))
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(json.loads(records[0]['content']), REPORTED)
        self.assertEqual(self.library.get(self.project['id']), self.project)

    def test_each_omitted_field_rejects_the_whole_batch_without_mutating_input(self):
        before = deepcopy(self.project)
        for missing in COMPLETE['planting']:
            command = deepcopy(COMPLETE)
            del command['planting'][missing]
            with self.subTest(missing=missing), self.assertRaisesRegex(ValidationError, f'explicitly include {missing}'):
                validated_plan(self.project, {'summary': REPORTED['summary'], 'commands': [
                    {'action': 'environment', 'environment': {'weather': 'fog'}}, command]}, set())
            self.assertEqual(self.project, before)
            self.assertEqual(self.library.get(before['id']), before)

    def test_explicit_defaults_match_unchanged_manual_defaults_for_every_species(self):
        context = scene_context(self.project, None)
        defaults = context['tool_defaults']['planting']
        for kind in ('pine', 'broadleaf', 'hedge'):
            catalog = context['catalog']['assemblies'][kind]
            command = {'action': 'planting', 'planting': {
                'kind': kind, 'name': kind.capitalize(), 'center': [12, 12],
                **{key: catalog[key] for key in ('width', 'depth', 'height')},
                **{key: defaults[key] for key in ('radius_m', 'count', 'seed', 'offset_m')}}}
            with self.subTest(kind=kind):
                model = validated_plan(self.project, {'summary': 'Default plant', 'commands': [command]}, set())
                manual = preview_commands(self.project, self.project['revision'], [
                    {'action': 'planting', 'planting': {'kind': kind, 'center': [12, 12]}}])
                self.assertEqual(design_signature(model['scene']), design_signature(manual['scene']))
                self.assertEqual(model['scene']['assemblies'][0]['spec']['name'], kind.capitalize())
        self.assertEqual(self.library.get(self.project['id']), self.project)

    def test_acceptance_still_compares_requested_name_and_height_not_just_valid_json(self):
        variants = [({}, True), ({'name': 'Pine'}, False), ({'height': 7}, False)]
        for changes, expected_pass in variants:
            command = deepcopy(COMPLETE); command['planting'].update(changes)
            with self.subTest(changes=changes), patch.object(OllamaPlanner, 'propose', return_value={
                    'summary': REPORTED['summary'], 'commands': [command]}):
                report = check_design('test:local', 11435)
            planting = next(case for case in report['cases'] if case['case'] == 'planting')
            self.assertEqual(planting['passed'], expected_pass)
            self.assertTrue(planting['preview_unchanged'])
            if expected_pass:
                self.assertTrue(planting['apply_matches'])
            else:
                field = next(iter(changes))
                self.assertEqual(planting['differences'][0], {
                    'path': 'scene.assemblies[0].spec.' + field,
                    'expected': 'Courtyard pine 1' if field == 'name' else 5,
                    'actual': 'Pine 1' if field == 'name' else 7})

    def test_required_but_invalid_values_still_reach_geometry_validation(self):
        for changes in ({'height': 0}, {'name': ' '}, {'width': None}, {'count': True}):
            command = deepcopy(COMPLETE); command['planting'].update(changes)
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                validated_plan(self.project, {'summary': 'Invalid planting', 'commands': [command]}, set())
            self.assertEqual(self.library.get(self.project['id']), self.project)


if __name__ == '__main__': unittest.main()
