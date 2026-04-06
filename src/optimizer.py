import csv
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List


def _to_float(value: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def summarize_by_video(metrics_path: Path) -> List[Dict[str, float]]:
    stats = defaultdict(lambda: {"views": 0.0, "watch": 0.0, "revenue": 0.0, "cost": 0.0, "count": 0.0})
    with metrics_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            key = row.get("video_id") or row.get("title") or "unknown"
            s = stats[key]
            s["views"] += _to_float(row.get("views"))
            s["watch"] += _to_float(row.get("watch_time_seconds"))
            s["revenue"] += _to_float(row.get("revenue_usd"))
            s["cost"] += _to_float(row.get("variable_cost_usd"))
            s["count"] += 1
    rows = []
    for video_id, s in stats.items():
        avg_watch = s["watch"] / s["count"] if s["count"] else 0.0
        profit = s["revenue"] - s["cost"]
        rows.append(
            {
                "video_id": video_id,
                "views": round(s["views"], 2),
                "avg_watch_seconds": round(avg_watch, 2),
                "revenue_usd": round(s["revenue"], 2),
                "profit_usd": round(profit, 2),
            }
        )
    rows.sort(key=lambda x: (x["profit_usd"], x["avg_watch_seconds"]), reverse=True)
    return rows


def build_optimization_report(metrics_path: Path, output_path: Path) -> dict:
    ranked = summarize_by_video(metrics_path)
    top = ranked[:3]
    bottom = ranked[-3:] if len(ranked) >= 3 else ranked
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "top_videos": top,
        "bottom_videos": bottom,
        "actions": [
            "Keep top formats and replicate their hook structure.",
            "Pause bottom formats for next cycle.",
            "Test one new angle while keeping niche constant.",
            "Reduce generation volume if break-even gap is increasing.",
        ],
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report
