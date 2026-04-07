import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List


def _run_shell_command(command: str, cwd: Path) -> Dict[str, object]:
    proc = subprocess.run(command, cwd=str(cwd), shell=True, check=False, capture_output=True, text=True)
    return {
        "command": command,
        "exit_code": proc.returncode,
        "stdout": (proc.stdout or "").strip(),
        "stderr": (proc.stderr or "").strip(),
        "ok": proc.returncode == 0,
    }


def _extract_json(text: str) -> Dict[str, object]:
    try:
        return json.loads(text or "{}")
    except json.JSONDecodeError:
        return {}


def run_metrics_import_hook(base_dir: Path) -> Dict[str, object]:
    command = os.getenv("METRICS_IMPORT_COMMAND", "").strip()
    if not command:
        return {
            "executed": False,
            "ok": True,
            "reason": "METRICS_IMPORT_COMMAND is not configured",
        }
    result = _run_shell_command(command, base_dir)
    result["executed"] = True
    return result


def process_upload_queue(
    queue_file: Path,
    base_dir: Path,
    command_template: str = "",
    dry_run: bool = False,
) -> Dict[str, object]:
    payload = json.loads(queue_file.read_text(encoding="utf-8"))
    uploads: List[Dict[str, object]] = payload.get("uploads", [])
    command_template = command_template or os.getenv("YOUTUBE_UPLOAD_COMMAND", "").strip()

    attempts = []
    uploaded = 0
    skipped = 0
    failed = 0

    for item in uploads:
        if item.get("status") != "ready_for_api_upload":
            skipped += 1
            continue
        if not command_template:
            item["status"] = "awaiting_upload_integration"
            item["last_upload_note"] = "Set YOUTUBE_UPLOAD_COMMAND to enable autonomous uploads."
            skipped += 1
            continue
        if dry_run:
            item["status"] = "dry_run_upload_planned"
            attempts.append({"script_id": item.get("script_id"), "ok": True, "dry_run": True})
            continue

        command = command_template.format(
            video_path=item.get("video_path", ""),
            title=item.get("title", ""),
            description=item.get("description", ""),
            privacy_status=item.get("privacyStatus", "private"),
            publish_at=item.get("publishAt", ""),
            script_id=item.get("script_id", ""),
        )
        result = _run_shell_command(command, base_dir)
        attempts.append({"script_id": item.get("script_id"), **result})
        if result["ok"]:
            output_payload = _extract_json(str(result.get("stdout", "")))
            item["status"] = "uploaded"
            item["uploaded_at"] = datetime.now(timezone.utc).isoformat()
            if output_payload.get("video_id"):
                item["youtube_video_id"] = output_payload["video_id"]
            uploaded += 1
        else:
            item["status"] = "upload_failed"
            item["last_upload_error"] = result.get("stderr", "")
            failed += 1

    payload["generated_at"] = payload.get("generated_at") or datetime.now(timezone.utc).isoformat()
    payload["last_processed_at"] = datetime.now(timezone.utc).isoformat()
    queue_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return {
        "uploads_total": len(uploads),
        "uploaded": uploaded,
        "failed": failed,
        "skipped": skipped,
        "attempts": attempts,
    }


def process_tiktok_queue(
    queue_file: Path,
    base_dir: Path,
    command_template: str = "",
    dry_run: bool = False,
) -> Dict[str, object]:
    payload = json.loads(queue_file.read_text(encoding="utf-8"))
    uploads: List[Dict[str, object]] = payload.get("uploads", [])
    command_template = command_template or os.getenv("TIKTOK_UPLOAD_COMMAND", "").strip()

    attempts = []
    uploaded = 0
    skipped = 0
    failed = 0

    for item in uploads:
        if item.get("status") != "ready_for_api_upload":
            skipped += 1
            continue
        if not command_template:
            item["status"] = "awaiting_upload_integration"
            item["last_upload_note"] = "Set TIKTOK_UPLOAD_COMMAND to enable autonomous uploads."
            skipped += 1
            continue
        if dry_run:
            item["status"] = "dry_run_upload_planned"
            attempts.append({"script_id": item.get("script_id"), "ok": True, "dry_run": True})
            continue

        command = command_template.format(
            video_path=item.get("video_path", ""),
            caption=item.get("caption", ""),
            publish_at=item.get("publishAt", ""),
            script_id=item.get("script_id", ""),
        )
        result = _run_shell_command(command, base_dir)
        attempts.append({"script_id": item.get("script_id"), **result})
        if result["ok"]:
            item["status"] = "uploaded"
            item["uploaded_at"] = datetime.now(timezone.utc).isoformat()
            uploaded += 1
        else:
            item["status"] = "upload_failed"
            item["last_upload_error"] = result.get("stderr", "")
            failed += 1

    payload["generated_at"] = payload.get("generated_at") or datetime.now(timezone.utc).isoformat()
    payload["last_processed_at"] = datetime.now(timezone.utc).isoformat()
    queue_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return {
        "uploads_total": len(uploads),
        "uploaded": uploaded,
        "failed": failed,
        "skipped": skipped,
        "attempts": attempts,
    }


def process_instagram_queue(
    queue_file: Path,
    base_dir: Path,
    command_template: str = "",
    dry_run: bool = False,
) -> Dict[str, object]:
    payload = json.loads(queue_file.read_text(encoding="utf-8"))
    uploads: List[Dict[str, object]] = payload.get("uploads", [])
    command_template = command_template or os.getenv("INSTAGRAM_UPLOAD_COMMAND", "").strip()

    attempts = []
    uploaded = 0
    skipped = 0
    failed = 0

    for item in uploads:
        if item.get("status") != "ready_for_api_upload":
            skipped += 1
            continue
        if not command_template:
            item["status"] = "awaiting_upload_integration"
            item["last_upload_note"] = "Set INSTAGRAM_UPLOAD_COMMAND to enable autonomous uploads."
            skipped += 1
            continue
        if dry_run:
            item["status"] = "dry_run_upload_planned"
            attempts.append({"script_id": item.get("script_id"), "ok": True, "dry_run": True})
            continue

        command = command_template.format(
            video_path=item.get("video_path", ""),
            caption=item.get("caption", ""),
            publish_at=item.get("publishAt", ""),
            script_id=item.get("script_id", ""),
        )
        result = _run_shell_command(command, base_dir)
        attempts.append({"script_id": item.get("script_id"), **result})
        if result["ok"]:
            item["status"] = "uploaded"
            item["uploaded_at"] = datetime.now(timezone.utc).isoformat()
            uploaded += 1
        else:
            item["status"] = "upload_failed"
            item["last_upload_error"] = result.get("stderr", "")
            failed += 1

    payload["generated_at"] = payload.get("generated_at") or datetime.now(timezone.utc).isoformat()
    payload["last_processed_at"] = datetime.now(timezone.utc).isoformat()
    queue_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return {
        "uploads_total": len(uploads),
        "uploaded": uploaded,
        "failed": failed,
        "skipped": skipped,
        "attempts": attempts,
    }
