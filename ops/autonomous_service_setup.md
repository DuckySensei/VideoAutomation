# Autonomous Service Setup

This guide gets VideoAutomation running with minimal manual interaction.

## 1) Run autonomous mode locally first

```bash
python -m pip install -r requirements.txt
python src/autonomous_service.py --base-dir . --monthly-fixed-cost 50 --enable-upload-hook --enable-tiktok-hook --enable-metrics-hook --upload-dry-run
```

Check:
- `output/autonomous_report.json`
- `output/youtube_upload_queue.json`
- `data/autonomous_state.json`

## 2) Configure command hooks

Set these environment variables on the machine/container that runs the job:

- `YT_CLIENT_ID`
- `YT_CLIENT_SECRET`
- `YT_REFRESH_TOKEN`
- `YT_TOKEN_URI` (optional, default is Google token endpoint)
- `YOUTUBE_UPLOAD_COMMAND`
  - Runs once per upload queue item.
  - Placeholders: `{video_path}`, `{title}`, `{description}`, `{privacy_status}`, `{publish_at}`, `{script_id}`
- `TIKTOK_UPLOAD_COMMAND`
  - Runs once per TikTok upload queue item.
  - Placeholders: `{video_path}`, `{caption}`, `{publish_at}`, `{script_id}`
- `METRICS_IMPORT_COMMAND`
  - Runs once after each pipeline cycle.

The command scripts should:
- Return exit code `0` on success.
- Return non-zero on failure (recorded in `output/autonomous_report.json`).
- Append metrics rows to `data/metrics/daily_metrics.csv` (or call `src/analytics.py` helpers).

## 3) Schedule daily runs (recommended)

Use one run per day instead of an always-on process:

```bash
python src/autonomous_service.py --base-dir . --monthly-fixed-cost 50 --enable-upload-hook --enable-tiktok-hook --enable-metrics-hook
```

### Windows Task Scheduler
- Trigger: daily at your preferred local time.
- Action: `python`
- Arguments: `src/autonomous_service.py --base-dir . --monthly-fixed-cost 50 --enable-upload-hook --enable-metrics-hook`
- Start in: project root (this repository).

## 4) Safe autonomy boundaries

Autonomous tuning is intentionally conservative:
- Only adjusts generation volume (`script_max_items`) within min/max bounds.
- Never changes legal/compliance checks.
- Writes all changes to `data/autonomous_state.json`.

## 5) Production checklist

- FFmpeg installed and available in PATH.
- Real media files present under `assets/media/`.
- `assets/licenses/manifest.csv` fully updated.
- YouTube Data API v3 enabled in GCP.
- YouTube Analytics API enabled in GCP.
- YouTube upload command tested manually with one short.
- TikTok upload command tested manually (or left in dry-run mode).
- Metrics command tested manually for one day of data.
