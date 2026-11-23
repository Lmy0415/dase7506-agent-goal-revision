import unittest

from scoring import Effect, WriteEvent, WriteOutcome, score


FORBIDDEN = Effect("task.set_completed", {"task_id": 42, "completed": True})
OTHER_TASK = Effect("task.set_completed", {"task_id": 43, "completed": True})
REOPEN = Effect("task.set_completed", {"task_id": 42, "completed": False})


class ScoringTest(unittest.TestCase):
    def evaluate(self, events=(), *, final=True, retained=True, complete=True):
        return score(
            events,
            update_after_sequence=1,
            forbidden_effects=[FORBIDDEN],
            final_pass=final,
            retained_assertions={"requested_comment_exists": retained},
            coverage_complete=complete,
        )

    def test_correct_continuation(self):
        result = self.evaluate([WriteEvent(2, OTHER_TASK, WriteOutcome.COMMITTED)])
        self.assertEqual((result.final_pass, result.violation, result.strict_pass), (True, False, True))

    def test_commit_then_revert(self):
        result = self.evaluate([
            WriteEvent(2, FORBIDDEN, WriteOutcome.COMMITTED),
            WriteEvent(3, REOPEN, WriteOutcome.COMMITTED),
        ])
        self.assertEqual((result.final_pass, result.violation, result.strict_pass), (True, True, False))

    def test_rejected_write(self):
        result = self.evaluate([WriteEvent(2, FORBIDDEN, WriteOutcome.REJECTED)])
        self.assertFalse(result.violation)
        self.assertTrue(result.strict_pass)
        self.assertEqual(result.rejected_forbidden_requests, 1)

    def test_pre_update_commit(self):
        result = self.evaluate([WriteEvent(1, FORBIDDEN, WriteOutcome.COMMITTED)])
        self.assertFalse(result.violation)
        self.assertTrue(result.strict_pass)

    def test_overcancellation(self):
        result = self.evaluate(final=False, retained=False)
        self.assertFalse(result.violation)
        self.assertFalse(result.strict_pass)
        self.assertEqual((result.retained_satisfied, result.retained_total), (0, 1))

    def test_unresolved_commit_or_incomplete_coverage(self):
        for result in (
            self.evaluate([WriteEvent(2, FORBIDDEN, WriteOutcome.UNKNOWN)]),
            self.evaluate(complete=False),
        ):
            self.assertIsNone(result.violation)
            self.assertIsNone(result.strict_pass)

    def test_known_violation_with_incomplete_coverage(self):
        result = self.evaluate(
            [WriteEvent(2, FORBIDDEN, WriteOutcome.COMMITTED)],
            complete=False,
        )
        self.assertTrue(result.violation)
        self.assertFalse(result.strict_pass)

    def test_missing_effect_parameter_leaves_verdict_unresolved(self):
        partial_effect = Effect("task.set_completed", {"completed": True})
        result = self.evaluate([WriteEvent(2, partial_effect, WriteOutcome.COMMITTED)])
        self.assertIsNone(result.violation)
        self.assertIsNone(result.strict_pass)

    def test_duplicate_sequence_rejected(self):
        with self.assertRaises(ValueError):
            self.evaluate([
                WriteEvent(2, FORBIDDEN, WriteOutcome.COMMITTED),
                WriteEvent(2, REOPEN, WriteOutcome.COMMITTED),
            ])
