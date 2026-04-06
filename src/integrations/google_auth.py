import os
from typing import Iterable

from google.oauth2.credentials import Credentials


def load_google_credentials(scopes: Iterable[str]) -> Credentials:
    client_id = os.getenv("YT_CLIENT_ID", "").strip()
    client_secret = os.getenv("YT_CLIENT_SECRET", "").strip()
    refresh_token = os.getenv("YT_REFRESH_TOKEN", "").strip()
    token_uri = os.getenv("YT_TOKEN_URI", "https://oauth2.googleapis.com/token").strip()

    missing = [
        key
        for key, value in {
            "YT_CLIENT_ID": client_id,
            "YT_CLIENT_SECRET": client_secret,
            "YT_REFRESH_TOKEN": refresh_token,
        }.items()
        if not value
    ]
    if missing:
        raise ValueError(f"Missing required environment variables: {', '.join(missing)}")

    return Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri=token_uri,
        client_id=client_id,
        client_secret=client_secret,
        scopes=list(scopes),
    )
