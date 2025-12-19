# Changelog - December 18, 2025

## Session Summary
This session focused on implementing **bidirectional Google Contacts sync** - the ability to push BlackBook contacts to Google Contacts so they sync to your phone.

---

## Features Implemented

### 1. Push to Google Contacts (Bidirectional Sync)
**Location:** Person detail page → Record Info → Google Sync section

BlackBook can now push contacts TO Google Contacts, not just import from them. This enables:
- Creating new contacts in Google Contacts from BlackBook
- Syncing BlackBook-only contacts to your phone
- True bidirectional sync workflow

**How it works:**
1. Navigate to any person's detail page
2. In the "Google Sync" section (Record Info sidebar), select a Google account
3. Click "Push to Google"
4. The contact is created in Google Contacts with all available data
5. Status changes from "Not linked" to "Linked"

**Data pushed to Google:**
- First name, Last name
- Email addresses (all from PersonEmail table)
- Phone number
- Current organization and title
- Birthday
- Location/Address
- Notes

**Files Added/Modified:**
- `app/services/contacts_service.py` - Added `push_to_google()` method to ContactsService class
- `app/routers/import_contacts.py` - Added `/import/google/push/{person_id}` POST endpoint
- `app/templates/persons/detail.html` - Added Push to Google button and account selector UI
- `app/templates/persons/_google_sync_status.html` - New HTMX partial for success/error states

### 2. Settings Page UI Consolidation
**Location:** `/settings`

Merged redundant UI sections into a cleaner layout:
- Combined "Google Contacts Sync" and "Recent Sync Activity" into one unified section
- Made sync history inline and compact (shows last 3 items)
- Reduced visual clutter while maintaining full functionality

---

## Technical Details

### Google OAuth Scopes
The Push to Google feature requires the full `contacts` scope (not just `contacts.readonly`). Users who connected their Google account before this update need to:
1. Disconnect their Google account in Settings
2. Reconnect to grant the new write permissions
3. The OAuth consent screen will now show "See, edit, download, and permanently delete your contacts"

### API Used
- Google People API `people.createContact` endpoint
- Creates contact in user's saved contacts (not "Other contacts")

### Error Handling
- Authentication failures prompt user to reconnect account
- 403 errors indicate scope issues (need `contacts` not just `contacts.readonly`)
- Already-linked contacts cannot be pushed again (prevents duplicates)

---

## Deployment Notes

### Network Share Copy Issues
Discovered that Windows network share copies (`\\bearcave\...`) don't reliably update files on Synology NAS. The workaround:
1. Edit files locally on Windows
2. Use SSH heredoc to add code directly to Synology, OR
3. Use `head`/`cat` commands to reconstruct files on Synology

### Deployment Commands (Synology)
```bash
# Standard rebuild
sudo docker-compose -f docker-compose.prod.yml down
sudo docker-compose -f docker-compose.prod.yml build --no-cache
sudo docker-compose -f docker-compose.prod.yml up -d

# Verify app started
sudo docker logs blackbook-app --tail 10

# Check for errors
sudo docker logs blackbook-app --tail 50
```

---

## Files Changed Summary

### New Files
- `app/templates/persons/_google_sync_status.html` - HTMX partial for push status

### Modified Files
- `app/services/contacts_service.py` - Added `push_to_google()` method (~120 lines)
- `app/routers/import_contacts.py` - Added push endpoint, added `Form` import
- `app/templates/persons/detail.html` - Added Push to Google UI in Google Sync section
- `app/templates/settings/index.html` - Merged sync sections

---

## Bug Fixes

### 1. Missing `Form` Import
**Issue:** App crashed on startup with `NameError: name 'Form' is not defined`
**Cause:** Added `Form(...)` parameter but forgot to import `Form` from FastAPI
**Fix:** Added `Form` to imports in `import_contacts.py`

### 2. Method Outside Class
**Issue:** `push_to_google` method was added after the class definition
**Cause:** Heredoc append placed method after `get_contacts_service()` function
**Fix:** Reconstructed file with method inside `ContactsService` class

### 3. `current_company` Attribute Error
**Issue:** `'Person' object has no attribute 'current_company'`
**Cause:** Person model uses `organizations` relationship, not a `current_company` field
**Fix:** Changed code to find current organization from `person.organizations`

---

## Next Steps (Future Enhancements)

1. **Sync Updates** - Push updates when BlackBook contact is modified
2. **Bulk Push** - Push multiple contacts at once
3. **Two-way Sync** - Detect and merge changes from both sides
4. **Conflict Resolution** - Handle when same contact modified in both places
