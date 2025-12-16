"""
Privacy filter for AI context.

Strips sensitive information (emails, phone numbers) before sending
data to external AI providers. This ensures PII is never exposed
to third-party services.
"""

import re
from typing import Any


# Regex patterns for sensitive data
EMAIL_PATTERN = re.compile(
    r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
)

# Phone patterns (various formats)
PHONE_PATTERNS = [
    # US formats: (123) 456-7890, 123-456-7890, 123.456.7890
    re.compile(r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}'),
    # International: +1 123 456 7890, +44 20 7123 4567
    re.compile(r'\+\d{1,3}[-.\s]?\d{1,4}[-.\s]?\d{1,4}[-.\s]?\d{1,9}'),
    # Simple number sequences that look like phones (7+ digits)
    re.compile(r'\b\d{7,15}\b'),
]

# Placeholder text for redacted content
EMAIL_PLACEHOLDER = "[EMAIL REDACTED]"
PHONE_PLACEHOLDER = "[PHONE REDACTED]"


def strip_emails(text: str) -> str:
    """
    Remove email addresses from text.

    Args:
        text: Input text that may contain emails

    Returns:
        Text with emails replaced by placeholder
    """
    if not text:
        return text
    return EMAIL_PATTERN.sub(EMAIL_PLACEHOLDER, text)


def strip_phone_numbers(text: str) -> str:
    """
    Remove phone numbers from text.

    Args:
        text: Input text that may contain phone numbers

    Returns:
        Text with phone numbers replaced by placeholder
    """
    if not text:
        return text

    result = text
    for pattern in PHONE_PATTERNS:
        result = pattern.sub(PHONE_PLACEHOLDER, result)
    return result


def strip_sensitive_data(text: str) -> str:
    """
    Remove all sensitive data (emails and phone numbers) from text.

    Args:
        text: Input text that may contain sensitive data

    Returns:
        Text with sensitive data replaced by placeholders
    """
    if not text:
        return text

    result = strip_emails(text)
    result = strip_phone_numbers(result)
    return result


def filter_person_for_ai(person_data: dict[str, Any]) -> dict[str, Any]:
    """
    Filter a person dict for AI context, removing sensitive fields.

    Args:
        person_data: Dictionary of person attributes

    Returns:
        Filtered dictionary safe for AI consumption
    """
    # Fields to completely exclude
    excluded_fields = {
        "emails",
        "email",
        "phone_numbers",
        "phone",
        "mobile",
        "work_phone",
        "home_phone",
    }

    # Fields to filter (strip sensitive data from content)
    text_fields = {"notes", "bio", "summary", "description"}

    filtered = {}
    for key, value in person_data.items():
        # Skip excluded fields entirely
        if key.lower() in excluded_fields:
            continue

        # Filter text fields
        if key.lower() in text_fields and isinstance(value, str):
            filtered[key] = strip_sensitive_data(value)
        else:
            filtered[key] = value

    return filtered


def filter_organization_for_ai(org_data: dict[str, Any]) -> dict[str, Any]:
    """
    Filter an organization dict for AI context, removing sensitive fields.

    Args:
        org_data: Dictionary of organization attributes

    Returns:
        Filtered dictionary safe for AI consumption
    """
    # Fields to completely exclude
    excluded_fields = {
        "phone",
        "phone_number",
        "contact_email",
        "email",
    }

    # Fields to filter (strip sensitive data from content)
    text_fields = {"notes", "description", "summary"}

    filtered = {}
    for key, value in org_data.items():
        # Skip excluded fields entirely
        if key.lower() in excluded_fields:
            continue

        # Filter text fields
        if key.lower() in text_fields and isinstance(value, str):
            filtered[key] = strip_sensitive_data(value)
        else:
            filtered[key] = value

    return filtered


def filter_interaction_for_ai(interaction_data: dict[str, Any]) -> dict[str, Any]:
    """
    Filter an interaction dict for AI context.

    Args:
        interaction_data: Dictionary of interaction attributes

    Returns:
        Filtered dictionary safe for AI consumption
    """
    # Fields to filter
    text_fields = {"notes", "summary", "description", "content"}

    filtered = {}
    for key, value in interaction_data.items():
        if key.lower() in text_fields and isinstance(value, str):
            filtered[key] = strip_sensitive_data(value)
        else:
            filtered[key] = value

    return filtered


class PrivacyFilter:
    """
    Privacy filter class for more complex filtering scenarios.

    Provides stateful filtering with tracking of what was redacted.
    """

    def __init__(self):
        self.redaction_count = 0
        self.emails_redacted = 0
        self.phones_redacted = 0

    def filter_text(self, text: str) -> str:
        """
        Filter text and track redactions.

        Args:
            text: Input text

        Returns:
            Filtered text
        """
        if not text:
            return text

        # Count emails before filtering
        email_matches = EMAIL_PATTERN.findall(text)
        self.emails_redacted += len(email_matches)

        # Count phones before filtering
        phone_count = 0
        for pattern in PHONE_PATTERNS:
            phone_count += len(pattern.findall(text))
        self.phones_redacted += phone_count

        self.redaction_count = self.emails_redacted + self.phones_redacted

        return strip_sensitive_data(text)

    def get_stats(self) -> dict[str, int]:
        """
        Get redaction statistics.

        Returns:
            Dictionary with redaction counts
        """
        return {
            "total_redactions": self.redaction_count,
            "emails_redacted": self.emails_redacted,
            "phones_redacted": self.phones_redacted,
        }

    def reset_stats(self) -> None:
        """Reset redaction statistics."""
        self.redaction_count = 0
        self.emails_redacted = 0
        self.phones_redacted = 0
