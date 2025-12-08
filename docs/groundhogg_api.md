# Groundhogg Goals Catcher API Authentication

## Overview
Groundhogg provides a REST API for integrating with Goals Catcher. This document covers the authentication fundamentals.

## Authentication Methods

Groundhogg REST API supports three authentication methods:

### 1. Groundhogg API Keys (Recommended for Server-Side Applications)

**Setup:**
1. Navigate to `Groundhogg > Settings > API` in your WordPress dashboard
2. Generate a new pair of API keys linked to your user account
3. You'll receive:
   - **Token** (`gh-token`)
   - **Public Key** (`gh-public-key`)

**Usage:**
Include these headers in your API requests:
```
gh-token: YOUR_TOKEN
gh-public-key: YOUR_PUBLIC_KEY
```

**Advantages:**
- API keys share the same privileges as the associated user
- Best for server-side applications and scripts
- No need to manage WordPress user credentials

**Example Request:**
```python
import requests

headers = {
    "gh-token": "your_token_here",
    "gh-public-key": "your_public_key_here",
    "Content-Type": "application/json"
}

response = requests.get(
    "https://your-site.com/wp-json/gh/v3/goals",
    headers=headers
)
```

---

### 2. WordPress Application Passwords

**Setup:**
1. Go to your WordPress user profile
2. Scroll to the "Application Passwords" section
3. Generate a new application password
4. You'll receive a password (save it immediately, it won't be shown again)

**Usage:**
Use HTTP Basic Authentication with base64 encoding:
```
Authorization: Basic base64(username:password)
```

Where:
- `username` = Your WordPress username
- `password` = The generated application password (not your regular WordPress password)

**Advantages:**
- Leverages WordPress's built-in authentication system
- Can be revoked individually
- Good for integrations that already use WordPress authentication

**Example Request:**
```python
import requests
import base64

username = "your_wordpress_username"
app_password = "your_application_password"

credentials = f"{username}:{app_password}"
encoded_credentials = base64.b64encode(credentials.encode()).decode()

headers = {
    "Authorization": f"Basic {encoded_credentials}",
    "Content-Type": "application/json"
}

response = requests.get(
    "https://your-site.com/wp-json/gh/v3/goals",
    headers=headers
)
```

---

### 3. WordPress REST Nonce (For Frontend JavaScript)

**Setup:**
- Generate a nonce using WordPress functions (typically `wp_create_nonce()`)
- Pass the nonce to your frontend script
- Include it in API requests

**Usage:**
```
X-WP-Nonce: YOUR_NONCE
```

**Advantages:**
- Suitable for frontend JavaScript applications
- Works with WordPress's built-in security

**Note:** This method is primarily for frontend applications. For Python/server-side scripts, use Method 1 or 2.

---

## API Base URL

The Groundhogg REST API base URL follows this pattern:
```
https://your-wordpress-site.com/wp-json/gh/v3/
```

Common endpoints:
- Goals: `/wp-json/gh/v3/goals`
- Contacts: `/wp-json/gh/v3/contacts`
- Tags: `/wp-json/gh/v3/tags`
- Funnels: `/wp-json/gh/v3/funnels`

## Environment Variables

Store your credentials securely in your `.env` file:

```env
# Groundhogg API Keys (Method 1)
GROUNDHOGG_TOKEN=your_token_here
GROUNDHOGG_PUBLIC_KEY=your_public_key_here
GROUNDHOGG_BASE_URL=https://your-site.com

# OR WordPress Application Password (Method 2)
GROUNDHOGG_WP_USERNAME=your_username
GROUNDHOGG_WP_APP_PASSWORD=your_app_password
GROUNDHOGG_BASE_URL=https://your-site.com
```

## Error Handling

Common authentication errors:
- **401 Unauthorized**: Invalid credentials or missing headers
- **403 Forbidden**: Valid credentials but insufficient permissions
- **404 Not Found**: Invalid API endpoint URL

Always check the response status code and handle errors appropriately.

## Security Best Practices

1. **Never commit credentials to version control** - Use `.env` files and add them to `.gitignore`
2. **Use API Keys over Application Passwords** when possible for server-side scripts
3. **Rotate credentials regularly** - Regenerate API keys periodically
4. **Use HTTPS** - Always make API requests over HTTPS
5. **Limit permissions** - Use a WordPress user with minimal required permissions

## References

- [Groundhogg REST API Documentation](https://help.groundhogg.io/article/146-rest-authentication)
- [WordPress REST API Handbook](https://developer.wordpress.org/rest-api/)

