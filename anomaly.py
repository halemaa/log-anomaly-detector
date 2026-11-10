"""
Log anomaly detector — flags spikes in server error rate.

Reads a web server access log (nginx or Apache Combined Log Format).
Uses a sliding window to track the recent error rate as it changes
over time, and flags windows where the rate crosses a threshold.

The algorithm is a dynamic sliding window in one pass over the log:
O(n) time, O(window_size) space.
"""

from __future__ import annotations

import re
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Iterator


# Combined Log Format, used by nginx and Apache:
# IP - user [time] "METHOD path HTTP/x" status size "referrer" "user-agent"
_LOG_LINE = re.compile(
    r'(?P<ip>\S+)\s+\S+\s+\S+\s+'
    r'\[(?P<time>[^\]]+)\]\s+'
    r'"(?P<method>\S+)\s+(?P<path>\S+)\s+\S+"\s+'
    r'(?P<status>\d+)\s+'
    r'(?P<size>\S+)'
)


@dataclass(frozen=True)
class LogEntry:
    time: datetime
    status: int
    path: str
    ip: str


@dataclass(frozen=True)
class Anomaly:
    time: datetime
    error_rate: float
    error_count: int
    total_requests: int
    window_seconds: int

    def summary(self) -> str:
        rate_pct = self.error_rate * 100
        return (
            f"{self.time:%Y-%m-%d %H:%M:%S}  "
            f"error rate {rate_pct:5.1f}%  "
            f"({self.error_count} of {self.total_requests} in last {self.window_seconds}s)"
        )


def parse_line(line: str) -> LogEntry | None:
    """Parse one log line. Returns None if it doesn't match the format."""
    m = _LOG_LINE.match(line)
    if not m:
        return None
    try:
        when = datetime.strptime(m["time"], "%d/%b/%Y:%H:%M:%S %z")
    except ValueError:
        return None
    return LogEntry(
        time=when,
        status=int(m["status"]),
        path=m["path"],
        ip=m["ip"],
    )


def parse_log(path: str) -> Iterator[LogEntry]:
    """Yield LogEntry objects from a log file, skipping malformed lines."""
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            entry = parse_line(line)
            if entry is not None:
                yield entry


def _is_error(status: int) -> bool:
    """5xx = server error. 4xx we treat as client error, not an anomaly."""
    return 500 <= status < 600


def detect_anomalies(
    entries: Iterator[LogEntry],
    window_seconds: int = 60,
    threshold_rate: float = 0.10,
    min_sample_size: int = 10,
    cooldown_seconds: int | None = None,
) -> list[Anomaly]:
    """
    Walk the log in one pass. Maintain a sliding window of recent entries.
    For each new entry, drop entries older than `window_seconds` from the
    left of the window, then check if the current window's error rate
    exceeds `threshold_rate`.

    Args:
        entries: a stream of LogEntry, in time order
        window_seconds: how far back the window looks
        threshold_rate: error rate above which a window is anomalous
            (0.10 = 10%)
        min_sample_size: don't flag until we have at least this many
            requests in the window (avoids crying wolf on quiet periods)
        cooldown_seconds: once an anomaly fires, suppress further ones
            for this long. Defaults to the window size.
    """
    if cooldown_seconds is None:
        cooldown_seconds = window_seconds

    window: deque[tuple[datetime, bool]] = deque()
    errors_in_window = 0
    last_flagged: datetime | None = None
    anomalies: list[Anomaly] = []

    for entry in entries:
        now = entry.time
        is_err = _is_error(entry.status)

        # 1. Expand: add the new entry to the right edge of the window.
        window.append((now, is_err))
        if is_err:
            errors_in_window += 1

        # 2. Shrink: drop anything from the left edge that's older than
        #    window_seconds. This is what makes it a "sliding" window.
        cutoff = now - timedelta(seconds=window_seconds)
        while window and window[0][0] < cutoff:
            _, old_err = window.popleft()
            if old_err:
                errors_in_window -= 1

        # 3. Check: is this window anomalous?
        if len(window) >= min_sample_size:
            rate = errors_in_window / len(window)
            if rate > threshold_rate:
                # Cooldown: don't fire again during the same spike.
                suppressed = (
                    last_flagged is not None
                    and (now - last_flagged).total_seconds() < cooldown_seconds
                )
                if not suppressed:
                    anomalies.append(
                        Anomaly(
                            time=now,
                            error_rate=rate,
                            error_count=errors_in_window,
                            total_requests=len(window),
                            window_seconds=window_seconds,
                        )
                    )
                    last_flagged = now

    return anomalies
