# 1 — Sliding window, in plain words

## The problem it solves

You have a stream of events — log lines, API requests, stock trades,
heartbeat packets. You want to answer a question about the *recent*
ones: how many errors in the last minute? How many trades in the last
hour? Is the moving average above a threshold?

The naive approach is quadratic:

```python
# BAD — O(n²)
for i, event in enumerate(events):
    recent = [e for e in events[:i+1] if e.time > event.time - window]
    check(recent)
```

Every event re-scans the whole history to find the "recent" ones. On a
million-line log, that's a trillion comparisons. The program crawls.

Sliding window fixes this by **keeping the recent events in a deque**
instead of recomputing them each time.

## The core move

```python
from collections import deque

window = deque()
for event in events:
    # Expand: new event joins the right side
    window.append(event)

    # Shrink: drop anything that aged out of the left side
    while window and window[0].time < event.time - WINDOW_SIZE:
        window.popleft()

    # Check: now the deque holds exactly the "recent" events
    check(window)
```

Three steps on every event: append, pop while stale, check. Each event
is added **once** and removed **once** across the whole run. That's
O(n) total — one pass, linear time.

## Why a deque, specifically

- `list.append(x)` is O(1), but `list.pop(0)` is O(n) because every
  other element has to shift left one slot. Using a list here would
  silently make the whole algorithm O(n²).
- `deque` is a doubly linked list of fixed-size chunks. Both
  `append()` and `popleft()` are O(1).

Any time you're expanding one side and shrinking the other, reach for
`collections.deque`.

## Two flavours of sliding window

### Fixed-size

The window always holds exactly `K` items. On every new event, pop
the oldest.

```python
# "The moving average of the last 5 readings"
window = deque(maxlen=5)   # deque enforces this automatically
window.append(new_reading)
avg = sum(window) / len(window)
```

Classic uses: moving averages, last-N-requests rate limiters, the
"maximum in every window of size K" interview problem.

### Dynamic (time-based or condition-based)

The window grows and shrinks based on a rule — in our case, "drop
events older than `window_seconds`." The window's size depends on
how many events happened in that time frame.

```python
# "Events in the last 60 seconds"
window = deque()
window.append(new_event)
while window and window[0].time < new_event.time - timedelta(seconds=60):
    window.popleft()
```

This is what `anomaly.py` does.

## Three-question mental model

For every sliding-window problem, ask:

1. **What's in the window?** (indices, values, error counts, a hash map)
2. **When do you shrink?** (fixed size? time-based? invalid state?)
3. **What do you check at each step?** (sum, rate, min, max, set membership)

For this project:
1. Pairs of `(timestamp, is_error_bool)` — one per log entry
2. When the oldest entry is more than `window_seconds` behind the current one
3. Error rate: count of `is_error=True` divided by the deque's length

That's the whole algorithm.

## Where you'll see it again

- **Rate limiters** — "max 100 requests per minute per IP" — a sliding
  window of request timestamps per IP
- **Intrusion detection** — "flag any IP that triggered more than 20
  failed logins in 5 minutes" — sliding window of failed auth events
- **Trading systems** — moving averages, Bollinger bands, volume
  anomalies — sliding windows everywhere
- **Metrics collection** — percentile summaries over the last 5 minutes
  (p50, p95, p99)
- **Fraud detection** — sudden burst of transactions on a card
- **LeetCode** — "Longest Substring Without Repeating Characters",
  "Minimum Window Substring", "Sliding Window Maximum", dozens more

The pattern isn't a trick — it's the standard answer whenever you're
asked something about "the recent N things."
