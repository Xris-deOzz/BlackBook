"""
Gmail compose URL utility for opening Gmail with pre-filled fields.

This module provides functions to generate Gmail compose URLs that open
Gmail in a new tab with pre-filled recipient, subject, and body fields.

No OAuth scope required - uses Gmail's URL scheme.

Usage:
    from app.utils.gmail_compose import build_gmail_compose_url
    
    url = build_gmail_compose_url(
        to="recipient@example.com",
        subject="Hello!",
        body="Message body here"
    )
"""

from urllib.parse import quote


def build_gmail_compose_url(
    to: str | list[str] | None = None,
    subject: str | None = None,
    body: str | None = None,
    cc: str | list[str] | None = None,
    bcc: str | list[str] | None = None,
) -> str:
    """
    Build a Gmail compose URL with pre-filled fields.
    
    Args:
        to: Recipient email(s) - string or list of strings
        subject: Email subject line
        body: Email body text (plain text, newlines preserved)
        cc: CC recipient(s) - string or list of strings
        bcc: BCC recipient(s) - string or list of strings
    
    Returns:
        Gmail compose URL string
    
    Example:
        >>> build_gmail_compose_url(
        ...     to=["john@example.com", "jane@example.com"],
        ...     subject="Team Update",
        ...     body="Hi team,\\n\\nHere's the update..."
        ... )
        'https://mail.google.com/mail/?view=cm&fs=1&to=john@example.com,jane@example.com&su=Team%20Update&body=Hi%20team%2C%0A%0AHere%27s%20the%20update...'
    """
    base_url = "https://mail.google.com/mail/"
    params = ["view=cm", "fs=1"]  # fs=1 opens in fullscreen compose
    
    def format_emails(emails: str | list[str] | None) -> str | None:
        """Format email(s) as comma-separated string."""
        if emails is None:
            return None
        if isinstance(emails, list):
            # Filter out empty strings and None values
            valid_emails = [e for e in emails if e]
            return ",".join(valid_emails) if valid_emails else None
        return emails if emails else None
    
    # Add 'to' parameter
    to_formatted = format_emails(to)
    if to_formatted:
        params.append(f"to={quote(to_formatted, safe='@,')}")
    
    # Add 'subject' parameter
    if subject:
        params.append(f"su={quote(subject)}")
    
    # Add 'body' parameter (newlines are preserved via URL encoding)
    if body:
        params.append(f"body={quote(body)}")
    
    # Add 'cc' parameter
    cc_formatted = format_emails(cc)
    if cc_formatted:
        params.append(f"cc={quote(cc_formatted, safe='@,')}")
    
    # Add 'bcc' parameter
    bcc_formatted = format_emails(bcc)
    if bcc_formatted:
        params.append(f"bcc={quote(bcc_formatted, safe='@,')}")
    
    return f"{base_url}?{'&'.join(params)}"


def build_gmail_compose_url_with_chooser(
    to: str | list[str] | None = None,
    subject: str | None = None,
    body: str | None = None,
    cc: str | list[str] | None = None,
    bcc: str | list[str] | None = None,
) -> str:
    """
    Build a Gmail compose URL that opens the account chooser.
    
    This is useful when the user has multiple Gmail accounts signed in
    and wants to choose which one to send from.
    
    Uses the /u/0/ pattern which shows account chooser.
    
    Args:
        to: Recipient email(s) - string or list of strings
        subject: Email subject line
        body: Email body text (plain text, newlines preserved)
        cc: CC recipient(s) - string or list of strings
        bcc: BCC recipient(s) - string or list of strings
    
    Returns:
        Gmail compose URL string with account chooser
    """
    base_url = "https://mail.google.com/mail/u/0/"
    params = ["view=cm", "fs=1"]  # fs=1 opens in fullscreen compose
    
    def format_emails(emails: str | list[str] | None) -> str | None:
        """Format email(s) as comma-separated string."""
        if emails is None:
            return None
        if isinstance(emails, list):
            valid_emails = [e for e in emails if e]
            return ",".join(valid_emails) if valid_emails else None
        return emails if emails else None
    
    # Add 'to' parameter
    to_formatted = format_emails(to)
    if to_formatted:
        params.append(f"to={quote(to_formatted, safe='@,')}")
    
    # Add 'subject' parameter
    if subject:
        params.append(f"su={quote(subject)}")
    
    # Add 'body' parameter
    if body:
        params.append(f"body={quote(body)}")
    
    # Add 'cc' parameter
    cc_formatted = format_emails(cc)
    if cc_formatted:
        params.append(f"cc={quote(cc_formatted, safe='@,')}")
    
    # Add 'bcc' parameter
    bcc_formatted = format_emails(bcc)
    if bcc_formatted:
        params.append(f"bcc={quote(bcc_formatted, safe='@,')}")
    
    return f"{base_url}?{'&'.join(params)}"


def build_gmail_reply_url(thread_id: str) -> str:
    """
    Build a Gmail URL to view/reply to a specific thread.
    
    Note: Gmail doesn't support pre-filling reply body via URL,
    so this opens the thread for manual reply.
    
    Args:
        thread_id: Gmail thread ID
    
    Returns:
        Gmail thread URL
    """
    return f"https://mail.google.com/mail/u/0/#all/{thread_id}"


def build_bulk_bcc_url(emails: list[str], subject: str | None = None) -> str:
    """
    Build a Gmail compose URL with multiple recipients in BCC.
    
    Useful for sending to multiple people without revealing addresses to each other.
    
    Args:
        emails: List of recipient email addresses
        subject: Optional email subject
    
    Returns:
        Gmail compose URL with emails in BCC field
    """
    return build_gmail_compose_url(bcc=emails, subject=subject)


# Christmas email templates
CHRISTMAS_TEMPLATES = {
    "polish": {
        "subject": "Wesołych Świąt! 🎄",
        "body": """Szanowni Państwo,

Z okazji zbliżających się Świąt Bożego Narodzenia oraz Nowego Roku, 
pragnę złożyć najserdeczniejsze życzenia zdrowia, szczęścia i pomyślności.

Niech ten magiczny czas będzie pełen radości spędzonej w gronie najbliższych.

Z poważaniem,
Christopher Ossowski"""
    },
    "english": {
        "subject": "Season's Greetings! 🎄",
        "body": """Dear Friends and Colleagues,

As the holiday season approaches, I wanted to take a moment to wish you 
and your loved ones a very Merry Christmas and a Happy New Year.

May this festive season bring you joy, peace, and prosperity.

Warm regards,
Christopher Ossowski"""
    }
}


def build_christmas_email_url(
    to: str | list[str],
    language: str = "english"
) -> str:
    """
    Build a Gmail compose URL with Christmas greeting template.
    
    Args:
        to: Recipient email(s)
        language: "english" or "polish"
    
    Returns:
        Gmail compose URL with pre-filled Christmas message
    """
    template = CHRISTMAS_TEMPLATES.get(language, CHRISTMAS_TEMPLATES["english"])
    return build_gmail_compose_url(
        to=to,
        subject=template["subject"],
        body=template["body"]
    )
