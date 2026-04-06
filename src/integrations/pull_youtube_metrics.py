import argparse
import json
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Dict, List

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from google_auth import load_google_credentials


ROOT_DIR = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from analytics import append_rows  # noqa: E402
from env_loader import load_autonomous_env  # noqa: E402

load_autonomous_env(ROOT_DIR)

ANALYTICS_SCOPE = "https://www.googleapis.com/auth/yt-analytics.readonly"
YOUTUBE_READ_SCOPE = "https://www.googleapis.com/auth/youtube.readonly"


def _safe_float(value: object) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _load_candidate_video_ids(base_dir: Path) -> List[str]:
    queue_file = base_dir / "output" / "youtube_upload_queue.json"
    if not queue_file.exists():
        return []
    payload = json.loads(queue_file.read_text(encoding="utf-8"))
    video_ids = []
    for item in payload.get("uploads", []):
        if item.get("youtube_video_id"):
            video_ids.append(item["youtube_video_id"])
    return sorted(set(video_ids))


def _video_title_map(youtube, video_ids: List[str]) -> Dict[str, str]:
    mapping: Dict[str, str] = {}
    if not video_ids:
        return mapping
    for start in range(0, len(video_ids), 50):
        batch = video_ids[start : start + 50]
        response = youtube.videos().list(part="snippet", id=",".join(batch), maxResults=50).execute()
        for item in response.get("items", []):
            vid = item.get("id")
            title = (item.get("snippet") or {}).get("title", "")
            if vid:
                mapping[vid] = title
    return mapping


def fetch_metrics_rows(base_dir: Path, days: int, variable_cost_usd: float) -> List[Dict[str, object]]:
    video_ids = _load_candidate_video_ids(base_dir)
    if not video_ids:
        return []

    credentials = load_google_credentials([ANALYTICS_SCOPE, YOUTUBE_READ_SCOPE])
    analytics = build("youtubeAnalytics", "v2", credentials=credentials, cache_discovery=False)
    youtube = build("youtube", "v3", credentials=credentials, cache_discovery=False)

    end_date = date.today() - timedelta(days=1)
    start_date = end_date - timedelta(days=max(0, days - 1))
    title_map = _video_title_map(youtube, video_ids)

    filters = f"video=={','.join(video_ids)}"
    response = analytics.reports().query(
        ids="channel==MINE",
        startDate=start_date.isoformat(),
        endDate=end_date.isoformat(),
        dimensions="day,video",
        metrics="views,estimatedMinutesWatched,averageViewDuration,impressionsCtr,estimatedRevenue",
        sort="day",
        filters=filters,
    ).execute()

    rows = []
    for row in response.get("rows", []):
        day, video_id, views, watch_minutes, avg_view_duration, ctr_value, revenue = row
        ctr_percent = _safe_float(ctr_value)
        if ctr_percent <= 1.0:
            ctr_percent *= 100.0
        rows.append(
            {
                "date": str(day),
                "video_id": str(video_id),
                "title": title_map.get(str(video_id), ""),
                "views": int(_safe_float(views)),
                "watch_time_seconds": round(_safe_float(watch_minutes) * 60.0, 2),
                "avg_view_duration_seconds": round(_safe_float(avg_view_duration), 2),
                "ctr_percent": round(ctr_percent, 4),
                "revenue_usd": round(_safe_float(revenue), 4),
                "variable_cost_usd": round(variable_cost_usd, 4),
            }
        )
    return rows


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Pull YouTube metrics and append to metrics CSV.")
    parser.add_argument("--base-dir", default=".", help="Project root")
    parser.add_argument("--days", type=int, default=1, help="Number of trailing days to fetch")
    parser.add_argument("--variable-cost-usd", type=float, default=0.0, help="Per-row variable cost value")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    try:
        root = Path(args.base_dir).resolve()
        rows = fetch_metrics_rows(root, days=args.days, variable_cost_usd=args.variable_cost_usd)
        metrics_file = root / "data" / "metrics" / "daily_metrics.csv"
        if rows:
            append_rows(metrics_file, rows)
        print(json.dumps({"ok": True, "rows_appended": len(rows)}, indent=2))
    except HttpError as exc:
        payload = {"ok": False, "error": str(exc), "status_code": getattr(exc.resp, "status", None)}
        print(json.dumps(payload, indent=2))
        raise SystemExit(1) from exc
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
        raise SystemExit(1) from exc
