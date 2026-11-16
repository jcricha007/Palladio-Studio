import json
import unittest
from unittest.mock import patch

from palladio.local_agent import OllamaPlanner, AgentError
from palladio.model_check import check


class ModelProfileTests(unittest.TestCase):
    def run_model(self, details, reply=None):
        calls = []
        def request(path, payload=None, **kwargs):
            calls.append((path, payload))
            if path == '/api/tags':
                return {'models': [{'name': 'local:latest', 'size': 14_000_000_000}]}
            if path == '/api/show':
                return {'model_info': {'general.architecture': 'test'}, **details}
            return reply or {'done': True, 'message': {'content': json.dumps({'summary': 'No change', 'commands': []})}}
        planner = OllamaPlanner()
        with patch.object(planner, '_request', side_effect=request):
            planner.propose({}, 'No changes', 'local:latest')
        return calls[-1][1]

    def test_reported_reasoning_levels_leave_room_for_json_and_unload(self):
        payload = self.run_model({'thinking': {'values': ['low', 'medium', 'high']}})
        self.assertEqual(payload['think'], 'low')
        self.assertEqual(payload['options']['num_predict'], 4096)
        self.assertEqual(payload['options']['num_ctx'], 16384)
        self.assertEqual(payload['keep_alive'], 0)
        self.assertIsInstance(payload['format'], dict)

    def test_older_gptoss_and_aliases_use_architecture_metadata(self):
        payload = self.run_model({'model_info': {'general.architecture': 'gptoss'}})
        self.assertEqual(payload['think'], 'low')

    def test_ordinary_models_do_not_receive_unsupported_thinking_options(self):
        for details in [{}, {'thinking': {'values': [False]}}, {'thinking': 'malformed'}]:
            with self.subTest(details=details):
                payload = self.run_model(details)
                self.assertNotIn('think', payload)
                self.assertEqual(payload['options']['num_predict'], 2048)

    def test_truncated_reasoning_reply_still_cannot_be_applied(self):
        with self.assertRaises(AgentError):
            self.run_model({'thinking': {'values': ['low']}}, {
                'done': True, 'done_reason': 'length',
                'message': {'thinking': 'unfinished', 'content': '{'}})

    def test_acceptance_checks_a_disposable_property_and_requested_result(self):
        plan = {'summary': 'Set fog', 'commands': [
            {'action': 'environment', 'environment': {'weather': 'fog'}}]}
        with patch.object(OllamaPlanner, 'propose', return_value=plan):
            result = check('test:latest', 11435)
        self.assertTrue(result['passed'])
        self.assertTrue(result['saved_property_unchanged'])
        plan['commands'][0]['environment']['hour'] = 3
        with patch.object(OllamaPlanner, 'propose', return_value=plan):
            with self.assertRaisesRegex(RuntimeError, 'extra changes'):
                check('test:latest', 11435)


if __name__ == '__main__':
    unittest.main()
