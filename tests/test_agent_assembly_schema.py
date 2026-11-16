"""Assembly-specific model contracts, real validators and transactional previews."""
from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from palladio.assemblies import ASSEMBLIES, generate_assembly
from palladio.local_agent import (AgentService, OllamaPlanner, PLAN_SCHEMA,
                                  assembly_catalog, assembly_fields, plan_schema,
                                  scene_context, validated_plan)
from palladio.scene import ValidationError
from palladio.store import Library


def action_variants(schema, action):
    return [branch for branch in schema['properties']['commands']['items']['oneOf']
            if branch['properties']['action']['const'] == action]


class AssemblySchemaTests(unittest.TestCase):
    def setUp(self):
        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.library = Library(Path(tmp.name) / 'assemblies.sqlite3')
        self.project = self.library.create('Schema check', 'meadow', False)

    def add_group(self, kind, **values):
        self.project = self.library.commit(self.project['id'], self.project['revision'], [
            {'action': 'assembly', 'assembly': {'kind': kind, **values}}])
        return self.project['scene']['assemblies'][-1]

    def test_creation_grammar_excludes_openings_even_when_empty_for_other_kinds(self):
        command = action_variants(PLAN_SCHEMA, 'assembly')[0]
        variants = command['properties']['assembly']['oneOf']
        for kind in ASSEMBLIES:
            with self.subTest(kind=kind):
                matching = [branch for branch in variants if kind in branch['properties']['kind']['enum']]
                self.assertEqual(len(matching), 1)
                branch = matching[0]
                self.assertFalse(branch['additionalProperties'])
                self.assertEqual('openings' in branch['properties'], kind == 'wall_run')
                self.assertEqual('water_level' in branch['properties'], kind in ('pool', 'pond'))
                self.assertEqual('window_width' in branch['properties'], kind in ('room', 'garage'))
                self.assertEqual('rooms_x' in branch['properties'], kind == 'dwelling')
                self.assertEqual('overhang' in branch['properties'], kind.endswith('_roof'))
                self.assertEqual('steps' in branch['properties'], kind == 'stairs')
                # Every advertised creation kind still reaches its real generator.
                plan = validated_plan(self.project, {'summary': 'Create assembly', 'commands': [
                    {'action': 'assembly', 'assembly': {'kind': kind}}]}, set())
                self.assertEqual(plan['scene']['assemblies'][-1]['spec']['kind'], kind)

    def test_updates_are_bound_to_the_target_kind_and_context_ids(self):
        groups = [{'id': kind + '-id', 'spec': {'kind': kind}}
                  for kind in ('garage', 'wall_run', 'dwelling', 'pool', 'foundation')]
        schema = plan_schema({'assemblies': groups})
        updates = action_variants(schema, 'assembly_update')
        for group in groups:
            branch = next(x for x in updates if group['id'] in x['properties']['id']['enum'])
            fields = branch['properties']['assembly']
            self.assertEqual(set(fields['properties']), assembly_fields(group['spec']['kind']))
            self.assertEqual(fields['minProperties'], 1)
            self.assertFalse(fields['additionalProperties'])
        for action in ('opening_set', 'opening_remove'):
            self.assertEqual(action_variants(schema, action)[0]['properties']['id']['enum'], ['wall_run-id'])
        self.assertEqual(action_variants(schema, 'foundation_refit')[0]['properties']['id']['enum'], ['foundation-id'])
        self.assertEqual(set(action_variants(schema, 'foundation_fit')[0]['properties']['id']['enum']),
                         {'garage-id', 'dwelling-id'})
        empty = plan_schema({})
        self.assertEqual(action_variants(empty, 'assembly_update'), [])
        self.assertEqual(action_variants(empty, 'opening_set'), [])
        self.assertTrue(action_variants(empty, 'assembly'))
        # Request-specific IDs must never leak into the shared template or another request.
        self.assertNotIn('garage-id', json.dumps(PLAN_SCHEMA))
        self.assertNotIn('garage-id', json.dumps(empty))

    def test_shell_and_keyed_wall_opening_changes_preview_apply_and_reopen(self):
        garage = self.add_group('garage')
        wall = self.add_group('wall_run', openings=[{'key': 'view', 'kind': 'window'}])
        before = deepcopy(self.project)
        commands = [
            {'action': 'assembly_update', 'id': garage['id'], 'assembly': {'window_width': 2.4}},
            {'action': 'opening_set', 'id': wall['id'], 'opening': {
                **wall['spec']['openings'][0], 'width': 2.4}},
        ]
        plan = validated_plan(self.project, {'summary': 'Widen the two existing windows',
                                            'commands': commands}, set(), {garage['id'], wall['id']})
        self.assertEqual(self.library.get(before['id']), before)
        self.assertEqual(self.project, before)
        result = self.library.commit(before['id'], plan['revision'], plan['commands'])
        self.assertEqual(result['revision'], before['revision'] + 1)
        self.assertEqual(result['scene'], plan['scene'])
        reopened = Library(self.library.path).get(before['id'])
        by_kind = {g['spec']['kind']: g['spec'] for g in reopened['scene']['assemblies']}
        self.assertEqual(by_kind['garage']['window_width'], 2.4)
        self.assertEqual(by_kind['wall_run']['openings'][0]['width'], 2.4)
        self.assertEqual(by_kind['garage']['door_width'], garage['spec']['door_width'])

    def test_bad_opening_lists_are_not_silently_dropped_or_partially_saved(self):
        garage = self.add_group('garage')
        for bad_openings in ([], [{'key': 'extra', 'kind': 'window'}]):
            for command in (
                {'action': 'assembly', 'assembly': {'kind': 'garage', 'openings': bad_openings}},
                {'action': 'assembly_update', 'id': garage['id'], 'assembly': {'openings': bad_openings}},
            ):
                with self.subTest(command=command), self.assertRaisesRegex(ValidationError, 'Garage shell.*openings'):
                    validated_plan(self.project, {'summary': 'Invalid edit', 'commands': [
                        {'action': 'environment', 'environment': {'weather': 'fog'}}, command]}, set(), {garage['id']})
                self.assertEqual(self.library.get(self.project['id']), self.project)
        wall = self.add_group('wall_run', openings=[{'key': 'view', 'kind': 'window'}])
        plan = validated_plan(self.project, {'summary': 'Remove wall openings', 'commands': [
            {'action': 'assembly_update', 'id': wall['id'], 'assembly': {'openings': []}}]}, set(), {wall['id']})
        self.assertEqual(plan['scene']['assemblies'][-1]['spec']['openings'], [])
        self.assertEqual(len(self.project['scene']['assemblies'][-1]['spec']['openings']), 1)

    def test_real_ollama_payload_uses_typed_schema_for_selected_assembly(self):
        garage = self.add_group('garage')
        member = next(iter(garage['members'].values()))
        commands = [{'action': 'assembly_update', 'id': garage['id'], 'assembly': {'window_width': 2.4}}]
        calls = []
        def request(path, payload=None, **kwargs):
            calls.append((path, payload))
            if path == '/api/tags':
                return {'models': [{'name': 'gpt-oss:20b', 'size': 14_000_000_000}]}
            if path == '/api/show':
                return {'model_info': {'general.architecture': 'gptoss'}}
            return {'done': True, 'message': {'content': json.dumps({'summary': 'Widen the existing window', 'commands': commands})}}
        planner = OllamaPlanner()
        with patch.object(planner, '_request', side_effect=request):
            result = AgentService(planner).preview(self.project, 'Widen the garage window to 2.4 m', member,
                provider='ollama', model='gpt-oss:20b', revision=self.project['revision'])
        body = next(payload for path, payload in calls if path == '/api/chat')
        variant = action_variants(body['format'], 'assembly_update')[0]
        self.assertEqual(variant['properties']['id']['enum'], [garage['id']])
        self.assertNotIn('openings', variant['properties']['assembly']['properties'])
        self.assertIn('window_width', variant['properties']['assembly']['properties'])
        self.assertEqual(action_variants(body['format'], 'opening_set'), [])
        context = json.loads(body['messages'][1]['content'])['scene_context']
        self.assertNotIn('openings', context['assemblies'][0]['editable_fields'])
        self.assertIn('window_width', context['assemblies'][0]['opening_controls'])
        self.assertEqual(result['commands'], commands)
        self.assertEqual(self.library.get(self.project['id']), self.project)

    def test_catalog_is_independent_and_preserves_selected_group_budget(self):
        garage = self.add_group('garage')
        context = scene_context(self.project, next(iter(garage['members'].values())))
        self.assertEqual(context['assemblies'][0]['id'], garage['id'])
        catalog = assembly_catalog()
        self.assertNotIn('openings', catalog['garage']['editable_fields'])
        self.assertIn('openings', catalog['wall_run']['editable_fields'])
        catalog['garage']['limits']['width'][0] = -100
        self.assertEqual(ASSEMBLIES['garage']['limits']['width'][0], 4)
        self.assertNotIn('editable_fields', ASSEMBLIES['garage'])


if __name__ == '__main__':
    unittest.main()
