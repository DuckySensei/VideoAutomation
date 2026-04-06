import json
import random
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Optional

from ass_subtitles import write_ass_centered
from ffmpeg_vertical import build_vertical_tts_command
from legal_compliance import validate_assets, build_attribution_lines
from media_probe import ffprobe_duration_sec
from tts_synthesize import synthesize_to_mp3


def _load_render_config(base_dir: Path) -> dict:
    path = base_dir / "config" / "render_config.json"
    if not path.is_file():
        path = base_dir / "config" / "render_config.example.json"
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _audio_denoise_filter(level: str) -> Optional[str]:
    level = (level or "off").strip().lower()
    if level == "off" or not level:
        return None
    if level == "light":
        return "highpass=f=180,afftdn=nf=-22"
    if level == "medium":
        return "highpass=f=180,afftdn=nf=-35"
    return None


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def ffmpeg_exists() -> bool:
    return shutil.which("ffmpeg") is not None


def ffprobe_exists() -> bool:
    return shutil.which("ffprobe") is not None


def _subtitle_vf(srt: Path, base_dir: Path) -> str:
    srt_abs = srt.resolve()
    base_abs = base_dir.resolve()
    try:
        rel = srt_abs.relative_to(base_abs)
    except ValueError:
        rel = None
    if rel is not None:
        p = rel.as_posix()
        return f"subtitles=filename={p}"
    p = srt_abs.as_posix()
    if len(p) >= 2 and p[1] == ":":
        p = p[0] + "\\:" + p[2:]
    return f"subtitles=filename={p}"


def build_ffmpeg_command(
    base_dir: Path,
    background_video: Path,
    voiceover_audio: Path,
    output_video: Path,
    subtitle_file: Path,
    bg_start_sec: float = 0.0,
    bg_duration_sec: Optional[float] = None,
    audio_denoise: str = "off",
) -> List[str]:
    cmd: List[str] = ["ffmpeg", "-y"]
    if bg_start_sec > 0:
        cmd.extend(["-ss", str(bg_start_sec)])
    cmd.extend(["-i", str(background_video)])
    if bg_duration_sec is not None and bg_duration_sec > 0:
        cmd.extend(["-t", str(bg_duration_sec)])
    cmd.extend(["-i", str(voiceover_audio)])

    cmd.extend(["-vf", _subtitle_vf(subtitle_file, base_dir)])

    af = _audio_denoise_filter(audio_denoise)
    if af:
        cmd.extend(["-af", af])

    cmd.extend(
        [
            "-shortest",
            "-c:v",
            "libx264",
            "-preset",
            "fast",
            "-c:a",
            "aac",
            str(output_video),
        ]
    )
    return cmd


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
    base_dir: Path,
) -> Dict[str, object]:
    ok, errors = validate_assets(approved_asset_ids, manifest_path)
    if not ok:
        raise ValueError(f"Asset validation failed: {errors}")

    payload = load_json(script_queue_file)
    items = payload.get("items", [])
    output_dir.mkdir(parents=True, exist_ok=True)
    subtitles_dir = output_dir / "subtitles"
    subtitles_dir.mkdir(parents=True, exist_ok=True)
    tts_dir = output_dir / "tts"
    tts_dir.mkdir(parents=True, exist_ok=True)

    attribution_lines = build_attribution_lines(approved_asset_ids, manifest_path)
    commands = []
    rendered = []

    cfg = _load_render_config(base_dir)
    bg_cfg = cfg.get("background") or {}
    audio_cfg = cfg.get("audio") or {}
    tts_cfg = cfg.get("tts") or {}
    vert_cfg = cfg.get("vertical") or {}

    tts_enabled = bool(tts_cfg.get("enabled", True))
    tts_voice = str(tts_cfg.get("voice", "en-US-GuyNeural"))
    subtitle_font_size = int(tts_cfg.get("subtitle_font_size", 78))
    subtitle_start_pad_sec = float(tts_cfg.get("subtitle_start_pad_sec", 0.12))
    subtitle_end_pad_sec = float(tts_cfg.get("subtitle_end_pad_sec", 0.08))
    random_start = bool(bg_cfg.get("random_start", True))
    max_segment_sec = float(bg_cfg.get("max_segment_sec", 180) or 180)
    bg_start_fixed = float(bg_cfg.get("start_sec", 0) or 0)
    bg_dur_cfg = bg_cfg.get("duration_sec", None)
    bg_duration_fixed: Optional[float] = None
    if bg_dur_cfg is not None:
        try:
            v = float(bg_dur_cfg)
            bg_duration_fixed = v if v > 0 else None
        except (TypeError, ValueError):
            bg_duration_fixed = None

    music_volume = float(audio_cfg.get("music_volume", 0.18))
    audio_denoise = str(audio_cfg.get("denoise", "off"))
    video_w = int(vert_cfg.get("width", 1080))
    video_h = int(vert_cfg.get("height", 1920))

    background_video = (base_dir / "assets" / "media" / "sample_bg_001.mp4").resolve()
    voiceover_audio = (base_dir / "assets" / "media" / "sample_music_001.mp3").resolve()

    if tts_enabled:
        try:
            import edge_tts  # noqa: F401
        except ImportError:
            tts_enabled = False

    def _skip_reason() -> str:
        if not ffmpeg_exists():
            return "FFmpeg not found on PATH (install FFmpeg and restart the terminal)."
        if tts_enabled and not ffprobe_exists():
            return "ffprobe not found on PATH (install FFmpeg full package)."
        if not background_video.is_file():
            return f"Missing background video: {background_video}"
        if not voiceover_audio.is_file():
            return f"Missing audio track: {voiceover_audio}"
        if tts_cfg.get("enabled", True) and not tts_enabled:
            return "TTS enabled but edge-tts not installed: pip install edge-tts"
        return ""

    for item in items:
        sid = item["script_id"]
        script_text = item.get("script_text", "")
        output_video = output_dir / f"{sid}.mp4"
        subtitle_srt = subtitles_dir / f"{sid}.srt"
        ass_path = subtitles_dir / f"{sid}.ass"
        tts_mp3 = tts_dir / f"{sid}.mp3"

        if tts_enabled:
            write_srt(script_text, subtitle_srt)
            try:
                synthesize_to_mp3(script_text, tts_mp3, tts_voice)
            except Exception as exc:  # noqa: BLE001
                rendered.append(
                    {
                        "script_id": sid,
                        "output_video": str(output_video),
                        "rendered": False,
                        "skip_reason": f"TTS failed: {exc}",
                    }
                )
                commands.append({"script_id": sid, "command": [], "mode": "tts"})
                continue

            try:
                tts_dur = ffprobe_duration_sec(tts_mp3)
            except Exception as exc:  # noqa: BLE001
                rendered.append(
                    {
                        "script_id": sid,
                        "output_video": str(output_video),
                        "rendered": False,
                        "skip_reason": f"ffprobe TTS: {exc}",
                    }
                )
                commands.append({"script_id": sid, "command": [], "mode": "tts"})
                continue

            segment_sec = min(tts_dur, max_segment_sec)
            if bg_duration_fixed is not None:
                segment_sec = min(segment_sec, bg_duration_fixed)

            try:
                vid_dur = ffprobe_duration_sec(background_video)
            except Exception as exc:  # noqa: BLE001
                rendered.append(
                    {
                        "script_id": sid,
                        "output_video": str(output_video),
                        "rendered": False,
                        "skip_reason": f"ffprobe video: {exc}",
                    }
                )
                commands.append({"script_id": sid, "command": [], "mode": "tts"})
                continue

            if segment_sec > vid_dur - 0.1:
                rendered.append(
                    {
                        "script_id": sid,
                        "output_video": str(output_video),
                        "rendered": False,
                        "skip_reason": f"Video ({vid_dur:.1f}s) shorter than segment ({segment_sec:.1f}s).",
                    }
                )
                commands.append({"script_id": sid, "command": [], "mode": "tts"})
                continue

            max_start = max(0.0, vid_dur - segment_sec - 0.05)
            if random_start:
                start_sec = random.uniform(0.0, max_start) if max_start > 0 else 0.0
            else:
                start_sec = min(bg_start_fixed, max_start)

            lines = [ln.strip() for ln in script_text.splitlines() if ln.strip()]
            write_ass_centered(
                lines,
                segment_sec,
                ass_path,
                font_size=subtitle_font_size,
                start_pad_sec=subtitle_start_pad_sec,
                end_pad_sec=subtitle_end_pad_sec,
            )

            cmd = build_vertical_tts_command(
                base_dir=base_dir,
                bg_video=background_video,
                music=voiceover_audio,
                tts_mp3=tts_mp3,
                ass_file=ass_path,
                output_mp4=output_video,
                bg_start_sec=start_sec,
                segment_sec=segment_sec,
                music_volume=music_volume,
                music_denoise=audio_denoise if audio_denoise in ("light", "medium") else None,
                video_w=video_w,
                video_h=video_h,
            )
            commands.append(
                {
                    "script_id": sid,
                    "command": cmd,
                    "mode": "tts_vertical",
                    "random_start_sec": start_sec,
                    "segment_sec": segment_sec,
                }
            )
        else:
            write_srt(script_text, subtitle_srt)
            cmd = build_ffmpeg_command(
                base_dir,
                background_video,
                voiceover_audio,
                output_video,
                subtitle_srt,
                bg_start_sec=bg_start_fixed,
                bg_duration_sec=bg_duration_fixed,
                audio_denoise=audio_denoise,
            )
            commands.append({"script_id": sid, "command": cmd, "mode": "legacy"})

        reason = _skip_reason()
        if reason:
            rendered.append(
                {
                    "script_id": sid,
                    "output_video": str(output_video),
                    "rendered": False,
                    "skip_reason": reason,
                }
            )
            continue

        cmd = commands[-1].get("command") or []
        if not cmd:
            continue

        proc = subprocess.run(
            cmd,
            cwd=str(base_dir),
            capture_output=True,
            text=True,
            check=False,
        )
        ok_file = output_video.is_file()
        entry: Dict[str, object] = {
            "script_id": sid,
            "output_video": str(output_video),
            "rendered": ok_file,
            "ffmpeg_exit_code": proc.returncode,
            "mode": commands[-1].get("mode"),
        }
        if commands[-1].get("mode") == "tts_vertical":
            entry["random_start_sec"] = commands[-1].get("random_start_sec")
            entry["segment_sec"] = commands[-1].get("segment_sec")
        if not ok_file or proc.returncode != 0:
            entry["skip_reason"] = (
                (proc.stderr or proc.stdout or "").strip()[-2000:] or "FFmpeg failed; see ffmpeg_exit_code."
            )
        rendered.append(entry)

    result = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "render_settings": {
            "tts_enabled": tts_enabled,
            "tts_voice": tts_voice if tts_enabled else None,
            "random_start": random_start,
            "max_segment_sec": max_segment_sec,
            "vertical": {"width": video_w, "height": video_h},
            "music_volume": music_volume,
            "audio_denoise": audio_denoise,
        },
        "attribution_lines": attribution_lines,
        "commands": commands,
        "results": rendered,
        "dry_run": not ffmpeg_exists(),
    }
    (output_dir / "render_jobs.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result
