"""Tests for the log anomaly detector."""

from datetime import datetime, timedelta, timezone

from anomaly import LogEntry, detect_anomalies, parse_line


def _mk_entry(seconds_from_start: int, status: int) -> LogEntry:
    """Convenience: build a LogEntry at a given offset."""
    base = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    return LogEntry(
        time=base + timedelta(seconds=seconds_from_start),
        status=status,
        path="/x",
        ip="1.1.1.1",
    )


def test_parse_valid_line():
    line = (
        '203.0.113.5 - - [10/Nov/2026:09:15:30 +0000] '
        '"GET /api/users HTTP/1.1" 500 234 "-" "curl/8.0"'
    )
    entry = parse_line(line)
    assert entry is not None
    assert entry.status == 500
    assert entry.path == "/api/users"
    assert entry.ip == "203.0.113.5"


def test_parse_rejects_malformed():
    assert parse_line("this is not a log line") is None
    assert parse_line("") is None


def test_no_errors_no_anomaly():
    """A stream of pure 200s should produce zero anomalies."""
    entries = [_mk_entry(i, 200) for i in range(600)]
    assert detect_anomalies(entries) == []


def test_sustained_error_burst_is_flagged():
    """50% error rate for a minute should fire at least once."""
    entries = []
    # 10 minutes of normal traffic (1% errors)
    for i in range(600):
        entries.append(_mk_entry(i, 500 if i % 100 == 0 else 200))
    # 1 minute of 50% errors starting at second 600
    for i in range(60):
        entries.append(_mk_entry(600 + i, 500 if i % 2 == 0 else 200))
        entries.append(_mk_entry(600 + i, 500 if i % 2 == 0 else 200))

    anomalies = detect_anomalies(entries, window_seconds=60, threshold_rate=0.10)
    assert len(anomalies) >= 1
    assert anomalies[0].error_rate >= 0.10


def test_cooldown_suppresses_repeat_flags():
    """Cooldown should prevent flooding during one sustained incident."""
    entries = []
    # 2 minutes of continuous 50% errors — without cooldown this would
    # fire on every single new entry.
    for i in range(120):
        entries.append(_mk_entry(i, 500 if i % 2 == 0 else 200))
        entries.append(_mk_entry(i, 500 if i % 2 == 0 else 200))

    anomalies = detect_anomalies(
        entries, window_seconds=60, threshold_rate=0.10, cooldown_seconds=60
    )
    # Should be a small handful, not hundreds.
    assert 1 <= len(anomalies) <= 3


def test_4xx_does_not_fire():
    """Client errors (4xx) are not server anomalies."""
    entries = [_mk_entry(i, 404) for i in range(600)]
    assert detect_anomalies(entries, threshold_rate=0.10) == []


def test_min_sample_size_respected():
    """Few errors in a tiny window shouldn't fire even at 100% rate."""
    # 3 requests, all errors — technically 100% but not statistically
    # meaningful
    entries = [_mk_entry(i, 500) for i in range(3)]
    assert detect_anomalies(entries, min_sample_size=10) == []
