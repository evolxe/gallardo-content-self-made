import requests
import sys

from config import get_env


def send_nextcloud_video_url_to_webhook(video_url, webhook_url):
    payload = {"video_url": video_url}
    try:
        response = requests.post(webhook_url, json=payload)
        response.raise_for_status()
        return f"Success: {response.status_code}"
    except requests.exceptions.RequestException as e:
        return f"Error: {e}"


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python script.py <video_url>")
        sys.exit(1)

    video_url = sys.argv[1]
    webhook_url = get_env("MAKE_WEBHOOK_URL")

    result = send_nextcloud_video_url_to_webhook(video_url, webhook_url)
    print(result)
