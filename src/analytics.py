import csv
from datetime import date
from pathlib import Path
from typing import List, Dict


FIELDS = [
    "date",
    "video_id",
    "title",
    "views",
    "watch_time_seconds",
    "avg_view_duration_seconds",
    "ctr_percent",
    "revenue_usd",
    "variable_cost_usd",
]


def ensure_metrics_csv(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        return
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()


def append_rows(path: Path, rows: List[Dict[str, object]]) -> None:
    ensure_metrics_csv(path)
    with path.open("a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        for row in rows:
            writer.writerow(row)


def break_even_progress(path: Path, monthly_fixed_cost_usd: float) -> Dict[str, float]:
    ensure_metrics_csv(path)
    revenue = 0.0
    variable_cost = 0.0
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            revenue += float(row.get("revenue_usd") or 0.0)
            variable_cost += float(row.get("variable_cost_usd") or 0.0)
    total_cost = monthly_fixed_cost_usd + variable_cost
    gap = total_cost - revenue
    return {
        "today": date.today().isoformat(),
        "revenue_usd": round(revenue, 2),
        "total_cost_usd": round(total_cost, 2),
        "gap_to_break_even_usd": round(gap, 2),
    }
