# Legal Low-Cost Video Automation

This project implements a legal-first, low-cost automation pipeline for short-form videos:

1. Trend ingest (RSS sources)
2. Script queue generation with duplication guard
3. Legal asset compliance check
4. Render job creation (FFmpeg command generation; auto-renders if FFmpeg + media exist)
5. YouTube upload queue generation
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
3. Add your real media files under `assets/media/`.
4. Update `assets/licenses/manifest.csv` to match real media and proof docs.
5. Run:

```bash
python src/main.py --base-dir . --monthly-fixed-cost 50
```

## What the pipeline outputs
- `data/trends.json`
- `data/script_queue.json`
- `output/renders/render_jobs.json`
- `output/youtube_upload_queue.json`
- `output/pipeline_report.json`
- `data/metrics/daily_metrics.csv`

## Scheduler Integration (YouTube)
The MVP writes a `ready_for_api_upload` queue for YouTube. You can wire this into YouTube Data API upload scripts once OAuth credentials are configured.

## Legal Guardrails
- Only approved assets from `assets/licenses/manifest.csv` are allowed.
- Required attributions are extracted automatically for descriptions.
- Scripts pass a similarity filter to reduce duplicate content.

## Break-Even Tracking
Break-even is tracked in `src/analytics.py`:
- `monthly_revenue >= monthly_fixed_cost + variable_costs`

Use `data/metrics/daily_metrics.csv` and the included ops runbooks to monitor progress and optimize.
