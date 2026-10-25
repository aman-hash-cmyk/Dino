"""Shared YouTube credentials: built from three environment variables / GitHub secrets."""
import os
from google.oauth2.credentials import Credentials

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/yt-analytics.readonly",
]


def get_credentials():
    try:
        return Credentials(
            token=None,
            refresh_token=os.environ["YT_REFRESH_TOKEN"],
            token_uri="https://oauth2.googleapis.com/token",
            client_id=os.environ["YT_CLIENT_ID"],
            client_secret=os.environ["YT_CLIENT_SECRET"],
            scopes=SCOPES,
        )
    except KeyError as e:
        raise SystemExit(f"Missing environment variable / secret: {e}")
