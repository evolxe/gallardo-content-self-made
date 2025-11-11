import requests

def send_nextcloud_video_url_to_webhook(video_url, webhook_url):
    payload = {"video_url": video_url}
    try:
        response = requests.post(webhook_url, json=payload)
        response.raise_for_status()  # Raise error for bad responses
        return f"Success: {response.status_code}"
    except requests.exceptions.RequestException as e:
        return f"Error: {e}"

# Example usage
video_url = "https://cloud.targethouse.dk/s/G6dkjpKG2RdJmHQ"  # Replace with your Nextcloud shared video URL
webhook_url = "https://hook.eu2.make.com/9ttd549oaqg6dkblhnlgbdq4aj2gocsb"
# webhook_url = "https://hook.us1.make.com/49o94mcv9ewes4cad9qat17d577cg253"

result = send_nextcloud_video_url_to_webhook(video_url, webhook_url)
print(result)


