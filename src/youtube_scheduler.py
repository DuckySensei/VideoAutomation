import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List


def _next_publish_times(start_hour_local: int, items_count: int, gap_hours: int = 12) -> List[str]:
    now = datetime.now(timezone.utc)
    start = now.replace(hour=start_hour_local, minute=0, second=0, microsecond=0)
    if start < now:
        start += timedelta(days=1)
    return [(start + timedelta(hours=i * gap_hours)).isoformat() for i in range(items_count)]


def build_upload_queue(
    script_queue_file: Path,
    render_jobs_file: Path,
    output_file: Path,
    start_hour_utc: int = 16,
) -> Dict[str, object]:
    scripts = json.loads(script_queue_file.read_text(encoding="utf-8")).get("items", [])
    render_map = {
        r["script_id"]: r
        for r in json.loads(render_jobs_file.read_text(encoding="utf-8")).get("results", [])
    }
    publish_times = _next_publish_times(start_hour_utc, len(scripts), gap_hours=12)

    queue = []
    for idx, item in enumerate(scripts):
        sid = item["script_id"]
        render_info = render_map.get(sid, {})
        queue.append(
            {
                "platform": "youtube",
                "script_id": sid,
                "video_path": render_info.get("output_video", ""),
                "title": item["metadata"]["title"],
                "description": item["metadata"]["description"],
                "privacyStatus": "private",
                "publishAt": publish_times[idx],
                "status": "ready_for_api_upload",
            }
        )
    payload = {"generated_at": datetime.now(timezone.utc).isoformat(), "uploads": queue}
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload
