# BlackBook Changelog - December 20, 2025

## Bug Fixes

### Tag Dropdown Not Showing Newly Created Tags
**File:** `app/routers/persons.py`

**Problem:** When a new tag was created in Settings (e.g., "NYC" under Location), it wouldn't appear in person profile tag dropdowns after page refresh, even though it was visible in Settings.

**Root Cause:** The query used INNER JOIN with PersonTag table:
```python
db.query(Tag).join(PersonTag, Tag.id == PersonTag.tag_id).distinct()
```
This excluded tags with 0 people associations since there were no matching rows in PersonTag.

**Solution:** Changed to direct filter on Tag.category:
```python
db.query(Tag).filter(Tag.category.is_(None)).order_by(Tag.name).all()
```
- `Tag.category IS NULL` = People tags (Location, Investor Type, etc.)
- `Tag.category = "Firm Category"` or `"Company Category"` = Organization tags

**Functions Fixed (6 total):**
1. `list_people()` - People list page tag filter
2. `get_batch_tags_modal()` - Batch tag assignment modal
3. `edit_person_form()` - Person edit form
4. `get_tag_manage_widget()` - Person profile tag dropdown
5. `add_tag_to_person()` - After adding tag refresh
6. `remove_tag_from_person()` - After removing tag refresh

---

## Documentation Updates

### Development Architecture Document Updated
**File:** `docs/DEVELOPMENT_ARCHITECTURE_2025.12.20.1.md`

Added:
- Clear data architecture diagram showing where data lives (Windows vs Synology vs GitHub)
- Explanation that GitHub contains CODE ONLY (no .env, no data, no backups)
- Clarification that production data (5,000+ contacts) lives ONLY on Synology
- Database location table explaining DB_HOST settings
- Critical workflow rule prominently displayed at top

---

## Workflow Notes

⚠️ **Issue Identified:** Tag fix was initially made directly on Synology network share, bypassing version control.

**Resolution:** 
1. Copied fix from Synology to `C:\BlackBook`
2. Will commit and push to GitHub
3. Will pull to Synology through proper workflow

**Lesson Learned:** Always follow the workflow:
```
C:\BlackBook → git push → SSH to Synology → git pull → restart Docker
```

---

## Next Steps

1. Commit changes to local Git
2. Push to GitHub
3. SSH to Synology, git pull, restart Docker
4. Test tag dropdown fix in production
5. Begin Google Contacts deduplication fix
