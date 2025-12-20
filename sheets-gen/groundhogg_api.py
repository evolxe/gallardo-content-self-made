#!/usr/bin/env python3
"""
Groundhogg Goals Catcher API Integration

This module provides functions to authenticate and interact with the Groundhogg REST API.
Supports both API Key authentication and WordPress Application Password authentication.
"""

import base64
import json
import logging
from typing import Optional, Dict, Any

import requests

from config import get_env
from log_utils import attach_log_streams, get_logger, log_call

# ------------------------------------------------------------
# Configuration
# ------------------------------------------------------------

# Groundhogg API Base URL
GROUNDHOGG_BASE_URL = get_env(
    "GROUNDHOGG_BASE_URL",
    required=False,
    default=""
).rstrip("/")

# Authentication Method 1: API Keys (Recommended)
GROUNDHOGG_TOKEN = get_env("GROUNDHOGG_TOKEN", required=False, default="")
GROUNDHOGG_PUBLIC_KEY = get_env("GROUNDHOGG_PUBLIC_KEY", required=False, default="")

# Authentication Method 2: WordPress Application Password
GROUNDHOGG_WP_USERNAME = get_env("GROUNDHOGG_WP_USERNAME", required=False, default="")
GROUNDHOGG_WP_APP_PASSWORD = get_env("GROUNDHOGG_WP_APP_PASSWORD", required=False, default="")

attach_log_streams("groundhogg_api")
logger = get_logger("gallardo.groundhogg_api")


# ------------------------------------------------------------
# Authentication Helpers
# ------------------------------------------------------------


def get_auth_headers() -> Dict[str, str]:
    """
    Get authentication headers based on available credentials.
    
    Priority:
    1. Groundhogg API Keys (if both token and public_key are set)
    2. WordPress Application Password (if username and app_password are set)
    
    Returns:
        Dictionary with authentication headers
        
    Raises:
        RuntimeError: If no valid authentication method is configured
    """
    headers = {"Content-Type": "application/json"}
    
    # Method 1: Groundhogg API Keys
    if GROUNDHOGG_TOKEN and GROUNDHOGG_PUBLIC_KEY:
        headers["gh-token"] = GROUNDHOGG_TOKEN
        headers["gh-public-key"] = GROUNDHOGG_PUBLIC_KEY
        logger.info("Using Groundhogg API Key authentication")
        return headers
    
    # Method 2: WordPress Application Password
    if GROUNDHOGG_WP_USERNAME and GROUNDHOGG_WP_APP_PASSWORD:
        credentials = f"{GROUNDHOGG_WP_USERNAME}:{GROUNDHOGG_WP_APP_PASSWORD}"
        encoded_credentials = base64.b64encode(credentials.encode()).decode()
        headers["Authorization"] = f"Basic {encoded_credentials}"
        logger.info("Using WordPress Application Password authentication")
        return headers
    
    raise RuntimeError(
        "No Groundhogg authentication configured. "
        "Set either (GROUNDHOGG_TOKEN + GROUNDHOGG_PUBLIC_KEY) "
        "or (GROUNDHOGG_WP_USERNAME + GROUNDHOGG_WP_APP_PASSWORD) in your .env file."
    )


def build_api_url(endpoint: str) -> str:
    """
    Build the full API URL from a relative endpoint.
    
    Args:
        endpoint: Relative endpoint path (e.g., "/goals" or "goals")
        
    Returns:
        Full API URL
        
    Raises:
        RuntimeError: If GROUNDHOGG_BASE_URL is not configured
    """
    if not GROUNDHOGG_BASE_URL:
        raise RuntimeError(
            "GROUNDHOGG_BASE_URL not configured. Set it in your .env file."
        )
    
    # Ensure endpoint starts with /
    if not endpoint.startswith("/"):
        endpoint = "/" + endpoint
    
    # Remove leading /wp-json/gh/v3 if present (to avoid duplication)
    endpoint = endpoint.replace("/wp-json/gh/v3", "")
    
    # Build full URL
    base_url = GROUNDHOGG_BASE_URL.rstrip("/")
    if not base_url.endswith("/wp-json/gh/v3"):
        base_url = f"{base_url}/wp-json/gh/v3"
    
    return f"{base_url}{endpoint}"


# ------------------------------------------------------------
# API Request Functions
# ------------------------------------------------------------


@log_call(logger)
def groundhogg_request(
    method: str,
    endpoint: str,
    data: Optional[Dict[str, Any]] = None,
    params: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Make an authenticated request to the Groundhogg API.
    
    Args:
        method: HTTP method (GET, POST, PUT, DELETE, etc.)
        endpoint: API endpoint (e.g., "/goals", "/contacts")
        data: Request body data (for POST/PUT requests)
        params: Query parameters (for GET requests)
        
    Returns:
        JSON response as a dictionary
        
    Raises:
        RuntimeError: If the API request fails
    """
    url = build_api_url(endpoint)
    headers = get_auth_headers()
    
    logger.info(
        "[Groundhogg API] %s %s params=%s data=%s",
        method,
        url,
        params,
        data,
    )
    
    response = requests.request(
        method=method,
        url=url,
        headers=headers,
        json=data,
        params=params,
    )
    
    logger.info(
        "[Groundhogg API] Response status=%s body=%s",
        response.status_code,
        response.text[:500],  # Log first 500 chars to avoid huge logs
    )
    
    # Handle non-JSON responses
    try:
        response_data = response.json()
    except json.JSONDecodeError:
        raise RuntimeError(
            f"Groundhogg API returned non-JSON response: "
            f"HTTP {response.status_code}. {response.text[:200]}"
        )
    
    # Handle errors
    if response.status_code >= 400:
        error_msg = response_data.get("message", "Unknown error")
        raise RuntimeError(
            f"Groundhogg API error (HTTP {response.status_code}): {error_msg}. "
            f"Response: {json.dumps(response_data, indent=2)}"
        )
    
    return response_data


# ------------------------------------------------------------
# Convenience Functions for Common Operations
# ------------------------------------------------------------


@log_call(logger)
def get_goals(params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Get goals from Groundhogg.
    
    Args:
        params: Optional query parameters (e.g., {"per_page": 10, "page": 1})
        
    Returns:
        API response containing goals
    """
    return groundhogg_request("GET", "/goals", params=params)


@log_call(logger)
def get_goal(goal_id: int) -> Dict[str, Any]:
    """
    Get a specific goal by ID.
    
    Args:
        goal_id: The goal ID
        
    Returns:
        API response containing the goal
    """
    return groundhogg_request("GET", f"/goals/{goal_id}")


@log_call(logger)
def create_goal(goal_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create a new goal.
    
    Args:
        goal_data: Goal data dictionary
        
    Returns:
        API response containing the created goal
    """
    return groundhogg_request("POST", "/goals", data=goal_data)


@log_call(logger)
def update_goal(goal_id: int, goal_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Update an existing goal.
    
    Args:
        goal_id: The goal ID to update
        goal_data: Updated goal data dictionary
        
    Returns:
        API response containing the updated goal
    """
    return groundhogg_request("PUT", f"/goals/{goal_id}", data=goal_data)


@log_call(logger)
def delete_goal(goal_id: int) -> Dict[str, Any]:
    """
    Delete a goal.
    
    Args:
        goal_id: The goal ID to delete
        
    Returns:
        API response
    """
    return groundhogg_request("DELETE", f"/goals/{goal_id}")


@log_call(logger)
def get_contacts(params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Get contacts from Groundhogg.
    
    Args:
        params: Optional query parameters
        
    Returns:
        API response containing contacts
    """
    return groundhogg_request("GET", "/contacts", params=params)


@log_call(logger)
def get_contact(contact_id: int) -> Dict[str, Any]:
    """
    Get a specific contact by ID.
    
    Args:
        contact_id: The contact ID
        
    Returns:
        API response containing the contact
    """
    return groundhogg_request("GET", f"/contacts/{contact_id}")


# ------------------------------------------------------------
# Test/Example Usage
# ------------------------------------------------------------


def test_authentication() -> bool:
    """
    Test the authentication by making a simple API call.
    
    Returns:
        True if authentication is successful, False otherwise
    """
    try:
        # Try to get goals (or any endpoint that requires auth)
        response = get_goals(params={"per_page": 1})
        logger.info("✓ Authentication successful!")
        return True
    except Exception as e:
        logger.error(f"✗ Authentication failed: {e}")
        return False


if __name__ == "__main__":
    # Example usage
    print("Testing Groundhogg API authentication...")
    
    if test_authentication():
        print("✓ Authentication successful!")
        
        # Example: Get first 5 goals
        print("\nFetching goals...")
        try:
            goals_response = get_goals(params={"per_page": 5})
            print(f"Response: {json.dumps(goals_response, indent=2)}")
        except Exception as e:
            print(f"Error fetching goals: {e}")
    else:
        print("✗ Authentication failed. Check your .env configuration.")

