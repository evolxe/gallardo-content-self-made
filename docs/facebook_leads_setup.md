# Facebook Lead Ads Integration Setup

This document explains how to set up the Facebook Lead Ads integration that automatically sends leads to Goal Catcher (Groundhogg).

## Overview

The integration consists of:
1. **Facebook Client** (`services/facebook/leads.py`) - Fetches forms and leads from Facebook Graph API
2. **Qualification Layer** (`services/facebook/qualification.py`) - Filters out invalid leads
3. **Processing Pipeline** (`services/facebook/processor.py`) - Maps and sends leads to Goal Catcher
4. **Logging System** (`services/facebook/logger.py`) - Tracks all processing operations
5. **Cron Job** (`process_facebook_leads.py` + `runFacebookLeads.sh`) - Runs every 5 minutes

## Prerequisites

1. Facebook App with Lead Ads API access
2. Facebook Page with Lead Generation Forms
3. Groundhogg (Goal Catcher) API credentials
4. Python 3.7+ with required dependencies

## Setup Steps

### 1. Facebook App Configuration

1. Go to [Facebook Developers](https://developers.facebook.com/)
2. Create or select an app
3. Add the following permissions:
   - `leads_retrieval` - Required to fetch leads
   - `pages_read_engagement` - Required to access page forms
4. Generate an access token:
   - For testing: Use Graph API Explorer
   - For production: Use a Page Access Token (long-lived, ~60 days)

### 2. Environment Variables

Add the following to your `.env` file:

```bash
# Facebook API Credentials
FACEBOOK_ACCESS_TOKEN=your_access_token_here
FACEBOOK_APP_ID=your_app_id_here
FACEBOOK_APP_SECRET=your_app_secret_here
FACEBOOK_PAGE_ID=your_page_id_here  # Optional, defaults to "me"
FACEBOOK_FORM_IDS=form_id_1,form_id_2,form_id_3  # Comma-separated list

# Groundhogg (Goal Catcher) Credentials
GROUNDHOGG_API_KEY=your_api_key_here
GROUNDHOGG_API_SECRET=your_api_secret_here
GROUNDHOGG_BASE_URL=https://your-site.com
```

### 3. Field Mapping Configuration

Edit `mappings/fbToGoalCatcher.json` to map Facebook fields to Goal Catcher fields:

```json
{
  "field_mappings": {
    "email": "email",
    "first_name": "first_name",
    "last_name": "last_name",
    "phone": "phone"
  },
  "required_fields": ["email"],
  "default_tags": ["Facebook Lead"],
  "default_funnel_id": null
}
```

### 4. Blacklisted Domains (Optional)

Create `config/blacklisted_domains.json` to block specific email domains:

```json
{
  "domains": [
    "example.com",
    "test.com",
    "fake.com"
  ]
}
```

### 5. Set Up Cron Job

#### Linux/macOS

1. Make the script executable:
   ```bash
   chmod +x runFacebookLeads.sh
   ```

2. Add to crontab (runs every 5 minutes):
   ```bash
   crontab -e
   ```
   
   Add this line:
   ```
   */5 * * * * /path/to/project/runFacebookLeads.sh >> /path/to/project/logs/facebook_cron.log 2>&1
   ```

#### Windows (Task Scheduler)

1. Open Task Scheduler
2. Create Basic Task
3. Set trigger to "Daily" → "Repeat task every" → 5 minutes
4. Action: Start a program
   - Program: `C:\path\to\python.exe`
   - Arguments: `C:\path\to\project\process_facebook_leads.py`
   - Start in: `C:\path\to\project`

## How It Works

1. **Cron Job Triggers** (`runFacebookLeads.sh`)
   - Activates Python virtual environment
   - Runs `process_facebook_leads.py`

2. **Lead Fetching** (`services/facebook/leads.py`)
   - Calls `getForms()` to get all lead generation forms
   - Calls `fetchLeads(formId)` to get new leads since last run
   - Normalizes lead data with `normalizeLeadData()`

3. **Qualification** (`services/facebook/qualification.py`)
   - Checks for duplicates (tracks processed lead IDs)
   - Validates email is not empty
   - Checks email domain is not blacklisted
   - Verifies required fields are present

4. **Field Mapping** (`mappings/fbToGoalCatcher.json`)
   - Maps Facebook field names to Goal Catcher field names
   - Handles custom fields

5. **Send to Goal Catcher** (`services/groundhogg.py`)
   - Creates contact in Groundhogg
   - Applies default tags
   - Adds to funnel (if configured)

6. **Logging** (`services/facebook/logger.py`)
   - Logs all processing results to `logs/facebook_leads.jsonl`
   - Tracks: received timestamp, processed timestamp, status, errors

## Monitoring

### View Recent Logs

```python
from services.facebook.logger import get_lead_logger

logger = get_lead_logger()
recent_logs = logger.get_recent_logs(limit=50)
for log in recent_logs:
    print(f"{log['lead_id']}: {log['status']} - {log.get('error', '')}")
```

### View Statistics

```python
from services.facebook.logger import get_lead_logger
from datetime import datetime, timedelta

logger = get_lead_logger()
since = datetime.now() - timedelta(days=7)
stats = logger.get_statistics(since=since)
print(f"Total: {stats['total']}, Success: {stats['success']}, Success Rate: {stats['success_rate']:.1f}%")
```

### Log Files

- `logs/facebook_leads.jsonl` - Processing logs (JSONL format)
- `logs/facebook_leads_error_*.log` - Error logs (created on failures)
- `.facebook_processed_leads.json` - Tracks processed lead IDs (for deduplication)
- `.facebook_last_processed.json` - Last processing timestamp

## Troubleshooting

### No Leads Being Processed

1. Check access token is valid:
   ```bash
   curl "https://graph.facebook.com/v18.0/me?access_token=YOUR_TOKEN"
   ```

2. Verify form IDs are correct:
   ```python
   from services.facebook.leads import get_client
   client = get_client()
   forms = client.getForms()
   print([f["id"] for f in forms])
   ```

3. Check logs for errors:
   ```bash
   tail -f logs/facebook_leads.jsonl
   ```

### Access Token Expired

The system will attempt to refresh tokens automatically. If that fails:
1. Generate a new access token from Facebook
2. Update `FACEBOOK_ACCESS_TOKEN` in `.env`
3. Restart the cron job

### Leads Not Appearing in Goal Catcher

1. Check Groundhogg API credentials
2. Verify field mapping in `mappings/fbToGoalCatcher.json`
3. Check qualification logs - leads might be rejected
4. Review error logs in `logs/facebook_leads_error_*.log`

## API Permissions Required

- `leads_retrieval` - Read lead generation forms and leads
- `pages_read_engagement` - Access page information
- `pages_show_list` - List pages (if using page access token)

## Rate Limits

Facebook Graph API has rate limits:
- 200 calls per hour per user (default)
- 4800 calls per hour per app (with app review)

The integration handles rate limiting with exponential backoff retries.

## Security Notes

- Never commit `.env` file to version control
- Store access tokens securely
- Use long-lived page access tokens for production
- Regularly rotate API secrets

