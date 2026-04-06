import argparse
import json
from pathlib import Path

from analytics import ensure_metrics_csv, break_even_progress
from env_loader import load_autonomous_env
from manual_drop import build_manual_drop_folder
from optimizer import build_optimization_report
from render_pipeline import render_jobs
from script_generator import build_script_queue
from tiktok_scheduler import build_tiktok_queue
from trend_ingest import ingest_trends
from youtube_scheduler import build_upload_queue


def run_once(
    base_dir: Path,
    monthly_fixed_cost: float = 50.0,
    script_max_items: int = 12,
    upload_start_hour_utc: int = 16,
    upload_gap_hours: int = 12,
) -> dict:
    load_autonomous_env(base_dir)
    data_dir = base_dir / "data"
    out_dir = base_dir / "output"
    manifest = base_dir / "assets" / "licenses" / "manifest.csv"
    niche = base_dir / "config" / "niche_profile.json"

    trends_file = data_dir / "trends.json"
    script_queue_file = data_dir / "script_queue.json"
    render_output_dir = out_dir / "renders"
    upload_queue_file = out_dir / "youtube_upload_queue.json"
    tiktok_queue_file = out_dir / "tiktok_upload_queue.json"
    metrics_file = data_dir / "metrics" / "daily_metrics.csv"
    optimization_report_file = out_dir / "optimization_report.json"

    trend_payload = ingest_trends(trends_file)
    script_payload = build_script_queue(trends_file, niche, script_queue_file, max_items=script_max_items)
    render_payload = render_jobs(
        script_queue_file=script_queue_file,
        output_dir=render_output_dir,
        manifest_path=manifest,
        approved_asset_ids=["sample_bg_001", "sample_music_001"],
        base_dir=base_dir,
    )
    upload_payload = build_upload_queue(
        script_queue_file,
        render_output_dir / "render_jobs.json",
        upload_queue_file,
        start_hour_utc=upload_start_hour_utc,
        gap_hours=upload_gap_hours,
    )
    tiktok_payload = build_tiktok_queue(
        script_queue_file,
        render_output_dir / "render_jobs.json",
        tiktok_queue_file,
        start_hour_utc=upload_start_hour_utc,
        gap_hours=upload_gap_hours,
    )
    drop_dir = out_dir / "drop_for_manual_upload"
    manual_drop = build_manual_drop_folder(
        script_queue_file,
        render_output_dir / "render_jobs.json",
        drop_dir,
    )

    ensure_metrics_csv(metrics_file)
    be = break_even_progress(metrics_file, monthly_fixed_cost)
    optimization = build_optimization_report(metrics_file, optimization_report_file)

    report = {
        "trends_count": len(trend_payload.get("ideas", [])),
        "scripts_count": len(script_payload.get("items", [])),
        "render_jobs_count": len(render_payload.get("commands", [])),
        "uploads_ready": len(upload_payload.get("uploads", [])),
        "tiktok_uploads_ready": len(tiktok_payload.get("uploads", [])),
        "manual_drop": manual_drop,
        "break_even": be,
        "optimization_actions": optimization.get("actions", []),
    }
    report_path = out_dir / "pipeline_report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Legal low-cost video automation pipeline")
    parser.add_argument("--base-dir", default=".", help="Project root")
    parser.add_argument("--monthly-fixed-cost", type=float, default=50.0, help="Monthly fixed tool cost in USD")
    parser.add_argument("--script-max-items", type=int, default=12, help="Max scripts to generate in each run")
    parser.add_argument("--upload-start-hour-utc", type=int, default=16, help="First scheduled publish hour (UTC)")
    parser.add_argument("--upload-gap-hours", type=int, default=12, help="Gap between scheduled uploads in hours")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    result = run_once(
        Path(args.base_dir).resolve(),
        monthly_fixed_cost=args.monthly_fixed_cost,
        script_max_items=args.script_max_items,
        upload_start_hour_utc=args.upload_start_hour_utc,
        upload_gap_hours=args.upload_gap_hours,
    )
    print(json.dumps(result, indent=2))
