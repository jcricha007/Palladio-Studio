"""Protocol/transaction tests with a loopback fake, not model-quality acceptance."""

from contextlib import contextmanager
from copy import deepcopy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event, Thread
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from palladio.__main__ import handler_for
from palladio.local_agent import (AgentError, AgentService, MAX_RESPONSE, OllamaPlanner,
                                  parse_json, scene_context, validated_plan)
from palladio.scene import ValidationError
from palladio.store import Library, RevisionConflict


@contextmanager
def running_server(handler):
    server = ThreadingHTTPServer(('127.0.0.1', 0), handler)
    server.daemon_threads = True
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


class ModelServer:
    def __init__(self):
        self.calls = []
        self.names = ['small:latest', 'other:12b']
        self.details = {'model_info': {'general.architecture': 'test'}}
        self.plan = {'summary': 'Set fog and add a room. Review before applying.', 'commands': [
            {'action': 'environment', 'environment': {'weather': 'fog'}},
            {'action': 'assembly', 'assembly': {'kind': 'room'}},
        ]}
        self.custom = {}
        self.started = Event()
        self.release = None
        fixture = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                self.reply()

            def do_POST(self):
                self.reply()

            def reply(self):
                length = int(self.headers.get('Content-Length', 0))
                payload = json.loads(self.rfile.read(length)) if length else None
                fixture.calls.append((self.path, payload))
                if self.path == '/api/chat':
                    fixture.started.set()
                    if fixture.release:
                        fixture.release.wait(5)
                default = {
                    '/api/tags': {'models': [{'name': name, 'size': 8000} for name in fixture.names]},
                    '/api/show': fixture.details,
                    '/api/chat': {'done': True, 'done_reason': 'stop',
                                  'message': {'role': 'assistant', 'content': json.dumps(fixture.plan)}},
                }.get(self.path, {})
                code, value = fixture.custom.get(self.path, (200, default))
                body = value if isinstance(value, bytes) else json.dumps(value).encode()
                self.send_response(code)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(body)))
                if code == 302:
                    self.send_header('Location', 'http://not-local.invalid/collect')
                self.end_headers()
                try:
                    self.wfile.write(body)
                except (BrokenPipeError, ConnectionResetError):
                    pass
        self.handler = Handler


class AgentTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.library = Library(Path(self.temp.name) / 'property.sqlite3')
        self.project = self.library.create('Home', 'meadow', True)
        self.ids = {item['id'] for item in self.project['scene']['elements']}

    def test_rules_need_no_runtime_and_return_full_preview(self):
        service = AgentService()
        with patch.object(service.ollama, '_request', side_effect=AssertionError('Must not contact Ollama')):
            result = service.preview(self.project, 'set weather to fog')
            self.assertEqual(result['provider'], 'rules')
            self.assertEqual(result['scene']['environment']['weather'], 'fog')
            self.assertEqual(result['commands'], [result['command']])
            self.assertEqual(self.library.get(self.project['id']), self.project)

    def test_all_commands_are_validated_on_copy_then_apply_atomically(self):
        first = self.project['scene']['elements'][0]
        commands = [
            {'action': 'update', 'id': first['id'], 'element': {'material': 'oak', 'position': [2, 0, 3]}},
            {'action': 'remove', 'id': self.project['scene']['elements'][1]['id']},
            {'action': 'add', 'element': {'kind': 'block', 'name': 'Test', 'material': 'stone', 'position': [0, 1, 0], 'size': [1, 1, 1]}},
            {'action': 'assembly', 'assembly': {'kind': 'dining'}},
            {'action': 'environment', 'environment': {'hour': 19}},
        ]
        before = deepcopy(self.project)
        plan = validated_plan(self.project, {'summary': 'Five edits', 'commands': commands}, self.ids)
        self.assertEqual(self.project, before)
        self.assertEqual(self.library.get(before['id']), before)
        self.assertEqual(len(plan['changes']), 5)
        result = self.library.commit(before['id'], plan['revision'], plan['commands'])
        self.assertEqual(result['revision'], 2)
        # Generated geometry matches, while new persisted IDs are assigned on commit.
        without_ids = lambda scene: [{k: v for k, v in p.items() if k != 'id'} for p in scene['elements']]
        self.assertEqual(without_ids(plan['scene']), without_ids(result['scene']))
        self.assertEqual(plan['scene']['environment'], result['scene']['environment'])
        self.assertEqual(self.library.commit(before['id'], 2, restore=1)['scene'], before['scene'])

    def test_bad_output_rejected_without_partial_mutation(self):
        target = next(iter(self.ids))
        bad = [None, [], {'summary': 'x', 'commands': [], 'python': 'print(1)'},
               {'summary': '', 'commands': []}, {'summary': 'x', 'commands': {}},
               {'summary': 'x', 'commands': [None]}, {'summary': 'x', 'commands': [{'action': []}]},
               {'summary': 'x', 'commands': [{'action': 'shell', 'command': 'whoami'}]},
               {'summary': 'x', 'commands': [{'action': 'remove', 'id': target, 'surprise': True}]},
               {'summary': 'x', 'commands': [{'action': 'update', 'id': target, 'element': {'size': [1, -2, 3]}}]},
               {'summary': 'x', 'commands': [{'action': 'update', 'id': target, 'element': {}}]},
               {'summary': 'x', 'commands': [{'action': 'add', 'element': {'id': 'model-owned'}}]},
               {'summary': 'x', 'commands': [{'action': 'environment', 'environment': {'weather': []}}]},
               {'summary': 'x', 'commands': [{'action': 'environment', 'environment': {'hour': True}}]},
               {'summary': 'x', 'commands': [{'action': 'assembly', 'assembly': {'kind': []}}]},
               {'summary': 'x', 'commands': [{'action': 'remove', 'id': 'invented'}]},
               {'summary': 'x', 'commands': [{'action': 'environment', 'environment': {'hour': 4}}] * 13}]
        for output in bad:
            with self.subTest(output=output), self.assertRaises(ValidationError):
                validated_plan(self.project, output, self.ids)
            self.assertEqual(self.library.get(self.project['id']), self.project)
        with self.assertRaises(ValidationError):
            validated_plan(self.project, {'summary': 'bad second', 'commands': [
                {'action': 'environment', 'environment': {'hour': 4}}, {'action': 'shell'}]}, self.ids)
        self.assertEqual(self.project['scene']['environment']['hour'], 16)

    def test_json_refuses_duplicate_nonfinite_and_nonobject(self):
        for raw in ('{"summary":"x","summary":"y"}', '{"n":NaN}', '{"n":Infinity}', '[]', 'null', '```json\n{}\n```'):
            with self.subTest(raw=raw), self.assertRaises(AgentError):
                parse_json(raw)

    def test_context_is_bounded_selection_aware_and_honestly_partial(self):
        project = deepcopy(self.project)
        first = project['scene']['elements'][0]
        project['scene']['elements'] = [{**first, 'id': str(i), 'position': [i, 0, 0]} for i in range(100)]
        context = scene_context(project, '99')
        self.assertTrue(context['context_is_partial'])
        self.assertEqual(context['elements'][0]['id'], '99')
        self.assertLessEqual(len(context['elements']), 40)
        self.assertEqual(context['total_elements'], 100)
        with self.assertRaises(ValidationError):
            validated_plan(project, {'summary': 'outside context', 'commands': [{'action': 'remove', 'id': '0'}]},
                           {item['id'] for item in context['elements']})
        with self.assertRaises(ValidationError):
            scene_context(project, 'not-here')

    def test_models_and_wire_payload_switch_without_saving(self):
        fixture = ModelServer()
        with running_server(fixture.handler) as server:
            service = AgentService(OllamaPlanner(server.server_port))
            self.assertEqual([x['name'] for x in service.models()['models']], sorted(fixture.names))
            for model in fixture.names:
                plan = service.preview(self.project, 'Set fog and add a room', provider='ollama', model=model, revision=1)
                self.assertEqual(plan['model'], model)
                self.assertEqual(len(plan['commands']), 2)
                self.assertEqual(plan['scene']['environment']['weather'], 'fog')
                self.assertEqual(self.library.get(self.project['id']), self.project)
            requests = [body for path, body in fixture.calls if path == '/api/chat']
            self.assertEqual([p['model'] for p in requests], fixture.names)
            self.assertEqual(requests[0]['keep_alive'], 0)
            self.assertFalse(requests[0]['stream'])
            self.assertIn('commands', requests[0]['format']['properties'])
            self.assertEqual(requests[0]['options']['num_ctx'], 16384)
            self.assertNotIn('tools', requests[0])  # bounded JSON plan, not an unconstrained tool loop
            self.assertNotIn('baseline', json.loads(requests[0]['messages'][1]['content'])['scene_context'])

    def test_zero_commands_is_informational_not_a_commit(self):
        fixture = ModelServer()
        fixture.plan = {'summary': 'Which room do you mean?', 'commands': []}
        with running_server(fixture.handler) as server:
            plan = AgentService(OllamaPlanner(server.server_port)).preview(
                self.project, 'make it bigger', provider='ollama', model='small:latest', revision=1)
            self.assertEqual(plan['commands'], [])
            self.assertEqual(plan['scene'], self.project['scene'])
            self.assertEqual(self.library.get(self.project['id'])['revision'], 1)

    def test_local_cloud_alias_and_missing_model_guards_before_prompt(self):
        fixture = ModelServer()
        fixture.custom['/api/tags'] = (200, {'models': [
            {'name': 'small:latest', 'size': 100}, {'name': 'secret-alias', 'size': 100},
            {'name': 'named-cloud', 'size': 100}, {'name': 'remote-alias', 'size': 100, 'remote_host': 'example.com'},
            {'name': 'empty', 'size': 0}, {'name': ['bad'], 'size': 100},
        ]})
        with running_server(fixture.handler) as server:
            planner = OllamaPlanner(server.server_port)
            self.assertEqual([x['name'] for x in planner.models()], ['secret-alias', 'small:latest'])
            for model in ('named-cloud', 'remote-alias', 'not-installed', '../../missing', None):
                with self.subTest(model=model), self.assertRaises(ValidationError):
                    planner.propose({}, 'private scene', model)
            fixture.details = {'remote_model': 'cloud-model', 'model_info': {'x': 1}}
            with self.assertRaises(ValidationError):
                planner.propose({}, 'private scene', 'secret-alias')
            fixture.details = {'model_info': {}}
            with self.assertRaises(ValidationError):
                planner.propose({}, 'private scene', 'small:latest')
            self.assertFalse(any(path == '/api/chat' for path, _ in fixture.calls))

    def test_http_error_redirect_malformed_and_oversize_fail_closed(self):
        fixture = ModelServer()
        with running_server(fixture.handler) as server:
            planner = OllamaPlanner(server.server_port)
            for result in ((503, {}), (302, {}), (200, b'not json'), (200, b' ' * (MAX_RESPONSE + 1))):
                fixture.custom['/api/tags'] = result
                with self.subTest(result=result[0]), self.assertRaises(AgentError):
                    planner.models()
            self.assertTrue(all(path == '/api/tags' for path, _ in fixture.calls))
        with self.assertRaises(AgentError):
            OllamaPlanner(server.server_port, timeout=.1).models()

    def test_truncated_and_tool_call_outputs_fail_closed(self):
        fixture = ModelServer()
        with running_server(fixture.handler) as server:
            planner = OllamaPlanner(server.server_port)
            for output in ({'done': False}, {'done': True, 'done_reason': 'length'},
                           {'done': True, 'message': {'content': '{}', 'tool_calls': [{'name': 'shell'}]}},
                           {'done': True, 'message': {'content': []}}, {'done': True, 'remote_host': 'example.com'}):
                fixture.custom['/api/chat'] = (200, output)
                with self.subTest(output=output), self.assertRaises(AgentError):
                    planner.propose({}, 'test', 'small:latest')

    def test_request_timeout_and_lock_release_after_error(self):
        fixture = ModelServer()
        fixture.release = Event()
        with running_server(fixture.handler) as server:
            service = AgentService(OllamaPlanner(server.server_port, timeout=.05))
            with self.assertRaises(AgentError):
                service.preview(self.project, 'test', provider='ollama', model='small:latest', revision=1)
            fixture.release.set()
            fixture.release = None
            service.ollama.timeout = 5
            self.assertEqual(service.preview(self.project, 'test', provider='ollama', model='small:latest', revision=1)['revision'], 1)

    def test_revision_required_and_single_flight_does_not_block_rules(self):
        service = AgentService()
        for revision in (None, True, 2):
            with self.subTest(revision=revision), self.assertRaises((ValidationError, RevisionConflict)):
                service.preview(self.project, 'test', provider='ollama', model='small:latest', revision=revision)
        service._inference_lock.acquire()
        try:
            with self.assertRaises(AgentError) as busy:
                service.preview(self.project, 'test', provider='ollama', model='small:latest', revision=1)
            self.assertEqual(busy.exception.status, 409)
            self.assertEqual(service.preview(self.project, 'add a wall')['provider'], 'rules')
        finally:
            service._inference_lock.release()

    def test_http_preview_stale_during_inference_and_security(self):
        fixture = ModelServer()
        with running_server(fixture.handler) as runtime:
            service = AgentService(OllamaPlanner(runtime.server_port))
            with running_server(handler_for(self.library, service)) as app:
                base = f'http://127.0.0.1:{app.server_port}'
                path = base + '/api/properties/' + self.project['id']
                def request(url, data=None, headers=None):
                    with urlopen(Request(url, data=None if data is None else json.dumps(data).encode(),
                                         headers={'Content-Type': 'application/json', **(headers or {})}), timeout=10) as reply:
                        return json.load(reply)
                self.assertEqual(request(base + '/api/agent')['endpoint'], service.ollama.endpoint)
                self.assertEqual(len(request(base + '/api/agent/models', {})['models']), 2)
                payload = {'prompt': 'test', 'revision': 1, 'provider': 'ollama', 'model': 'small:latest'}
                plan = request(path + '/preview', payload)
                self.assertEqual(request(path)['revision'], 1)
                self.assertEqual(len(plan['commands']), 2)
                for headers in ({'Origin': 'https://evil.example'}, {'Host': 'evil.example'}):
                    with self.assertRaises(HTTPError) as denied:
                        request(path + '/preview', payload, headers)
                    self.assertEqual(denied.exception.code, 403)
                fixture.release = Event()
                fixture.started.clear()
                outcomes = []
                def slow_request():
                    try:
                        request(path + '/preview', payload)
                    except HTTPError as error:
                        outcomes.append(error.code)
                thread = Thread(target=slow_request)
                thread.start()
                self.assertTrue(fixture.started.wait(5))
                request(path + '/edit', {'revision': 1, 'commands': [{'action': 'environment', 'environment': {'hour': 5}}]})
                fixture.release.set()
                thread.join(5)
                self.assertFalse(thread.is_alive())
                self.assertEqual(outcomes, [409])
                self.assertEqual(request(path)['revision'], 2)
                self.assertEqual(request(path)['scene']['environment']['weather'], 'clear')


if __name__ == '__main__':
    unittest.main()
