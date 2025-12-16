# Changelog - December 14, 2025

**Document Version:** 2025.12.14.1
**Session Focus:** Christmas Lists Feature & Documentation Update

---

## Summary

This session completed the Christmas Email Lists feature and updated project documentation to reflect all recent feature additions including Email Inbox, Tasks, Birthdays, and more.

---

## Features Implemented

### 1. Christmas Email Lists Feature (Completed)

A dedicated page for managing Polish and English Christmas email recipient lists with AI-powered suggestions.

**Files Created:**
- `app/routers/christmas_lists.py` - Router with all endpoints
- `app/services/christmas_service.py` - Business logic for suggestions
- `app/templates/christmas_lists/index.html` - Overview page with list counts
- `app/templates/christmas_lists/list.html` - Individual list view
- `app/templates/christmas_lists/suggestions.html` - Suggestions review page
- `app/templates/christmas_lists/_suggestions_table.html` - Table partial
- `app/templates/christmas_lists/_table.html` - List members table partial

**Features:**
- Overview page showing Polish and English list counts
- AI-powered suggestions based on:
  - Location (Poland address = Polish list)
  - City names (Warsaw, Krakow, etc. = Polish list)
  - Name patterns (-ski, -ska, -wicz, -czyk suffixes = Medium confidence Polish)
  - Default to English for others with email
- Confidence levels: HIGH, MEDIUM, LOW
- One-click assignment to either list
- Bulk assignment by confidence level
- Pagination (25/50/100/250 per page)
- CSV export for each list
- Tag management from suggestions page
- Skip functionality for undecided contacts

**Endpoints:**
- `GET /christmas-lists` - Overview page
- `GET /christmas-lists/polish` - Polish list
- `GET /christmas-lists/english` - English list
- `GET /christmas-lists/suggestions` - Suggestions with pagination
- `POST /christmas-lists/assign` - Assign to list
- `POST /christmas-lists/remove` - Remove from list
- `POST /christmas-lists/bulk-assign` - Bulk assign by confidence
- `GET /christmas-lists/export/{list_type}` - CSV export
- `GET /christmas-lists/table/{list_type}` - HTMX table refresh
- `GET /christmas-lists/suggestions-table` - HTMX suggestions refresh

**Navigation:**
- Added to "Lists & Views" dropdown menu
- Shows Christmas tree emoji (🎄) for easy identification

---

### 2. Navigation Styling Attempt (Unresolved)

Attempted to fix dropdown button colors for "Communication" and "Lists & Views" to match other nav items.

**Issue:** Dropdown buttons show white text while other nav items show blue-gray (`#cbd5e1`)

**Attempted Solutions:**
- CSS with `!important` rules
- `-webkit-text-fill-color` property
- Inline `style` attributes
- Various CSS selector specificity combinations

**Status:** Still showing white despite all attempts. Something in Tailwind CSS or browser defaults is overriding styles. Left for future investigation.

**Files Modified:**
- `app/templates/base.html` - Added CSS rules and inline styles (not working)

---

## Documentation Updates

### README.md - Comprehensive Update

Updated to reflect all features added over the past several days:

**Features Section (Reorganized):**
- Core CRM features
- Google Integration (Gmail Sync, Gmail Compose, Calendar, Tasks)
- Dashboard Widgets (Calendar, Tasks, Birthdays, Layout)
- Communication Tools (Email Inbox, Bulk Email)
- Seasonal Features (Christmas Lists)
- AI Features
- Other (PWA, Dark Mode, LinkedIn Import)

**Project Structure:**
- Added all new routers (emails_inbox, calendar, tasks, dashboard, christmas_lists)
- Added services directory with all services
- Added utils directory
- Added alembic migrations directory
- Added start_blackbook.bat

**API Endpoints:**
- Added Email Inbox endpoints
- Added Calendar endpoints
- Added Tasks endpoints
- Added Dashboard endpoints
- Added Christmas Lists endpoints

---

## Files Modified Summary

| File | Changes |
|------|---------|
| `README.md` | Major update - features, structure, endpoints |
| `app/templates/base.html` | Navigation styling attempts (unresolved) |

## Files Created Summary

| File | Purpose |
|------|---------|
| `docs/CHANGELOG_2025.12.14.md` | This changelog |

---

## Recent Features Reference (Dec 13-14)

For reference, here are features implemented in recent sessions:

### Gmail Compose Links (Dec 13)
- `app/utils/gmail_compose.py` - URL builder utility
- Email button on person detail page
- "Email Selected" bulk action on people list

### Dashboard Widgets (Recent)
- Today's Calendar with meeting attendee matching
- Today's Tasks with Google Tasks sync
- Birthday Reminders with calendar view
- Customizable widget layout and ordering

### Email Inbox (Recent)
- Full email inbox page at `/emails`
- Folder filtering (inbox, sent, all)
- Gmail label filtering
- Full-text search
- Contact linking
- Email detail view

### Google Tasks Integration (Recent)
- Tasks widget on dashboard
- Sync from Google Tasks API
- Complete/uncomplete tasks
- Inline editing of task details
- Create new tasks
- Delete tasks
- Task list ordering

---

## Known Issues

1. **Navigation Dropdown Colors**: "Communication" and "Lists & Views" buttons still show white text instead of matching blue-gray color of other nav items.

---

## Next Steps

1. Investigate navigation button color issue (may need to check Tailwind config or browser dev tools)
2. Consider adding email compose functionality to Christmas Lists export

---

*End of Changelog*
