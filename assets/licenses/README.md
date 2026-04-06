# Licensed Asset Workflow

Use this folder to track legal rights for every media file used in production.

## Rules
- Only use assets that are:
  - creator-owned, or
  - commercially licensed for your use case, or
  - Creative Commons where reuse is explicitly allowed.
- Keep proof links, purchase receipts, and terms snapshots.
- If attribution is required, include it in video description using the attribution template.

## Files
- `manifest.csv`: source-of-truth for allowed assets.
- `attribution_template.md`: reusable description snippet for required credits.
- Place actual media files in `assets/media/` and ensure each file has a matching row in `manifest.csv`.

## Required manifest fields
- `asset_id`: stable unique ID.
- `file_path`: relative path to file.
- `license_type`: e.g. `creator_owned`, `commercial_stock`, `cc_by_4_0`.
- `license_scope`: short note about allowed usage.
- `source_url`: where the asset came from.
- `proof_path_or_receipt`: local path or receipt reference.
- `attribution_required`: `yes` or `no`.
- `attribution_text`: the exact credit line when required.
- `status`: `approved` or `rejected`.
