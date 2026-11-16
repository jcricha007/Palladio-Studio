"""Model edit grammar must respect persistent assembly ownership."""
from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from palladio.commands import preview_commands
from palladio.groups import MEMBER_EDIT_FIELDS
from palladio.local_agent import (AgentService, ELEMENT_FIELDS, OllamaPlanner, PLAN_SCHEMA,
                                  plan_schema, scene_context, schema_instructions, validated_plan)
from palladio.scene import ValidationError
from palladio.store import Library
from test_agent_assembly_schema import action_variants


class OwnershipSchemaTests(unittest.TestCase):
    def setUp(self):
        temp = TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.library = Library(Path(temp.name) / 'ownership.sqlite3')
        self.project = self.library.create('Ownership', 'open meadow')
        self.project = self.library.commit(self.project['id'], self.project['revision'], [
            {'action': 'assembly', 'assembly': {'kind': 'garage', 'name': 'Workshop'}},
            {'action': 'add', 'element': {'kind': 'block', 'name': 'Marker', 'material': 'stone',
                                         'position': [15, 0, 15], 'size': [1, 1, 1]}}])
        self.group = self.project['scene']['assemblies'][0]
        self.glass = next(e for e in self.project['scene']['elements'] if e['kind'] == 'glazing')
        self.marker = next(e for e in self.project['scene']['elements'] if e['name'] == 'Marker')
        self.context = scene_context(self.project, self.glass['id'])

    def preview(self, commands):
        return validated_plan(self.project, {'summary': 'Review changes', 'commands': commands},
            {e['id'] for e in self.context['elements']}, {g['id'] for g in self.context['assemblies']})

    def test_real_window_request_has_disjoint_update_grammars_and_correct_group_geometry(self):
        command = {'action': 'assembly_update', 'id': self.group['id'], 'assembly': {'window_width': 2.4}}
        calls = []
        def request(path, payload=None, **kwargs):
            if path == '/api/tags': return {'models': [{'name': 'test:local', 'size': 100}]}
            if path == '/api/show': return {'model_info': {'general.architecture': 'gptoss'}}
            calls.append(payload)
            return {'done': True, 'message': {'content': json.dumps({
                'summary': 'Widen the rear window to 2.4 m', 'commands': [command]})}}
        planner = OllamaPlanner()
        with patch.object(planner, '_request', side_effect=request):
            plan = AgentService(planner).preview(self.project,
                'Widen the existing rear window of Workshop to 2.4 m. Preserve every other property and do not add openings.',
                self.glass['id'], provider='ollama', model='test:local', revision=self.project['revision'])
        schema = calls[0]['format']
        updates = action_variants(schema, 'update')
        self.assertEqual(len(updates), 2)
        linked = next(branch for branch in updates if self.glass['id'] in branch['properties']['id']['enum'])
        free = next(branch for branch in updates if self.marker['id'] in branch['properties']['id']['enum'])
        self.assertEqual(set(linked['properties']['element']['properties']), {'name', 'material', 'finish'})
        self.assertEqual(set(free['properties']['element']['properties']), set(ELEMENT_FIELDS))
        self.assertTrue(set(linked['properties']['id']['enum']).isdisjoint(free['properties']['id']['enum']))
        for branch in updates:
            self.assertEqual(branch['properties']['element']['minProperties'], 1)
            self.assertFalse(branch['properties']['element']['additionalProperties'])
        self.assertEqual(action_variants(schema, 'remove')[0]['properties']['id']['enum'], [self.marker['id']])
        request_context = json.loads(calls[0]['messages'][1]['content'])['scene_context']
        glass = next(e for e in request_context['elements'] if e['id'] == self.glass['id'])
        self.assertEqual(glass['assembly_id'], self.group['id'])
        self.assertEqual(set(glass['editable_fields']), MEMBER_EDIT_FIELDS)
        self.assertIn('Linked assembly parts', schema_instructions(schema))
        expected = preview_commands(self.project, self.project['revision'], [command])
        self.assertEqual(plan['scene'], expected['scene'])
        self.assertEqual(plan['commands'], [command])
        self.assertEqual(self.library.get(self.project['id']), self.project)
        saved = self.library.commit(self.project['id'], plan['revision'], plan['commands'])
        self.assertEqual(saved['scene'], plan['scene'])
        self.assertEqual(saved['scene']['assemblies'][0]['members'], self.group['members'])

    def test_reported_glazing_resize_and_other_member_geometry_edits_still_reject_atomically(self):
        changes = [{'size': [2.4, 1.2, .06]}, {'position': [4, 2, 1]}, {'yaw': 20}, {'kind': 'block'}]
        commands = [{'action': 'update', 'id': self.glass['id'], 'element': change} for change in changes]
        commands.append({'action': 'remove', 'id': self.glass['id']})
        before = deepcopy(self.project)
        for command in commands:
            with self.subTest(command=command), self.assertRaisesRegex(ValidationError, 'belongs to an assembly'):
                self.preview([{'action': 'environment', 'environment': {'weather': 'fog'}}, command])
            self.assertEqual(self.project, before)
            self.assertEqual(self.library.get(before['id']), before)

    def test_member_appearance_overrides_survive_group_window_regeneration_and_reopen(self):
        style = {'name': 'Rear view glass', 'material': 'glass', 'finish': {'color': '#aaccee'}}
        plan = self.preview([{'action': 'update', 'id': self.glass['id'], 'element': style},
                             {'action': 'assembly_update', 'id': self.group['id'], 'assembly': {'window_width': 2.4}}])
        self.assertEqual(self.library.get(self.project['id']), self.project)
        saved = self.library.commit(self.project['id'], plan['revision'], plan['commands'])
        self.assertEqual(saved['scene'], plan['scene'])
        actual = next(e for e in saved['scene']['elements'] if e['id'] == self.glass['id'])
        self.assertEqual(actual['name'], style['name'])
        self.assertEqual(actual['material'], 'glass')
        self.assertEqual(actual['finish']['color'], '#aaccee')
        self.assertEqual(actual['size'][0], 2.4)
        self.assertEqual(Library(self.library.path).get(saved['id']), saved)

    def test_detach_applied_then_fresh_preview_enables_independent_geometry_and_removal(self):
        before = deepcopy(self.context)
        plan = self.preview([{'action': 'assembly_detach', 'id': self.group['id']}])
        self.assertEqual(self.library.get(self.project['id']), self.project)
        self.project = self.library.commit(self.project['id'], plan['revision'], plan['commands'])
        self.context = scene_context(self.project, self.glass['id'])
        schema = plan_schema(self.context)
        updates = action_variants(schema, 'update')
        self.assertEqual(len(updates), 1)
        self.assertEqual(set(updates[0]['properties']['element']['properties']), set(ELEMENT_FIELDS))
        self.assertIn(self.glass['id'], action_variants(schema, 'remove')[0]['properties']['id']['enum'])
        self.assertEqual(action_variants(schema, 'assembly_update'), [])
        glass_context = next(e for e in self.context['elements'] if e['id'] == self.glass['id'])
        self.assertNotIn('assembly_id', glass_context)
        commands = [{'action': 'update', 'id': self.glass['id'], 'element': {'size': [2.4, 1.2, .06]}},
                    {'action': 'update', 'id': self.marker['id'], 'element': {'position': [16, 0, 15]}}]
        changed = self.preview(commands)
        saved = self.library.commit(self.project['id'], changed['revision'], changed['commands'])
        self.assertEqual(saved['scene'], changed['scene'])
        # The previous request and global schema retain their original ownership.
        old = action_variants(plan_schema(before), 'update')
        old_member = next(b for b in old if self.glass['id'] in b['properties']['id']['enum'])
        self.assertNotIn('size', old_member['properties']['element']['properties'])
        self.assertNotIn(self.glass['id'], json.dumps(PLAN_SCHEMA))

    def test_partial_context_never_promotes_a_member_when_its_owner_is_omitted(self):
        child = next(e for e in self.context['elements'] if e['id'] == self.glass['id'])
        schema = plan_schema({'elements': [child], 'assemblies': []})
        updates = action_variants(schema, 'update')
        self.assertEqual(len(updates), 1)
        self.assertEqual(set(updates[0]['properties']['element']['properties']), MEMBER_EDIT_FIELDS)
        for action in ('remove', 'assembly_update', 'assembly_remove', 'assembly_detach', 'layout'):
            self.assertEqual(action_variants(schema, action), [], action)

    def test_schemas_do_not_share_mutable_fields_or_offer_empty_scene_edits(self):
        schema = plan_schema(self.context)
        updates = action_variants(schema, 'update')
        first = updates[0]['properties']['element']['properties']['finish']
        first['anyOf'][0]['properties']['color']['pattern'] = 'changed'
        self.assertNotEqual(updates[1]['properties']['element']['properties']['finish']['anyOf'][0]['properties']['color']['pattern'], 'changed')
        self.assertNotIn('changed', json.dumps(plan_schema(self.context)))
        for action in ('update', 'remove'):
            self.assertEqual(action_variants(plan_schema({}), action), [])


if __name__ == '__main__': unittest.main()
