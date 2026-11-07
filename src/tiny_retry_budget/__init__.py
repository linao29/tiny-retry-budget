"""tiny-retry-budget: a shared retry budget for downstream dependencies.

This package exposes a single class, :class:`RetryBudget`, which limits the
number of retries a process will perform against a shared failing dependency.
The goal is to prevent a failing downstream service from being amplified by
many callers all retrying at once.
"""

from .core import RetryBudget

__all__ = ["RetryBudget"]
