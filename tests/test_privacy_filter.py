"""
Tests for AI privacy filter.
"""

import pytest

from app.services.ai.privacy_filter import (
    strip_emails,
    strip_phone_numbers,
    strip_sensitive_data,
    filter_person_for_ai,
    filter_organization_for_ai,
    PrivacyFilter,
    EMAIL_PLACEHOLDER,
    PHONE_PLACEHOLDER,
)


class TestStripEmails:
    """Test email stripping functionality."""

    def test_strip_simple_email(self):
        """Test stripping a simple email."""
        text = "Contact me at john@example.com for more info."
        result = strip_emails(text)
        assert "john@example.com" not in result
        assert EMAIL_PLACEHOLDER in result

    def test_strip_multiple_emails(self):
        """Test stripping multiple emails."""
        text = "Email john@example.com or jane@company.org"
        result = strip_emails(text)
        assert "john@example.com" not in result
        assert "jane@company.org" not in result
        assert result.count(EMAIL_PLACEHOLDER) == 2

    def test_strip_email_with_subdomain(self):
        """Test stripping email with subdomain."""
        text = "Contact support@mail.company.co.uk"
        result = strip_emails(text)
        assert "support@mail.company.co.uk" not in result
        assert EMAIL_PLACEHOLDER in result

    def test_strip_email_with_plus(self):
        """Test stripping email with plus addressing."""
        text = "Use john+newsletter@example.com"
        result = strip_emails(text)
        assert "john+newsletter@example.com" not in result

    def test_preserve_non_email_text(self):
        """Test that non-email text is preserved."""
        text = "The meeting is at 3pm tomorrow."
        result = strip_emails(text)
        assert result == text

    def test_empty_string(self):
        """Test with empty string."""
        assert strip_emails("") == ""

    def test_none_input(self):
        """Test with None input."""
        assert strip_emails(None) is None


class TestStripPhoneNumbers:
    """Test phone number stripping functionality."""

    def test_strip_us_format_parentheses(self):
        """Test US format with parentheses."""
        text = "Call me at (555) 123-4567"
        result = strip_phone_numbers(text)
        assert "(555) 123-4567" not in result
        assert PHONE_PLACEHOLDER in result

    def test_strip_us_format_dashes(self):
        """Test US format with dashes."""
        text = "Phone: 555-123-4567"
        result = strip_phone_numbers(text)
        assert "555-123-4567" not in result

    def test_strip_us_format_dots(self):
        """Test US format with dots."""
        text = "Phone: 555.123.4567"
        result = strip_phone_numbers(text)
        assert "555.123.4567" not in result

    def test_strip_international_format(self):
        """Test international format."""
        text = "Call +1 555 123 4567"
        result = strip_phone_numbers(text)
        assert "+1 555 123 4567" not in result

    def test_strip_uk_format(self):
        """Test UK format."""
        text = "Phone: +44 20 7123 4567"
        result = strip_phone_numbers(text)
        assert "+44 20 7123 4567" not in result

    def test_preserve_short_numbers(self):
        """Test that short numbers are preserved."""
        text = "He scored 100 points."
        result = strip_phone_numbers(text)
        assert "100" in result

    def test_empty_string(self):
        """Test with empty string."""
        assert strip_phone_numbers("") == ""


class TestStripSensitiveData:
    """Test combined sensitive data stripping."""

    def test_strip_both_email_and_phone(self):
        """Test stripping both email and phone."""
        text = "Contact john@example.com or call 555-123-4567"
        result = strip_sensitive_data(text)
        assert "john@example.com" not in result
        assert "555-123-4567" not in result
        assert EMAIL_PLACEHOLDER in result
        assert PHONE_PLACEHOLDER in result

    def test_preserve_regular_text(self):
        """Test that regular text is preserved."""
        text = "John is the CEO of Acme Corp and works in New York."
        result = strip_sensitive_data(text)
        assert result == text

    def test_complex_text(self):
        """Test with complex text containing multiple items."""
        text = """
        John Smith
        Email: john@acme.com
        Phone: (555) 123-4567
        Works at Acme Corp
        LinkedIn: linkedin.com/in/johnsmith
        """
        result = strip_sensitive_data(text)
        assert "john@acme.com" not in result
        assert "(555) 123-4567" not in result
        assert "John Smith" in result
        assert "Acme Corp" in result
        assert "LinkedIn" in result


class TestFilterPersonForAI:
    """Test person dict filtering."""

    def test_excludes_email_field(self):
        """Test that email field is excluded."""
        data = {
            "full_name": "John Smith",
            "email": "john@example.com",
            "title": "CEO",
        }
        result = filter_person_for_ai(data)
        assert "email" not in result
        assert result["full_name"] == "John Smith"
        assert result["title"] == "CEO"

    def test_excludes_phone_fields(self):
        """Test that phone fields are excluded."""
        data = {
            "full_name": "John Smith",
            "phone": "555-123-4567",
            "mobile": "555-987-6543",
            "work_phone": "555-111-2222",
        }
        result = filter_person_for_ai(data)
        assert "phone" not in result
        assert "mobile" not in result
        assert "work_phone" not in result

    def test_filters_notes_content(self):
        """Test that notes content is filtered."""
        data = {
            "full_name": "John Smith",
            "notes": "Contact at john@example.com or 555-123-4567",
        }
        result = filter_person_for_ai(data)
        assert "john@example.com" not in result["notes"]
        assert "555-123-4567" not in result["notes"]

    def test_preserves_allowed_fields(self):
        """Test that allowed fields are preserved."""
        data = {
            "full_name": "John Smith",
            "title": "CEO",
            "linkedin_url": "https://linkedin.com/in/johnsmith",
            "status": "active",
        }
        result = filter_person_for_ai(data)
        assert result["full_name"] == "John Smith"
        assert result["title"] == "CEO"
        assert result["linkedin_url"] == "https://linkedin.com/in/johnsmith"


class TestFilterOrganizationForAI:
    """Test organization dict filtering."""

    def test_excludes_contact_fields(self):
        """Test that contact fields are excluded."""
        data = {
            "name": "Acme Corp",
            "phone": "555-123-4567",
            "contact_email": "contact@acme.com",
        }
        result = filter_organization_for_ai(data)
        assert "phone" not in result
        assert "contact_email" not in result
        assert result["name"] == "Acme Corp"

    def test_filters_notes_content(self):
        """Test that notes content is filtered."""
        data = {
            "name": "Acme Corp",
            "notes": "Main contact: john@acme.com (555-123-4567)",
        }
        result = filter_organization_for_ai(data)
        assert "john@acme.com" not in result["notes"]
        assert "555-123-4567" not in result["notes"]


class TestPrivacyFilterClass:
    """Test PrivacyFilter class with statistics."""

    def test_tracks_email_redactions(self):
        """Test that email redactions are tracked."""
        filter = PrivacyFilter()
        filter.filter_text("Contact john@example.com and jane@example.com")

        stats = filter.get_stats()
        assert stats["emails_redacted"] == 2

    def test_tracks_phone_redactions(self):
        """Test that phone redactions are tracked."""
        filter = PrivacyFilter()
        filter.filter_text("Call 555-123-4567 or 555-987-6543")

        stats = filter.get_stats()
        assert stats["phones_redacted"] >= 2

    def test_tracks_total_redactions(self):
        """Test that total redactions are tracked."""
        filter = PrivacyFilter()
        filter.filter_text("Email john@example.com or call 555-123-4567")

        stats = filter.get_stats()
        assert stats["total_redactions"] >= 2

    def test_accumulates_across_calls(self):
        """Test that stats accumulate across multiple calls."""
        filter = PrivacyFilter()
        filter.filter_text("Email: john@example.com")
        filter.filter_text("Email: jane@example.com")

        stats = filter.get_stats()
        assert stats["emails_redacted"] == 2

    def test_reset_stats(self):
        """Test resetting statistics."""
        filter = PrivacyFilter()
        filter.filter_text("Email: john@example.com")
        filter.reset_stats()

        stats = filter.get_stats()
        assert stats["total_redactions"] == 0
        assert stats["emails_redacted"] == 0
