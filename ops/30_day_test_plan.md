# 30-Day Publishing Test Plan

This runbook is built for 1-3 hours/week.

## Week 0 Setup (once)
- Confirm niche and templates in `config/niche_profile.json`.
- Confirm legal asset records in `assets/licenses/manifest.csv`.
- Run one pipeline dry run:
  - `python src/main.py --base-dir . --monthly-fixed-cost 50`
- Validate generated files and fix any missing asset references.

## Daily Cadence (15-20 minutes)
- Run the pipeline once per day.
- Review `output/youtube_upload_queue.json`.
- Upload/schedule approved videos from the queue.
- Log daily performance rows in `data/metrics/daily_metrics.csv`.

## Weekly Cadence (60-90 minutes)
- Remove lowest-performing 20% scripts from future prompts.
- Adjust one hook pattern and one CTA style.
- Check break-even gap from `output/pipeline_report.json`.

## Minimum Throughput Targets
- Week 1-2: 1 short/day
- Week 3-4: 2 shorts/day if quality metrics hold

## KPI Baselines to Track
- 3-second retention trend
- Average view duration
- Revenue per 1,000 views (blended)
- Daily revenue vs daily variable cost

## End-of-Month Review
- Compute total revenue and costs.
- Keep only templates with above-median retention and earnings.
- Decide: scale, hold, or pivot niche based on break-even gap.
