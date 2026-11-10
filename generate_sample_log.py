"""
Generate a sample web server log for testing the anomaly detector.

Creates about an hour of traffic with:
- Baseline ~1% error rate (normal noise)
- Two deliberate "incidents" where errors spike
- Realistic paths, IPs, timestamps

Writes to `sample.log` in the current folder.

Usage:
    python generate_sample_log.py
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone


RNG = random.Random(42)

PATHS = [
    "/", "/api/users", "/api/users/me", "/api/orders",
    "/api/orders/history", "/health", "/login", "/dashboard",
    "/api/products", "/static/app.css", "/static/app.js",
]

USER_AGENTS = [
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)",
]


def _random_ip() -> str:
    return f"{RNG.randint(10, 250)}.{RNG.randint(0, 255)}.{RNG.randint(0, 255)}.{RNG.randint(1, 254)}"


def _format_line(when: datetime, status: int) -> str:
    path = RNG.choice(PATHS)
    size = RNG.randint(200, 50_000) if status < 400 else RNG.randint(0, 500)
    ua = RNG.choice(USER_AGENTS)
    stamp = when.strftime("%d/%b/%Y:%H:%M:%S %z")
    method = "POST" if path in ("/login", "/api/orders") else "GET"
    return (
        f'{_random_ip()} - - [{stamp}] '
        f'"{method} {path} HTTP/1.1" {status} {size} "-" "{ua}"'
    )


def _pick_status(error_rate: float) -> int:
    """Return a status code, with the given probability of being 5xx."""
    if RNG.random() < error_rate:
        return RNG.choice([500, 502, 503, 503, 504])
    # 4xx happens about 5% of the time independently (client errors)
    if RNG.random() < 0.05:
        return RNG.choice([400, 401, 403, 404, 404])
    return RNG.choice([200, 200, 200, 200, 200, 201, 304])


def generate(output_path: str = "sample.log") -> None:
    start = datetime(2026, 11, 10, 9, 0, 0, tzinfo=timezone.utc)
    end = start + timedelta(hours=1)

    # Two "incidents": windows of elevated error rate.
    # Incident 1: 15–20 min in, 35% error rate (clear spike)
    # Incident 2: 45–47 min in, 25% error rate (shorter, subtler)
    incidents = [
        (start + timedelta(minutes=15), start + timedelta(minutes=20), 0.35),
        (start + timedelta(minutes=45), start + timedelta(minutes=47), 0.25),
    ]

    def current_error_rate(t: datetime) -> float:
        for inc_start, inc_end, rate in incidents:
            if inc_start <= t < inc_end:
                return rate
        return 0.01  # baseline noise

    with open(output_path, "w", encoding="utf-8") as fh:
        t = start
        while t < end:
            # ~5 requests per second with some jitter
            for _ in range(RNG.randint(3, 8)):
                status = _pick_status(current_error_rate(t))
                fh.write(_format_line(t, status) + "\n")
            t += timedelta(seconds=1)

    print(f"Wrote {output_path}")
    print(f"  Time range: {start:%H:%M:%S} to {end:%H:%M:%S} UTC")
    print(f"  Two planted incidents:")
    for inc_start, inc_end, rate in incidents:
        print(f"    - {inc_start:%H:%M:%S}–{inc_end:%H:%M:%S}  (rate ~{rate*100:.0f}%)")


if __name__ == "__main__":
    generate()
