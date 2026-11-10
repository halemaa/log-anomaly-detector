# 3 — Big O of this code, line by line

## The claim

`detect_anomalies` runs in **O(n)** time and **O(k)** space, where:

- `n` = number of log entries
- `k` = number of entries in the window at any one time

This note walks through why, so you can derive it yourself next time.

## Set the variables

- `n` is the input size (log lines)
- `k` is the window size *in entries*, bounded by whatever fits in
  `window_seconds` at your traffic rate

In our sample log at ~5 requests/sec with a 60s window, `k ≈ 300`.
At 1,000 requests/sec, `k ≈ 60,000`. Either way, `k ≤ n` and `k` is
bounded by rate × window size, not by `n` itself.

## Walk through the hot loop

```python
for entry in entries:                                    # (1)
    now = entry.time
    is_err = _is_error(entry.status)

    window.append((now, is_err))                         # (2)
    if is_err:
        errors_in_window += 1

    cutoff = now - timedelta(seconds=window_seconds)
    while window and window[0][0] < cutoff:              # (3)
        _, old_err = window.popleft()                    # (4)
        if old_err:
            errors_in_window -= 1

    if len(window) >= min_sample_size:                   # (5)
        rate = errors_in_window / len(window)
        if rate > threshold_rate:
            ...
```

### (1) The outer loop

Runs exactly `n` times, once per entry. So any constant-time work
inside the loop contributes O(n) total.

### (2) `deque.append()`

O(1). A deque is a doubly linked list of fixed-size blocks; appending
is adding to the last block (or allocating a new block when the last
fills up, which is O(1) amortised). Same complexity as `list.append`.

### (3) The `while` loop that shrinks the window

This is the trickiest part of the analysis. Looking at it in isolation
you might think "a loop inside a loop — O(n²)!" That's wrong, and
understanding why is the insight behind sliding window.

**Amortised argument.** Each entry is added to the deque exactly once
(step 2) and removed exactly once (step 4). Over the entire outer
loop — `n` iterations — the total number of inner-loop iterations
across ALL outer iterations is at most `n`.

So the inner `while` is O(n) in total, not O(n) per outer iteration.
Average cost per outer iteration: O(1).

This is the same argument as "amortised O(1) for `list.append`":
occasional expensive steps, averaged over the whole run, come out
cheap.

### (4) `deque.popleft()`

O(1), same reason as `append`.

### (5) Everything else inside the loop

Constant time — arithmetic, comparisons, the `len()` of a deque is
O(1) in Python because it's cached. Contributes O(n) across the run.

## Totalling it up

- Outer loop: `n` iterations
- Per-iteration work: O(1) direct + amortised O(1) from the inner
  loop
- **Total time: O(n)**

- Memory: the deque holds at most `k` entries, plus a handful of
  scalar counters.
- **Total space: O(k)**

Both are optimal. You can't do better than O(n) for a problem that
requires looking at every entry at least once, and you can't do better
than O(k) when you need to know what's in the window.

## Why this matters in practice

The sample log in this repo has about 20,000 entries. The detector
finishes in about 60 ms on a laptop.

If we'd written the naive version — "for each entry, scan backwards to
find the last 60 seconds" — that would be O(n·k). On 20,000 entries
with `k ≈ 300`, that's 6 million operations. Still fast enough to
*seem* fine for a toy. But:

- 1 million-line log: naive is 300 million ops. Several seconds.
- 10 million-line log: naive is 3 billion ops. A couple of minutes.
- 100 million-line log: naive is ~unusable.

Sliding window handles all of them linearly: a 100 million-line log
still finishes in minutes, not hours, with basically flat memory.

This is why "pick the right algorithm" isn't an academic concern.
It's the difference between a tool you ship and one that works in
dev and dies in production.

## How to narrate this in an interview

> "The detector is one pass over the log. On every entry I append to
> a deque and then pop anything older than the window from the left
> side. Each entry is added once and removed once across the whole
> run, so the total work is O(n) amortised, and memory is O(k) where
> k is the number of entries in the window. That's optimal — I need
> to see every entry at least once, and I need to know what's in the
> window at any given time."

That's the whole analysis in two sentences. Practice it out loud.
