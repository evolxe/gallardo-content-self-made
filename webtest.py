import requests

from config import get_env


def send_nextcloud_video_url_to_webhook(video_url, webhook_url):
    payload = {"video_url": video_url}
    try:
        response = requests.post(webhook_url, json=payload)
        response.raise_for_status()  # Raise error for bad responses
        return f"Success: {response.status_code}"
    except requests.exceptions.RequestException as e:
        return f"Error: {e}"


def main():
    video_url = get_env("TEST_VIDEO_URL")
    webhook_url = get_env("WEBTEST_WEBHOOK_URL")

    result = send_nextcloud_video_url_to_webhook(video_url, webhook_url)
    print(result)


if __name__ == "__main__":
    main()
