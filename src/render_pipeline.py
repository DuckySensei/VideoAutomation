import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict

from legal_compliance import validate_assets, build_attribution_lines


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def ffmpeg_exists() -> bool:
    return shutil.which("ffmpeg") is not None


def build_ffmpeg_command(
    background_video: Path,
    voiceover_audio: Path,
    output_video: Path,
    subtitle_file: Path,
) -> List[str]:
    return [
        "ffmpeg",
        "-y",
        "-i",
        str(background_video),
        "-i",
        str(voiceover_audio),
        "-vf",
        f"subtitles={subtitle_file}",
        "-shortest",
        "-c:v",
        "libx264",
        "-preset",
        "fast",
        "-c:a",
        "aac",
        str(output_video),
    ]


def write_srt(script_text: str, srt_path: Path, block_seconds: int = 3) -> None:
    lines = [ln.strip() for ln in script_text.splitlines() if ln.strip()]
    time_cursor = 0
    chunks = []
    for idx, line in enumerate(lines, start=1):
        start = time_cursor
        end = time_cursor + block_seconds
        chunks.append(
            f"{idx}\n"
            f"00:00:{start:02d},000 --> 00:00:{end:02d},000\n"
            f"{line}\n"
        )
        time_cursor = end
    srt_path.write_text("\n".join(chunks), encoding="utf-8")


def render_jobs(
    script_queue_file: Path,
    output_dir: Path,
    manifest_path: Path,
    approved_asset_ids: List[str],
) -> Dict[str, object]:
    ok, errors = validate_assets(approved_asset_ids, manifest_path)
    if not ok:
        raise ValueError(f"Asset validation failed: {errors}")

    payload = load_json(script_queue_file)
    items = payload.get("items", [])
    output_dir.mkdir(parents=True, exist_ok=True)
    subtitles_dir = output_dir / "subtitles"
    subtitles_dir.mkdir(parents=True, exist_ok=True)

    attribution_lines = build_attribution_lines(approved_asset_ids, manifest_path)
    commands = []
    rendered = []

    # MVP default assets referenced in manifest examples.
    background_video = Path("assets/media/sample_bg_001.mp4")
    voiceover_audio = Path("assets/media/sample_music_001.mp3")

    for item in items:
        sid = item["script_id"]
        subtitle_file = subtitles_dir / f"{sid}.srt"
        output_video = output_dir / f"{sid}.mp4"
        write_srt(item["script_text"], subtitle_file)
        cmd = build_ffmpeg_command(background_video, voiceover_audio, output_video, subtitle_file)
        commands.append({"script_id": sid, "command": cmd})

        if ffmpeg_exists() and background_video.exists() and voiceover_audio.exists():
            subprocess.run(cmd, check=False)
            rendered.append({"script_id": sid, "output_video": str(output_video), "rendered": output_video.exists()})
        else:
            # Dry-run mode keeps the command for later execution.
            rendered.append({"script_id": sid, "output_video": str(output_video), "rendered": False})

    result = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "attribution_lines": attribution_lines,
        "commands": commands,
        "results": rendered,
        "dry_run": not ffmpeg_exists(),
    }
    (output_dir / "render_jobs.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result
