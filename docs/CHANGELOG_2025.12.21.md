# Changelog - 2025.12.21

## Infrastructure Cleanup

### Code Location Consolidation
- **Archived** old OneDrive folder `C:\Users\ossow\OneDrive\PerunsBlackBook` to `C:\BlackBook_Archive\`
- **Single source of truth:** `C:\BlackBook` is now the ONLY code editing location
- Updated MCP server config in `%APPDATA%\Claude\claude_desktop_config.json`
- Created `CLAUDE.md` in project root for Claude Code context

### Git Setup on Synology
- Installed Git Server package on Synology NAS
- Initialized git repo at `/volume1/docker/blackbook`
- Configured GitHub remote with Personal Access Token
- Established deployment workflow: Windows → GitHub → Synology

### Database Configuration
- Exposed PostgreSQL on port 5433 (5432 was in use by system)
- Local development now connects to Synology database via Tailscale
- Updated `.env`: `DB_HOST=bearcave`, `DB_PORT=5433`
- Created backup: `perunsblackbook_backup_2025.12.21.sql`

---

## Tag Management System Fixes

### Tag Subcategories Table
- Repopulated `tag_subcategories` with correct 9 subcategories:
  1. Relationship Origin (#f43f5e)
  2. Classmates (#06b6d4) - includes former Education tags
  3. Holidays (#f97316)
  4. Location (#3b82f6)
  5. Personal (#ec4899)
  6. Professional (#a855f7)
  7. Former Colleagues (#14b8a6)
  8. Social (#22c55e)
  9. Investor Type (#6366f1)

### Tag Assignments Fixed
- Fixed tags with wrong subcategory assignments
- Moved Education tags → Classmates (merged)
- Created 10 new Relationship Origin tags (Family, Friend, Classmate, etc.)
- Fixed `category = NULL` for person tags (was causing UI filter issue)
- Moved Arts → Personal, Competition → Professional

### Investor Type Tags Expanded
- Renamed "Angel" → "Angel Investor"
- Deleted 6 unused generic tags (0 people assigned)
- Added 18 new detailed investor type tags:
  - VC: Early Stage, Growth
  - PE: Buyout, Growth Equity
  - Hedge Funds: Long/Short, Market Neutral, Risk Arb, Distressed, Activist, Macro, Relative Value, Credit, Quant/HFT
  - Other: Family Office, Private Credit, LP, Corporate VC, Sovereign Wealth
- Preserved 3 legacy tags with existing people (Venture VC: 288, PE/Institutional: 68, Angel Investor: 154)

### Headhunter Tags Merged
- Merged "Headhunters" (11 people) into "Headhunter/Recruiter" (48 people)
- Deleted empty "Headhunting Firm" tag

---

## Tag Management UI Enhancements

### People Tags Section
- ✅ Edit button (pencil icon) to rename subcategories
- ✅ Color picker for subcategory default color
- ✅ Apply button to bulk-update all tags in subcategory
- ✅ Delete button for subcategories

### Organization Tags Section
- ✅ Edit button to rename categories
- ✅ Color picker for category color
- ✅ Apply button to bulk-update all tags in category
- ✅ Delete button for categories
- Removed redundant "+Add" button (already in top dropdown)

### New Backend Endpoints
- `PUT /tags/subcategories/{id}` - Update subcategory name/color
- `PUT /tags/categories` - Rename organization tag category
- `POST /tags/categories/apply-color` - Bulk color update
- `POST /tags/categories/delete` - Delete category (tags become uncategorized)

### UI Consistency
- Both People Tags and Organization Tags now have identical control layouts
- Button order: Edit → Color Picker → Apply → Delete

---

## Files Modified

### New Files
- `CLAUDE.md` - Claude Code context and instructions
- `docs/CHANGELOG_2025.12.21.md` - This file
- `docs/SUMMARY_TAG_EDIT_FEATURES.md` - Feature summary
- `docs/TASK_SUBCATEGORY_EDIT_BUTTON.md` - Task instructions (completed)
- `.env.local.backup` - Backup of local environment

### Modified Files
- `app/routers/tags.py` - 4 new API endpoints
- `app/templates/settings/index.html` - Edit buttons, JS functions, UI updates
- `docker-compose.prod.yml` - Exposed port 5433
- Multiple docs/* files - Removed old OneDrive path references

---

## Current State

### Tag Counts
- **People Tags:** 71 tags across 9 subcategories
- **Organization Tags:** 61 tags
- **Investor Type:** 21 tags (3 legacy + 18 new)
- **Relationship Origin:** 10 tags (new)

### Development Workflow
```
Edit: C:\BlackBook
Test: http://localhost:8000 (connects to Synology DB)
Commit: git push origin main
Deploy: ssh xrisnyc@bearcave → git pull → docker restart
```
