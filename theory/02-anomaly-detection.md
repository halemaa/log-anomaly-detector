# 2 — Anomaly detection, briefly

## What this tool actually does

`anomaly.py` watches a stream of HTTP requests and asks one question
once per request: *"over the last 60 seconds, is more than 10% of
traffic failing with a 5xx?"*

That's it. One rule, one threshold, one window.

It's deliberately simple because **most real anomaly detection in
production starts here.** The exotic algorithms (ARIMA, Isolation
Forest, LSTM autoencoders) only pay off after you've exhausted
rule-based thresholds — and most teams never need to.

## Why 5xx specifically, not 4xx

- **5xx** means *your server* broke. Something went wrong on our side.
  A 5xx spike is almost always worth investigating.
- **4xx** means *the client* did something wrong. A 404 spike could
  be a crawler hitting dead URLs, a typo in a deployment, or a scanner
  probing your site. Noisy, often irrelevant.

Mixing them together drowns the real signal in noise. The detector
treats them separately. 5xx fires anomalies. 4xx doesn't.

## What a "baseline" is, and why we skipped having one

The current tool uses a **static threshold** (10%). That's a conscious
simplification. A more sophisticated version would use a
**baseline-relative threshold** — "current window is 10x higher than
the rolling average of the last hour" — so it adapts to each service's
normal error rate.

Why we didn't:
- Static thresholds are easy to explain and easy to tune
- A service's normal error rate is usually small enough that "above
  10%" is a safe absolute rule
- Baseline-relative detection has its own failure mode: a service
  that's *always* broken has a high baseline, so the rule never fires

Good anomaly detectors in practice use *both*: a static safety net
and a baseline-relative detector. We shipped the safety net first,
the way most SOCs do.

## How this maps to tools you've heard of

| Tool | What it adds on top of this idea |
|---|---|
| **Datadog / New Relic APM** | Automatic baselines per service and endpoint, correlation across signals |
| **Prometheus + Alertmanager** | `rate()` and `histogram_quantile()` compute sliding windows in query time, then alert rules fire |
| **Splunk / Elastic Security** | Same pattern against security events: failed logins, firewall drops, DNS queries |
| **AWS CloudWatch Anomaly Detection** | ML-fitted baselines, confidence bands, automatic seasonal adjustment |
| **Wazuh / OSSEC** | Rule-based detection on host logs (brute force, privilege escalation signatures) |

The common thread: **count events in a recent window, compare to
expectation, alert on the outliers.** The algorithm is the same thing
this repo demonstrates. The difference is engineering — storage
backends, distributed scaling, enrichment, correlation, visualisation.

## Where sliding-window anomaly detection fits in the security kill chain

- **Reconnaissance** — port scans show up as bursts of SYN packets or
  bursts of 404s on random paths
- **Credential stuffing** — bursts of failed logins from distributed
  IPs targeting one endpoint
- **DoS / DDoS** — the obvious one: requests per second spike, error
  rate follows
- **Data exfiltration** — bursts of large response bodies from one IP,
  or bursts of DNS queries to unusual domains
- **Lateral movement** — bursts of SMB or SSH auth events across hosts

All of them reduce to "count things in a window, compare to the
baseline." The window sizes and thresholds differ; the pattern
doesn't.

## What this tool can't do (yet)

- **No alerting output.** It prints to stdout. A real SOC tool emits
  structured events to a SIEM.
- **No source correlation.** An attack from a single IP looks the
  same as a widespread outage. Per-IP windows would separate them.
- **No seasonality.** Legitimate traffic has daily and weekly
  rhythms. A static threshold doesn't adapt.
- **No streaming mode.** It reads a file end-to-end. Production
  tools tail logs and alert in real time.
- **No stateful memory across runs.** If you alert at 09:15:16 and
  run it again at 09:16:16, both runs will fire the same alert.

The `04-production-considerations.md` note walks through what
closing each of those gaps would look like.

## The interview phrasing

> "I built a sliding-window anomaly detector. It reads an nginx
> access log, maintains a deque of the last 60 seconds of events in
> one O(n) pass, and flags when the 5xx error rate exceeds 10%. I
> used a cooldown so one sustained incident doesn't produce a
> flood of duplicate alerts. The same pattern is what Prometheus
> uses with `rate()` and what SIEM tools use for brute-force
> detection — fixed-threshold rule on a sliding window of events."

That's a two-sentence summary of a small project that signals
you've thought about SOC work seriously.
