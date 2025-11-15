#!/usr/bin/env python3
"""
Post a video stored in a Nextcloud public share to X (Twitter) using Ayrshare.

Usage:
    python post_nextcloud_to_x.py "https://cloud.example.com/s/SHAREID" \
        --text "My video from Nextcloud"
"""

import argparse
import json
from urllib.parse import urlparse, urlunparse
import requests

# ------------------------------------------------------------
# Your Ayrshare API key (as requested)
# ------------------------------------------------------------
AYRSHARE_API_KEY = "678BF37B-BFA4487A-AF8D6B2B-7984761F"
AYRSHARE_PROFILE_KEY = None   # set if you use Ayrshare User Profiles

AYRSHARE_POST_ENDPOINT = "https://api.ayrshare.com/api/post"


def build_nextcloud_download_url(share_url: str) -> str:
    """
    Convert Nextcloud share link to a direct download link.
    """
    video_exts = (".mp4", ".mov", ".m4v", ".webm", ".avi", ".mpg", ".mpeg")

    if share_url.lower().endswith(video_exts):
        return share_url

    parsed = urlparse(share_url)

    if parsed.path.endswith("/download") or parsed.path.endswith("/download/"):
        return share_url

    new_path = parsed.path.rstrip("/") + "/download"
    new_url = urlunparse(parsed._replace(path=new_path))

    return new_url


def post_video_to_x(nextcloud_share_url: str, post_text: str, platform: str = "twitter") -> dict:
    """
    Publish the Nextcloud video to X via Ayrshare.
    """

    media_url = build_nextcloud_download_url(nextcloud_share_url)

    headers = {
        "Authorization": f"Bearer {AYRSHARE_API_KEY}",
        "Content-Type": "application/json",
    }

    if AYRSHARE_PROFILE_KEY:
        headers["Profile-Key"] = AYRSHARE_PROFILE_KEY

    payload = {
        "post": post_text,
        "platforms": [platform],
        "mediaUrls": [media_url],
        "isVideo": True,
    }

    response = requests.post(AYRSHARE_POST_ENDPOINT, headers=headers, json=payload)

    try:
        data = response.json()
    except Exception:
        raise RuntimeError(
            f"Ayrshare returned non-JSON response: HTTP {response.status_code} — {response.text}"
        )

    if response.status_code >= 400 or data.get("status") == "error":
        raise RuntimeError(
            f"Ayrshare API error (HTTP {response.status_code}): {json.dumps(data, indent=2)}"
        )

    return data


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Post a Nextcloud-hosted video to X (Twitter) via Ayrshare."
    )
    parser.add_argument(
        "share_url",
        help="Public Nextcloud share URL (e.g., https://cloud.example.com/s/ID)"
    )
    parser.add_argument(
        "--text", "-t",
        default="",
        help="Text to include in the post."
    )
    parser.add_argument(
        "--platform",
        default="twitter",
        help="Ayrshare platform (default: twitter)."
    )

    args = parser.parse_args()

    print(f"Original Nextcloud URL: {args.share_url}")
    print(f"Derived download URL: {build_nextcloud_download_url(args.share_url)}")

    try:
        result = post_video_to_x(
            nextcloud_share_url=args.share_url,
            post_text=args.text,
            platform=args.platform,
        )
        print("\n✅ Successfully posted to Ayrshare!")
        print(json.dumps(result, indent=2))

    except Exception as e:
        print(f"\n❌ ERROR posting to Ayrshare:\n{e}")


if __name__ == "__main__":
    main()


