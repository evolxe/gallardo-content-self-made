import requests
import sys

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
    webhook_url = "https://hook.us1.make.com/va1z9eix6ymbw51x8quz1qgaifspuomn"

    result = send_nextcloud_video_url_to_webhook(video_url, webhook_url)
    print(result)


