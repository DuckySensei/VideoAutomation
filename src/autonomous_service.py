import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict

from analytics import ensure_metrics_csv
from automation_hooks import (
    process_instagram_queue,
    process_tiktok_queue,
    process_upload_queue,
    run_metrics_import_hook,
)
from env_loader import load_autonomous_env
from main import run_once
from optimizer import summarize_by_video
from process_util import is_process_running


def _load_state(path: Path) -> Dict[str, object]:
    if not path.exists():
        return {
            "script_max_items": 10,
            "upload_start_hour_utc": 16,
            "upload_gap_hours": 12,
            "min_items": 6,
            "max_items": 10,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "last_actions": [],
        }
    return json.loads(path.read_text(encoding="utf-8"))


def _save_state(path: Path, state: Dict[str, object]) -> None:
    state["updated_at"] = datetime.now(timezone.utc).isoformat()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2), encoding="utf-8")


def _apply_safe_tuning(base_dir: Path, state: Dict[str, object]) -> Dict[str, object]:
    metrics_file = base_dir / "data" / "metrics" / "daily_metrics.csv"
    ensure_metrics_csv(metrics_file)
    ranked = summarize_by_video(metrics_file)

    actions = []
    if not ranked:
        state["last_actions"] = ["No metrics yet; keeping current knobs."]
        return state

    top = ranked[0]
    low_profit = top.get("profit_usd", 0.0) < 0.0
    low_watch = top.get("avg_watch_seconds", 0.0) < 8.0
    high_watch = top.get("avg_watch_seconds", 0.0) > 18.0

    current = int(state.get("script_max_items", 10))
    min_items = int(state.get("min_items", 6))
    max_items = int(state.get("max_items", 20))

    if low_profit and low_watch and current > min_items:
        state["script_max_items"] = max(min_items, current - 2)
        actions.append("Reduced script volume by 2 due to low watch and negative profit.")
    elif high_watch and current < max_items:
        state["script_max_items"] = min(max_items, current + 1)
        actions.append("Increased script volume by 1 due to strong watch performance.")
    else:
        actions.append("No tuning change applied this cycle.")

    state["last_actions"] = actions
    return state


def run_autonomous_cycle(
    base_dir: Path,
    monthly_fixed_cost: float,
    state_path: Path,
    enable_upload_hook: bool,
    enable_tiktok_hook: bool,
    enable_instagram_hook: bool,
    enable_metrics_hook: bool,
    upload_dry_run: bool,
) -> Dict[str, object]:
    state = _load_state(state_path)
    state = _apply_safe_tuning(base_dir, state)
    _save_state(state_path, state)

    pipeline_report = run_once(
        base_dir=base_dir,
        monthly_fixed_cost=monthly_fixed_cost,
        script_max_items=int(state.get("script_max_items", 10)),
        upload_start_hour_utc=int(state.get("upload_start_hour_utc", 16)),
        upload_gap_hours=int(state.get("upload_gap_hours", 12)),
    )

    metrics_hook = {"executed": False, "ok": True, "reason": "disabled"}
    if enable_metrics_hook:
        metrics_hook = run_metrics_import_hook(base_dir)

    upload_hook = {"executed": False, "ok": True, "reason": "disabled"}
    if enable_upload_hook:
        queue_file = base_dir / "output" / "youtube_upload_queue.json"
        hook_result = process_upload_queue(queue_file, base_dir, dry_run=upload_dry_run)
        upload_hook = {"executed": True, "ok": hook_result.get("failed", 0) == 0, "result": hook_result}

    tiktok_hook = {"executed": False, "ok": True, "reason": "disabled"}
    if enable_tiktok_hook:
        queue_file = base_dir / "output" / "tiktok_upload_queue.json"
        hook_result = process_tiktok_queue(queue_file, base_dir, dry_run=upload_dry_run)
        tiktok_hook = {"executed": True, "ok": hook_result.get("failed", 0) == 0, "result": hook_result}

    instagram_hook = {"executed": False, "ok": True, "reason": "disabled"}
    if enable_instagram_hook:
        queue_file = base_dir / "output" / "instagram_upload_queue.json"
        hook_result = process_instagram_queue(queue_file, base_dir, dry_run=upload_dry_run)
        instagram_hook = {"executed": True, "ok": hook_result.get("failed", 0) == 0, "result": hook_result}

    autonomous_report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "state": state,
        "pipeline_report": pipeline_report,
        "metrics_hook": metrics_hook,
        "upload_hook": upload_hook,
        "tiktok_hook": tiktok_hook,
        "instagram_hook": instagram_hook,
    }
    report_path = base_dir / "output" / "autonomous_report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(autonomous_report, indent=2), encoding="utf-8")
    return autonomous_report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Autonomous runner for VideoAutomation.")
    parser.add_argument("--base-dir", default=".", help="Project root")
    parser.add_argument("--monthly-fixed-cost", type=float, default=50.0, help="Monthly fixed tool cost in USD")
    parser.add_argument("--state-file", default="data/autonomous_state.json", help="Path to autonomous tuning state")
    parser.add_argument("--enable-upload-hook", action="store_true", help="Process upload queue with upload hook")
    parser.add_argument("--enable-tiktok-hook", action="store_true", help="Process TikTok queue with upload hook")
    parser.add_argument("--enable-instagram-hook", action="store_true", help="Process Instagram queue with upload hook")
    parser.add_argument("--enable-metrics-hook", action="store_true", help="Run metrics import hook command")
    parser.add_argument("--upload-dry-run", action="store_true", help="Simulate upload hook without command execution")
    parser.add_argument("--loop", action="store_true", help="Run continuously on an interval")
    parser.add_argument("--interval-seconds", type=int, default=86400, help="Loop interval in seconds (default 24h)")
    parser.add_argument(
        "--pid-file",
        default="data/autonomous.pid",
        help="Write loop PID here (only with --loop)",
    )
    return parser.parse_args()


def _write_pid_file(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(str(os.getpid()), encoding="utf-8")


def _remove_pid_file(path: Path) -> None:
    path.unlink(missing_ok=True)


if __name__ == "__main__":
    args = parse_args()
    root = Path(args.base_dir).resolve()
    load_autonomous_env(root)
    state_file = (root / args.state_file).resolve()
    pid_path = (root / args.pid_file).resolve()

    if not args.loop:
        result = run_autonomous_cycle(
            base_dir=root,
            monthly_fixed_cost=args.monthly_fixed_cost,
            state_path=state_file,
            enable_upload_hook=args.enable_upload_hook,
            enable_tiktok_hook=args.enable_tiktok_hook,
            enable_instagram_hook=args.enable_instagram_hook,
            enable_metrics_hook=args.enable_metrics_hook,
            upload_dry_run=args.upload_dry_run,
        )
        print(json.dumps(result, indent=2))
    else:
        if pid_path.exists():
            try:
                old_pid = int(pid_path.read_text(encoding="utf-8").strip().splitlines()[0])
            except (ValueError, IndexError):
                old_pid = -1
            if old_pid > 0 and is_process_running(old_pid):
                print(
                    json.dumps(
                        {
                            "error": "Autonomous loop already running",
                            "pid": old_pid,
                            "pid_file": str(pid_path),
                        },
                        indent=2,
                    ),
                    file=sys.stderr,
                )
                sys.exit(1)
            pid_path.unlink(missing_ok=True)

        _write_pid_file(pid_path)
        try:
            while True:
                result = run_autonomous_cycle(
                    base_dir=root,
                    monthly_fixed_cost=args.monthly_fixed_cost,
                    state_path=state_file,
                    enable_upload_hook=args.enable_upload_hook,
                    enable_tiktok_hook=args.enable_tiktok_hook,
                    enable_instagram_hook=args.enable_instagram_hook,
                    enable_metrics_hook=args.enable_metrics_hook,
                    upload_dry_run=args.upload_dry_run,
                )
                print(json.dumps({"cycle_completed_at": result.get("generated_at")}, indent=2))
                time.sleep(max(60, args.interval_seconds))
        except KeyboardInterrupt:
            pass
        finally:
            _remove_pid_file(pid_path)
