import unittest
from unittest.mock import Mock, patch

from scripts.formal import BranchModel, PROTOCOL
from scripts.pilot import BranchBudgetError
from scripts.screen_candidates import FormalTools


class FormalBudgetTest(unittest.TestCase):
    def test_planning_and_tool_calls_consume_the_same_allowance(self):
        provider = Mock()
        provider.request.return_value = {"usage": {"prompt_tokens": 2, "completion_tokens": 3}}
        branch = BranchModel(provider)
        messages = [{"role": "user", "content": "Run the task."}]
        with patch.dict(PROTOCOL, post_update_model_calls=2):
            branch.request("B", messages, json_mode=True)
            branch.request("B", messages, tools=[])
            with self.assertRaisesRegex(BranchBudgetError, "model-call"):
                branch.request("B", messages, tools=[])
        self.assertEqual(provider.request.call_count, 2)
        self.assertEqual((branch.input_tokens, branch.output_tokens), (4, 6))

    def test_input_limit_is_checked_before_provider_call(self):
        provider = Mock()
        branch = BranchModel(provider)
        with patch.dict(PROTOCOL, post_update_input_tokens=1):
            with self.assertRaisesRegex(BranchBudgetError, "input-token"):
                branch.request("A", [{"role": "user", "content": "Run the task."}])
        provider.request.assert_not_called()

    def test_attachment_get_is_a_mutation(self):
        adapter = FormalTools.__new__(FormalTools)
        self.assertTrue(adapter.is_mutating(
            {"method": "GET", "app_name": "gmail", "api_name": "download_attachment"},
        ))
        self.assertFalse(adapter.is_mutating(
            {"method": "GET", "app_name": "gmail", "api_name": "show_email"},
        ))
