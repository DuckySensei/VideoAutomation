"""FFmpeg filter graph: 9:16 vertical + ASS + TTS + music (original video audio discarded)."""
from pathlib import Path
from typing import List, Optional


def _ass_rel(path: Path, base_dir: Path) -> str:
    try:
        return path.resolve().relative_to(base_dir.resolve()).as_posix()
    except ValueError:
        p = path.resolve().as_posix()
        if len(p) >= 2 and p[1] == ":":
            p = p[0] + "\\:" + p[2:]
        return p


def build_vertical_tts_command(
    base_dir: Path,
    bg_video: Path,
    music: Path,
    tts_mp3: Path,
    ass_file: Path,
    output_mp4: Path,
    bg_start_sec: float,
    segment_sec: float,
    music_volume: float,
    music_denoise: Optional[str],
    video_w: int,
    video_h: int,
) -> List[str]:
    ass_rel = _ass_rel(ass_file, base_dir)
    d = segment_sec

    # Video: scale to cover 9:16, burn ASS subtitles, discard original audio [0:a]
    vchain = (
        f"[0:v]scale=-2:{video_h},crop={video_w}:{video_h}:(iw-{video_w})/2:0,"
        f"subtitles=filename={ass_rel},format=yuv420p[v]"
    )

    # Music: loop if short, trim to segment, optional denoise, duck volume
    mu = f"[1:a]aloop=loop=-1:size=2e+09,atrim=0:{d},asetpts=PTS-STARTPTS[mu0]"
    if music_denoise == "light":
        mu += ";[mu0]highpass=f=180,afftdn=nf=-22[mu1];[mu1]volume=" + str(music_volume) + "[bg]"
    elif music_denoise == "medium":
        mu += ";[mu0]highpass=f=180,afftdn=nf=-35[mu1];[mu1]volume=" + str(music_volume) + "[bg]"
    else:
        mu += ";[mu0]volume=" + str(music_volume) + "[bg]"

    # TTS + music mix; voice defines length (duration=first)
    aud = (
        f"[2:a]atrim=0:{d},asetpts=PTS-STARTPTS[voice];"
        f"[voice][bg]amix=inputs=2:duration=first:dropout_transition=2[a]"
    )

    fc = vchain + ";" + mu + ";" + aud

    return [
        "ffmpeg",
        "-y",
        "-ss",
        str(bg_start_sec),
        "-t",
        str(d),
        "-i",
        str(bg_video),
        "-i",
        str(music),
        "-i",
        str(tts_mp3),
        "-filter_complex",
        fc,
        "-map",
        "[v]",
        "-map",
        "[a]",
        "-c:v",
        "libx264",
        "-preset",
        "fast",
        "-c:a",
        "aac",
        "-movflags",
        "+faststart",
        str(output_mp4),
    ]
