# tiny-retry-budget

A shared retry budget so a failing dependency cannot amplify load.

```python
from tiny_retry_budget import RetryBudget

budget = RetryBudget(ratio=0.1, cap=10)

# A call succeeded; earn one tenth of a retry.
budget.record_success()

# A call failed; ask permission before retrying.
if budget.allow():
    pass  # safe to retry
else:
    pass  # do not retry; the budget is exhausted
```

The budget starts empty. Retries are earned by successes, not granted up
front, so a cold process cannot immediately hammer a dependency that may
already be failing.

## Why this exists

When a downstream dependency degrades, every caller that retries makes the
problem worse. A per-process retry limit does not help when hundreds of
processes share the same dependency. A shared budget does: each success
earns a fraction of a retry, and the total outstanding retries are capped.

The trade-off is that a cold start disallows retries until successes have
been recorded. That is intentional. The alternative -- starting with a full
budget -- would let a cold start immediately amplify an outage, which is the
exact failure mode this library exists to prevent.

## API

`RetryBudget(ratio=0.1, cap=10, clock=None)`

- `ratio`: retries earned per success. Non-negative. Defaults to `0.1`.
- `cap`: absolute maximum number of outstanding retries. Positive.
  Defaults to `10`.
- `clock`: optional callable returning a monotonic timestamp. Defaults to
  `time.monotonic`. Injecting a fake clock keeps tests deterministic.

Methods and properties:

- `record_success()`: earn `ratio` retry tokens, capped at `cap`.
- `allow() -> bool`: consume one retry token if available.
- `reset()`: discard all tokens and reset the clock reference.
- `ratio`, `cap`, `tokens`: read-only properties.

## Edge case

Because tokens accumulate as floats, a ratio like `0.1` will not produce
exactly one token after ten successes in binary floating point. The budget
tracks fractional tokens and only allows a retry once the total reaches
`1.0`. If you need exact decimal accounting, choose a ratio that is exactly
representable (for example `0.25`) or record successes in batches.
