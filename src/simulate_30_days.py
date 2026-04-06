import argparse
import random
from datetime import date, timedelta
from pathlib import Path

from analytics import append_rows, ensure_metrics_csv, break_even_progress


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate synthetic 30-day metrics for break-even testing.")
    parser.add_argument("--metrics-file", default="data/metrics/daily_metrics.csv")
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--videos-per-day", type=int, default=2)
    parser.add_argument("--monthly-fixed-cost", type=float, default=50.0)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    metrics_file = Path(args.metrics_file)
    ensure_metrics_csv(metrics_file)

    start = date.today() - timedelta(days=args.days - 1)
    rows = []
    for day_idx in range(args.days):
        d = (start + timedelta(days=day_idx)).isoformat()
        for video_idx in range(args.videos_per_day):
            views = random.randint(200, 3000)
            avg_view_duration = random.uniform(8, 23)
            watch = views * avg_view_duration
            revenue = round((views / 1000.0) * random.uniform(0.2, 1.2), 2)
            cost = round(random.uniform(0.02, 0.12), 2)
            rows.append(
                {
                    "date": d,
                    "video_id": f"sim-{day_idx:02d}-{video_idx:02d}",
                    "title": f"Simulation Video {day_idx}-{video_idx}",
                    "views": views,
                    "watch_time_seconds": round(watch, 2),
                    "avg_view_duration_seconds": round(avg_view_duration, 2),
                    "ctr_percent": round(random.uniform(2.0, 9.0), 2),
                    "revenue_usd": revenue,
                    "variable_cost_usd": cost,
                }
            )
    append_rows(metrics_file, rows)
    summary = break_even_progress(metrics_file, args.monthly_fixed_cost)
    print(summary)


if __name__ == "__main__":
    main()
