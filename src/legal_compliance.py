import csv
from pathlib import Path
from typing import Dict, List, Tuple


def load_license_manifest(manifest_path: Path) -> Dict[str, dict]:
    rows: Dict[str, dict] = {}
    with manifest_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows[row["asset_id"]] = row
    return rows


def validate_assets(asset_ids: List[str], manifest_path: Path) -> Tuple[bool, List[str]]:
    manifest = load_license_manifest(manifest_path)
    errors: List[str] = []
    for asset_id in asset_ids:
        row = manifest.get(asset_id)
        if not row:
            errors.append(f"Asset '{asset_id}' not found in license manifest.")
            continue
        if row.get("status") != "approved":
            errors.append(f"Asset '{asset_id}' is not approved.")
    return (len(errors) == 0, errors)


def build_attribution_lines(asset_ids: List[str], manifest_path: Path) -> List[str]:
    manifest = load_license_manifest(manifest_path)
    lines: List[str] = []
    for asset_id in asset_ids:
        row = manifest.get(asset_id)
        if not row:
            continue
        if row.get("attribution_required", "").lower() == "yes":
            text = row.get("attribution_text", "").strip()
            if text:
                lines.append(f"- {text}")
    return lines
