#!/usr/bin/env python3
"""
Facebook Lead Processing Pipeline

Main pipeline that:
1. Fetches new leads from Facebook
2. Qualifies leads
3. Maps fields to Goal Catcher format
4. Sends to Goal Catcher via Groundhogg
5. Logs all operations
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from config import BASE_DIR, get_env
from log_utils import attach_log_streams, get_logger, log_call
from services.facebook.leads import get_client
from services.facebook.logger import get_lead_logger
from services.facebook.qualification import get_qualifier
from services.groundhogg import create_contact, tag_contact, add_contact_to_funnel

attach_log_streams("facebook_processor")
logger = get_logger("gallardo.facebook_processor")


# ============================================================================
# Field Mapping
# ============================================================================

def load_field_mapping() -> Dict[str, Any]:
    """
    Load field mapping from fbToGoalCatcher.json.
    
    Returns:
        Mapping configuration dictionary
    """
    mapping_file = BASE_DIR / "mappings" / "fbToGoalCatcher.json"
    
    if not mapping_file.exists():
        logger.warning("Mapping file not found: %s, using defaults", mapping_file)
        return {
            "field_mappings": {
                "email": "email",
                "first_name": "first_name",
                "last_name": "last_name",
                "phone": "phone",
            },
            "required_fields": ["email"],
            "default_tags": ["Facebook Lead"],
        }
    
    try:
        with open(mapping_file, "r", encoding="utf-8") as f:
            mapping = json.load(f)
        logger.debug("Loaded field mapping from %s", mapping_file)
        return mapping
    except Exception as e:
        logger.error("Failed to load field mapping: %s", e)
        raise


def map_lead_to_goal_catcher(
    lead_data: Dict[str, Any],
    mapping_config: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Map Facebook lead data to Goal Catcher (Groundhogg) format.
    
    Args:
        lead_data: Normalized Facebook lead data
        mapping_config: Mapping configuration from fbToGoalCatcher.json
        
    Returns:
        Mapped lead data for Goal Catcher
    """
    field_mappings = mapping_config.get("field_mappings", {})
    custom_mappings = mapping_config.get("custom_field_mappings", {})
    
    mapped = {}
    
    # Map standard fields
    for fb_field, gc_field in field_mappings.items():
        if fb_field in lead_data:
            value = lead_data[fb_field]
            if value:  # Only include non-empty values
                mapped[gc_field] = value
    
    # Map custom fields
    for fb_field, gc_field in custom_mappings.items():
        if fb_field in lead_data:
            value = lead_data[fb_field]
            if value:
                mapped[gc_field] = value
    
    # Add source metadata
    mapped["source"] = "Facebook Lead Ads"
    if "facebook_lead_id" in lead_data:
        mapped["source_id"] = lead_data["facebook_lead_id"]
    
    logger.debug("Mapped lead data: %s", mapped.get("email", "no email"))
    return mapped


# ============================================================================
# Lead Processing
# ============================================================================

class LeadProcessor:
    """
    Main lead processing pipeline.
    """
    
    def __init__(
        self,
        form_ids: Optional[List[str]] = None,
        last_processed_file: Optional[Path] = None,
    ):
        """
        Initialize lead processor.
        
        Args:
            form_ids: List of Facebook form IDs to process (or read from env)
            last_processed_file: Path to file storing last processed timestamp
        """
        self.form_ids = form_ids or self._load_form_ids()
        self.last_processed_file = last_processed_file or (
            BASE_DIR / ".facebook_last_processed.json"
        )
        self.mapping_config = load_field_mapping()
        self.qualifier = get_qualifier()
        self.client = get_client()
        self.lead_logger = get_lead_logger()
        
        logger.info(
            "Initialized lead processor: form_ids=%s",
            self.form_ids,
        )
    
    def _load_form_ids(self) -> List[str]:
        """Load form IDs from environment variable."""
        form_ids_str = get_env("FACEBOOK_FORM_IDS", required=False, default="")
        if form_ids_str:
            return [fid.strip() for fid in form_ids_str.split(",") if fid.strip()]
        return []
    
    def _get_last_processed_time(self) -> Optional[datetime]:
        """Get the last processed timestamp."""
        if not self.last_processed_file.exists():
            return None
        
        try:
            with open(self.last_processed_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                timestamp_str = data.get("last_processed")
                if timestamp_str:
                    return datetime.fromisoformat(timestamp_str)
        except Exception as e:
            logger.warning("Failed to load last processed time: %s", e)
        
        return None
    
    def _save_last_processed_time(self, timestamp: datetime) -> None:
        """Save the last processed timestamp."""
        try:
            self.last_processed_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.last_processed_file, "w", encoding="utf-8") as f:
                json.dump(
                    {"last_processed": timestamp.isoformat()},
                    f,
                    indent=2,
                )
            logger.debug("Saved last processed time: %s", timestamp.isoformat())
        except Exception as e:
            logger.warning("Failed to save last processed time: %s", e)
    
    @log_call(logger)
    def process_lead(
        self,
        lead_data: Dict[str, Any],
        form_id: str,
    ) -> Dict[str, Any]:
        """
        Process a single lead: qualify, map, and send to Goal Catcher.
        
        Args:
            lead_data: Normalized Facebook lead data
            form_id: Facebook form ID
            
        Returns:
            Processing result dictionary with status and details
        """
        lead_id = lead_data.get("facebook_lead_id", "unknown")
        received_time = datetime.now()
        
        result = {
            "lead_id": lead_id,
            "form_id": form_id,
            "received_timestamp": received_time.isoformat(),
            "processed_timestamp": None,
            "status": "pending",
            "error": None,
            "goal_catcher_contact_id": None,
        }
        
        try:
            # Step 1: Qualify lead
            is_qualified, reason = self.qualifier.qualify(lead_data)
            if not is_qualified:
                result["status"] = "rejected"
                result["error"] = reason
                result["processed_timestamp"] = datetime.now().isoformat()
                logger.info("Lead %s rejected: %s", lead_id, reason)
                return result
            
            # Step 2: Map to Goal Catcher format
            mapped_data = map_lead_to_goal_catcher(lead_data, self.mapping_config)
            
            # Step 3: Send to Goal Catcher (Groundhogg)
            email = mapped_data.get("email")
            first_name = mapped_data.get("first_name")
            last_name = mapped_data.get("last_name")
            phone = mapped_data.get("phone")
            
            # Extract custom fields (everything except standard fields)
            standard_fields = {"email", "first_name", "last_name", "phone", "source", "source_id"}
            custom_fields = {
                k: v for k, v in mapped_data.items() if k not in standard_fields
            }
            
            # Create contact in Groundhogg
            contact = create_contact(
                email=email,
                first_name=first_name,
                last_name=last_name,
                phone=phone,
                custom_fields=custom_fields if custom_fields else None,
            )
            
            contact_id = contact.get("id")
            result["goal_catcher_contact_id"] = contact_id
            
            # Apply default tags if configured
            default_tags = self.mapping_config.get("default_tags", [])
            if default_tags and contact_id:
                # Convert tag names/IDs to list of integers (tag IDs)
                tag_ids = []
                for tag in default_tags:
                    if isinstance(tag, int):
                        tag_ids.append(tag)
                    elif isinstance(tag, str) and tag.isdigit():
                        tag_ids.append(int(tag))
                    # If it's a string name, skip (requires tag ID lookup)
                    # User should configure tag IDs in mapping file
                
                if tag_ids:
                    try:
                        tag_contact(contact_id=contact_id, tag_ids=tag_ids)
                        logger.debug("Applied tags to contact: %s", tag_ids)
                    except Exception as e:
                        logger.warning("Failed to apply tags: %s", e)
            
            # Add to funnel if configured
            funnel_id = self.mapping_config.get("default_funnel_id")
            if funnel_id:
                add_contact_to_funnel(email=email, funnel_id=funnel_id)
                logger.debug("Added contact to funnel: %d", funnel_id)
            
            # Mark as processed
            self.qualifier.mark_as_processed(lead_id)
            
            result["status"] = "success"
            result["processed_timestamp"] = datetime.now().isoformat()
            logger.info(
                "Lead %s processed successfully: contact_id=%s",
                lead_id,
                contact_id,
            )
            
        except Exception as e:
            result["status"] = "error"
            result["error"] = str(e)
            result["processed_timestamp"] = datetime.now().isoformat()
            logger.error(
                "Failed to process lead %s: %s",
                lead_id,
                e,
                exc_info=True,
            )
        
        # Log the result
        self.lead_logger.log_lead_processing(result)
        
        return result
    
    @log_call(logger)
    def process_all_forms(self, since: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """
        Process all leads from all configured forms.
        
        Args:
            since: Optional datetime to fetch leads since (defaults to last processed time)
            
        Returns:
            List of processing results
        """
        if not self.form_ids:
            logger.warning("No form IDs configured, skipping processing")
            return []
        
        # Use last processed time if not specified
        if since is None:
            since = self._get_last_processed_time()
            if since:
                # Add 1 second to avoid processing the same lead twice
                since = since + timedelta(seconds=1)
                logger.info("Fetching leads since: %s", since.isoformat())
            else:
                logger.info("No last processed time found, fetching all leads")
        
        all_results = []
        current_time = datetime.now()
        
        for form_id in self.form_ids:
            try:
                logger.info("Processing form: %s", form_id)
                
                # Fetch leads
                leads = self.client.fetchLeads(form_id, since=since)
                logger.info("Fetched %d leads for form %s", len(leads), form_id)
                
                # Process each lead
                for lead in leads:
                    # Normalize lead data
                    normalized = self.client.normalizeLeadData(lead)
                    
                    # Process lead
                    result = self.process_lead(normalized, form_id)
                    all_results.append(result)
                
            except Exception as e:
                logger.error(
                    "Failed to process form %s: %s",
                    form_id,
                    e,
                    exc_info=True,
                )
                all_results.append({
                    "form_id": form_id,
                    "status": "error",
                    "error": str(e),
                    "processed_timestamp": datetime.now().isoformat(),
                })
        
        # Save last processed time
        self._save_last_processed_time(current_time)
        
        # Log summary
        success_count = sum(1 for r in all_results if r.get("status") == "success")
        rejected_count = sum(1 for r in all_results if r.get("status") == "rejected")
        error_count = sum(1 for r in all_results if r.get("status") == "error")
        
        logger.info(
            "Processing complete: success=%d rejected=%d errors=%d total=%d",
            success_count,
            rejected_count,
            error_count,
            len(all_results),
        )
        
        return all_results


# Global processor instance
_processor: Optional[LeadProcessor] = None


def get_processor() -> LeadProcessor:
    """Get or create global lead processor instance."""
    global _processor
    if _processor is None:
        _processor = LeadProcessor()
    return _processor


@log_call(logger)
def process_facebook_leads() -> List[Dict[str, Any]]:
    """
    Main entry point for processing Facebook leads.
    
    This function is called by the cron job.
    
    Returns:
        List of processing results
    """
    logger.info("Starting Facebook leads processing pipeline")
    processor = get_processor()
    results = processor.process_all_forms()
    logger.info("Facebook leads processing pipeline completed")
    return results


if __name__ == "__main__":
    # For testing
    results = process_facebook_leads()
    print(f"Processed {len(results)} leads")
    for result in results:
        print(f"  - {result.get('lead_id', 'unknown')}: {result.get('status')}")

