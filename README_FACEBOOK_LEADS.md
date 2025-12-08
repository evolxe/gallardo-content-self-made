# Facebook Lead Ads Integration

This integration automatically fetches leads from Facebook Lead Ads and sends them to Goal Catcher (Groundhogg).

## Quick Start

1. **Set up environment variables** in `.env`:
   ```bash
   FACEBOOK_ACCESS_TOKEN=your_token
   FACEBOOK_FORM_IDS=form_id_1,form_id_2
   GROUNDHOGG_API_KEY=your_key
   GROUNDHOGG_API_SECRET=your_secret
   GROUNDHOGG_BASE_URL=https://your-site.com
   ```

2. **Configure field mapping** in `mappings/fbToGoalCatcher.json`

3. **Set up cron job** to run every 5 minutes:
   ```bash
   */5 * * * * /path/to/runFacebookLeads.sh
   ```

## What Gets Built

✅ **Facebook Client** (`services/facebook/leads.py`)
   - `getForms()` - Fetch all lead generation forms
   - `fetchLeads(formId)` - Fetch leads for a form
   - `normalizeLeadData()` - Normalize Facebook lead format

✅ **Qualification Layer** (`services/facebook/qualification.py`)
   - Filters duplicates
   - Validates email is not empty
   - Blocks blacklisted domains
   - Checks required fields

✅ **Processing Pipeline** (`services/facebook/processor.py`)
   - Maps Facebook fields to Goal Catcher fields
   - Sends leads to Goal Catcher via Groundhogg API
   - Applies tags and funnels

✅ **Logging System** (`services/facebook/logger.py`)
   - Stores lead received timestamp
   - Stores lead processed timestamp
   - Tracks success/errors

✅ **Cron Job** (`process_facebook_leads.py` + `runFacebookLeads.sh`)
   - Runs every 5 minutes
   - Processes new leads automatically

## File Structure

```
services/facebook/
├── __init__.py
├── leads.py          # Facebook Graph API client
├── qualification.py  # Lead filtering/validation
├── processor.py      # Main processing pipeline
└── logger.py         # Processing logs

mappings/
└── fbToGoalCatcher.json  # Field mapping configuration

process_facebook_leads.py  # Main cron job entry point
runFacebookLeads.sh        # Cron job wrapper script
```

## Documentation

See `docs/facebook_leads_setup.md` for detailed setup instructions.

## Testing

Run manually to test:
```bash
python process_facebook_leads.py
```

Check logs:
```bash
tail -f logs/facebook_leads.jsonl
```

## Done When

✅ A new Facebook lead automatically appears inside Goal Catcher

The integration is complete and ready to use!

