"""
URL validation and normalization utilities for Nextcloud share links.

This module provides functions to validate and normalize Nextcloud URLs
to ensure consistent format handling across the application.
"""

from urllib.parse import urlparse, urlunparse
from typing import Optional, Tuple


def normalize_nextcloud_url(url: str) -> str:
    """
    Normalize Nextcloud URLs to a standard format.
    
    Accepts various formats and converts to standard: https://cloud.targethouse.dk/s/{ID}/download
    
    Supported input formats:
    - https://cloud.targethouse.dk/s/{ID}
    - https://cloud.targethouse.dk/s/{ID}/download
    - https://cloud.targethouse.dk/s/{ID}/download?path=%2F&files=video.mp4
    - https://cloud.targethouse.dk/f/{ID} (federated shares)
    
    Args:
        url: The URL to normalize
        
    Returns:
        Normalized URL in format: https://cloud.targethouse.dk/s/{ID}/download
        If not a Nextcloud URL, returns the original URL unchanged.
    """
    if not url or not isinstance(url, str):
        return url
    
    url = url.strip().strip('"')
    
    # If already ends with video extension, return as-is (might be direct file link)
    video_exts = (".mp4", ".mov", ".m4v", ".webm", ".avi", ".mpg", ".mpeg", ".mkv")
    if url.lower().endswith(video_exts):
        return url
    
    # Parse URL
    parsed = urlparse(url)
    
    # Handle /s/ public share links
    if "/s/" in parsed.path:
        # Extract share ID (everything after /s/ up to next / or end)
        parts = parsed.path.split("/s/")
        if len(parts) > 1:
            share_part = parts[1].split("/")[0]  # Get share ID (before any /download or path)
            
            # Rebuild as standard format: /s/{ID}/download
            normalized_path = f"/s/{share_part}/download"
            
            # Preserve query params if present (e.g., ?path=%2F&files=video.mp4)
            if parsed.query:
                normalized_url = urlunparse(parsed._replace(path=normalized_path))
            else:
                normalized_url = urlunparse(parsed._replace(path=normalized_path, query="", fragment=""))
            
            return normalized_url
    
    # Handle /f/ federated/private share links
    if "/f/" in parsed.path:
        parts = parsed.path.split("/f/")
        if len(parts) > 1:
            share_part = parts[1].split("/")[0]
            normalized_path = f"/f/{share_part}/download"
            if parsed.query:
                normalized_url = urlunparse(parsed._replace(path=normalized_path))
            else:
                normalized_url = urlunparse(parsed._replace(path=normalized_path, query="", fragment=""))
            return normalized_url
    
    # If not a Nextcloud share link, return as-is (could be external URL or local path)
    return url


def validate_nextcloud_url(url: str) -> Tuple[bool, Optional[str]]:
    """
    Validate Nextcloud URL format.
    
    Checks if the URL is a valid Nextcloud share link format.
    Local file paths are considered valid (they're handled separately).
    
    Args:
        url: The URL to validate
        
    Returns:
        Tuple of (is_valid, error_message)
        - is_valid: True if URL is valid, False otherwise
        - error_message: None if valid, error description if invalid
    """
    if not url or not isinstance(url, str):
        return False, "URL is required and must be a string"
    
    url = url.strip()
    
    # Empty string is invalid
    if not url:
        return False, "URL cannot be empty"
    
    # Check if it's a URL (starts with http)
    if not url.startswith(("http://", "https://")):
        # Could be a local path, that's OK - validation passes
        # (local path validation happens elsewhere)
        return True, None
    
    # Validate Nextcloud share link format
    if "cloud.targethouse.dk" in url:
        if "/s/" not in url and "/f/" not in url:
            return False, (
                "Nextcloud URL must be a share link (format: https://cloud.targethouse.dk/s/... or "
                "https://cloud.targethouse.dk/f/...). "
                "Copy the link from Nextcloud by clicking 'Share' → 'Copy link'. "
                "Do not use internal paths or WebDAV URLs."
            )
        
        # Additional validation: check URL structure
        parsed = urlparse(url)
        if not parsed.scheme in ("http", "https"):
            return False, "URL must use http:// or https:// protocol"
        
        if not parsed.netloc:
            return False, "URL is missing domain name"
    
    # If it's a URL but not Nextcloud, that's OK (could be external video hosting)
    return True, None


def validate_and_normalize_url(url: str) -> Tuple[str, Optional[str]]:
    """
    Validate and normalize a URL in one step.
    
    This is a convenience function that combines validation and normalization.
    
    Args:
        url: The URL to validate and normalize
        
    Returns:
        Tuple of (normalized_url, error_message)
        - normalized_url: The normalized URL (or original if not Nextcloud)
        - error_message: None if valid, error description if invalid
    """
    is_valid, error = validate_nextcloud_url(url)
    
    if not is_valid:
        return url, error
    
    normalized = normalize_nextcloud_url(url)
    return normalized, None


def is_nextcloud_url(url: str) -> bool:
    """
    Check if a URL is a Nextcloud share link.
    
    Args:
        url: The URL to check
        
    Returns:
        True if the URL is a Nextcloud share link, False otherwise
    """
    if not url or not isinstance(url, str):
        return False
    
    url = url.strip()
    
    if not url.startswith(("http://", "https://")):
        return False
    
    return "cloud.targethouse.dk" in url and ("/s/" in url or "/f/" in url)


def extract_share_id(url: str) -> Optional[str]:
    """
    Extract the share ID from a Nextcloud share URL.
    
    Args:
        url: The Nextcloud share URL
        
    Returns:
        The share ID (the part after /s/ or /f/), or None if not found
    """
    if not url or not isinstance(url, str):
        return None
    
    url = url.strip()
    
    # Try /s/ first
    if "/s/" in url:
        parts = url.split("/s/")
        if len(parts) > 1:
            share_id = parts[1].split("/")[0].split("?")[0]  # Remove path and query params
            return share_id
    
    # Try /f/ for federated shares
    if "/f/" in url:
        parts = url.split("/f/")
        if len(parts) > 1:
            share_id = parts[1].split("/")[0].split("?")[0]
            return share_id
    
    return None


def validate_text_color(color: str) -> Tuple[bool, Optional[str], Optional[Tuple[int, int, int]]]:
    """
    Validate text color format and convert to RGB tuple.
    
    Expected format: #RRGGBB (6-digit hex code with # prefix)
    Examples: #FFFFFF, #000000, #FF0000, #00FF00, #0000FF
    
    Args:
        color: The color string to validate (e.g., "#FFFFFF")
        
    Returns:
        Tuple of (is_valid, error_message, rgb_tuple)
        - is_valid: True if color is valid, False otherwise
        - error_message: None if valid, error description if invalid
        - rgb_tuple: (R, G, B) tuple if valid, None if invalid
    """
    if not color or not isinstance(color, str):
        return False, "Text Color is required and must be a string", None
    
    color = color.strip()
    
    # Empty string is OK (will use default)
    if not color:
        return True, None, None
    
    # Must start with #
    if not color.startswith("#"):
        return False, "Text Color must start with '#' (e.g., #FFFFFF)", None
    
    # Must be exactly 7 characters (# + 6 hex digits)
    if len(color) != 7:
        return False, "Text Color must be 6 hex digits after '#' (e.g., #FFFFFF, not #FFF)", None
    
    # Check that remaining 6 characters are valid hex digits
    hex_part = color[1:]
    try:
        # Convert hex to integer to validate
        rgb_int = int(hex_part, 16)
        # Convert to RGB tuple
        r = int(hex_part[0:2], 16)
        g = int(hex_part[2:4], 16)
        b = int(hex_part[4:6], 16)
        return True, None, (r, g, b)
    except ValueError:
        return False, f"Text Color contains invalid hex digits: '{hex_part}'. Use format #RRGGBB (e.g., #FFFFFF)", None


def validate_text_size(size: str) -> Tuple[bool, Optional[str], Optional[int]]:
    """
    Validate text size format and convert to integer pixels.
    
    Expected format: Integer pixels (e.g., "90", "120", "72")
    Valid range: 12-300 pixels (reasonable bounds for video text)
    
    Args:
        size: The text size string to validate (e.g., "90")
        
    Returns:
        Tuple of (is_valid, error_message, size_int)
        - is_valid: True if size is valid, False otherwise
        - error_message: None if valid, error description if invalid
        - size_int: Integer pixel size if valid, None if invalid
    """
    if not size or not isinstance(size, str):
        return True, None, None  # Empty is OK, will use default
    
    size = size.strip()
    
    # Empty string is OK (will use default)
    if not size:
        return True, None, None
    
    # Must be a valid integer
    try:
        size_int = int(size)
    except ValueError:
        return False, f"Text Size must be an integer (e.g., '90', '120'). Got: '{size}'", None
    
    # Validate reasonable bounds (12-300 pixels)
    if size_int < 12:
        return False, f"Text Size must be at least 12 pixels. Got: {size_int}", None
    
    if size_int > 300:
        return False, f"Text Size must be at most 300 pixels. Got: {size_int}", None
    
    return True, None, size_int

