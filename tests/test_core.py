import unittest

from tiny_retry_budget import RetryBudget


class FakeClock:
    """A deterministic clock for tests.

    The budget does not currently refill based on time, but the clock is part
    of the public constructor and tests exercise that it is accepted and
    stored. Using a fake clock keeps tests independent of wall time.
    """

    def __init__(self, start: float = 0.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now


class RetryBudgetConstructionTests(unittest.TestCase):
    def test_defaults_are_usable(self) -> None:
        budget = RetryBudget()
        self.assertEqual(budget.ratio, 0.1)
        self.assertEqual(budget.cap, 10)
        self.assertEqual(budget.tokens, 0.0)

    def test_negative_ratio_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            RetryBudget(ratio=-0.1)

    def test_zero_ratio_is_allowed(self) -> None:
        budget = RetryBudget(ratio=0.0)
        self.assertEqual(budget.ratio, 0.0)

    def test_non_positive_cap_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            RetryBudget(cap=0)
        with self.assertRaises(ValueError):
            RetryBudget(cap=-1)

    def test_clock_is_accepted(self) -> None:
        clock = FakeClock(123.0)
        budget = RetryBudget(clock=clock)
        self.assertEqual(budget.tokens, 0.0)


class RetryBudgetTokenTests(unittest.TestCase):
    def test_cold_start_disallows_retry(self) -> None:
        budget = RetryBudget(ratio=1.0, cap=10)
        self.assertFalse(budget.allow())

    def test_one_success_earns_one_retry_at_ratio_one(self) -> None:
        budget = RetryBudget(ratio=1.0, cap=10)
        budget.record_success()
        self.assertTrue(budget.allow())
        self.assertFalse(budget.allow())

    def test_fractional_ratio_accumulates(self) -> None:
        budget = RetryBudget(ratio=0.25, cap=10)
        for _ in range(4):
            budget.record_success()
        self.assertAlmostEqual(budget.tokens, 1.0)
        self.assertTrue(budget.allow())
        self.assertAlmostEqual(budget.tokens, 0.0)

    def test_tokens_are_capped(self) -> None:
        budget = RetryBudget(ratio=1.0, cap=3)
        for _ in range(10):
            budget.record_success()
        self.assertEqual(budget.tokens, 3.0)

    def test_cap_is_enforced_across_fractional_accumulation(self) -> None:
        budget = RetryBudget(ratio=0.5, cap=2)
        for _ in range(10):
            budget.record_success()
        self.assertEqual(budget.tokens, 2.0)

    def test_allow_decrements_exactly_one_token(self) -> None:
        budget = RetryBudget(ratio=1.0, cap=10)
        for _ in range(3):
            budget.record_success()
        self.assertEqual(budget.tokens, 3.0)
        self.assertTrue(budget.allow())
        self.assertEqual(budget.tokens, 2.0)

    def test_reset_clears_tokens(self) -> None:
        budget = RetryBudget(ratio=1.0, cap=10)
        budget.record_success()
        budget.reset()
        self.assertEqual(budget.tokens, 0.0)
        self.assertFalse(budget.allow())

    def test_ratio_zero_never_allows_retry(self) -> None:
        budget = RetryBudget(ratio=0.0, cap=10)
        for _ in range(100):
            budget.record_success()
        self.assertEqual(budget.tokens, 0.0)
        self.assertFalse(budget.allow())


if __name__ == "__main__":
    unittest.main()
