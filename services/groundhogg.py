#!/usr/bin/env python3
"""
Groundhogg REST API Client

Complete Python client for interacting with the Groundhogg REST API, including:
- Authentication with API key and signature generation
- HTTP client with retry logic and credential caching
- Contact management functions (create, update, tag, add to funnel, notes, fields)
"""

import hashlib
import hmac
import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

from config import BASE_DIR, get_env
from log_utils import attach_log_streams, get_logger, log_call

attach_log_streams("groundhogg")
logger = get_logger("gallardo.groundhogg")


# ============================================================================
# Authentication
# ============================================================================

class GroundhoggAuth:
    """
    Handles authentication for Groundhogg REST API requests.
    
    Groundhogg uses WordPress REST API authentication with:
    - API Key (public identifier)
    - API Secret (used for signature generation)
    - Base URL (WordPress site URL)
    
    Authentication is done via headers:
    - X-Groundhogg-Auth: API Key
    - X-Groundhogg-Signature: HMAC-SHA256 signature of the request
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        """
        Initialize Groundhogg authentication.
        
        Args:
            api_key: Groundhogg API key (or read from GROUNDHOGG_API_KEY env var)
            api_secret: Groundhogg API secret (or read from GROUNDHOGG_API_SECRET env var)
            base_url: WordPress site base URL (or read from GROUNDHOGG_BASE_URL env var)
        """
        self.api_key = api_key or get_env("GROUNDHOGG_API_KEY", required=False, default="")
        self.api_secret = api_secret or get_env("GROUNDHOGG_API_SECRET", required=False, default="")
        self.base_url = (base_url or get_env("GROUNDHOGG_BASE_URL", required=False, default="")).rstrip("/")
        
        if not self.api_key:
            logger.warning("GROUNDHOGG_API_KEY not set - authentication will fail")
        if not self.api_secret:
            logger.warning("GROUNDHOGG_API_SECRET not set - authentication will fail")
        if not self.base_url:
            logger.warning("GROUNDHOGG_BASE_URL not set - API calls will fail")

    def generate_signature(
        self,
        method: str,
        path: str,
        body: Optional[str] = None,
        timestamp: Optional[int] = None,
    ) -> str:
        """
        Generate HMAC-SHA256 signature for Groundhogg API request.
        
        The signature is generated from:
        - HTTP method (GET, POST, PUT, PATCH, DELETE)
        - Request path (e.g., /wp-json/gh/v3/contacts)
        - Request body (if present, JSON stringified)
        - Timestamp (Unix timestamp)
        
        Args:
            method: HTTP method (uppercase)
            path: API endpoint path
            body: Request body as string (JSON) or None
            timestamp: Unix timestamp (defaults to current time)
            
        Returns:
            HMAC-SHA256 signature as hexadecimal string
        """
        if not self.api_secret:
            raise ValueError("API secret is required to generate signature")
        
        timestamp = timestamp or int(time.time())
        
        # Normalize path (remove leading/trailing slashes, ensure it starts with /)
        path = "/" + path.lstrip("/")
        
        # Build signature string
        # Format: METHOD|PATH|BODY|TIMESTAMP
        body_str = body if body else ""
        signature_string = f"{method.upper()}|{path}|{body_str}|{timestamp}"
        
        logger.debug(
            "Generating signature for: method=%s path=%s body_len=%d timestamp=%d",
            method,
            path,
            len(body_str),
            timestamp,
        )
        
        # Generate HMAC-SHA256 signature
        signature = hmac.new(
            self.api_secret.encode("utf-8"),
            signature_string.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        
        logger.debug("Generated signature: %s", signature[:16] + "...")
        
        return signature

    def get_auth_headers(
        self,
        method: str,
        path: str,
        body: Optional[Dict] = None,
        timestamp: Optional[int] = None,
    ) -> Dict[str, str]:
        """
        Generate authentication headers for Groundhogg API request.
        
        Args:
            method: HTTP method
            path: API endpoint path
            body: Request body as dict (will be JSON stringified)
            timestamp: Unix timestamp (defaults to current time)
            
        Returns:
            Dictionary with authentication headers:
            - X-Groundhogg-Auth: API key
            - X-Groundhogg-Signature: HMAC signature
            - X-Groundhogg-Timestamp: Unix timestamp
        """
        if not self.api_key:
            raise ValueError("API key is required for authentication")
        
        timestamp = timestamp or int(time.time())
        
        # Convert body to JSON string if provided
        body_str = None
        if body is not None:
            body_str = json.dumps(body, sort_keys=True, separators=(",", ":"))
        
        # Generate signature
        signature = self.generate_signature(method, path, body_str, timestamp)
        
        headers = {
            "X-Groundhogg-Auth": self.api_key,
            "X-Groundhogg-Signature": signature,
            "X-Groundhogg-Timestamp": str(timestamp),
            "Content-Type": "application/json",
        }
        
        logger.debug(
            "Generated auth headers: key=%s timestamp=%d signature=%s...",
            self.api_key[:8] + "...",
            timestamp,
            signature[:16] + "...",
        )
        
        return headers

    def is_configured(self) -> bool:
        """Check if authentication is properly configured."""
        return bool(self.api_key and self.api_secret and self.base_url)


# ============================================================================
# Credential Caching
# ============================================================================

class CredentialCache:
    """
    Local credential cache for storing and refreshing authentication tokens.
    
    Stores credentials in a JSON file in the project root.
    """

    def __init__(self, cache_file: Optional[Path] = None):
        """
        Initialize credential cache.
        
        Args:
            cache_file: Path to cache file (defaults to .groundhogg_cache.json in project root)
        """
        self.cache_file = cache_file or (BASE_DIR / ".groundhogg_cache.json")
        self._cache: Dict[str, Any] = {}
        self._load_cache()

    def _load_cache(self) -> None:
        """Load cache from file if it exists."""
        if self.cache_file.exists():
            try:
                with open(self.cache_file, "r", encoding="utf-8") as f:
                    self._cache = json.load(f)
                logger.debug("Loaded credential cache from %s", self.cache_file)
            except Exception as e:
                logger.warning("Failed to load credential cache: %s", e)
                self._cache = {}

    def _save_cache(self) -> None:
        """Save cache to file."""
        try:
            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump(self._cache, f, indent=2)
            logger.debug("Saved credential cache to %s", self.cache_file)
        except Exception as e:
            logger.warning("Failed to save credential cache: %s", e)

    def get(self, key: str, default: Any = None) -> Any:
        """Get value from cache."""
        return self._cache.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Set value in cache and save to file."""
        self._cache[key] = value
        self._save_cache()

    def clear(self) -> None:
        """Clear all cached values."""
        self._cache = {}
        if self.cache_file.exists():
            try:
                self.cache_file.unlink()
                logger.debug("Cleared credential cache file")
            except Exception as e:
                logger.warning("Failed to delete cache file: %s", e)


# ============================================================================
# HTTP Client
# ============================================================================

class GroundhoggClient:
    """
    HTTP client for Groundhogg REST API with retry logic and credential caching.
    """

    def __init__(
        self,
        auth: Optional[GroundhoggAuth] = None,
        base_url: Optional[str] = None,
        timeout: int = 30,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        cache: Optional[CredentialCache] = None,
    ):
        """
        Initialize Groundhogg API client.
        
        Args:
            auth: GroundhoggAuth instance (creates new one if not provided)
            base_url: Base URL for API (overrides auth.base_url if provided)
            timeout: Request timeout in seconds
            max_retries: Maximum number of retry attempts for failed requests
            retry_delay: Delay between retries in seconds
            cache: CredentialCache instance (creates new one if not provided)
        """
        self.auth = auth or GroundhoggAuth()
        self.base_url = base_url or self.auth.base_url
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.cache = cache or CredentialCache()
        
        # Session for connection pooling
        self.session = requests.Session()
        
        logger.info(
            "Initialized Groundhogg client: base_url=%s timeout=%d max_retries=%d",
            self.base_url,
            self.timeout,
            self.max_retries,
        )

    def _build_url(self, path: str) -> str:
        """Build full URL from path."""
        # Ensure path starts with /
        path = "/" + path.lstrip("/")
        # Ensure base_url doesn't end with /
        base = self.base_url.rstrip("/")
        return f"{base}{path}"

    def _should_retry(self, response: requests.Response, attempt: int) -> bool:
        """
        Determine if a request should be retried.
        
        Retries on:
        - Network errors (connection timeout, DNS failure, etc.)
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
        Handle authentication errors by clearing cached credentials.
        
        Args:
            response: Response object with 401 status
        """
        logger.warning("Authentication error (401) - clearing cached credentials")
        # Clear any cached tokens/credentials
        self.cache.clear()
        # Note: For Groundhogg, we use API key/secret, not tokens
        # But we clear cache in case we add token-based auth in the future

    @log_call(logger)
    def request(
        self,
        method: str,
        path: str,
        params: Optional[Dict] = None,
        data: Optional[Dict] = None,
        json_data: Optional[Dict] = None,
        headers: Optional[Dict] = None,
    ) -> requests.Response:
        """
        Make HTTP request to Groundhogg API with retry logic.
        
        Args:
            method: HTTP method (GET, POST, PUT, PATCH, DELETE)
            path: API endpoint path (e.g., /wp-json/gh/v3/contacts)
            params: URL query parameters
            data: Form data (not typically used with JSON API)
            json_data: JSON request body
            headers: Additional headers (auth headers are added automatically)
            
        Returns:
            Response object
            
        Raises:
            requests.RequestException: If request fails after all retries
        """
        url = self._build_url(path)
        
        # Use json_data if provided, otherwise data
        body = json_data if json_data is not None else data
        
        # Get authentication headers
        try:
            auth_headers = self.auth.get_auth_headers(method, path, body)
        except Exception as e:
            logger.error("Failed to generate auth headers: %s", e)
            raise
        
        # Merge with additional headers
        request_headers = {**auth_headers, **(headers or {})}
        
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
                    data=data,
                    headers=request_headers,
                    timeout=self.timeout,
                )
                
                logger.debug(
                    "Response: status=%d headers=%s",
                    response.status_code,
                    dict(response.headers),
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

    def get(self, path: str, params: Optional[Dict] = None, **kwargs) -> requests.Response:
        """Make GET request."""
        return self.request("GET", path, params=params, **kwargs)

    def post(self, path: str, json_data: Optional[Dict] = None, **kwargs) -> requests.Response:
        """Make POST request."""
        return self.request("POST", path, json_data=json_data, **kwargs)

    def put(self, path: str, json_data: Optional[Dict] = None, **kwargs) -> requests.Response:
        """Make PUT request."""
        return self.request("PUT", path, json_data=json_data, **kwargs)

    def patch(self, path: str, json_data: Optional[Dict] = None, **kwargs) -> requests.Response:
        """Make PATCH request."""
        return self.request("PATCH", path, json_data=json_data, **kwargs)

    def delete(self, path: str, **kwargs) -> requests.Response:
        """Make DELETE request."""
        return self.request("DELETE", path, **kwargs)

    def close(self) -> None:
        """Close the session."""
        self.session.close()
        logger.debug("Closed Groundhogg client session")

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()


# ============================================================================
# Contact Management Functions
# ============================================================================

# Global client instance (lazy initialization)
_client: Optional[GroundhoggClient] = None


def get_client() -> GroundhoggClient:
    """Get or create global Groundhogg client instance."""
    global _client
    if _client is None:
        _client = GroundhoggClient()
    return _client


def set_client(client: GroundhoggClient) -> None:
    """Set the global client instance (useful for testing)."""
    global _client
    _client = client


@log_call(logger)
def create_contact(
    email: str,
    first_name: Optional[str] = None,
    last_name: Optional[str] = None,
    phone: Optional[str] = None,
    owner_id: Optional[int] = None,
    tags: Optional[List[int]] = None,
    custom_fields: Optional[Dict[str, Any]] = None,
    client: Optional[GroundhoggClient] = None,
) -> Dict[str, Any]:
    """
    Create a new contact in Groundhogg.
    
    Endpoint: POST /wp-json/gh/v3/contacts
    
    Args:
        email: Contact email address (required)
        first_name: First name
        last_name: Last name
        phone: Phone number
        owner_id: Owner/assignee ID
        tags: List of tag IDs to apply
        custom_fields: Dictionary of custom field values
        client: GroundhoggClient instance (uses global client if not provided)
        
    Returns:
        Contact data dictionary
        
    Raises:
        requests.RequestException: If API request fails
    """
    if not email:
        raise ValueError("Email is required to create a contact")
    
    client = client or get_client()
    
    payload: Dict[str, Any] = {
        "email": email,
    }
    
    if first_name:
        payload["first_name"] = first_name
    if last_name:
        payload["last_name"] = last_name
    if phone:
        payload["phone"] = phone
    if owner_id:
        payload["owner_id"] = owner_id
    if tags:
        payload["tags"] = tags
    if custom_fields:
        payload.update(custom_fields)
    
    logger.info("Creating contact: email=%s", email)
    
    response = client.post("/wp-json/gh/v3/contacts", json_data=payload)
    result = response.json()
    
    logger.info("Contact created: id=%s email=%s", result.get("id"), email)
    
    return result


@log_call(logger)
def update_contact(
    contact_id: int,
    email: Optional[str] = None,
    first_name: Optional[str] = None,
    last_name: Optional[str] = None,
    phone: Optional[str] = None,
    owner_id: Optional[int] = None,
    custom_fields: Optional[Dict[str, Any]] = None,
    client: Optional[GroundhoggClient] = None,
) -> Dict[str, Any]:
    """
    Update an existing contact in Groundhogg.
    
    Endpoint: PUT /wp-json/gh/v3/contacts/{id}
    
    Args:
        contact_id: Contact ID
        email: New email address
        first_name: First name
        last_name: Last name
        phone: Phone number
        owner_id: Owner/assignee ID
        custom_fields: Dictionary of custom field values to update
        client: GroundhoggClient instance (uses global client if not provided)
        
    Returns:
        Updated contact data dictionary
        
    Raises:
        requests.RequestException: If API request fails
    """
    client = client or get_client()
    
    payload: Dict[str, Any] = {}
    
    if email:
        payload["email"] = email
    if first_name:
        payload["first_name"] = first_name
    if last_name:
        payload["last_name"] = last_name
    if phone:
        payload["phone"] = phone
    if owner_id:
        payload["owner_id"] = owner_id
    if custom_fields:
        payload.update(custom_fields)
    
    if not payload:
        raise ValueError("At least one field must be provided to update")
    
    logger.info("Updating contact: id=%d", contact_id)
    
    response = client.put(
        f"/wp-json/gh/v3/contacts/{contact_id}",
        json_data=payload,
    )
    result = response.json()
    
    logger.info("Contact updated: id=%d", contact_id)
    
    return result


@log_call(logger)
def tag_contact(
    contact_id: int,
    tag_ids: List[int],
    client: Optional[GroundhoggClient] = None,
) -> Dict[str, Any]:
    """
    Apply tags to a contact.
    
    Endpoint: PUT /wp-json/gh/v3/contacts/apply_tags
    
    Args:
        contact_id: Contact ID
        tag_ids: List of tag IDs to apply
        client: GroundhoggClient instance (uses global client if not provided)
        
    Returns:
        Response dictionary
        
    Raises:
        requests.RequestException: If API request fails
    """
    if not tag_ids:
        raise ValueError("At least one tag ID must be provided")
    
    client = client or get_client()
    
    payload = {
        "contact_id": contact_id,
        "tags": tag_ids,
    }
    
    logger.info("Applying tags to contact: id=%d tags=%s", contact_id, tag_ids)
    
    response = client.put("/wp-json/gh/v3/contacts/apply_tags", json_data=payload)
    result = response.json()
    
    logger.info("Tags applied to contact: id=%d", contact_id)
    
    return result


@log_call(logger)
def add_contact_to_funnel(
    email: str,
    funnel_id: int,
    step_id: Optional[int] = None,
    client: Optional[GroundhoggClient] = None,
) -> Dict[str, Any]:
    """
    Add a contact to a funnel (trigger funnel step).
    
    Endpoint: POST /wp-json/gh/v3/plugin-api/
    
    This uses the Plugin API REST endpoint to trigger a funnel for a contact.
    
    Args:
        email: Contact email address
        funnel_id: Funnel ID
        step_id: Optional step ID (if not provided, starts at beginning)
        client: GroundhoggClient instance (uses global client if not provided)
        
    Returns:
        Response dictionary
        
    Raises:
        requests.RequestException: If API request fails
    """
    if not email:
        raise ValueError("Email is required")
    
    client = client or get_client()
    
    # Build call_name for funnel trigger
    # Format: funnel_{funnel_id} or funnel_{funnel_id}_{step_id}
    if step_id:
        call_name = f"funnel_{funnel_id}_{step_id}"
    else:
        call_name = f"funnel_{funnel_id}"
    
    payload = {
        "call_name": call_name,
        "email": email,
    }
    
    logger.info(
        "Adding contact to funnel: email=%s funnel_id=%d step_id=%s",
        email,
        funnel_id,
        step_id,
    )
    
    response = client.post("/wp-json/gh/v3/plugin-api/", json_data=payload)
    result = response.json()
    
    logger.info("Contact added to funnel: email=%s funnel_id=%d", email, funnel_id)
    
    return result


@log_call(logger)
def update_contact_notes(
    contact_id: int,
    note_id: Optional[int] = None,
    content: Optional[str] = None,
    note_type: Optional[str] = None,
    client: Optional[GroundhoggClient] = None,
) -> Dict[str, Any]:
    """
    Update contact notes.
    
    Endpoint: PATCH /wp-json/gh/v4/notes/{id} (for updating existing note)
    Endpoint: POST /wp-json/gh/v4/notes (for creating new note)
    
    Args:
        contact_id: Contact ID
        note_id: Note ID (if updating existing note)
        content: Note content
        note_type: Note type (e.g., "note", "call", "meeting")
        client: GroundhoggClient instance (uses global client if not provided)
        
    Returns:
        Note data dictionary
        
    Raises:
        requests.RequestException: If API request fails
    """
    client = client or get_client()
    
    if note_id:
        # Update existing note
        if not content:
            raise ValueError("Content is required to update a note")
        
        payload: Dict[str, Any] = {
            "content": content,
        }
        if note_type:
            payload["note_type"] = note_type
        
        logger.info("Updating note: note_id=%d contact_id=%d", note_id, contact_id)
        
        response = client.patch(f"/wp-json/gh/v4/notes/{note_id}", json_data=payload)
        result = response.json()
        
        logger.info("Note updated: note_id=%d", note_id)
        
    else:
        # Create new note
        if not content:
            raise ValueError("Content is required to create a note")
        
        payload = {
            "contact_id": contact_id,
            "content": content,
        }
        if note_type:
            payload["note_type"] = note_type
        
        logger.info("Creating note for contact: contact_id=%d", contact_id)
        
        response = client.post("/wp-json/gh/v4/notes", json_data=payload)
        result = response.json()
        
        logger.info("Note created: note_id=%s contact_id=%d", result.get("id"), contact_id)
    
    return result


@log_call(logger)
def update_contact_fields(
    contact_id: int,
    fields: Dict[str, Any],
    client: Optional[GroundhoggClient] = None,
) -> Dict[str, Any]:
    """
    Update contact custom fields.
    
    This is a convenience function that calls update_contact() with custom_fields.
    
    Args:
        contact_id: Contact ID
        fields: Dictionary of field names to values
        client: GroundhoggClient instance (uses global client if not provided)
        
    Returns:
        Updated contact data dictionary
        
    Raises:
        requests.RequestException: If API request fails
    """
    if not fields:
        raise ValueError("At least one field must be provided")
    
    return update_contact(contact_id, custom_fields=fields, client=client)


@log_call(logger)
def get_contact(
    contact_id: int,
    client: Optional[GroundhoggClient] = None,
) -> Dict[str, Any]:
    """
    Get contact by ID.
    
    Endpoint: GET /wp-json/gh/v3/contacts/{id}
    
    Args:
        contact_id: Contact ID
        client: GroundhoggClient instance (uses global client if not provided)
        
    Returns:
        Contact data dictionary
        
    Raises:
        requests.RequestException: If API request fails
    """
    client = client or get_client()
    
    logger.info("Getting contact: id=%d", contact_id)
    
    response = client.get(f"/wp-json/gh/v3/contacts/{contact_id}")
    result = response.json()
    
    logger.info("Retrieved contact: id=%d email=%s", contact_id, result.get("email"))
    
    return result


@log_call(logger)
def search_contacts(
    search: Optional[str] = None,
    tags: Optional[List[int]] = None,
    limit: int = 25,
    offset: int = 0,
    client: Optional[GroundhoggClient] = None,
) -> Dict[str, Any]:
    """
    Search for contacts.
    
    Endpoint: GET /wp-json/gh/v3/contacts
    
    Args:
        search: Search query (searches email, name, etc.)
        tags: Filter by tag IDs
        limit: Number of results to return
        offset: Pagination offset
        client: GroundhoggClient instance (uses global client if not provided)
        
    Returns:
        Response dictionary with contacts list
        
    Raises:
        requests.RequestException: If API request fails
    """
    client = client or get_client()
    
    params: Dict[str, Any] = {
        "limit": limit,
        "offset": offset,
    }
    
    if search:
        params["search"] = search
    if tags:
        params["tags"] = ",".join(map(str, tags))
    
    logger.info("Searching contacts: search=%s tags=%s limit=%d", search, tags, limit)
    
    response = client.get("/wp-json/gh/v3/contacts", params=params)
    result = response.json()
    
    contacts = result.get("contacts", [])
    logger.info("Found %d contacts", len(contacts))
    
    return result

