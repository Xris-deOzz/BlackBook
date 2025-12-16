# Gmail Integration - Full Specification

**Document Version:** 2025.12.16.1  
**Project:** Perun's BlackBook  
**Author:** Christopher  
**Status:** OAuth Scopes Configured, Code Update Pending

---

## 1. Overview

This specification covers the complete Gmail integration for Perun's BlackBook, consisting of two main components:

1. **Gmail Compose Links (Priority 1)** - Quick implementation for sending emails via Gmail popout
2. **Gmail Inbox Integration (Priority 2)** - Full email reading and management within BlackBook

### Current State

BlackBook already has:
- Google OAuth2 authentication with multi-account support
- `gmail.readonly` scope enabled
- `GmailService` class for searching emails by person
- Email history display on Person profile pages ("Interactions" tab)
- Email caching system (1-hour TTL)
- Email ignore patterns (domains/addresses)

### Files to Reference

| File | Purpose |
|------|---------|
| `app/services/gmail_service.py` | Existing Gmail API integration |
| `app/services/google_auth.py` | OAuth scopes and authentication |
| `app/routers/emails.py` | Existing email endpoints |
| `app/models/email_cache.py` | Email caching model |
| `app/models/interaction.py` | Interaction model with gmail fields |
| `app/models/google_account.py` | Connected Google accounts |
| `docs/GOOGLE_SETUP.md` | OAuth setup instructions |

---

## 2. Part 1: Gmail Compose Links (Priority 1 - Quick Win)

### 2.1 Goal

Add "Email" buttons throughout BlackBook that open Gmail in a new tab with pre-filled recipient, subject, and body. This requires NO additional OAuth scopes - it uses Gmail's compose URL scheme.

### 2.2 Gmail Compose URL Format

```
https://mail.google.com/mail/?view=cm&fs=1&to={to}&su={subject}&body={body}&cc={cc}&bcc={bcc}
```

All parameters must be URL-encoded. Multiple recipients are comma-separated.

**Example:**
```
https://mail.google.com/mail/?view=cm&fs=1&to=john%40example.com&su=Happy%20Holidays!&body=Hi%20John%2C%0A%0AWishing%20you%20a%20wonderful%20holiday%20season!
```

### 2.3 Tasks - Phase 5A: Gmail Compose Utility

**Location:** `app/utils/gmail_compose.py` (new file)

```python
"""
Gmail compose URL utility for opening Gmail with pre-filled fields.

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
        'https://mail.google.com/mail/?view=cm&fs=1&to=john%40example.com%2Cjane%40example.com&su=Team%20Update&body=Hi%20team%2C%0A%0AHere%27s%20the%20update...'
    """
    base_url = "https://mail.google.com/mail/"
    params = ["view=cm", "fs=1"]  # fs=1 opens in fullscreen compose
    
    def format_emails(emails: str | list[str] | None) -> str | None:
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
        # Preserve newlines by encoding them
        params.append(f"body={quote(body)}")
    
    if cc:
        params.append(f"cc={quote(format_emails(cc), safe='@,')}")
    
    if bcc:
        params.append(f"bcc={quote(format_emails(bcc), safe='@,')}")
    
    return f"{base_url}?{'&'.join(params)}"


def build_gmail_reply_url(
    thread_id: str,
    to: str | None = None,
    subject: str | None = None,
) -> str:
    """
    Build a Gmail URL to reply to a specific thread.
    
    Note: Gmail doesn't support pre-filling reply body via URL,
    so this opens the thread for manual reply.
    
    Args:
        thread_id: Gmail thread ID
        to: Optional recipient override
        subject: Optional subject override (will prepend "Re: " if not present)
    
    Returns:
        Gmail thread URL
    """
    # Direct link to thread - user can reply from there
    return f"https://mail.google.com/mail/u/0/#all/{thread_id}"
```

**Task Checklist:**
- [ ] Create `app/utils/__init__.py` if it doesn't exist
- [ ] Create `app/utils/gmail_compose.py` with the above code
- [ ] Add unit tests in `tests/test_gmail_compose.py`
- [ ] Test URL generation with special characters (quotes, ampersands, newlines)

### 2.4 Tasks - Phase 5B: Person Profile Integration

**Goal:** Add "Email" button to Person detail page header

**File to modify:** `app/templates/persons/detail.html`

**Implementation:**

1. Add Email button next to existing action buttons in the person header:

```html
<!-- In person header actions area -->
{% if person.primary_email %}
<a href="{{ gmail_compose_url }}" 
   target="_blank"
   class="inline-flex items-center px-3 py-2 border border-gray-300 shadow-sm text-sm leading-4 font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500">
    <svg class="h-4 w-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"/>
    </svg>
    Email
</a>
{% else %}
<button disabled
        class="inline-flex items-center px-3 py-2 border border-gray-200 text-sm leading-4 font-medium rounded-md text-gray-400 bg-gray-100 cursor-not-allowed"
        title="No email address on file">
    <svg class="h-4 w-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"/>
    </svg>
    Email
</button>
{% endif %}
```

2. **Update the route handler** in `app/routers/person_details.py`:

```python
from app.utils.gmail_compose import build_gmail_compose_url

@router.get("/{person_id}", response_class=HTMLResponse)
async def get_person_detail(
    request: Request,
    person_id: UUID,
    db: Session = Depends(get_db),
):
    person = db.query(Person).filter_by(id=person_id).first()
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")
    
    # Build Gmail compose URL if person has email
    gmail_compose_url = None
    if person.primary_email:
        gmail_compose_url = build_gmail_compose_url(to=person.primary_email)
    
    return templates.TemplateResponse(
        "persons/detail.html",
        {
            "request": request,
            "person": person,
            "gmail_compose_url": gmail_compose_url,
            # ... other context
        },
    )
```

3. **Handle multiple emails** - If person has multiple email addresses, show a dropdown:

```html
{% if person.emails|length > 1 %}
<div class="relative" x-data="{ open: false }">
    <button @click="open = !open" 
            class="inline-flex items-center px-3 py-2 border border-gray-300 shadow-sm text-sm leading-4 font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50">
        <svg class="h-4 w-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"/>
        </svg>
        Email
        <svg class="ml-2 h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"/>
        </svg>
    </button>
    <div x-show="open" @click.away="open = false"
         class="absolute right-0 mt-2 w-56 rounded-md shadow-lg bg-white ring-1 ring-black ring-opacity-5 z-10">
        <div class="py-1">
            {% for email in person.emails %}
            <a href="{{ build_gmail_compose_url(email.email) }}" 
               target="_blank"
               class="block px-4 py-2 text-sm text-gray-700 hover:bg-gray-100">
                {{ email.email }}
                {% if email.is_primary %}<span class="text-xs text-gray-500">(primary)</span>{% endif %}
            </a>
            {% endfor %}
        </div>
    </div>
</div>
{% elif person.primary_email %}
<!-- Single email button as shown above -->
{% endif %}
```

**Task Checklist:**
- [ ] Add Email button to person detail page header
- [ ] Pass `gmail_compose_url` from route handler to template
- [ ] Handle case where person has no email (disabled button)
- [ ] Handle multiple emails with dropdown selector
- [ ] Test button opens Gmail correctly in new tab

### 2.5 Tasks - Phase 5C: Bulk Email for Contact Lists

**Goal:** Select multiple people and compose email to all of them (BCC)

**File to modify:** `app/templates/persons/list.html`

**Implementation:**

1. Add checkbox column to people list table:

```html
<thead>
    <tr>
        <th class="w-8 px-2">
            <input type="checkbox" 
                   id="select-all" 
                   class="rounded border-gray-300 text-indigo-600 focus:ring-indigo-500"
                   @change="toggleAll($event.target.checked)">
        </th>
        <!-- existing columns -->
    </tr>
</thead>
<tbody>
    {% for person in persons %}
    <tr>
        <td class="px-2">
            <input type="checkbox" 
                   name="selected_persons" 
                   value="{{ person.id }}"
                   data-email="{{ person.primary_email or '' }}"
                   class="person-checkbox rounded border-gray-300 text-indigo-600 focus:ring-indigo-500"
                   @change="updateBulkActions()">
        </td>
        <!-- existing columns -->
    </tr>
    {% endfor %}
</tbody>
```

2. Add bulk action bar (appears when items selected):

```html
<div id="bulk-action-bar" 
     class="hidden fixed bottom-4 left-1/2 transform -translate-x-1/2 bg-gray-900 text-white px-6 py-3 rounded-lg shadow-lg flex items-center space-x-4 z-50">
    <span id="selected-count">0 selected</span>
    <button onclick="emailSelected()" 
            class="inline-flex items-center px-3 py-1.5 bg-indigo-600 hover:bg-indigo-700 rounded text-sm font-medium">
        <svg class="h-4 w-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"/>
        </svg>
        Email Selected
    </button>
    <button onclick="clearSelection()" class="text-gray-400 hover:text-white">
        <svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
        </svg>
    </button>
</div>
```

3. Add JavaScript for bulk selection:

```javascript
// In persons/list.html or separate JS file

function updateBulkActions() {
    const checkboxes = document.querySelectorAll('.person-checkbox:checked');
    const bar = document.getElementById('bulk-action-bar');
    const count = document.getElementById('selected-count');
    
    if (checkboxes.length > 0) {
        bar.classList.remove('hidden');
        count.textContent = `${checkboxes.length} selected`;
    } else {
        bar.classList.add('hidden');
    }
}

function toggleAll(checked) {
    document.querySelectorAll('.person-checkbox').forEach(cb => {
        cb.checked = checked;
    });
    updateBulkActions();
}

function clearSelection() {
    document.querySelectorAll('.person-checkbox').forEach(cb => {
        cb.checked = false;
    });
    document.getElementById('select-all').checked = false;
    updateBulkActions();
}

function emailSelected() {
    const checkboxes = document.querySelectorAll('.person-checkbox:checked');
    const emails = [];
    
    checkboxes.forEach(cb => {
        const email = cb.dataset.email;
        if (email) {
            emails.push(email);
        }
    });
    
    if (emails.length === 0) {
        alert('None of the selected contacts have email addresses.');
        return;
    }
    
    // Build Gmail compose URL with all emails in BCC (for privacy)
    const bccList = emails.join(',');
    const url = `https://mail.google.com/mail/?view=cm&fs=1&bcc=${encodeURIComponent(bccList)}`;
    
    window.open(url, '_blank');
}
```

**Task Checklist:**
- [ ] Add checkbox column to people list table
- [ ] Add "Select All" checkbox in header
- [ ] Add floating bulk action bar
- [ ] Implement `emailSelected()` function that opens Gmail with BCC
- [ ] Handle contacts without email addresses gracefully
- [ ] Style bulk action bar to match BlackBook theme

### 2.6 Tasks - Phase 5D: Quick Compose from Other Locations

**Goal:** Add email buttons to Organization pages and navigation

**Implementation:**

1. **Organization page** - `app/templates/organizations/detail.html`:
   - Add "Email" button if organization has contact email
   - Add "Email Primary Contact" if organization has linked contacts

2. **Global compose button** - Add to navigation or as floating action:
   ```html
   <a href="https://mail.google.com/mail/?view=cm&fs=1" 
      target="_blank"
      class="..." 
      title="Compose new email">
       <svg><!-- mail icon --></svg>
       Compose
   </a>
   ```

3. **Email history list** - Add reply button to email threads:
   - In `app/templates/persons/_email_list.html`
   - Add "Reply" link that opens Gmail thread

**Task Checklist:**
- [ ] Add Email button to Organization detail page
- [ ] Add "Email Primary Contact" option for organizations with linked people
- [ ] Add global "Compose" button (optional - in nav or floating)
- [ ] Add "Reply" action to email thread list items

---

## 3. Part 2: Full Gmail Inbox Integration (Priority 2)

### 3.1 Goal

Create a dedicated Email page in BlackBook showing all emails across connected Gmail accounts, with ability to:
- View inbox with filtering and search
- Read email content within BlackBook
- Compose and send emails via Gmail API
- Link emails to CRM contacts
- Add new contacts from email senders

### 3.2 OAuth Scope Updates

**Current scopes** (in `app/services/google_auth.py`):
```python
GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
]
```

**Required additional scopes:**
```python
GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",    # Read emails
    "https://www.googleapis.com/auth/gmail.send",        # Send emails
    "https://www.googleapis.com/auth/gmail.compose",     # Create drafts
    "https://www.googleapis.com/auth/gmail.modify",      # Mark read/unread, labels
]
```

**Note:** After adding scopes, users must re-authenticate to grant new permissions.

### 3.3 Database Schema - Email Metadata Storage

**New tables needed:**

```sql
-- Email messages metadata (not full content - fetched on demand)
CREATE TABLE email_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    google_account_id UUID NOT NULL REFERENCES google_accounts(id) ON DELETE CASCADE,
    gmail_message_id VARCHAR(255) NOT NULL,
    gmail_thread_id VARCHAR(255) NOT NULL,
    
    -- Metadata (stored locally for fast filtering)
    subject VARCHAR(1000),
    snippet TEXT,
    from_email VARCHAR(255),
    from_name VARCHAR(255),
    to_emails JSONB DEFAULT '[]',      -- Array of {email, name}
    cc_emails JSONB DEFAULT '[]',
    bcc_emails JSONB DEFAULT '[]',
    
    -- Status
    is_read BOOLEAN DEFAULT FALSE,
    is_starred BOOLEAN DEFAULT FALSE,
    is_draft BOOLEAN DEFAULT FALSE,
    is_sent BOOLEAN DEFAULT FALSE,      -- True if from user's sent folder
    labels JSONB DEFAULT '[]',          -- Gmail labels
    
    -- Dates
    internal_date TIMESTAMP WITH TIME ZONE,  -- Gmail's internal timestamp
    received_at TIMESTAMP WITH TIME ZONE,
    
    -- Attachments metadata (not content)
    has_attachments BOOLEAN DEFAULT FALSE,
    attachment_count INTEGER DEFAULT 0,
    
    -- Sync tracking
    history_id BIGINT,                  -- Gmail history ID for incremental sync
    synced_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    UNIQUE(google_account_id, gmail_message_id)
);

CREATE INDEX idx_email_messages_account ON email_messages(google_account_id);
CREATE INDEX idx_email_messages_thread ON email_messages(gmail_thread_id);
CREATE INDEX idx_email_messages_date ON email_messages(internal_date DESC);
CREATE INDEX idx_email_messages_from ON email_messages(from_email);
CREATE INDEX idx_email_messages_read ON email_messages(is_read);

-- Email to Person linkage
CREATE TABLE email_person_links (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email_message_id UUID NOT NULL REFERENCES email_messages(id) ON DELETE CASCADE,
    person_id UUID NOT NULL REFERENCES persons(id) ON DELETE CASCADE,
    link_type VARCHAR(50) NOT NULL,     -- 'from', 'to', 'cc', 'mentioned'
    linked_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    linked_by VARCHAR(50) DEFAULT 'auto',  -- 'auto' or 'manual'
    
    UNIQUE(email_message_id, person_id, link_type)
);

CREATE INDEX idx_email_person_links_email ON email_person_links(email_message_id);
CREATE INDEX idx_email_person_links_person ON email_person_links(person_id);

-- Sync state tracking per account
CREATE TABLE email_sync_state (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    google_account_id UUID NOT NULL REFERENCES google_accounts(id) ON DELETE CASCADE,
    last_history_id BIGINT,
    last_full_sync_at TIMESTAMP WITH TIME ZONE,
    last_incremental_sync_at TIMESTAMP WITH TIME ZONE,
    sync_status VARCHAR(50) DEFAULT 'idle',  -- 'idle', 'syncing', 'error'
    error_message TEXT,
    messages_synced INTEGER DEFAULT 0,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    UNIQUE(google_account_id)
);
```

### 3.4 Tasks - Phase 6: Database & Models

**Task Checklist:**
- [ ] Create Alembic migration for new tables
- [ ] Create SQLAlchemy model: `app/models/email_message.py`
- [ ] Create SQLAlchemy model: `app/models/email_person_link.py`
- [ ] Create SQLAlchemy model: `app/models/email_sync_state.py`
- [ ] Add models to `app/models/__init__.py`
- [ ] Run migration and verify tables created

### 3.5 Tasks - Phase 7: Gmail Sync Service

**File:** `app/services/gmail_sync_service.py` (new)

**Core methods needed:**

```python
class GmailSyncService:
    """Service for syncing Gmail messages to local database."""
    
    def __init__(self, db: Session):
        self.db = db
    
    async def full_sync(
        self,
        account: GoogleAccount,
        max_results: int = 500,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> SyncResult:
        """
        Perform full sync of all messages from Gmail.
        
        Called on first sync or to rebuild local cache.
        Uses Gmail messages.list API with pagination.
        """
        pass
    
    async def incremental_sync(
        self,
        account: GoogleAccount,
    ) -> SyncResult:
        """
        Perform incremental sync using Gmail history API.
        
        Only fetches changes since last sync (new messages, 
        status changes, deletions).
        """
        pass
    
    async def sync_all_accounts(self) -> dict[str, SyncResult]:
        """Sync all active Google accounts."""
        pass
    
    def _parse_message(
        self,
        message_data: dict,
        account: GoogleAccount,
    ) -> EmailMessage:
        """Parse Gmail API message response into EmailMessage model."""
        pass
    
    def _auto_link_to_persons(
        self,
        email_message: EmailMessage,
    ) -> list[EmailPersonLink]:
        """
        Auto-link email to CRM persons based on email addresses.
        
        Matches from/to/cc addresses against PersonEmail records.
        """
        pass
```

**Task Checklist:**
- [ ] Create `GmailSyncService` class
- [ ] Implement `full_sync()` with pagination (handle "all time" history)
- [ ] Implement `incremental_sync()` using Gmail history API
- [ ] Implement `_parse_message()` to extract metadata
- [ ] Implement `_auto_link_to_persons()` for CRM matching
- [ ] Add progress tracking for long-running syncs
- [ ] Handle rate limits and retries gracefully
- [ ] Add unit tests for message parsing

### 3.6 Tasks - Phase 8: Background Sync Task

**File:** `app/tasks/email_sync.py` (new)

**Implementation options:**

1. **Simple approach (recommended for now):** APScheduler running in FastAPI process
2. **Future option:** Celery with Redis for more robust background tasks

```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.services.gmail_sync_service import GmailSyncService

scheduler = AsyncIOScheduler()

@scheduler.scheduled_job('interval', minutes=15)
async def sync_emails_task():
    """Background task to sync emails every 15 minutes."""
    async with get_async_session() as db:
        service = GmailSyncService(db)
        await service.sync_all_accounts()

def start_scheduler():
    """Start the background scheduler."""
    scheduler.start()
```

**In `app/main.py`:**
```python
from app.tasks.email_sync import start_scheduler

@app.on_event("startup")
async def startup_event():
    start_scheduler()
```

**Task Checklist:**
- [ ] Add APScheduler to `requirements.txt`
- [ ] Create `app/tasks/email_sync.py`
- [ ] Configure 15-minute sync interval
- [ ] Add manual sync trigger endpoint
- [ ] Add sync status to settings page
- [ ] Handle scheduler graceful shutdown

### 3.7 Tasks - Phase 9: Email Inbox Page (UI)

**Route:** `/emails`

**File:** `app/routers/emails_inbox.py` (new router)

**Features:**
- List view of all emails (paginated)
- Account filter dropdown
- Search bar (Gmail syntax)
- Label/folder sidebar
- Unread count badges
- Date grouping (Today, Yesterday, This Week, etc.)

**Template structure:**
```
app/templates/emails/
├── inbox.html          # Main inbox page
├── _email_list.html    # HTMX partial for email list
├── _email_detail.html  # HTMX partial for email content
├── _compose_modal.html # Compose modal (if doing in-app compose)
└── _filters.html       # Sidebar filters
```

**Task Checklist:**
- [ ] Create `/emails` route
- [ ] Create inbox.html template with sidebar layout
- [ ] Implement email list with HTMX pagination
- [ ] Add account filter dropdown
- [ ] Add search bar with Gmail search syntax
- [ ] Add label/folder filter sidebar
- [ ] Implement email detail view (fetch full content on demand)
- [ ] Add "View in Gmail" link on each email
- [ ] Add "Link to Contact" action
- [ ] Add "Add to CRM" action for unknown senders
- [ ] Style to match BlackBook theme

### 3.8 Tasks - Phase 10: Email Sending via API (Optional Enhancement)

**Note:** The Gmail compose link approach (Part 1) may be sufficient. In-app sending is more complex.

**If implementing in-app sending:**

```python
# In gmail_service.py

async def send_email(
    self,
    account: GoogleAccount,
    to: list[str],
    subject: str,
    body: str,
    cc: list[str] | None = None,
    bcc: list[str] | None = None,
    reply_to_message_id: str | None = None,
) -> dict:
    """
    Send an email via Gmail API.
    
    Requires gmail.send scope.
    """
    from email.mime.text import MIMEText
    import base64
    
    message = MIMEText(body)
    message['to'] = ', '.join(to)
    message['subject'] = subject
    if cc:
        message['cc'] = ', '.join(cc)
    
    # Add thread reference for replies
    if reply_to_message_id:
        message['In-Reply-To'] = reply_to_message_id
        message['References'] = reply_to_message_id
    
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    
    credentials = self._get_credentials(account)
    service = build("gmail", "v1", credentials=credentials)
    
    result = service.users().messages().send(
        userId="me",
        body={'raw': raw}
    ).execute()
    
    return result
```

**Task Checklist (if implementing):**
- [ ] Add `gmail.send` scope to OAuth
- [ ] Update `GOOGLE_SETUP.md` with new scope instructions
- [ ] Implement `send_email()` in GmailService
- [ ] Create compose modal UI
- [ ] Add rich text editor (optional - can start with plain text)
- [ ] Handle attachments (future enhancement)
- [ ] Auto-log sent emails as interactions
- [ ] Test reply threading

### 3.9 Tasks - Phase 11: CRM Integration

**Auto-linking logic:**

When emails are synced:
1. Extract all email addresses from From/To/CC
2. Query `person_emails` table for matches
3. Create `email_person_links` records for matches
4. For unmatched addresses, optionally add to "suggested contacts" queue

**UI enhancements:**

1. **On Person profile "Interactions" tab:**
   - Show linked emails from `email_person_links`
   - Add "Link Email" button to manually link emails

2. **On Email detail view:**
   - Show CRM contacts involved in thread
   - "Add to CRM" button for unknown addresses

**Task Checklist:**
- [ ] Implement auto-linking during sync
- [ ] Add linked emails to Person "Interactions" tab
- [ ] Add "Link to Contact" action on emails
- [ ] Add "Add to CRM" quick action for unknown senders
- [ ] Add email count badge on Person cards

### 3.10 Navigation Integration

**Add to main navigation sidebar:**

```html
<a href="/emails" class="nav-link">
    <svg><!-- inbox icon --></svg>
    <span>Email</span>
    {% if unread_count > 0 %}
    <span class="badge">{{ unread_count }}</span>
    {% endif %}
</a>
```

**Task Checklist:**
- [ ] Add "Email" link to main navigation
- [ ] Add unread count badge
- [ ] Add "Recent Emails" widget to Dashboard (optional)

---

## 4. Implementation Order

### Immediate (Christmas Emails) - ~2-3 hours

1. Phase 5A: Gmail compose utility ✓
2. Phase 5B: Person profile email button ✓
3. Phase 5C: Bulk email selection ✓

### Short Term - ~1-2 days

4. Phase 5D: Organization page + global compose
5. Phase 6: Database schema for email storage
6. Phase 7: Gmail sync service

### Medium Term - ~2-3 days

7. Phase 8: Background sync task
8. Phase 9: Email inbox page UI
9. Phase 11: CRM integration

### Optional / Future

10. Phase 10: In-app email sending
11. Email templates
12. AI email summarization
13. Proton Mail integration

---

## 5. Testing Checklist

### Gmail Compose Links
- [ ] Single recipient URL works
- [ ] Multiple recipients in BCC works
- [ ] Special characters in subject/body encoded correctly
- [ ] Newlines preserved in body
- [ ] Button disabled when no email on person

### Gmail Sync
- [ ] Full sync completes without errors
- [ ] Incremental sync picks up new messages
- [ ] Auto-linking correctly matches CRM contacts
- [ ] Rate limits handled gracefully
- [ ] Sync state persisted across restarts

### Email Inbox UI
- [ ] Emails load with pagination
- [ ] Search filters correctly
- [ ] Account filter works
- [ ] Email detail fetches content
- [ ] "View in Gmail" opens correct thread
- [ ] Mobile responsive

---

## 6. Configuration

**Environment variables to add:**

```env
# Email sync settings
EMAIL_SYNC_INTERVAL_MINUTES=15
EMAIL_SYNC_MAX_RESULTS=500
EMAIL_SYNC_ENABLED=true
```

**Settings page additions:**
- Toggle email sync on/off
- Configure sync frequency
- Select which accounts to sync
- Manual "Sync Now" button
- View sync status and last sync time

---

## 7. Security Considerations

1. **OAuth scopes:** Request minimum necessary scopes
2. **Token storage:** Refresh tokens already encrypted (existing system)
3. **Email content:** Fetch on demand, don't store body in database
4. **Rate limits:** Respect Gmail API quotas (250 quota units/user/second)
5. **Error handling:** Don't expose API errors to UI

---

## 8. References

- [Gmail API Documentation](https://developers.google.com/gmail/api)
- [Gmail API Scopes](https://developers.google.com/gmail/api/auth/scopes)
- [Gmail Search Operators](https://support.google.com/mail/answer/7190)
- [Gmail History API](https://developers.google.com/gmail/api/guides/sync)
- [Gmail Compose URL Parameters](https://stackoverflow.com/questions/6548570/url-to-compose-a-message-in-gmail-with-full-message-body)

---

*End of Gmail Integration Specification*
