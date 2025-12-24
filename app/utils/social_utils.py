"""
Utility functions for parsing social profile URLs.
"""

import re
from typing import Optional


def extract_linkedin_id(url: Optional[str]) -> Optional[str]:
    """
    Extract LinkedIn member ID from various LinkedIn URL formats.

    Handles:
    - https://www.linkedin.com/in/john-doe-123456/
    - https://linkedin.com/in/johndoe
    - http://www.linkedin.com/in/john-doe
    - https://www.linkedin.com/in/john-doe?param=value
    - linkedin.com/in/johndoe

    Args:
        url: LinkedIn profile URL

    Returns:
        The LinkedIn member ID (e.g., 'john-doe-123456') or None if invalid
    """
    if not url:
        return None

    url = url.strip()
    if not url:
        return None

    # Pattern to match LinkedIn profile URLs
    # Matches: linkedin.com/in/MEMBER_ID with optional protocol, www, trailing slash, query params
    pattern = r'(?:https?://)?(?:www\.)?linkedin\.com/in/([a-zA-Z0-9\-_%]+)/?(?:\?.*)?$'

    match = re.match(pattern, url, re.IGNORECASE)
    if match:
        # URL decode the ID and return lowercase
        member_id = match.group(1).lower()
        # Remove any URL encoding like %20
        member_id = member_id.replace('%20', '-')
        return member_id

    return None


def normalize_linkedin_url(url: Optional[str]) -> Optional[str]:
    """
    Normalize a LinkedIn URL to a consistent format.

    Converts various formats to: https://www.linkedin.com/in/member-id

    Args:
        url: LinkedIn profile URL in any format

    Returns:
        Normalized LinkedIn URL or None if invalid
    """
    member_id = extract_linkedin_id(url)
    if member_id:
        return f"https://www.linkedin.com/in/{member_id}"
    return None


def extract_twitter_handle(url: Optional[str]) -> Optional[str]:
    """
    Extract Twitter/X handle from URL or handle string.

    Handles:
    - https://twitter.com/johndoe
    - https://x.com/johndoe
    - @johndoe
    - johndoe

    Args:
        url: Twitter URL or handle

    Returns:
        The Twitter handle without @ prefix, or None if invalid
    """
    if not url:
        return None

    url = url.strip()
    if not url:
        return None

    # If it starts with @, just strip it
    if url.startswith('@'):
        return url[1:].lower()

    # Pattern to match Twitter/X URLs
    pattern = r'(?:https?://)?(?:www\.)?(?:twitter|x)\.com/([a-zA-Z0-9_]+)/?(?:\?.*)?$'

    match = re.match(pattern, url, re.IGNORECASE)
    if match:
        return match.group(1).lower()

    # If it's just a plain handle (no @ or URL)
    if re.match(r'^[a-zA-Z0-9_]+$', url):
        return url.lower()

    return None
