# Tag Subcategory Feature - Implementation Tasks

**Version**: 2024.12.21.1
**Status**: In Progress
**Reference**: `docs/TAG_SUBCATEGORY_MAPPING_2024.12.21.1.md`

---

## Overview

This document tracks the implementation of the enhanced tag subcategory system for BlackBook.

**Goals**:
1. Auto-assign subcategories to Google Contact labels during sync
2. Integrate subcategory management into tag list UI (remove standalone section)
3. Provide bulk subcategory assignment for tags without subcategories

---

## Phase 1: Documentation & Mapping ✅

- [x] **Task 1.1**: Create `TAG_SUBCATEGORY_MAPPING_2024.12.21.1.md`
  - Defines all 10 subcategories with colors
  - Maps 80+ Google labels to subcategories
  - Contains Python code ready to copy

---

## Phase 2: Database & Migration

- [x] **Task 2.1**: Update `app/models/tag_subcategory.py` ✅ (2024-12-21)
  - Updated `DEFAULT_SUBCATEGORY_COLORS` dict with 10 subcategories
  - Added `GOOGLE_LABEL_TO_SUBCATEGORY` mapping (80+ labels)
  - Added `SUBCATEGORY_ORDER` list
  - Added helper functions: `get_subcategory_for_label()`, `get_color_for_subcategory()`

- [x] **Task 2.2**: Update migration `a6w45x6y8z90_add_tag_subcategories_table.py` ✅ (2024-12-21)
  - Changed seed data to 10 correct subcategories
  - Used colors from mapping doc
  - Increased name column from 50 to 100 chars

- [x] **Task 2.3**: Test migration locally ✅ (2024-12-21)
  - Migration applied cleanly
  - Server started successfully
  ```bash
  cd C:\BlackBook
  .\venv\Scripts\activate
  python -m alembic upgrade head
  ```

---

## Phase 3: Google Sync Enhancement

- [x] **Task 3.1**: Update `app/services/contacts_service.py` ✅ (2024-12-21)
  - Imported mapping from `tag_subcategory.py`
  - Modified `_get_or_create_tag()` to:
    - Look up label in `GOOGLE_LABEL_TO_SUBCATEGORY`
    - Set `tag.subcategory` if found
    - Set `tag.color` from `SUBCATEGORY_COLORS` if subcategory assigned

- [x] **Task 3.2**: Test sync locally ✅ (2024-12-21)
  - Server runs correctly with sync enhancements

---

## Phase 4: UI Changes

- [x] **Task 4.1**: Update `app/templates/settings/index.html` ✅ (2024-12-21)
  - Integrated subcategory controls in People Tags section headers
  - Color picker, Apply to All button, Delete button in each subcategory header

- [x] **Task 4.2**: Subcategory header controls ✅ (2024-12-21)
  - Integrated directly into index.html (no separate partial needed)
  - Collapsible subcategory headers with color indicators
  - Inline color picker with immediate save
  - Apply to All button applies subcategory color to all tags
  - Delete button removes subcategory (tags keep their names)

- [x] **Task 4.3**: Combined Add button dropdown ✅ (2024-12-21)
  - "Add New" dropdown with "Add Tag" and "Add Subcategory" options
  - Modal for adding new subcategory with color picker

- [x] **Task 4.4**: Bulk assignment UI for Uncategorized ✅ (2024-12-21)
  - Yellow-highlighted "Uncategorized" section with helpful hint
  - Bulk action bar with Select All, subcategory dropdown, Apply Color checkbox
  - Checkboxes in table rows for multi-select
  - Selection counter showing number selected
  - Assign Subcategory button triggers bulk update

- [x] **Task 4.5**: Bulk assignment endpoint ✅ (2024-12-21)
  - `POST /tags/bulk-assign-subcategory` added to `app/routers/tags.py`
  - Accepts JSON: {tag_ids, subcategory, apply_color}
  - Updates multiple tags in single transaction

---

## Phase 5: Deploy & Test

- [ ] **Task 5.1**: Commit and push to GitHub
  ```bash
  cd C:\BlackBook
  git add -A
  git commit -m "Add tag subcategory auto-mapping and UI integration"
  git push origin main
  ```

- [ ] **Task 5.2**: Deploy to Synology
  ```bash
  ssh bearcave
  cd /volume1/docker/blackbook
  git pull origin main
  docker-compose exec blackbook alembic upgrade head
  docker-compose restart blackbook
  ```

- [ ] **Task 5.3**: Test on production
  - Verify subcategories display correctly
  - Test "Apply to All" functionality
  - Test adding new subcategory
  - Test Google sync with new contact

---

## Files to Modify

| File | Phase | Changes |
|------|-------|---------|
| `app/models/tag_subcategory.py` | 2 | Add mappings and constants |
| `alembic/versions/a6w45x6y8z90_*.py` | 2 | Update seed data |
| `app/services/contacts_service.py` | 3 | Add auto-subcategory logic |
| `app/templates/settings/index.html` | 4 | Remove standalone section, update UI |
| `app/templates/tags/_tag_subcategory_header.html` | 4 | New partial template |
| `app/routers/tags.py` | 4 | Add bulk assignment endpoint |

---

## Testing Checklist

### Local Testing (Windows)
- [ ] Migration runs without errors
- [ ] Settings page loads without errors
- [ ] Subcategory headers display with color and actions
- [ ] "Apply to All" updates tag colors
- [ ] "Add Tag" dropdown works
- [ ] Bulk subcategory assignment works

### Production Testing (Synology)
- [ ] Migration runs without errors
- [ ] Existing tags retain their data
- [ ] Google sync assigns subcategories to new tags
- [ ] UI displays 82+ tags correctly grouped

---

## Rollback Plan

If issues occur:
1. Revert migration: `alembic downgrade -1`
2. Git revert: `git revert HEAD`
3. Restart Docker: `docker-compose restart blackbook`

---

## Notes for Claude Code

If using Claude Code to implement any tasks:
1. Read this file first for context
2. Read `TAG_SUBCATEGORY_MAPPING_2024.12.21.1.md` for the actual mappings
3. Follow the existing code patterns in `contacts_service.py`
4. Test locally before committing
5. Update this checklist when tasks are completed

