# Changelog - December 13, 2025

**Document Version:** 2025.12.13.1
**Session Focus:** Bug Fixes & UI Improvements

---

## Summary

This session addressed several issues from the previous Gemini SDK migration work, fixed a critical bug on the Organizations search page, and improved UI elements.

---

## Issues Fixed

### 1. Organizations Page Search - 422 Error (Critical)

**Problem:** Searching on the Organizations page returned a 422 validation error:
```
Input should be a valid integer, unable to parse string as an integer
```
This occurred when `category_id` and `type_id` were passed as empty strings in the URL (`category_id=&type_id=`).

**Root Cause:** FastAPI's `Optional[int]` parameter type cannot parse empty strings - it expects either a valid integer or `None`.

**Solution:** Changed parameter types from `Optional[int]` to `Optional[str]` and added manual conversion with empty string handling.

**Files Modified:**
- `app/routers/organizations.py`
  - Lines 58-59: Main endpoint parameter types
  - Lines 124-134: Added string-to-int conversion logic
  - Lines 184-185: `/table` endpoint parameter types
  - Lines 198-220: Added conversion logic for table endpoint

**Code Pattern:**
```python
# Before
category_id: Optional[int] = Query(None, ...)

# After
category_id: Optional[str] = Query(None, ...)

# Conversion logic
category_id_int = int(category_id) if category_id and category_id.strip() else None
```

---

### 2. Organizations Page Tags Dropdown - Tom Select Not Initializing

**Problem:** The Tags filter showed as a tall native HTML `<select multiple>` element instead of a styled Tom Select dropdown.

**Root Cause:** A JavaScript syntax error on line 306 was preventing all JavaScript from executing:
```javascript
// Broken - improper escaping
const allBtn = document.querySelector('[onclick="filterByLetter(\\'\\')"]');
```

**Solution:** Fixed the string escaping:
```javascript
// Fixed - proper quoting
const allBtn = document.querySelector("[onclick=\"filterByLetter('')\"]");
```

**Additional Fix:** Also corrected a Jinja2 template expression that could cause issues:
```jinja2
{# Before - inline conditional #}
const initialTypeId = {{ (type_id if type_id else '') | tojson | safe }};

{# After - using default filter #}
const initialTypeId = {{ type_id | default('') | tojson | safe }};
```

**Files Modified:**
- `app/templates/organizations/list.html`
  - Line 234: Fixed Jinja2 expression for `initialTypeId`
  - Line 306: Fixed JavaScript string escaping for querySelector
  - Lines 16-24: Added CSS styling for Tom Select dropdown height limit

---

### 3. Startup Script Created

**Problem:** User needed a simple way to start BlackBook after computer restart.

**Solution:** Created `start_blackbook.bat` in the project root.

**File Created:**
- `start_blackbook.bat`

**Features:**
- Checks if Docker Desktop is running (required for PostgreSQL)
- Starts the FastAPI server with auto-reload on port 8000
- Provides clear error messages if Docker isn't running

---

## Files Modified Summary

| File | Changes |
|------|---------|
| `app/routers/organizations.py` | Fixed 422 error - parameter type handling |
| `app/templates/organizations/list.html` | Fixed JS syntax error, Tom Select initialization, CSS styling |
| `start_blackbook.bat` | **NEW** - Startup script for Windows |

---

## Testing Performed

1. **Organizations Search:** Verified searching for "TPG" returns 2 results (previously returned 422 error)
2. **Tags Dropdown:** Verified Tom Select initializes and shows "Select tags..." placeholder
3. **Console Check:** Confirmed no JavaScript errors, "Tom Select initialized successfully" message appears

---

## Known Issues Remaining

1. **Stale Server Processes:** Multiple Python processes were found on port 8000 before restart. Computer restart resolved this.

---

## Related Previous Work

This session continued from:
- **Gemini SDK Migration (2025.12.12)** - Migrated to new `google-genai` SDK
- **OpenAI Tool Calling Fix** - Added `tool_choice: "auto"` and enhanced system prompts

---

## Next Steps (From Previous Session)

1. Test the `add_affiliated_person` tool with OpenAI 4o on organization pages
2. Verify Gemini models work correctly with the new SDK

---

---

## Gmail Compose Links (Priority 1) - Implemented

### New Utility Module

**Created:** `app/utils/gmail_compose.py`

A utility module for building Gmail compose URLs with pre-filled fields:

```python
from app.utils.gmail_compose import build_gmail_compose_url

# Single recipient
url = build_gmail_compose_url(to="john@example.com")

# Multiple recipients with subject and body
url = build_gmail_compose_url(
    to=["john@example.com", "jane@example.com"],
    subject="Hello!",
    body="Message content here"
)

# BCC for bulk emails (privacy)
url = build_gmail_compose_url(bcc=["user1@example.com", "user2@example.com"])
```

### Person Detail Page - Email Button

**Modified:** `app/routers/persons.py`, `app/templates/persons/detail.html`

- Added import for `build_gmail_compose_url`
- Route handler now passes `gmail_compose_url` to template
- Email button appears in the header actions (first button)
- Button is active if person has an email, disabled (greyed out) if not
- Clicking opens Gmail in a new tab with To: field pre-filled

### People List Page - Bulk Email

**Modified:**
- `app/templates/persons/_table.html` - Added "Email Selected" button
- `app/templates/persons/_row.html` - Added `data-email` attribute to checkboxes
- `app/templates/persons/list.html` - Added `emailSelected()` JavaScript function

Features:
- Select multiple people using checkboxes
- Click "Email Selected" button in action bar
- Opens Gmail with all selected email addresses in BCC (for privacy)
- Shows alert if none of the selected contacts have email addresses

### Files Created/Modified Summary

| File | Status | Purpose |
|------|--------|---------|
| `app/utils/__init__.py` | NEW | Utils package init |
| `app/utils/gmail_compose.py` | NEW | Gmail URL builder utility |
| `app/routers/persons.py` | MODIFIED | Added gmail_compose_url to person detail |
| `app/templates/persons/detail.html` | MODIFIED | Added Email button in header |
| `app/templates/persons/_table.html` | MODIFIED | Added "Email Selected" bulk action button |
| `app/templates/persons/_row.html` | MODIFIED | Added data-email attribute |
| `app/templates/persons/list.html` | MODIFIED | Added emailSelected() function |

---

*End of Changelog*
