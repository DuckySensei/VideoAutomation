# Local mini-dashboard

From the repo root:

```bash
python src/dashboard_server.py --base-dir .
```

Open **http://127.0.0.1:8765/** in your browser.

You get:

- Pipeline counts (scripts, renders, upload queue)
- Break-even snapshot
- Whether the autonomous **loop PID** is running (reads `data/autonomous.pid`)
- Manual drop stats + path to **`output/drop_for_manual_upload/latest/video.mp4`**
- Last rows from `data/metrics/daily_metrics.csv`
- Copy-paste commands for **one cycle**, **loop**, **stop**, and **render one video**

`config/autonomous.env` is loaded automatically (same as `main.py` / `autonomous_service.py`).

Stop the dashboard with **Ctrl+C** in the terminal (it does not stop the autonomous loop).
