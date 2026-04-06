"""Load config/autonomous.env into os.environ (setdefault — existing env wins)."""
import os
from pathlib import Path


def load_autonomous_env(base_dir: Path) -> None:
    path = base_dir / "config" / "autonomous.env"
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            os.environ.setdefault(key, value)
