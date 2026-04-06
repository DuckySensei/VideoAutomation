"""ffprobe helpers."""
import subprocess
from pathlib import Path


def ffprobe_duration_sec(path: Path) -> float:
    r = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if r.returncode != 0:
        raise RuntimeError(r.stderr or r.stdout or "ffprobe failed")
    return float((r.stdout or "").strip() or 0.0)
