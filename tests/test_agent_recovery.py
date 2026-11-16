"""Bounded JSON recovery and actionable, opt-in local-model acceptance evidence."""
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event
import unittest
from unittest.mock import patch

from palladio.local_agent import AgentError, AgentService, OllamaPlanner, parse_json, scene_context
from palladio.jobs import DesignJobs
from palladio.model_check import check_design
from palladio.scene import ValidationError
from palladio.store import Library, RevisionConflict


PLAN = {'summary': 'Set fog', 'commands': [{'action': 'environment', 'environment': {'weather': 'fog'}}]}


def reply(content):
    return {'done': True, 'done_reason': 'stop', 'eval_count': 80,
            'message': {'content': content, 'thinking': 'Private reasoning is never captured'}}


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        temp = TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.library = Library(Path(temp.name) / 'recovery.sqlite3')
        self.project = self.library.create('Recovery', 'open meadow')
        self.calls = []

    def transport(self, replies, show=None):
        replies = iter(replies)
        def request(path, payload=None, **kwargs):
            self.calls.append((path, deepcopy(payload)))
            if path == '/api/tags': return {'models': [{'name': 'local:latest', 'size': 100}]}
            if path == '/api/show': return show() if show else {'model_info': {'general.architecture': 'gptoss'}}
            return next(replies)
        return request

    def preview(self, service):
        return service.preview(self.project, 'Set weather to fog only', provider='ollama',
                               model='local:latest', revision=self.project['revision'])

    def test_one_invalid_json_retry_preserves_context_and_validates_before_apply(self):
        records = []; planner = OllamaPlanner(diagnostics=records); service = AgentService(planner)
        with patch.object(planner, '_request', side_effect=self.transport([reply('{broken'), reply(json.dumps(PLAN))])):
            plan = self.preview(service)
        calls = [body for path, body in self.calls if path == '/api/chat']
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0]['format'], calls[1]['format'])
        self.assertEqual(calls[0]['messages'][0], calls[1]['messages'][0])
        self.assertTrue(calls[1]['messages'][1]['content'].startswith(calls[0]['messages'][1]['content']))
        self.assertIn('format_retry', calls[1]['messages'][1]['content'])
        self.assertEqual(plan['scene']['environment']['weather'], 'fog')
        self.assertEqual(self.library.get(self.project['id']), self.project)
        self.assertEqual(records[0]['parse_error']['position'], 1)
        self.assertNotIn('thinking', json.dumps(records))
        saved = self.library.commit(self.project['id'], plan['revision'], plan['commands'])
        self.assertEqual(saved['scene'], plan['scene'])

    def test_recovery_stops_after_two_invalid_replies_and_releases_lock(self):
        planner = OllamaPlanner(); service = AgentService(planner)
        with patch.object(planner, '_request', side_effect=self.transport([reply(''), reply('```json\n{}\n```')])):
            with self.assertRaisesRegex(AgentError, 'after one retry'): self.preview(service)
        self.assertEqual(sum(path == '/api/chat' for path, _ in self.calls), 2)
        self.assertIsNone(planner.diagnostics)
        self.assertEqual(self.library.get(self.project['id']), self.project)
        with patch.object(planner, '_request', side_effect=self.transport([reply(json.dumps(PLAN))])):
            self.assertEqual(self.preview(service)['scene']['environment']['weather'], 'fog')

    def test_protocol_failures_are_not_retried_or_captured(self):
        failures = [
            {**reply('{}'), 'done_reason': 'length'},
            {**reply('{}'), 'remote_host': 'remote.invalid'},
            {'done': True, 'message': {'content': '{}', 'tool_calls': [{'name': 'exec'}]}},
            {'done': False, 'message': {'content': '{}'}},
        ]
        for failure in failures:
            with self.subTest(failure=failure):
                self.calls.clear(); records = []; planner = OllamaPlanner(diagnostics=records)
                with patch.object(planner, '_request', side_effect=self.transport([failure])):
                    with self.assertRaises(AgentError): self.preview(AgentService(planner))
                self.assertEqual(sum(path == '/api/chat' for path, _ in self.calls), 1)
                self.assertEqual(records, [])

    def test_diagnostic_capture_is_bounded(self):
        records = []; planner = OllamaPlanner(diagnostics=records)
        with patch.object(planner, '_request', side_effect=self.transport([reply('x' * 7000), reply(json.dumps(PLAN))])):
            self.preview(AgentService(planner))
        self.assertEqual(records[0]['content_chars'], 7000)
        self.assertEqual(len(records[0]['content']), 6000)
        self.assertTrue(records[0]['content_clipped'])

    def test_pausing_a_job_rejects_a_late_repaired_reply(self):
        jobs = DesignJobs(self.library)
        job = jobs.create(self.project['id'], {'title': 'Fog', 'brief': 'Set fog', 'steps': ['Set weather to fog']})
        job = jobs.change(self.project['id'], job['id'], {'version': job['version'], 'action': 'start'})
        started, release = Event(), Event()
        transport = self.transport([reply('{'), reply(json.dumps(PLAN))])
        def request(path, payload=None, **kwargs):
            if path == '/api/chat' and any(old_path == '/api/chat' for old_path, _ in self.calls):
                started.set()
                if not release.wait(5): raise RuntimeError('Test did not release repair')
            return transport(path, payload, **kwargs)
        planner = OllamaPlanner()
        with patch.object(planner, '_request', side_effect=request), ThreadPoolExecutor(1) as pool:
            future = pool.submit(jobs.propose, self.project['id'], job['id'],
                                 {'version': job['version'], 'revision': self.project['revision'],
                                  'provider': 'ollama', 'model': 'local:latest'}, AgentService(planner))
            try:
                self.assertTrue(started.wait(3))
                paused = jobs.change(self.project['id'], job['id'], {'version': job['version'], 'action': 'pause'})
            finally: release.set()
            with self.assertRaises(RevisionConflict): future.result(3)
        self.assertEqual(jobs.get(self.project['id'], job['id']), paused)
        self.assertEqual(self.library.get(self.project['id']), self.project)

    def test_local_weights_are_checked_again_before_retry(self):
        shows = iter([{'model_info': {'general.architecture': 'gptoss'}}, {'remote_host': 'remote.invalid'}])
        planner = OllamaPlanner()
        with patch.object(planner, '_request', side_effect=self.transport([reply('{')], lambda: next(shows))):
            with self.assertRaisesRegex(ValidationError, 'Cloud/remote'): self.preview(AgentService(planner))
        self.assertEqual(sum(path == '/api/chat' for path, _ in self.calls), 1)

    def test_valid_but_unsupported_tools_are_not_repaired_into_something_else(self):
        planner = OllamaPlanner()
        output = {'summary': 'Unsupported', 'commands': [{'action': 'shell', 'command': 'whoami'}]}
        with patch.object(planner, '_request', side_effect=self.transport([reply(json.dumps(output))])):
            with self.assertRaisesRegex(AgentError, 'unsupported tool'): self.preview(AgentService(planner))
        self.assertEqual(sum(path == '/api/chat' for path, _ in self.calls), 1)
        self.assertEqual(self.library.get(self.project['id']), self.project)

    def test_parser_keeps_duplicate_key_and_nonfinite_rejection(self):
        for value in ('{"commands":[],"commands":[]}', '{"number":NaN}', '[]'):
            with self.subTest(value=value), self.assertRaises(AgentError) as failure: parse_json(value)
            self.assertTrue(failure.exception.diagnostics['reason'])

    def test_design_report_retains_failed_commands_and_exact_planting_differences(self):
        def request(path, payload=None, **kwargs):
            if path == '/api/tags': return {'models': [{'name': 'local:latest', 'size': 100}]}
            if path == '/api/show': return {'model_info': {'general.architecture': 'gptoss'}}
            context = json.loads(payload['messages'][1]['content'].split('\n', 1)[0])
            prompt = context['request']
            if 'rear window' in prompt:
                commands = [{'action': 'assembly_update', 'id': context['scene_context']['assemblies'][0]['id'],
                             'assembly': {'window_width': 2.4}}]
            elif 'building tool' in prompt: return reply('{invalid')
            else:
                commands = [{'action': 'planting', 'planting': {'kind': 'pine', 'name': 'Courtyard pine',
                             'width': 4, 'depth': 3, 'height': 5, 'center': [12, 12], 'radius_m': 3,
                             'count': 4, 'seed': 17, 'offset_m': 0}}]
            return reply(json.dumps({'summary': 'Fixture', 'commands': commands}))
        with patch.object(OllamaPlanner, '_request', side_effect=request): report = check_design('local:latest', 11435)
        window, building, planting = report['cases']
        self.assertEqual([case['passed'] for case in report['cases']], [True, False, False])
        self.assertNotIn('model_responses', window)
        self.assertEqual(len(building['model_responses']), 2)
        self.assertEqual(building['error_details']['position'], 1)
        self.assertEqual(planting['commands'][0]['planting']['width'], 4)
        self.assertIn({'path': 'scene.assemblies[0].spec.width', 'expected': 3, 'actual': 4}, planting['differences'])
        self.assertLessEqual(len(planting['differences']), 8)
        self.assertNotIn('thinking', json.dumps(report))
        self.assertTrue(planting['preview_unchanged'])

    def test_reported_planting_defaults_agree_with_the_generator(self):
        context = scene_context(self.project, None)
        self.assertEqual(context['tool_defaults']['planting']['offset_m'], 0)
        for kind in ('pine', 'broadleaf', 'hedge'):
            scene = self.library.commit(self.project['id'], self.project['revision'], [
                {'action': 'planting', 'planting': {'kind': kind, 'center': [0, 0]}}])['scene']
            spec = scene['assemblies'][0]['spec']
            for field in ('width', 'depth', 'height'):
                self.assertEqual(spec[field], context['catalog']['assemblies'][kind][field])
            self.project = self.library.get(self.project['id'])
            # Each assertion above should inspect the newly planted species.
            self.project = self.library.commit(self.project['id'], self.project['revision'], restore=1)


if __name__ == '__main__': unittest.main()
