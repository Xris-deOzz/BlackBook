# Claude Code Prompt: Gmail Integration

**Date:** 2025.12.16  
**Priority:** Christmas email functionality first
**OAuth Status:** ✅ Scopes configured in Google Cloud Console (2025-12-16)

---

## Quick Context

You're working on Perun's BlackBook, a self-hosted personal CRM. The full specification is at:
**`docs/GMAIL_INTEGRATION_2025.12.13.1.md`**

Read that document first for complete details.

---

## Immediate Task: Gmail Compose Links (Priority 1)

**Goal:** Add "Email" buttons that open Gmail with pre-filled fields. No API changes needed - just URL generation.

### Step 1: Create Utility Module

Create `app/utils/gmail_compose.py`:

```python
"""Gmail compose URL builder."""
from urllib.parse import quote

def build_gmail_compose_url(
    to: str | list[str] | None = None,
    subject: str | None = None,
    body: str | None = None,
    cc: str | list[str] | None = None,
    bcc: str | list[str] | None = None,
) -> str:
    """Build Gmail compose URL with pre-filled fields."""
    base_url = "https://mail.google.com/mail/"
    params = ["view=cm", "fs=1"]
    
    def format_emails(emails):
        if emails is None:
            return None
        if isinstance(emails, list):
            return ",".join(emails)
        return emails
    
    if to:
        params.append(f"to={quote(format_emails(to), safe='@,')}")
    if subject:
        params.append(f"su={quote(subject)}")
    if body:
        params.append(f"body={quote(body)}")
    if cc:
        params.append(f"cc={quote(format_emails(cc), safe='@,')}")
    if bcc:
        params.append(f"bcc={quote(format_emails(bcc), safe='@,')}")
    
    return f"{base_url}?{'&'.join(params)}"
```

Also create `app/utils/__init__.py` if it doesn't exist.

### Step 2: Add Email Button to Person Profile

In `app/routers/person_details.py`, import the utility and pass URL to template:

```python
from app.utils.gmail_compose import build_gmail_compose_url

# In the route handler, add to template context:
gmail_compose_url = None
if person.primary_email:
    gmail_compose_url = build_gmail_compose_url(to=person.primary_email)
```

In `app/templates/persons/detail.html`, add button in header actions:

```html
{% if gmail_compose_url %}
<a href="{{ gmail_compose_url }}" target="_blank"
   class="inline-flex items-center px-3 py-2 border border-gray-300 shadow-sm text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50">
    <svg class="h-4 w-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" 
              d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"/>
    </svg>
    Email
</a>
{% endif %}
```

### Step 3: Bulk Email from People List

In `app/templates/persons/list.html`:

1. Add checkbox column to table
2. Add bulk action bar that appears when items selected
3. Add JavaScript to collect selected emails and open Gmail with BCC

See full implementation in `docs/GMAIL_INTEGRATION_2025.12.13.1.md` section 2.5.

---

## After Priority 1: Full Gmail Integration (Priority 2)

Once compose links are working, proceed with:

1. **Database schema** - Create email_messages, email_person_links, email_sync_state tables
2. **Gmail sync service** - Sync metadata from all accounts (full + incremental)
3. **Background task** - 15-minute sync interval with APScheduler
4. **Email inbox page** - New /emails route with list/detail views
5. **CRM integration** - Auto-link emails to persons, add-to-CRM action

Full details in the specification document.

---

## Key Files to Modify

| File | Purpose |
|------|---------|
| `app/utils/gmail_compose.py` | NEW - URL builder |
| `app/routers/person_details.py` | Add gmail_compose_url to context |
| `app/templates/persons/detail.html` | Add Email button |
| `app/templates/persons/list.html` | Add bulk selection + email |
| `app/services/google_auth.py` | Add gmail.send scope (Phase 2) - **Scope already in GCP, code update needed** |
| `app/services/gmail_sync_service.py` | NEW - Sync service (Phase 2) |
| `app/routers/emails_inbox.py` | NEW - Inbox routes (Phase 2) |

---

## Testing

After implementing compose links:
1. Go to any Person with an email address
2. Click "Email" button
3. Should open Gmail in new tab with To: field pre-filled
4. Test bulk select on People list, click "Email Selected"
5. Should open Gmail with all selected emails in BCC

---

## Questions?

If anything is unclear, check `docs/GMAIL_INTEGRATION_2025.12.13.1.md` for complete details including:
- Database schema SQL
- Full code examples
- UI mockup descriptions
- Testing checklists
