import argparse
import json
from pathlib import Path

from analytics import ensure_metrics_csv, break_even_progress
from optimizer import build_optimization_report
from render_pipeline import render_jobs
from script_generator import build_script_queue
from trend_ingest import ingest_trends
from youtube_scheduler import build_upload_queue


def run_once(base_dir: Path, monthly_fixed_cost: float = 50.0) -> dict:
    data_dir = base_dir / "data"
    out_dir = base_dir / "output"
    manifest = base_dir / "assets" / "licenses" / "manifest.csv"
    niche = base_dir / "config" / "niche_profile.json"

    trends_file = data_dir / "trends.json"
    script_queue_file = data_dir / "script_queue.json"
    render_output_dir = out_dir / "renders"
    upload_queue_file = out_dir / "youtube_upload_queue.json"
    metrics_file = data_dir / "metrics" / "daily_metrics.csv"
    optimization_report_file = out_dir / "optimization_report.json"

    trend_payload = ingest_trends(trends_file)
    script_payload = build_script_queue(trends_file, niche, script_queue_file)
    render_payload = render_jobs(
        script_queue_file=script_queue_file,
        output_dir=render_output_dir,
        manifest_path=manifest,
        approved_asset_ids=["sample_bg_001", "sample_music_001"],
    )
    upload_payload = build_upload_queue(script_queue_file, render_output_dir / "render_jobs.json", upload_queue_file)

    ensure_metrics_csv(metrics_file)
    be = break_even_progress(metrics_file, monthly_fixed_cost)
    optimization = build_optimization_report(metrics_file, optimization_report_file)

    report = {
        "trends_count": len(trend_payload.get("ideas", [])),
        "scripts_count": len(script_payload.get("items", [])),
        "render_jobs_count": len(render_payload.get("commands", [])),
        "uploads_ready": len(upload_payload.get("uploads", [])),
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
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    result = run_once(Path(args.base_dir).resolve(), monthly_fixed_cost=args.monthly_fixed_cost)
    print(json.dumps(result, indent=2))
