#!/usr/bin/env python3
"""
Facebook Lead Ads Integration Service

This module provides a client for interacting with the Facebook Graph API
to fetch lead generation forms and leads.

Usage:
    from services.facebook.leads import FacebookLeadsClient
    
    client = FacebookLeadsClient()
    forms = client.getForms()
    leads = client.fetchLeads(form_id="123456789")
    normalized = client.normalizeLeadData(lead_data)
"""

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

from config import BASE_DIR, get_env
from log_utils import attach_log_streams, get_logger, log_call

attach_log_streams("facebook_leads")
logger = get_logger("gallardo.facebook_leads")


# ============================================================================
# Facebook Graph API Configuration
# ============================================================================

class FacebookAuth:
    """
    Handles authentication for Facebook Graph API requests.
    
    Facebook uses OAuth 2.0 access tokens for API authentication.
    Access tokens can be:
    - User access tokens (short-lived, ~1-2 hours)
    - Page access tokens (long-lived, ~60 days)
    - App access tokens (for app-level operations)
    """
    
    def __init__(
        self,
        access_token: Optional[str] = None,
        app_id: Optional[str] = None,
        app_secret: Optional[str] = None,
    ):
        """
        Initialize Facebook authentication.
        
        Args:
            access_token: Facebook access token (or read from FACEBOOK_ACCESS_TOKEN env var)
            app_id: Facebook App ID (or read from FACEBOOK_APP_ID env var)
            app_secret: Facebook App Secret (or read from FACEBOOK_APP_SECRET env var)
        """
        self.access_token = access_token or get_env("FACEBOOK_ACCESS_TOKEN", required=False, default="")
        self.app_id = app_id or get_env("FACEBOOK_APP_ID", required=False, default="")
        self.app_secret = app_secret or get_env("FACEBOOK_APP_SECRET", required=False, default="")
        
        if not self.access_token:
            logger.warning("FACEBOOK_ACCESS_TOKEN not set - API calls will fail")
        if not self.app_id:
            logger.warning("FACEBOOK_APP_ID not set - token renewal may fail")
        if not self.app_secret:
            logger.warning("FACEBOOK_APP_SECRET not set - token renewal may fail")
    
    def get_auth_headers(self) -> Dict[str, str]:
        """
        Generate authentication headers for Facebook API request.
        
        Returns:
            Dictionary with Authorization header
        """
        if not self.access_token:
            raise ValueError("Access token is required for authentication")
        
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }
    
    def refresh_access_token(self) -> Optional[str]:
        """
        Refresh the access token using app credentials.
        
        This exchanges a short-lived token for a long-lived token.
        For page access tokens, you need to use the page-specific endpoint.
        
        Returns:
            New access token if successful, None otherwise
        """
        if not self.app_id or not self.app_secret:
            logger.warning("Cannot refresh token: APP_ID or APP_SECRET not set")
            return None
        
        if not self.access_token:
            logger.warning("Cannot refresh token: no access token available")
            return None
        
        try:
            # Exchange short-lived token for long-lived token
            url = "https://graph.facebook.com/v18.0/oauth/access_token"
            params = {
                "grant_type": "fb_exchange_token",
                "client_id": self.app_id,
                "client_secret": self.app_secret,
                "fb_exchange_token": self.access_token,
            }
            
            logger.info("Refreshing Facebook access token...")
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            
            result = response.json()
            new_token = result.get("access_token")
            
            if new_token:
                logger.info("Successfully refreshed access token")
                self.access_token = new_token
                return new_token
            else:
                logger.error("Token refresh response missing access_token")
                return None
                
        except requests.exceptions.RequestException as e:
            logger.error("Failed to refresh access token: %s", e)
            return None
        except Exception as e:
            logger.error("Unexpected error refreshing token: %s", e, exc_info=True)
            return None
    
    def is_configured(self) -> bool:
        """Check if authentication is properly configured."""
        return bool(self.access_token)


# ============================================================================
# Facebook Leads Client
# ============================================================================

class FacebookLeadsClient:
    """
    HTTP client for Facebook Graph API with lead generation form and lead fetching.
    """
    
    GRAPH_API_BASE = "https://graph.facebook.com/v18.0"
    
    def __init__(
        self,
        auth: Optional[FacebookAuth] = None,
        timeout: int = 30,
        max_retries: int = 3,
        retry_delay: float = 1.0,
    ):
        """
        Initialize Facebook Leads API client.
        
        Args:
            auth: FacebookAuth instance (creates new one if not provided)
            timeout: Request timeout in seconds
            max_retries: Maximum number of retry attempts for failed requests
            retry_delay: Delay between retries in seconds
        """
        self.auth = auth or FacebookAuth()
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        
        # Session for connection pooling
        self.session = requests.Session()
        
        logger.info(
            "Initialized Facebook Leads client: timeout=%d max_retries=%d",
            self.timeout,
            self.max_retries,
        )
    
    def _build_url(self, endpoint: str) -> str:
        """Build full Graph API URL from endpoint."""
        endpoint = endpoint.lstrip("/")
        return f"{self.GRAPH_API_BASE}/{endpoint}"
    
    def _should_retry(self, response: Optional[requests.Response], attempt: int) -> bool:
        """
        Determine if a request should be retried.
        
        Retries on:
        - Network errors
        - 5xx server errors
        - 401 Unauthorized (might be token expiration)
        - 429 Too Many Requests (rate limiting)
        
        Args:
            response: Response object (may be None for network errors)
            attempt: Current attempt number (1-indexed)
            
        Returns:
            True if request should be retried
        """
        if attempt >= self.max_retries:
            return False
        
        # Network errors (response is None)
        if response is None:
            return True
        
        status = response.status_code
        
        # Retry on server errors
        if 500 <= status < 600:
            return True
        
        # Retry on rate limiting
        if status == 429:
            return True
        
        # Retry on authentication errors (might be token expiration)
        if status == 401:
            return True
        
        return False
    
    def _handle_auth_error(self, response: requests.Response) -> None:
        """
        Handle authentication errors by attempting token refresh.
        
        Args:
            response: Response object with 401 status
        """
        logger.warning("Authentication error (401) - attempting token refresh")
        self.auth.refresh_access_token()
    
    @log_call(logger)
    def request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict] = None,
        json_data: Optional[Dict] = None,
        headers: Optional[Dict] = None,
    ) -> requests.Response:
        """
        Make HTTP request to Facebook Graph API with retry logic.
        
        Args:
            method: HTTP method (GET, POST, PUT, PATCH, DELETE)
            endpoint: API endpoint (e.g., "me/leadgen_forms")
            params: URL query parameters
            json_data: JSON request body
            headers: Additional headers (auth headers are added automatically)
            
        Returns:
            Response object
            
        Raises:
            requests.RequestException: If request fails after all retries
        """
        url = self._build_url(endpoint)
        
        # Get authentication headers
        try:
            auth_headers = self.auth.get_auth_headers()
        except Exception as e:
            logger.error("Failed to generate auth headers: %s", e)
            raise
        
        # Merge with additional headers
        request_headers = {**auth_headers, **(headers or {})}
        
        # Add access_token to params if not present
        if params is None:
            params = {}
        if "access_token" not in params:
            params["access_token"] = self.auth.access_token
        
        # Retry logic
        last_exception = None
        for attempt in range(1, self.max_retries + 1):
            try:
                logger.debug(
                    "Request attempt %d/%d: %s %s",
                    attempt,
                    self.max_retries,
                    method,
                    url,
                )
                
                response = self.session.request(
                    method=method,
                    url=url,
                    params=params,
                    json=json_data,
                    headers=request_headers,
                    timeout=self.timeout,
                )
                
                logger.debug(
                    "Response: status=%d",
                    response.status_code,
                )
                
                # Check if we should retry
                if self._should_retry(response, attempt):
                    if response.status_code == 401:
                        self._handle_auth_error(response)
                    
                    # Calculate delay (exponential backoff)
                    delay = self.retry_delay * (2 ** (attempt - 1))
                    logger.warning(
                        "Request failed (status=%d), retrying in %.2f seconds (attempt %d/%d)",
                        response.status_code,
                        delay,
                        attempt,
                        self.max_retries,
                    )
                    time.sleep(delay)
                    continue
                
                # Success or non-retryable error
                response.raise_for_status()
                return response
                
            except requests.exceptions.RequestException as e:
                last_exception = e
                logger.warning(
                    "Request exception on attempt %d/%d: %s",
                    attempt,
                    self.max_retries,
                    e,
                )
                
                if not self._should_retry(None, attempt):
                    break
                
                # Exponential backoff
                delay = self.retry_delay * (2 ** (attempt - 1))
                time.sleep(delay)
        
        # All retries exhausted
        logger.error(
            "Request failed after %d attempts: %s",
            self.max_retries,
            last_exception,
        )
        raise last_exception or requests.exceptions.RequestException(
            f"Request failed after {self.max_retries} attempts"
        )
    
    def get(self, endpoint: str, params: Optional[Dict] = None, **kwargs) -> requests.Response:
        """Make GET request."""
        return self.request("GET", endpoint, params=params, **kwargs)
    
    def post(self, endpoint: str, json_data: Optional[Dict] = None, **kwargs) -> requests.Response:
        """Make POST request."""
        return self.request("POST", endpoint, json_data=json_data, **kwargs)
    
    @log_call(logger)
    def getForms(self, page_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Fetch all lead generation forms.
        
        Endpoint: GET /{page-id}/leadgen_forms
        Requires: leads_retrieval permission
        
        Args:
            page_id: Facebook Page ID (or read from FACEBOOK_PAGE_ID env var)
                     If not provided, uses "me" (requires user access token)
            
        Returns:
            List of lead generation form dictionaries
            
        Raises:
            requests.RequestException: If API request fails
        """
        if not page_id:
            page_id = get_env("FACEBOOK_PAGE_ID", required=False, default="me")
        
        logger.info("Fetching lead generation forms for page: %s", page_id)
        
        forms = []
        endpoint = f"{page_id}/leadgen_forms"
        params = {
            "fields": "id,name,status,leads_count,created_time,page_id",
            "limit": 100,  # Maximum allowed by Facebook
        }
        
        # Handle pagination
        while True:
            response = self.get(endpoint, params=params)
            data = response.json()
            
            if "data" in data:
                forms.extend(data["data"])
                logger.debug("Fetched %d forms (total: %d)", len(data["data"]), len(forms))
            
            # Check for next page
            if "paging" in data and "next" in data["paging"]:
                # Extract cursor from next URL
                next_url = data["paging"]["next"]
                # Facebook pagination uses 'after' cursor
                # We'll extract it from the URL or use the cursor directly
                if "after" in data["paging"]["cursors"]:
                    params["after"] = data["paging"]["cursors"]["after"]
                else:
                    break
            else:
                break
        
        logger.info("Fetched %d lead generation forms", len(forms))
        return forms
    
    @log_call(logger)
    def fetchLeads(self, form_id: str, since: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """
        Fetch leads for a specific lead generation form.
        
        Endpoint: GET /{form-id}/leads
        Requires: leads_retrieval permission
        
        Args:
            form_id: Lead generation form ID
            since: Optional datetime to fetch leads since (defaults to all leads)
            
        Returns:
            List of lead dictionaries
            
        Raises:
            requests.RequestException: If API request fails
        """
        if not form_id:
            raise ValueError("Form ID is required")
        
        logger.info("Fetching leads for form: %s", form_id)
        
        leads = []
        endpoint = f"{form_id}/leads"
        params = {
            "fields": "id,created_time,field_data",
            "limit": 100,  # Maximum allowed by Facebook
        }
        
        # Add time filter if provided
        if since:
            params["filtering"] = json.dumps([{
                "field": "time_created",
                "operator": "GREATER_THAN",
                "value": int(since.timestamp()),
            }])
        
        # Handle pagination
        while True:
            response = self.get(endpoint, params=params)
            data = response.json()
            
            if "data" in data:
                leads.extend(data["data"])
                logger.debug("Fetched %d leads (total: %d)", len(data["data"]), len(leads))
            
            # Check for next page
            if "paging" in data and "next" in data["paging"]:
                if "after" in data["paging"]["cursors"]:
                    params["after"] = data["paging"]["cursors"]["after"]
                else:
                    break
            else:
                break
        
        logger.info("Fetched %d leads for form %s", len(leads), form_id)
        return leads
    
    @log_call(logger)
    def normalizeLeadData(self, lead_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize Facebook lead data into a standard format.
        
        Facebook leads come with field_data array containing name/value pairs.
        This function extracts and normalizes the data into a flat dictionary.
        
        Args:
            lead_data: Raw lead data from Facebook API
            
        Returns:
            Normalized lead dictionary with standard field names
        """
        if not lead_data:
            raise ValueError("Lead data is required")
        
        normalized = {
            "facebook_lead_id": lead_data.get("id", ""),
            "created_time": lead_data.get("created_time", ""),
        }
        
        # Extract field_data
        field_data = lead_data.get("field_data", [])
        for field in field_data:
            field_name = field.get("name", "").lower()
            field_value = field.get("values", [])
            
            # Get first value if array, otherwise use as-is
            if isinstance(field_value, list) and len(field_value) > 0:
                value = field_value[0]
            else:
                value = field_value if not isinstance(field_value, list) else ""
            
            # Normalize common field names
            if field_name in ["email", "e-mail", "email_address"]:
                normalized["email"] = str(value).strip()
            elif field_name in ["first_name", "firstname", "fname"]:
                normalized["first_name"] = str(value).strip()
            elif field_name in ["last_name", "lastname", "lname"]:
                normalized["last_name"] = str(value).strip()
            elif field_name in ["phone", "phone_number", "mobile", "telephone"]:
                normalized["phone"] = str(value).strip()
            elif field_name in ["full_name", "name"]:
                # Try to split full name
                name_parts = str(value).strip().split(maxsplit=1)
                if len(name_parts) == 2:
                    normalized["first_name"] = name_parts[0]
                    normalized["last_name"] = name_parts[1]
                else:
                    normalized["first_name"] = str(value).strip()
            else:
                # Store other fields with original name
                normalized[field_name] = str(value).strip()
        
        logger.debug("Normalized lead data: %s", normalized.get("email", "no email"))
        return normalized
    
    def close(self) -> None:
        """Close the session."""
        self.session.close()
        logger.debug("Closed Facebook Leads client session")
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()


# Global client instance (lazy initialization)
_client: Optional[FacebookLeadsClient] = None


def get_client() -> FacebookLeadsClient:
    """Get or create global Facebook Leads client instance."""
    global _client
    if _client is None:
        _client = FacebookLeadsClient()
    return _client


def set_client(client: FacebookLeadsClient) -> None:
    """Set the global client instance (useful for testing)."""
    global _client
    _client = client

