import argparse
import json
import os
import time
import urllib.parse
import urllib.request
from pathlib import Path


GRAPH_VERSION = "v21.0"


def _json_request(url: str, method: str = "GET", data: dict | None = None) -> dict:
    body = None
    headers = {}
    if data is not None:
        body = urllib.parse.urlencode(data).encode("utf-8")
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _resolve_video_url(video_path: str) -> str:
    direct = os.getenv("INSTAGRAM_VIDEO_URL", "").strip()
    if direct:
        return direct
    base = os.getenv("INSTAGRAM_VIDEO_URL_BASE", "").strip().rstrip("/")
    if not base:
        return ""
    filename = Path(video_path).name
    return f"{base}/{filename}"


def upload_to_instagram(video_path: str, caption: str, publish_at: str, dry_run: bool) -> dict:
    if dry_run:
        return {
            "ok": True,
            "dry_run": True,
            "video_path": video_path,
            "caption_preview": caption[:100],
            "publish_at": publish_at,
        }

    access_token = os.getenv("INSTAGRAM_ACCESS_TOKEN", "").strip()
    ig_user_id = os.getenv("INSTAGRAM_ACCOUNT_ID", "").strip()
    video_url = _resolve_video_url(video_path)
    if not access_token or not ig_user_id:
        raise ValueError("Missing INSTAGRAM_ACCESS_TOKEN or INSTAGRAM_ACCOUNT_ID")
    if not video_url:
        raise ValueError("Set INSTAGRAM_VIDEO_URL_BASE (or INSTAGRAM_VIDEO_URL) to a publicly reachable URL")

    create_url = f"https://graph.facebook.com/{GRAPH_VERSION}/{ig_user_id}/media"
    create_payload = {
        "media_type": "REELS",
        "video_url": video_url,
        "caption": caption[:2200],
        "share_to_feed": "true",
        "access_token": access_token,
    }
    creation = _json_request(create_url, method="POST", data=create_payload)
    creation_id = creation.get("id", "")
    if not creation_id:
        raise RuntimeError(f"Instagram media container creation failed: {creation}")

    status_url = f"https://graph.facebook.com/{GRAPH_VERSION}/{creation_id}"
    for _ in range(30):
        status = _json_request(
            status_url,
            data={
                "fields": "status_code",
                "access_token": access_token,
            },
        )
        code = status.get("status_code", "")
        if code == "FINISHED":
            break
        if code in {"ERROR", "EXPIRED"}:
            raise RuntimeError(f"Instagram container processing failed: {status}")
        time.sleep(2)

    publish_url = f"https://graph.facebook.com/{GRAPH_VERSION}/{ig_user_id}/media_publish"
    published = _json_request(
        publish_url,
        method="POST",
        data={
            "creation_id": creation_id,
            "access_token": access_token,
        },
    )
    media_id = published.get("id", "")
    if not media_id:
        raise RuntimeError(f"Instagram publish failed: {published}")

    return {
        "ok": True,
        "instagram_media_id": media_id,
        "video_url": video_url,
        "publish_at_ignored": bool(publish_at),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Upload one Reel to Instagram Graph API.")
    parser.add_argument("--video", required=True, help="Local video path (filename used with INSTAGRAM_VIDEO_URL_BASE)")
    parser.add_argument("--caption", default="", help="Caption text")
    parser.add_argument("--publish-at", default="", help="Optional publish time (currently ignored by API flow)")
    parser.add_argument("--dry-run", action="store_true", help="Simulate upload without API calls")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    try:
        result = upload_to_instagram(
            video_path=args.video,
            caption=args.caption,
            publish_at=args.publish_at,
            dry_run=args.dry_run,
        )
        print(json.dumps(result, indent=2))
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
        raise SystemExit(1) from exc
