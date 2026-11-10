"""
Run the anomaly detector against a log file.

Usage:
    python detect.py sample.log
    python detect.py /var/log/nginx/access.log --window 30 --threshold 0.05
"""

from __future__ import annotations

import argparse
import sys

from anomaly import detect_anomalies, parse_log


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Flag spikes in HTTP 5xx error rate using a sliding window.",
    )
    parser.add_argument("logfile", help="path to an nginx/Apache access log")
    parser.add_argument(
        "--window", type=int, default=60,
        help="window size in seconds (default: 60)",
    )
    parser.add_argument(
        "--threshold", type=float, default=0.10,
        help="error rate above which to flag (default: 0.10 = 10%%)",
    )
    parser.add_argument(
        "--min-sample", type=int, default=10,
        help="minimum requests in a window before flagging (default: 10)",
    )
    args = parser.parse_args()

    entries = parse_log(args.logfile)
    anomalies = detect_anomalies(
        entries,
        window_seconds=args.window,
        threshold_rate=args.threshold,
        min_sample_size=args.min_sample,
    )

    print(f"Scanning {args.logfile}")
    print(
        f"Window: {args.window}s  ·  "
        f"Threshold: {args.threshold*100:.1f}%  ·  "
        f"Min sample: {args.min_sample}"
    )
    print()

    if not anomalies:
        print("No anomalies found.")
        return 0

    print(f"Found {len(anomalies)} anomal{'y' if len(anomalies) == 1 else 'ies'}:")
    print("-" * 78)
    for a in anomalies:
        print("  " + a.summary())
    print()
    return 1   # nonzero so you can use this in CI or alerting


if __name__ == "__main__":
    sys.exit(main())
