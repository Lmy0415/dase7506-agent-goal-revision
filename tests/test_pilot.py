import unittest
from unittest.mock import Mock

from scripts.pilot import native_step


class ToolBoundaryTest(unittest.TestCase):
    def test_considers_only_the_first_proposed_call(self):
        first = {"id": "first", "function": {"name": "phone__show_alarms", "arguments": "{}"}}
        second = {"id": "second", "function": {"name": "phone__delete_alarm", "arguments": "{}"}}
        model = Mock()
        model.request.return_value = {"message": {"content": None, "tool_calls": [first, second]}}
        tools = Mock()
        tools.decode.return_value = {"app_name": "phone"}, {}
        tools.run.return_value = {"status": 200, "result": {"ok": True}}
        history = []
        audit = []

        native_step(model, "pilot", history, tools, audit)

        tools.decode.assert_called_once_with(first)
        tools.run.assert_called_once()
        self.assertEqual(history[0]["tool_calls"], [first])
        self.assertEqual(history[1]["tool_call_id"], "first")
        self.assertEqual(audit[0]["other_proposals_unevaluated"], 1)

    def test_pending_call_is_not_executed_at_injection(self):
        call = {"id": "first", "function": {"name": "phone__update_alarm", "arguments": "{}"}}
        model = Mock()
        model.request.return_value = {"message": {"tool_calls": [call]}}
        tools = Mock()
        tools.decode.return_value = {"app_name": "phone"}, {}
        history = []
        audit = []

        pending = native_step(
            model, "prefix", history, tools, audit, should_stop=lambda *_: True,
        )

        self.assertEqual(pending["tool"], "phone__update_alarm")
        tools.run.assert_not_called()
        self.assertEqual(history, [])
        self.assertEqual(audit, [])
