"""Tests for Gmail compose URL utility."""

import pytest
from app.utils.gmail_compose import (
    build_gmail_compose_url,
    build_gmail_compose_url_with_chooser,
    build_gmail_reply_url,
    build_bulk_bcc_url,
    build_christmas_email_url,
)


class TestBuildGmailComposeUrl:
    """Tests for build_gmail_compose_url function."""
    
    def test_basic_url_no_params(self):
        """Test URL with no parameters."""
        url = build_gmail_compose_url()
        assert url == "https://mail.google.com/mail/?view=cm&fs=1"
    
    def test_single_recipient(self):
        """Test URL with single recipient."""
        url = build_gmail_compose_url(to="john@example.com")
        assert "to=john@example.com" in url
        assert url.startswith("https://mail.google.com/mail/?view=cm&fs=1")
    
    def test_multiple_recipients_list(self):
        """Test URL with multiple recipients as list."""
        url = build_gmail_compose_url(to=["john@example.com", "jane@example.com"])
        assert "to=john@example.com,jane@example.com" in url
    
    def test_subject_encoding(self):
        """Test subject is properly URL encoded."""
        url = build_gmail_compose_url(subject="Hello World!")
        assert "su=Hello%20World%21" in url
    
    def test_body_with_newlines(self):
        """Test body preserves newlines via encoding."""
        url = build_gmail_compose_url(body="Line 1\nLine 2")
        assert "body=Line%201%0ALine%202" in url
    
    def test_cc_recipients(self):
        """Test CC recipients."""
        url = build_gmail_compose_url(to="main@example.com", cc="copy@example.com")
        assert "cc=copy@example.com" in url
    
    def test_bcc_recipients(self):
        """Test BCC recipients."""
        url = build_gmail_compose_url(bcc=["hidden1@example.com", "hidden2@example.com"])
        assert "bcc=hidden1@example.com,hidden2@example.com" in url
    
    def test_full_email(self):
        """Test URL with all parameters."""
        url = build_gmail_compose_url(
            to="recipient@example.com",
            subject="Test Subject",
            body="Test body",
            cc="cc@example.com",
            bcc="bcc@example.com"
        )
        assert "to=recipient@example.com" in url
        assert "su=Test%20Subject" in url
        assert "body=Test%20body" in url
        assert "cc=cc@example.com" in url
        assert "bcc=bcc@example.com" in url
    
    def test_special_characters_in_subject(self):
        """Test special characters are encoded."""
        url = build_gmail_compose_url(subject="Hello & Goodbye")
        assert "su=Hello%20%26%20Goodbye" in url
    
    def test_empty_email_list(self):
        """Test empty email list is handled."""
        url = build_gmail_compose_url(to=[])
        assert "to=" not in url
    
    def test_none_values_ignored(self):
        """Test None values are not included."""
        url = build_gmail_compose_url(to="test@example.com", subject=None, body=None)
        assert "to=test@example.com" in url
        assert "su=" not in url
        assert "body=" not in url
    
    def test_polish_characters(self):
        """Test Polish characters are encoded."""
        url = build_gmail_compose_url(subject="Wesołych Świąt")
        assert "su=Weso%C5%82ych%20%C5%9Awi%C4%85t" in url


class TestBuildGmailComposeUrlWithChooser:
    """Tests for build_gmail_compose_url_with_chooser function."""
    
    def test_uses_account_chooser_path(self):
        """Test URL uses /u/0/ for account chooser."""
        url = build_gmail_compose_url_with_chooser(to="test@example.com")
        assert "mail.google.com/mail/u/0/" in url
    
    def test_single_recipient(self):
        """Test with single recipient."""
        url = build_gmail_compose_url_with_chooser(to="john@example.com")
        assert "to=john@example.com" in url
    
    def test_with_subject_and_body(self):
        """Test with subject and body."""
        url = build_gmail_compose_url_with_chooser(
            to="test@example.com",
            subject="Hello",
            body="Test message"
        )
        assert "to=test@example.com" in url
        assert "su=Hello" in url
        assert "body=Test%20message" in url


class TestBuildGmailReplyUrl:
    """Tests for build_gmail_reply_url function."""
    
    def test_thread_url(self):
        """Test thread URL generation."""
        url = build_gmail_reply_url("abc123")
        assert url == "https://mail.google.com/mail/u/0/#all/abc123"


class TestBuildBulkBccUrl:
    """Tests for build_bulk_bcc_url function."""
    
    def test_bulk_bcc(self):
        """Test bulk BCC URL."""
        emails = ["a@example.com", "b@example.com", "c@example.com"]
        url = build_bulk_bcc_url(emails)
        assert "bcc=a@example.com,b@example.com,c@example.com" in url
        assert "to=" not in url
    
    def test_bulk_bcc_with_subject(self):
        """Test bulk BCC with subject."""
        emails = ["a@example.com", "b@example.com"]
        url = build_bulk_bcc_url(emails, subject="Group Message")
        assert "bcc=a@example.com,b@example.com" in url
        assert "su=Group%20Message" in url


class TestBuildChristmasEmailUrl:
    """Tests for build_christmas_email_url function."""
    
    def test_english_template(self):
        """Test English Christmas template."""
        url = build_christmas_email_url("friend@example.com", "english")
        assert "to=friend@example.com" in url
        assert "Season%27s%20Greetings" in url
    
    def test_polish_template(self):
        """Test Polish Christmas template."""
        url = build_christmas_email_url("friend@example.com", "polish")
        assert "to=friend@example.com" in url
        assert "Weso%C5%82ych" in url  # Wesołych encoded
    
    def test_default_is_english(self):
        """Test default language is English."""
        url = build_christmas_email_url("friend@example.com")
        assert "Season%27s%20Greetings" in url
    
    def test_multiple_recipients(self):
        """Test Christmas email to multiple recipients."""
        url = build_christmas_email_url(
            ["friend1@example.com", "friend2@example.com"],
            "english"
        )
        assert "to=friend1@example.com,friend2@example.com" in url
