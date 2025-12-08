#!/usr/bin/env python3
"""
Facebook Lead Processing Logger

Stores lead processing logs with:
- Lead received timestamp
- Lead processed timestamp
- Lead success / errors
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from config import BASE_DIR
from log_utils import attach_log_streams, get_logger

attach_log_streams("facebook_logger")
logger = get_logger("gallardo.facebook_logger")


class LeadProcessingLogger:
    """
    Logger for Facebook lead processing operations.
    """
    
    def __init__(self, log_file: Optional[Path] = None):
        """
        Initialize lead processing logger.
        
        Args:
            log_file: Path to log file (defaults to logs/facebook_leads.jsonl)
        """
        if log_file is None:
            log_dir = BASE_DIR / "logs"
            log_dir.mkdir(exist_ok=True)
            log_file = log_dir / "facebook_leads.jsonl"
        
        self.log_file = log_file
        logger.info("Initialized lead processing logger: %s", self.log_file)
    
    def log_lead_processing(self, result: Dict[str, Any]) -> None:
        """
        Log a lead processing result.
        
        Args:
            result: Processing result dictionary with:
                - lead_id: Facebook lead ID
                - form_id: Form ID
                - received_timestamp: When lead was received
                - processed_timestamp: When lead was processed
                - status: success/rejected/error
                - error: Error message if failed
                - goal_catcher_contact_id: Contact ID in Goal Catcher
        """
        try:
            # Ensure log file exists
            self.log_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Append to JSONL file (one JSON object per line)
            with open(self.log_file, "a", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False)
                f.write("\n")
            
            logger.debug("Logged lead processing: %s", result.get("lead_id", "unknown"))
            
        except Exception as e:
            logger.error("Failed to log lead processing: %s", e, exc_info=True)
    
    def get_recent_logs(
        self,
        limit: int = 100,
        since: Optional[datetime] = None,
        status: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get recent processing logs.
        
        Args:
            limit: Maximum number of logs to return
            since: Only return logs since this datetime
            status: Filter by status (success/rejected/error)
            
        Returns:
            List of log entries
        """
        if not self.log_file.exists():
            return []
        
        logs = []
        try:
            with open(self.log_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    
                    try:
                        entry = json.loads(line)
                        
                        # Filter by status
                        if status and entry.get("status") != status:
                            continue
                        
                        # Filter by timestamp
                        if since:
                            processed_time_str = entry.get("processed_timestamp")
                            if processed_time_str:
                                processed_time = datetime.fromisoformat(processed_time_str)
                                if processed_time < since:
                                    continue
                        
                        logs.append(entry)
                        
                    except json.JSONDecodeError:
                        logger.warning("Invalid JSON in log file: %s", line[:100])
                        continue
            
            # Return most recent first
            logs.reverse()
            return logs[:limit]
            
        except Exception as e:
            logger.error("Failed to read logs: %s", e, exc_info=True)
            return []
    
    def get_statistics(
        self,
        since: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Get processing statistics.
        
        Args:
            since: Only count logs since this datetime
            
        Returns:
            Statistics dictionary
        """
        logs = self.get_recent_logs(limit=10000, since=since)
        
        total = len(logs)
        success = sum(1 for log in logs if log.get("status") == "success")
        rejected = sum(1 for log in logs if log.get("status") == "rejected")
        errors = sum(1 for log in logs if log.get("status") == "error")
        
        return {
            "total": total,
            "success": success,
            "rejected": rejected,
            "errors": errors,
            "success_rate": (success / total * 100) if total > 0 else 0,
        }


# Global logger instance
_lead_logger: Optional[LeadProcessingLogger] = None


def get_lead_logger() -> LeadProcessingLogger:
    """Get or create global lead processing logger instance."""
    global _lead_logger
    if _lead_logger is None:
        _lead_logger = LeadProcessingLogger()
    return _lead_logger

