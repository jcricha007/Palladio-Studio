"""Design-tool integration through real geometry, transactions and job checkpoints."""
from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from palladio.jobs import DesignJobs
from palladio.local_agent import AgentService, OllamaPlanner, PLAN_SCHEMA, plan_schema, schema_instructions, scene_context, validated_plan
from palladio.placement import height_at
from palladio.scene import ValidationError
from palladio.store import Library, RevisionConflict
from test_agent_assembly_schema import action_variants


BUILDING = {'action': 'building', 'building': {
    'shell': {'kind': 'garage', 'name': 'Workshop', 'width': 8, 'depth': 6,
              'height': 3, 'position': [0, 0, 0], 'yaw': 25},
    'ground_offset_m': .8, 'roof': {'kind': 'gable_roof', 'height': 1.8, 'overhang': .5},
    'foundation': {'columns_x': 3, 'columns_z': 2}}}
CAMERA = {'target': [0, 1.5, 0], 'azimuth': .7, 'pitch': .3, 'distance': 20, 'fov_degrees': 45}


def geometry(scene):
    """New IDs differ between preview and Apply; dimensions and ownership must not."""
    result = deepcopy(scene)
    for item in result['elements']: item.pop('id')
    for group in result.get('assemblies', []):
        group.pop('id'); group['members'] = sorted(group['members'])
    for key in ('views', 'finishes', 'terrain_layers'):
        for item in result.get(key, []): item.pop('id')
    return result


class AgentDesignTests(unittest.TestCase):
    def setUp(self):
        temp = TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.library = Library(Path(temp.name) / 'design.sqlite3')
        self.project = self.library.create('Design tools', 'open meadow')

    def edit(self, *commands):
        self.project = self.library.commit(self.project['id'], self.project['revision'], list(commands))
        return self.project

    def preview(self, commands, context=None):
        context = context or scene_context(self.project, None)
        return validated_plan(self.project, {'summary': 'Review design changes', 'commands': commands},
                              {e['id'] for e in context['elements']}, {g['id'] for g in context['assemblies']},
                              {t['id'] for t in context['terrain_layers']},
                              {f['id'] for f in context['finishes']}, {v['id'] for v in context['views']})

    def test_complete_building_preview_apply_reopen_restore_and_stale_apply(self):
        before = deepcopy(self.project)
        plan = self.preview([BUILDING])
        self.assertEqual(self.library.get(before['id']), before)
        groups = plan['scene']['assemblies']
        self.assertEqual([g['spec']['kind'] for g in groups], ['garage', 'gable_roof', 'foundation'])
        shell, roof, foundation = [g['spec'] for g in groups]
        self.assertAlmostEqual(roof['position'][1], shell['position'][1] + shell['height'] + .35)
        for key in ('width', 'depth', 'yaw'): self.assertEqual(roof[key], shell[key])
        self.assertAlmostEqual(foundation['position'][1] + foundation['height'], shell['position'][1])
        self.edit(*plan['commands'])
        self.assertEqual(geometry(plan['scene']), geometry(self.project['scene']))
        self.assertEqual(Library(self.library.path).get(before['id']), self.project)
        with self.assertRaises(RevisionConflict): self.library.commit(before['id'], before['revision'], plan['commands'])
        restored = self.library.commit(before['id'], self.project['revision'], restore=before['revision'])
        self.assertEqual(restored['scene'], before['scene'])

    def test_invalid_building_supports_or_shell_fields_roll_back_every_part(self):
        bad = deepcopy(BUILDING); bad['building']['ground_offset_m'] = 0
        wrong_openings = deepcopy(BUILDING); wrong_openings['building']['shell']['openings'] = []
        for command in (bad, wrong_openings):
            with self.subTest(command=command), self.assertRaises(ValidationError): self.preview([command])
        with self.assertRaises(ValidationError): self.edit(bad)
        self.assertEqual(self.library.get(self.project['id']), self.project)
        self.assertEqual(self.project['scene']['elements'], [])

    def test_layout_promotes_and_deduplicates_whole_assemblies(self):
        self.edit({'action': 'assembly', 'assembly': {'kind': 'room'}})
        group = self.project['scene']['assemblies'][0]
        ids = list(group['members'].values())[:2]
        plan = self.preview([{'action': 'layout', 'layout': {'operation': 'move', 'ids': ids, 'offset': [4, 0, 2]}}])
        self.assertEqual(plan['scene']['assemblies'][0]['spec']['position'], [4, 0, 2])
        self.assertEqual(len(plan['scene']['elements']), len(self.project['scene']['elements']))
        copy = self.preview([{'action': 'layout', 'layout': {'operation': 'copy', 'ids': ids, 'offset': [8, 0, 0]}}])
        self.assertEqual(len(copy['scene']['assemblies']), 2)
        for operation, extra in [('rotate', {'angle': 30}), ('align', {'axis': 'z'}), ('grid', {'spacing_m': .5})]:
            with self.subTest(operation=operation): self.preview([{'action': 'layout', 'layout': {'operation': operation, 'ids': ids, **extra}}])

    def test_finish_palette_and_views_use_visible_ids_and_persist(self):
        self.edit({'action': 'assembly', 'assembly': {'kind': 'room'}})
        member = self.project['scene']['elements'][0]['id']
        commands = [
            {'action': 'finish_apply', 'finish_id': 'builtin:limestone', 'ids': [member], 'scope': 'assembly'},
            {'action': 'finish_save', 'source_id': member, 'name': 'Exterior'},
            {'action': 'view_save', 'name': 'Approach', 'camera': CAMERA}]
        plan = self.preview(commands); self.edit(*plan['commands'])
        self.assertEqual(geometry(self.project['scene']), geometry(plan['scene']))
        self.assertTrue(all(e['finish']['pattern'] == 'stone' for e in self.project['scene']['elements']))
        view = self.project['scene']['views'][0]; finish = self.project['scene']['finishes'][0]
        plan = self.preview([
            {'action': 'finish_apply', 'finish_id': finish['id'], 'ids': [member], 'scope': 'part'},
            {'action': 'view_update', 'id': view['id'], 'name': 'Closer approach', 'camera': {**CAMERA, 'distance': 12}},
            {'action': 'finish_remove', 'finish_id': finish['id']}])
        self.edit(*plan['commands'])
        self.assertEqual(self.project['scene']['views'][0]['camera']['distance'], 12)
        self.assertEqual(self.project['scene']['finishes'], [])
        self.assertTrue(all('finish' in e for e in self.project['scene']['elements']))
        self.edit(*self.preview([{'action': 'view_remove', 'id': view['id']}])['commands'])
        self.assertEqual(self.project['scene']['views'], [])

    def test_planting_follows_terrain_and_explicit_restore(self):
        command = {'action': 'planting', 'planting': {'kind': 'pine', 'count': 4, 'seed': 17,
                   'center': [12, 12], 'radius_m': 3, 'height': 5}}
        plan = self.preview([command]); self.edit(*plan['commands'])
        self.assertEqual(geometry(self.project['scene']), geometry(plan['scene']))
        self.edit({'action': 'terrain_layer', 'layer': {'mode': 'raise', 'center': [12, 12], 'radius_m': 10, 'amount_m': 2}})
        plan = self.preview([{'action': 'terrain_restore'}])
        for group in plan['scene']['assemblies']:
            x, y, z = group['spec']['position']
            self.assertAlmostEqual(y, height_at(self.project['baseline']['terrain'], x, z))
        self.assertNotIn('terrain_layers', plan['scene'])

    def test_detach_then_convert_wall_keeps_geometry_and_finish(self):
        self.edit({'action': 'assembly', 'assembly': {'kind': 'room'}})
        group = self.project['scene']['assemblies'][0]
        detached = self.preview([{'action': 'assembly_detach', 'id': group['id']}])
        self.assertEqual(detached['scene']['assemblies'], [])
        self.assertEqual([e['position'] for e in detached['scene']['elements']], [e['position'] for e in self.project['scene']['elements']])
        self.edit(*detached['commands'])
        wall = next(e for e in self.project['scene']['elements'] if e['kind'] == 'wall' and e['size'][0] > 2)
        self.edit({'action': 'update', 'id': wall['id'], 'element': {'finish': {'color': '#aa8855'}}})
        plan = self.preview([{'action': 'wall_convert', 'id': wall['id']}])
        self.assertEqual(plan['scene']['assemblies'][0]['spec']['kind'], 'wall_run')
        self.assertEqual(plan['scene']['assemblies'][0]['spec']['wall_finish']['color'], '#aa8855')
        self.assertNotIn(wall['id'], [e['id'] for e in plan['scene']['elements']])

    def test_new_targeted_tools_cannot_escape_context_or_partially_save(self):
        self.edit(BUILDING, {'action': 'view_save', 'name': 'Approach', 'camera': CAMERA},
                  {'action': 'terrain_layer', 'layer': {'mode': 'raise', 'center': [20, 20], 'radius_m': 5, 'amount_m': 1}})
        group = self.project['scene']['assemblies'][0]; member = next(iter(group['members'].values()))
        self.edit({'action': 'finish_save', 'source_id': member, 'name': 'Private finish'})
        outside = [
            {'action': 'roof_fit', 'id': group['id'], 'roof': {'kind': 'hip_roof'}},
            {'action': 'assembly_detach', 'id': group['id']},
            {'action': 'wall_convert', 'id': member},
            {'action': 'layout', 'layout': {'operation': 'move', 'ids': [member], 'offset': [1, 0, 0]}},
            {'action': 'finish_apply', 'finish_id': 'builtin:limestone', 'ids': [member], 'scope': 'assembly'},
            {'action': 'finish_save', 'source_id': member, 'name': 'Hidden source'},
            {'action': 'finish_remove', 'finish_id': self.project['scene']['finishes'][0]['id']},
            {'action': 'view_remove', 'id': self.project['scene']['views'][0]['id']},
            {'action': 'terrain_restore'}]
        before = deepcopy(self.project)
        for command in outside:
            with self.subTest(action=command['action']), self.assertRaises(ValidationError):
                validated_plan(self.project, {'summary': 'Rejected batch', 'commands': [
                    {'action': 'environment', 'environment': {'weather': 'fog'}}, command]}, set())
        self.assertEqual(self.project, before); self.assertEqual(self.library.get(before['id']), before)
        # A visible child cannot authorize a whole-group operation when its group was omitted.
        for command in outside[3:5]:
            with self.assertRaisesRegex(ValidationError, 'assembly outside'):
                validated_plan(self.project, {'summary': 'No group context', 'commands': [command]}, {member})

    def test_context_schema_scopes_ids_and_keeps_request_branches_independent(self):
        self.edit(BUILDING, {'action': 'view_save', 'name': 'Approach', 'camera': CAMERA})
        context = scene_context(self.project, None)
        schema = plan_schema(context)
        self.assertEqual(len(context['assemblies']), 3)
        self.assertIn('builtin:limestone', [f['id'] for f in context['finishes']])
        self.assertEqual(action_variants(schema, 'roof_fit')[0]['properties']['id']['enum'], [context['assemblies'][0]['id']])
        self.assertEqual(action_variants(schema, 'wall_convert'), [])
        self.assertEqual(action_variants(schema, 'terrain_restore'), [])
        self.assertEqual(action_variants(schema, 'view_remove')[0]['properties']['id']['enum'], [context['views'][0]['id']])
        self.assertNotIn(context['elements'][0]['id'], schema_instructions(schema))
        self.assertIn(context['elements'][0]['id'], json.dumps(schema))
        first = action_variants(schema, 'layout')[0]
        first['properties']['layout']['properties']['ids']['items']['enum'].clear()
        self.assertTrue(action_variants(schema, 'layout')[1]['properties']['layout']['properties']['ids']['items']['enum'])
        self.assertNotIn(context['elements'][0]['id'], json.dumps(PLAN_SCHEMA))
        self.assertEqual(action_variants(plan_schema({}), 'view_remove'), [])

    def test_actual_transport_payload_exposes_building_and_applies_through_job_checkpoint(self):
        planner = OllamaPlanner(); seen = []
        def request(path, payload=None, **kwargs):
            if path == '/api/tags': return {'models': [{'name': 'test:local', 'size': 100}]}
            if path == '/api/show': return {'model_info': {'general.architecture': 'test'}}
            seen.append(payload)
            return {'done': True, 'message': {'content': json.dumps({'summary': 'Workshop with roof and supports', 'commands': [BUILDING]})}}
        jobs = DesignJobs(self.library)
        job = jobs.create(self.project['id'], {'title': 'Workshop', 'brief': 'Build a workshop', 'steps': ['Build workshop', 'Plant trees']})
        job = jobs.change(self.project['id'], job['id'], {'version': job['version'], 'action': 'start'})
        with patch.object(planner, '_request', side_effect=request):
            result = jobs.propose(self.project['id'], job['id'], {'version': job['version'], 'revision': self.project['revision'],
                                  'provider': 'ollama', 'model': 'test:local'}, AgentService(planner))
        self.assertTrue(action_variants(seen[0]['format'], 'building'))
        self.assertEqual(seen[0]['options']['num_ctx'], 32768)
        self.assertIn('design_job', json.loads(seen[0]['messages'][1]['content'])['scene_context'])
        self.assertEqual(self.library.get(self.project['id']), self.project)
        applied = jobs.apply(self.project['id'], job['id'], {'version': result['job']['version'], 'revision': self.project['revision']})
        self.assertEqual(len(applied['project']['scene']['assemblies']), 3)
        self.assertEqual(applied['job']['steps'][1]['status'], 'pending')
        self.assertEqual(geometry(applied['project']['scene']), geometry(result['plan']['scene']))

    def test_live_acceptance_reports_semantic_failures_and_rejects_extra_edits(self):
        from palladio.model_check import check_design
        def propose(context, prompt, model, **kwargs):
            groups = context['assemblies']
            commands = [{'action': 'assembly_update', 'id': groups[0]['id'], 'assembly': {'window_width': 2.4}}] if groups else []
            return {'summary': 'Test fixture', 'commands': commands}
        with patch.object(OllamaPlanner, 'propose', side_effect=propose):
            report = check_design('fixture:local', 11435)
        self.assertFalse(report['passed'])
        self.assertEqual([case['passed'] for case in report['cases']], [True, False, False])
        self.assertTrue(report['cases'][0]['preview_unchanged'])
        self.assertTrue(report['cases'][0]['apply_matches'])
        def extra(context, prompt, model, **kwargs):
            output = propose(context, prompt, model)
            output['commands'].append({'action': 'environment', 'environment': {'weather': 'fog'}})
            return output
        with patch.object(OllamaPlanner, 'propose', side_effect=extra):
            report = check_design('fixture:local', 11435)
        self.assertTrue(all(not case['passed'] for case in report['cases']))


if __name__ == '__main__': unittest.main()
