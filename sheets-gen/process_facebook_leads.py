#!/usr/bin/env python3
"""
Facebook Lead Processing Cron Job

This script processes Facebook leads and sends them to Goal Catcher.
It is designed to be run as a cron job every 5 minutes.

Usage:
    python process_facebook_leads.py

Environment Variables:
    FACEBOOK_ACCESS_TOKEN: Facebook access token
    FACEBOOK_APP_ID: Facebook App ID (optional, for token renewal)
    FACEBOOK_APP_SECRET: Facebook App Secret (optional, for token renewal)
    FACEBOOK_PAGE_ID: Facebook Page ID (optional, defaults to "me")
    FACEBOOK_FORM_IDS: Comma-separated list of form IDs to process
    
    GROUNDHOGG_API_KEY: Groundhogg API key
    GROUNDHOGG_API_SECRET: Groundhogg API secret
    GROUNDHOGG_BASE_URL: Groundhogg base URL
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

from log_utils import attach_log_streams, get_logger, flush_error_log
from services.facebook.logger import get_lead_logger
from services.facebook.processor import process_facebook_leads

attach_log_streams("process_facebook_leads")
logger = get_logger("gallardo.process_facebook_leads")


def main() -> None:
    """Main entry point for cron job."""
    logger.info("=" * 80)
    logger.info("Facebook Lead Processing Cron Job Started")
    logger.info("=" * 80)
    
    try:
        # Process leads
        results = process_facebook_leads()
        
        # Log all results
        lead_logger = get_lead_logger()
        for result in results:
            lead_logger.log_lead_processing(result)
        
        # Get and log statistics
        stats = lead_logger.get_statistics()
        logger.info(
            "Processing Statistics: total=%d success=%d rejected=%d errors=%d success_rate=%.1f%%",
            stats["total"],
            stats["success"],
            stats["rejected"],
            stats["errors"],
            stats["success_rate"],
        )
        
        logger.info("=" * 80)
        logger.info("Facebook Lead Processing Cron Job Completed Successfully")
        logger.info("=" * 80)
        
    except Exception as e:
        logger.error("Fatal error in Facebook lead processing: %s", e, exc_info=True)
        flush_error_log(e)
        sys.exit(1)


if __name__ == "__main__":
    main()

