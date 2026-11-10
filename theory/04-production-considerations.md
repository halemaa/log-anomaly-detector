# 4 — What's missing to make this production

This tool works. It's small, correct, well-tested, and does what it
says. But I want to be honest about the gap between this and
something you'd run against a bank's logs at 3 AM.

Listing the gaps is a strength, not a weakness. Interviewers love
candidates who can say "here's what I built, and here's what I'd add
to make it real."

## Gap 1: It reads a file, not a stream

Right now the detector reads the whole log, scans once, exits. A
production tool would **tail** the file: open it, read to end, then
block waiting for new lines, process them as they arrive.

Change: wrap the parsing loop in something like `tailer.follow()` or
reimplement the basic `tail -f` logic with `seek()`.

Trade-off: you gain real-time alerting but need to handle log
rotation (the file gets renamed or truncated when `logrotate` runs).

## Gap 2: It alerts to stdout

Prints to the terminal. Fine for CLI, useless for a service.

Real options:
- Emit structured JSON to a file or socket → picked up by a log
  shipper → routed to a SIEM
- Push to Slack / PagerDuty via webhook
- Send to Prometheus Alertmanager
- Write to a Postgres / ClickHouse table for a dashboard

Change: swap the final `print()` for an `Alerter` protocol with
backends.

## Gap 3: It flags overall rate, not per-source

A spike from 1,000 distinct IPs (an actual outage) looks identical
to a spike from one IP (a scanner or a stuck client).

Change: keep a dict of `{client_ip: deque_of_recent_events}` and
run the detector per IP as well as overall. Flag per-IP bursts
separately.

Trade-off: memory grows with the number of unique IPs. Bounded by
LRU eviction or by keeping only "interesting" IPs (first-seen today,
on a watchlist, etc.).

## Gap 4: It has no notion of seasonality

Traffic has rhythms. Monday 9 AM is not Sunday 3 AM. A static
threshold is tuned for one and wrong for the other.

Real tools either:
- Learn a baseline per hour-of-week (168 baselines per service)
- Use a rolling baseline of "same time, last week"
- Use statistical models (Holt-Winters, Prophet) that explicitly
  model seasonality

Change: track baseline buckets by `(day_of_week, hour)` and compare
the current window to the matching bucket.

## Gap 5: It has no stateful memory across runs

Run it at 09:15, run it again at 09:16, both runs alert on the same
spike. In production you'd want to remember "I already alerted on
this incident."

Change: persist the last-flagged timestamp to a file or small DB,
load it on startup. Or lean on your alerting tool's own
deduplication.

## Gap 6: Log format is hard-coded

Only parses Combined Log Format. If someone sends it a different
format — nginx with `log_format main`, HAProxy, syslog, CloudFront
— it quietly fails to parse everything.

Change: accept a format string via CLI flag, or support a few common
formats by name, or (more flexibly) require a `--regex` argument with
named groups.

## Gap 7: No tests against real-world log quirks

Our test suite uses well-formed synthetic data. Real logs have:
- Lines that straddle a buffer boundary (log rotation)
- Lines that are longer than expected (extra headers)
- Unicode in user agents
- Clock skew (events out of time order)
- `-` instead of a size when the response had no body

The detector handles some of these (the parser returns None on
unmatched lines), but we haven't proven it. A corpus of real-world
logs — even one `access.log.1` donated from a friend's server —
would exercise every edge case we'd see in production.

## Gap 8: Observability of the detector itself

Who watches the watcher? In production you'd want metrics *about*
the detector:
- `logs_parsed_total`
- `logs_unparseable_total`
- `anomalies_flagged_total`
- `window_size_current`
- `processing_lag_seconds`

Change: expose a `/metrics` endpoint, or emit counters to statsd on
each loop iteration.

## Gap 9: Concurrency

A single file on a single machine is fine. Multiple log files,
multiple services, multiple hosts — you need parallelism. And now
you need coordination: deduplicating alerts across multiple detector
instances, sharing baselines, deciding who alerts.

This is where you stop writing a tool and start running a service.
Usually the answer is "stop here, use an existing SIEM."

## The honest one-paragraph summary

> "This is the simplest correct version of sliding-window anomaly
> detection. To ship it: add streaming input, structured output,
> per-source windows, seasonality-aware baselines, and stateful
> dedup across runs. Most teams never need all of those — a static
> threshold on a sliding window is where real incident detection
> starts, not where it ends."

That's a senior-sounding sentence that costs you nothing to say
truthfully.
