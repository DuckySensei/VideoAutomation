import argparse
import json
import os


def upload_to_tiktok(video_path: str, caption: str, publish_at: str, dry_run: bool) -> dict:
    if dry_run:
        return {
            "ok": True,
            "dry_run": True,
            "video_path": video_path,
            "caption_preview": caption[:80],
            "publish_at": publish_at,
        }

    access_token = os.getenv("TIKTOK_ACCESS_TOKEN", "").strip()
    if not access_token:
        raise ValueError(
            "TikTok upload integration requires TIKTOK_ACCESS_TOKEN and a real API implementation."
        )

    # Placeholder until TikTok upload API integration is implemented for your approved app.
    raise NotImplementedError(
        "TikTok upload API flow is app-dependent. Use --dry-run now or replace this script with your approved upload flow."
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Upload one short video to TikTok (scaffold).")
    parser.add_argument("--video", required=True, help="Path to video file")
    parser.add_argument("--caption", default="", help="Video caption")
    parser.add_argument("--publish-at", default="", help="Optional publish time")
    parser.add_argument("--dry-run", action="store_true", help="Simulate upload without API call")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    try:
        result = upload_to_tiktok(
            video_path=args.video,
            caption=args.caption,
            publish_at=args.publish_at,
            dry_run=args.dry_run,
        )
        print(json.dumps(result, indent=2))
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
        raise SystemExit(1) from exc
