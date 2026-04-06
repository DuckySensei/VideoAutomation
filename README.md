# Legal Low-Cost Video Automation

This project implements a legal-first, low-cost automation pipeline for short-form videos:

1. Trend ingest (RSS sources)
2. Script queue generation with duplication guard
3. Legal asset compliance check
4. Render job creation (FFmpeg command generation; auto-renders if FFmpeg + media exist)
5. YouTube Shorts + TikTok upload queue generation
6. Analytics + break-even tracking

## Budget and Time Fit
- Designed for `$25-$75/month`
- Ongoing operator time target: `1-3 hours/week`

## Project Structure
- `config/` niche and prompt templates
- `assets/licenses/` legal manifest + attribution template
- `src/` pipeline modules
- `data/` generated trends, queues, and metrics
- `output/` render jobs, upload queue, and pipeline report
- `ops/` runbooks for 30-day test and optimization

## Quick Start
1. Install Python 3.10+.
2. (Optional) Install FFmpeg and add to PATH for local renders.
3. Install dependencies:

```bash
python -m pip install -r requirements.txt
```

4. Add your real media files under `assets/media/`.
5. Update `assets/licenses/manifest.csv` to match real media and proof docs.
6. Run:

```bash
python src/main.py --base-dir . --monthly-fixed-cost 50
```

## What the pipeline outputs
- `data/trends.json`
- `data/script_queue.json`
- `output/renders/render_jobs.json`
- `output/youtube_upload_queue.json`
- `output/tiktok_upload_queue.json`
- `output/drop_for_manual_upload/` — one folder per video: `video.mp4` + caption/title/description text files for hand-upload (see `ops/manual_upload_workflow.md`)
- `output/pipeline_report.json`
- `data/metrics/daily_metrics.csv`

## Scheduler Integration (YouTube Shorts + TikTok)
The pipeline writes `ready_for_api_upload` queues:
- `output/youtube_upload_queue.json` for YouTube Shorts
- `output/tiktok_upload_queue.json` for TikTok

You can wire both into API upload scripts once credentials are configured.

## Local dashboard

```bash
python src/dashboard_server.py --base-dir .
```

Then open **http://127.0.0.1:8765/** — pipeline status, metrics table, PID status for the autonomous loop, and start/stop commands. See `ops/dashboard.md`.

`config/autonomous.env` is loaded when you run the dashboard (and the main pipeline).

## Autonomous Service Mode
You can run this project as an unattended daily service using `src/autonomous_service.py`.

One cycle (recommended for schedulers):

```bash
python src/autonomous_service.py --base-dir . --monthly-fixed-cost 50 --enable-upload-hook --enable-tiktok-hook --enable-metrics-hook
```

Continuous loop mode (writes `data/autonomous.pid`; dashboard shows if it is running):

```bash
python src/autonomous_service.py --base-dir . --loop --interval-seconds 86400 --enable-upload-hook --enable-tiktok-hook --enable-metrics-hook --pid-file data/autonomous.pid
```

Stop the loop:

```bash
python src/stop_autonomous.py --base-dir .
```

### Hook-based integration
Autonomous mode supports external command hooks so you can keep uploader/analytics scripts separate:

- `YOUTUBE_UPLOAD_COMMAND`: command template run per queue item.
  - Available placeholders: `{video_path}`, `{title}`, `{description}`, `{privacy_status}`, `{publish_at}`, `{script_id}`
- `TIKTOK_UPLOAD_COMMAND`: command template run per TikTok queue item.
  - Available placeholders: `{video_path}`, `{caption}`, `{publish_at}`, `{script_id}`
- `METRICS_IMPORT_COMMAND`: command run once per cycle to import analytics into `data/metrics/daily_metrics.csv`

Example:

```bash
set YOUTUBE_UPLOAD_COMMAND=python src/integrations/upload_to_youtube.py --video "{video_path}" --title "{title}" --description "{description}" --privacy "{privacy_status}" --publish-at "{publish_at}"
set TIKTOK_UPLOAD_COMMAND=python src/integrations/upload_to_tiktok.py --video "{video_path}" --caption "{caption}" --publish-at "{publish_at}" --dry-run
set METRICS_IMPORT_COMMAND=python src/integrations/pull_youtube_metrics.py --base-dir . --days 1 --variable-cost-usd 0.02
```

Google OAuth environment variables required by both hooks:

```bash
set YT_CLIENT_ID=your_client_id.apps.googleusercontent.com
set YT_CLIENT_SECRET=your_client_secret
set YT_REFRESH_TOKEN=your_refresh_token
set YT_TOKEN_URI=https://oauth2.googleapis.com/token
```

Autonomous outputs:
- `data/autonomous_state.json` (safe tuning knobs)
- `output/autonomous_report.json` (latest cycle status)

## Legal Guardrails
- Only approved assets from `assets/licenses/manifest.csv` are allowed.
- Required attributions are extracted automatically for descriptions.
- Scripts pass a similarity filter to reduce duplicate content.

## Break-Even Tracking
Break-even is tracked in `src/analytics.py`:
- `monthly_revenue >= monthly_fixed_cost + variable_costs`

Use `data/metrics/daily_metrics.csv` and the included ops runbooks to monitor progress and optimize.
