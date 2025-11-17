#!/usr/bin/env python3
"""
Post a video stored in a Nextcloud public share to ALL linked accounts on a Late Profile.

Usage:
    python post_nextcloud_to_all.py --share_url "https://cloud.example.com/s/SHAREID" \
        --text "My video from Nextcloud"
"""

import argparse
import json
import logging
import os
from typing import Optional
from urllib.parse import urlparse, urlunparse

import requests

from config import get_env
from log_utils import attach_log_streams, get_logger, log_call

# ------------------------------------------------------------
# Late API Credentials
# ------------------------------------------------------------
LATE_API_KEY = get_env("LATE_API_KEY")

# IMPORTANT: Set your Late Profile ID in the environment:
LATE_PROFILE_ID = get_env("LATE_PROFILE_ID")

LATE_POST_ENDPOINT = os.environ.get(
    "LATE_POST_ENDPOINT", "https://getlate.dev/api/v1/posts"
)
LATE_TIMEZONE = os.environ.get("LATE_TIMEZONE", "UTC")

attach_log_streams("late_post")
logger = get_logger("gallardo.late_post")


@log_call(logger)
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


@log_call(logger)
def post_video_to_all_accounts(
    nextcloud_share_url: str,
    post_text: str,
    *,
    scheduled_for: Optional[str] = None,
    timezone: Optional[str] = None,
    publish_now: Optional[bool] = None,
) -> dict:
    """
    Publish the Nextcloud video to ALL connected accounts on a Late profile.
    """

    if LATE_PROFILE_ID == "REPLACE_WITH_LATE_PROFILE_ID":
        raise RuntimeError(
            "❌ You must set LATE_PROFILE_ID to your real Late Profile ID."
        )

    media_url = build_nextcloud_download_url(nextcloud_share_url)

    headers = {
        "Authorization": f"Bearer {LATE_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "content": post_text,
        "profileId": LATE_PROFILE_ID,  # <-- The important change
        "mediaItems": [{"type": "video", "source": "url", "url": media_url}],
    }

    if scheduled_for:
        payload["scheduledFor"] = scheduled_for
        payload["timezone"] = timezone or LATE_TIMEZONE
        payload["publishNow"] = False
    else:
        payload["publishNow"] = True if publish_now is None else publish_now

    logger.info(
        "[Late API] POST %s payload=%s headers=%s",
        LATE_POST_ENDPOINT,
        payload,
        headers,
    )
    response = requests.post(LATE_POST_ENDPOINT, headers=headers, json=payload)
    logger.info(
        "[Late API] Response status=%s body=%s headers=%s",
        response.status_code,
        response.text,
        dict(response.headers),
    )

    try:
        data = response.json()
    except Exception:
        raise RuntimeError(
            f"Late returned non-JSON response: HTTP {response.status_code}. {response.text}"
        )

    if response.status_code >= 400:
        raise RuntimeError(
            f"Late API error (HTTP {response.status_code}): {json.dumps(data, indent=2)}"
        )

    return data


@log_call(logger)
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Post a Nextcloud-hosted video to ALL accounts via Late."
    )
    parser.add_argument(
        "--share_url",
        help="Public Nextcloud share URL (e.g., https://cloud.example.com/s/ID)",
    )
    parser.add_argument("--text", "-t", default="", help="Text to include in the post.")
    parser.add_argument(
        "--scheduled_for",
        help="Schedule time in format YYYY-MM-DDTHH:MM:SS (use timezone flag).",
    )
    parser.add_argument(
        "--timezone",
        default=LATE_TIMEZONE,
        help=f"Timezone name for scheduled posts (default: {LATE_TIMEZONE}).",
    )

    args = parser.parse_args()

    logger.info("Original Nextcloud URL: %s", args.share_url)
    logger.info(
        "Derived download URL: %s",
        build_nextcloud_download_url(args.share_url),
    )

    try:
        result = post_video_to_all_accounts(
            nextcloud_share_url=args.share_url,
            post_text=args.text,
            scheduled_for=args.scheduled_for,
            timezone=args.timezone,
        )
        logger.info("Successfully posted via Late to ALL accounts: %s", result)

    except Exception as e:
        logger.error("ERROR posting to Late: %s", e)


if __name__ == "__main__":
    main()
