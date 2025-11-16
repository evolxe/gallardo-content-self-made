Quick Start
Here's how to set up profiles and schedule your first post:

1. Create a Profile
# Create a profile to organize your social accounts
```
curl -X POST https://getlate.dev/api/v1/profiles \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Personal Brand",
    "description": "My personal social media accounts",
    "color": "#ffeda0"
  }'
```  

success
```
{"message":"Profile created successfully","profile":{"userId":"69197ba8766ddc0f4c695738","name":"Personal Brand","description":"My personal social media accounts","isDefault":false,"color":"#ffeda0","_id":"6919808587fd7ed7d58952fc","createdAt":"2025-11-16T07:43:01.715Z","updatedAt":"2025-11-16T07:43:01.715Z","__v":0}}
```
2. Connect Social Accounts
# Connect social accounts to your profile (redirects to OAuth)
```
curl "https://getlate.dev/api/v1/connect/twitter?profileId=PROFILE_ID" \
  -H "Authorization: Bearer YOUR_API_KEY"
```  
3. Schedule a Post
# Schedule a post using accounts from your profile
```
curl -X POST https://getlate.dev/api/v1/posts \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "Hello, world! 🌍",
    "scheduledFor": "2024-01-01T12:00:00",
    "timezone": "America/New_York",
    "platforms": [
      {"platform": "twitter", "accountId": "TWITTER_ACCOUNT_ID"},
      {"platform": "linkedin", "accountId": "LINKEDIN_ACCOUNT_ID"},
      {"platform": "threads", "accountId": "THREADS_ACCOUNT_ID"}
    ]
  }'
```
