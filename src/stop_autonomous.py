"""Stop the autonomous loop process recorded in data/autonomous.pid (Windows: taskkill)."""
import argparse
import os
import signal
import subprocess
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Stop autonomous loop by PID file")
    parser.add_argument("--base-dir", default=".", help="Project root")
    parser.add_argument("--pid-file", default="data/autonomous.pid", help="PID file path relative to base-dir")
    args = parser.parse_args()
    root = Path(args.base_dir).resolve()
    pid_path = (root / args.pid_file).resolve()
    if not pid_path.exists():
        print("No PID file found; loop does not appear to be running.")
        sys.exit(0)
    try:
        pid = int((pid_path.read_text(encoding="utf-8") or "").strip().splitlines()[0])
    except (ValueError, IndexError):
        print("Invalid PID file; removing it.")
        pid_path.unlink(missing_ok=True)
        sys.exit(1)

    if sys.platform == "win32":
        r = subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True, text=True, check=False)
        if r.returncode != 0:
            print(r.stderr or r.stdout or "taskkill failed")
    else:
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            print(f"Process {pid} not found.")

    pid_path.unlink(missing_ok=True)
    print(f"Stopped PID {pid} (if it was still running).")


if __name__ == "__main__":
    main()
