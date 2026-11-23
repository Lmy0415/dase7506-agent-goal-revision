import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch

import requests

from flash import DeepSeekFlash, ModelServiceError


MESSAGES = [{"role": "user", "content": "Reply OK."}]


class BudgetTest(unittest.TestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.path = Path(temp.name) / "ledger.jsonl"
        self.post = Mock()
        with patch("flash.dotenv_values", return_value={"DEEPSEEK_API_KEY": "dummy-test-key"}):
            self.client = DeepSeekFlash(self.path, post=self.post)

    def entries(self):
        return [json.loads(line) for line in self.path.read_text().splitlines()]

    def test_budget_checked_before_network(self):
        self.client.cap = 1
        with self.assertRaisesRegex(ModelServiceError, "budget"):
            self.client.request("test", MESSAGES, max_tokens=1)
        self.post.assert_not_called()

    def test_records_reservation_and_peak_upper_bound(self):
        response = self.post.return_value
        response.status_code = 200
        response.json.return_value = {
            "usage": {"prompt_tokens": 10, "completion_tokens": 2, "prompt_cache_hit_tokens": 4},
            "choices": [{"message": {"content": "OK"}}],
        }
        self.client.request("test", MESSAGES, max_tokens=2)
        reserved, settled = self.entries()
        self.assertEqual((reserved["status"], settled["status"]), ("reserved", "settled"))
        self.assertEqual(settled["charge_upper_nanos"], 5400)
        self.assertNotIn("dummy-test-key", self.path.read_text())

    def test_timeout_retains_budget_reservation(self):
        self.post.side_effect = requests.Timeout()
        with self.assertRaisesRegex(ModelServiceError, "transport"):
            self.client.request("test", MESSAGES, max_tokens=1)
        reserved, timeout = self.entries()
        self.assertEqual(timeout["charge_upper_nanos"], reserved["charge_upper_nanos"])
        self.client.cap = reserved["charge_upper_nanos"]
        with self.assertRaisesRegex(ModelServiceError, "budget"):
            self.client.request("retry", MESSAGES, max_tokens=1)
        self.assertEqual(self.post.call_count, 1)
