import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
_SRC = _REPO / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from env_loader import load_autonomous_env  # noqa: E402
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

from google_auth import load_google_credentials


UPLOAD_SCOPE = "https://www.googleapis.com/auth/youtube.upload"


def _parse_publish_at(value: str) -> str:
    if not value:
        return ""
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def upload_video(
    video_path: str,
    title: str,
    description: str,
    privacy_status: str,
    publish_at: str,
) -> dict:
    credentials = load_google_credentials([UPLOAD_SCOPE])
    youtube = build("youtube", "v3", credentials=credentials, cache_discovery=False)

    status = {"privacyStatus": privacy_status}
    publish_at_utc = _parse_publish_at(publish_at)
    if publish_at_utc and privacy_status == "private":
        status["publishAt"] = publish_at_utc

    body = {
        "snippet": {
            "title": title[:100],
            "description": description[:5000],
            "categoryId": "22",
        },
        "status": status,
    }

    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=MediaFileUpload(video_path, chunksize=-1, resumable=True),
    )

    response = None
    while response is None:
        _, response = request.next_chunk()

    return {
        "ok": True,
        "video_id": response.get("id", ""),
        "privacyStatus": privacy_status,
        "publishAt": publish_at_utc,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Upload one video to YouTube.")
    parser.add_argument("--video", required=True, help="Path to video file")
    parser.add_argument("--title", required=True, help="Video title")
    parser.add_argument("--description", default="", help="Video description")
    parser.add_argument("--privacy", default="private", choices=["private", "public", "unlisted"], help="Privacy status")
    parser.add_argument("--publish-at", default="", help="RFC3339/ISO datetime for scheduled publish (private only)")
    return parser.parse_args()


if __name__ == "__main__":
    load_autonomous_env(_REPO)
    args = parse_args()
    try:
        result = upload_video(
            video_path=args.video,
            title=args.title,
            description=args.description,
            privacy_status=args.privacy,
            publish_at=args.publish_at,
        )
        print(json.dumps(result, indent=2))
    except HttpError as exc:
        payload = {"ok": False, "error": str(exc), "status_code": getattr(exc.resp, "status", None)}
        print(json.dumps(payload, indent=2))
        raise SystemExit(1) from exc
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
        raise SystemExit(1) from exc
