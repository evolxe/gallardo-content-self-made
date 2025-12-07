#!/usr/bin/env python3
"""
Facebook Lead Qualification Layer

Filters and validates leads before sending to Goal Catcher:
- Duplicates
- Empty emails
- Blacklisted domains
- Missing required fields
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from config import BASE_DIR
from log_utils import attach_log_streams, get_logger

attach_log_streams("facebook_qualification")
logger = get_logger("gallardo.facebook_qualification")


class LeadQualifier:
    """
    Qualification layer for Facebook leads.
    """
    
    def __init__(
        self,
        blacklisted_domains: Optional[List[str]] = None,
        required_fields: Optional[List[str]] = None,
        processed_leads_file: Optional[Path] = None,
    ):
        """
        Initialize lead qualifier.
        
        Args:
            blacklisted_domains: List of email domains to reject
            required_fields: List of required field names
            processed_leads_file: Path to file storing processed lead IDs
        """
        self.blacklisted_domains = blacklisted_domains or []
        self.required_fields = required_fields or ["email"]
        
        # File to track processed leads (for deduplication)
        self.processed_leads_file = processed_leads_file or (
            BASE_DIR / ".facebook_processed_leads.json"
        )
        self._processed_lead_ids: Set[str] = set()
        self._load_processed_leads()
        
        # Load blacklisted domains from config if available
        self._load_blacklisted_domains()
    
    def _load_blacklisted_domains(self) -> None:
        """Load blacklisted domains from config file if it exists."""
        blacklist_file = BASE_DIR / "config" / "blacklisted_domains.json"
        if blacklist_file.exists():
            try:
                with open(blacklist_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.blacklisted_domains.extend(data.get("domains", []))
                logger.info("Loaded %d blacklisted domains from config", len(self.blacklisted_domains))
            except Exception as e:
                logger.warning("Failed to load blacklisted domains: %s", e)
    
    def _load_processed_leads(self) -> None:
        """Load set of processed lead IDs from file."""
        if self.processed_leads_file.exists():
            try:
                with open(self.processed_leads_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._processed_lead_ids = set(data.get("lead_ids", []))
                logger.debug("Loaded %d processed lead IDs", len(self._processed_lead_ids))
            except Exception as e:
                logger.warning("Failed to load processed leads: %s", e)
                self._processed_lead_ids = set()
    
    def _save_processed_leads(self) -> None:
        """Save set of processed lead IDs to file."""
        try:
            self.processed_leads_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.processed_leads_file, "w", encoding="utf-8") as f:
                json.dump({"lead_ids": list(self._processed_lead_ids)}, f, indent=2)
            logger.debug("Saved %d processed lead IDs", len(self._processed_lead_ids))
        except Exception as e:
            logger.warning("Failed to save processed leads: %s", e)
    
    def is_duplicate(self, lead_id: str) -> bool:
        """
        Check if a lead has already been processed.
        
        Args:
            lead_id: Facebook lead ID
            
        Returns:
            True if lead is a duplicate
        """
        is_dup = lead_id in self._processed_lead_ids
        if is_dup:
            logger.debug("Lead %s is a duplicate", lead_id)
        return is_dup
    
    def has_empty_email(self, lead_data: Dict[str, Any]) -> bool:
        """
        Check if lead has an empty or missing email.
        
        Args:
            lead_data: Normalized lead data dictionary
            
        Returns:
            True if email is empty or missing
        """
        email = lead_data.get("email", "").strip()
        is_empty = not email
        if is_empty:
            logger.debug("Lead %s has empty email", lead_data.get("facebook_lead_id", "unknown"))
        return is_empty
    
    def is_blacklisted_domain(self, email: str) -> bool:
        """
        Check if email domain is blacklisted.
        
        Args:
            email: Email address
            
        Returns:
            True if domain is blacklisted
        """
        if not email or "@" not in email:
            return False
        
        domain = email.split("@")[1].lower()
        is_blacklisted = domain in [d.lower() for d in self.blacklisted_domains]
        
        if is_blacklisted:
            logger.debug("Email %s has blacklisted domain: %s", email, domain)
        
        return is_blacklisted
    
    def has_missing_required_fields(self, lead_data: Dict[str, Any]) -> bool:
        """
        Check if lead is missing required fields.
        
        Args:
            lead_data: Normalized lead data dictionary
            
        Returns:
            True if required fields are missing
        """
        missing = []
        for field in self.required_fields:
            value = lead_data.get(field, "").strip()
            if not value:
                missing.append(field)
        
        if missing:
            logger.debug(
                "Lead %s missing required fields: %s",
                lead_data.get("facebook_lead_id", "unknown"),
                missing,
            )
        
        return len(missing) > 0
    
    def qualify(self, lead_data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """
        Qualify a lead by running all validation checks.
        
        Args:
            lead_data: Normalized lead data dictionary
            
        Returns:
            Tuple of (is_qualified, reason)
            - is_qualified: True if lead passes all checks
            - reason: Error message if not qualified, None if qualified
        """
        lead_id = lead_data.get("facebook_lead_id", "")
        
        # Check duplicate
        if self.is_duplicate(lead_id):
            return False, "Duplicate lead"
        
        # Check empty email
        if self.has_empty_email(lead_data):
            return False, "Empty email"
        
        email = lead_data.get("email", "").strip()
        
        # Check blacklisted domain
        if self.is_blacklisted_domain(email):
            return False, f"Blacklisted domain: {email.split('@')[1]}"
        
        # Check required fields
        if self.has_missing_required_fields(lead_data):
            missing = [f for f in self.required_fields if not lead_data.get(f, "").strip()]
            return False, f"Missing required fields: {', '.join(missing)}"
        
        # All checks passed
        logger.info("Lead %s qualified successfully", lead_id)
        return True, None
    
    def mark_as_processed(self, lead_id: str) -> None:
        """
        Mark a lead as processed (for deduplication).
        
        Args:
            lead_id: Facebook lead ID
        """
        self._processed_lead_ids.add(lead_id)
        self._save_processed_leads()
        logger.debug("Marked lead %s as processed", lead_id)


# Global qualifier instance
_qualifier: Optional[LeadQualifier] = None


def get_qualifier() -> LeadQualifier:
    """Get or create global lead qualifier instance."""
    global _qualifier
    if _qualifier is None:
        _qualifier = LeadQualifier()
    return _qualifier

