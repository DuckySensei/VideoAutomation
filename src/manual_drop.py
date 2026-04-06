"""
Copy each rendered video into a flat folder layout for manual upload (e.g. TikTok app, YouTube Studio).
"""
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List


def build_manual_drop_folder(
    script_queue_file: Path,
    render_jobs_file: Path,
    drop_root: Path,
) -> Dict[str, object]:
    scripts = json.loads(script_queue_file.read_text(encoding="utf-8")).get("items", [])
    render_map = {
        r["script_id"]: r
        for r in json.loads(render_jobs_file.read_text(encoding="utf-8")).get("results", [])
    }

    drop_root.mkdir(parents=True, exist_ok=True)
    copied: List[str] = []
    skipped_video: List[str] = []

    for item in scripts:
        sid = item["script_id"]
        meta = item.get("metadata", {})
        render_info = render_map.get(sid, {})
        video_src = render_info.get("output_video", "")
        sub = drop_root / sid
        sub.mkdir(parents=True, exist_ok=True)

        dest_video = sub / "video.mp4"
        if video_src and Path(video_src).is_file():
            shutil.copy2(video_src, dest_video)
            copied.append(sid)
        else:
            skipped_video.append(sid)
            note = sub / "VIDEO_MISSING.txt"
            why = render_info.get("skip_reason", "")
            lines = [
                "No video.mp4 was produced for this script.",
                "",
                f"Expected output file: {video_src or '(none)'}",
                "",
            ]
            if why:
                lines.extend(["Reason from render step:", why, ""])
            else:
                lines.append(
                    "Typical causes: FFmpeg not installed, or missing files under assets/media/ "
                    "(see assets/media/README.txt)."
                )
            note.write_text("\n".join(lines), encoding="utf-8")

        (sub / "tiktok_caption.txt").write_text(meta.get("tiktok_caption", meta.get("title", "")), encoding="utf-8")
        (sub / "youtube_title.txt").write_text(meta.get("title", ""), encoding="utf-8")
        (sub / "youtube_description.txt").write_text(meta.get("description", ""), encoding="utf-8")

        readme = sub / "README.txt"
        readme.write_text(
            "Manual upload bundle\n"
            "- video.mp4 — upload to YouTube Shorts / TikTok / etc.\n"
            "- tiktok_caption.txt — paste as caption on TikTok\n"
            "- youtube_title.txt / youtube_description.txt — paste in YouTube Studio\n",
            encoding="utf-8",
        )

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "drop_root": str(drop_root),
        "folders": len(scripts),
        "videos_copied": len(copied),
        "videos_missing": len(skipped_video),
    }
    (drop_root / "_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    _sync_latest_bundle(drop_root, scripts)
    return summary


def _sync_latest_bundle(drop_root: Path, scripts: List[dict]) -> None:
    """Copy the newest item (by created_at) to drop_root/latest for quick access."""
    if not scripts:
        return
    best = max(scripts, key=lambda x: x.get("created_at", ""))
    sid = best["script_id"]
    src = drop_root / sid
    dst = drop_root / "latest"
    if dst.exists():
        shutil.rmtree(dst)
    if src.exists():
        shutil.copytree(src, dst)
        (dst / "SCRIPT_ID.txt").write_text(sid + "\n", encoding="utf-8")
