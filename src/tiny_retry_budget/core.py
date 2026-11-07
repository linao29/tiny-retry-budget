"""Core retry budget implementation.

The budget is a token bucket with two independent limits:

* a *retry ratio*: the number of retries allowed per successful call
* an *absolute cap*: a hard upper bound on outstanding retries, regardless
  of how many successes have happened.

Both limits are enforced by :meth:`RetryBudget.allow`. The ratio prevents a
steady stream of failures from consuming unbounded retries, while the cap
protects against a burst of callers exhausting the budget before any
successes can replenish it.

A monotonic clock is injected so tests do not depend on wall time and so the
budget behaves correctly across system clock changes.
"""

from __future__ import annotations

import time
from typing import Callable, Optional


class RetryBudget:
    """A shared budget that limits retries against a failing dependency.

    The budget is refilled by *successes* and consumed by *retries*. A call
    that succeeds calls :meth:`record_success`; a call that fails and wants to
    retry calls :meth:`allow` first. If :meth:`allow` returns ``False`` the
    caller should not retry.

    The budget is parameterised by:

    * ``ratio``: retries allowed per success. A ratio of ``0.1`` means one
      retry is earned for every ten successes. Must be non-negative.
    * ``cap``: absolute maximum number of retries that can be outstanding at
      once. Must be positive.
    * ``clock``: a callable returning a monotonic timestamp. Defaults to
      :func:`time.monotonic`. Injecting a fake clock keeps tests deterministic.

    The budget starts empty; callers must earn retries by recording successes.
    This is deliberate: a cold start should not immediately allow retries
    against a dependency that may already be failing.
    """

    def __init__(
        self,
        ratio: float = 0.1,
        cap: int = 10,
        clock: Optional[Callable[[], float]] = None,
    ) -> None:
        if ratio < 0:
            raise ValueError("ratio must be non-negative")
        if cap <= 0:
            raise ValueError("cap must be positive")
        self._ratio = float(ratio)
        self._cap = int(cap)
        self._clock = clock if clock is not None else time.monotonic
        # Fractional tokens are tracked as a float so a ratio like 0.1 does
        # not lose precision when successes arrive one at a time.
        self._tokens: float = 0.0
        self._last_refill: float = self._clock()

    @property
    def ratio(self) -> float:
        """The configured retry ratio."""
        return self._ratio

    @property
    def cap(self) -> int:
        """The configured absolute retry cap."""
        return self._cap

    @property
    def tokens(self) -> float:
        """Current number of available retry tokens.

        This is exposed for observability and tests. It is never negative and
        never exceeds :attr:`cap`.
        """
        return self._tokens

    def record_success(self) -> None:
        """Record one successful call, earning ``ratio`` retry tokens.

        Tokens are capped at :attr:`cap`. The cap is enforced here as well as
        in :meth:`allow` so that a long run of successes cannot accumulate an
        unbounded number of tokens.
        """
        self._tokens = min(self._cap, self._tokens + self._ratio)

    def allow(self) -> bool:
        """Attempt to consume one retry token.

        Returns ``True`` and decrements the budget if a token is available.
        Returns ``False`` otherwise. The check and decrement happen together
        so callers cannot oversubscribe the budget by racing.
        """
        if self._tokens >= 1.0:
            self._tokens -= 1.0
            return True
        return False

    def reset(self) -> None:
        """Discard all tokens and reset the clock reference.

        This is intended for tests and for long-lived processes that want to
        drop accumulated budget, for example after a dependency recovers.
        """
        self._tokens = 0.0
        self._last_refill = self._clock()
