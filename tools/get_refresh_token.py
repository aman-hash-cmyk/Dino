#!/usr/bin/env python3
"""
get_refresh_token.py - ONE-TIME helper, run on your own computer.

1. Put the OAuth client file you downloaded from Google Cloud next to this
   script's parent folder as  client_secret.json
2. Run:  python tools/get_refresh_token.py
3. A browser opens; log in with the Google account that owns your YouTube channel
   and pick the channel. Copy the three printed values into GitHub secrets.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from google_auth_oauthlib.flow import InstalledAppFlow  # noqa: E402
from yt_auth import SCOPES  # noqa: E402

secret = ROOT / "client_secret.json"
if not secret.exists():
    sys.exit(f"Put your downloaded OAuth file at {secret}")
flow = InstalledAppFlow.from_client_secrets_file(str(secret), SCOPES)
creds = flow.run_local_server(port=0, access_type="offline", prompt="consent")
info = json.loads(secret.read_text())
info = info.get("installed") or info.get("web")
print("\nAdd these three as GitHub repository secrets:\n")
print("YT_CLIENT_ID     =", info["client_id"])
print("YT_CLIENT_SECRET =", info["client_secret"])
print("YT_REFRESH_TOKEN =", creds.refresh_token)
