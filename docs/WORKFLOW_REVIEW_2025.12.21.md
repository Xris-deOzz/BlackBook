# Development Workflow Review - 2025.12.21

## Current Workflow
```
C:\BlackBook (edit) → localhost:8000 (test) → GitHub (push) → Synology (pull/deploy)
```

## Identified Issues & Mitigations

### 1. Date Confusion in Claude Code
**Issue:** Claude Code created files with 2024 instead of 2025
**Fix:** Added explicit date reminder at top of CLAUDE.md
**Status:** ✅ Fixed

### 2. Wrong Working Directory in VS Code
**Issue:** Claude Code searched in old OneDrive paths
**Fix:** Must open VS Code specifically in `C:\BlackBook` folder
**Prevention:** Added note to CLAUDE.md about this

### 3. No Database Migrations for Tag Changes
**Issue:** Today's tag subcategory changes were manual SQL, not migrations
**Risk:** Schema drift between dev/prod, no version control for DB state
**Recommendation:** For future schema changes, create proper Alembic migrations

### 4. Tag Taxonomy Not in Version Control
**Issue:** Source Excel file `BlackBook_Tag_Taxonomy_v2_clean.xlsx` not in repo
**Risk:** No record of expected tag structure
**Recommendation:** Export to CSV or JSON and commit, or add Excel to repo

### 5. Environment File in Repo
**Issue:** `.env.local.backup` was committed (contains credentials)
**Risk:** Potential credential exposure
**Recommendation:** Add `*.backup` to `.gitignore`

### 6. Completed Task Docs Not Archived
**Issue:** Old task/prompt docs cluttered docs/ folder
**Fix:** Moved completed docs to `docs/archive/`
**Status:** ✅ Fixed

### 7. No Automated Testing
**Issue:** Manual browser testing only
**Risk:** Regressions not caught before deploy
**Recommendation:** Add basic pytest tests for critical endpoints

### 8. Single Point of Failure - Database
**Issue:** Local dev uses Synology production database
**Risk:** Dev testing could corrupt production data
**Recommendation:** Consider separate test database for destructive testing

---

## Process Checklist for Future Development

### Before Starting Work
- [ ] Ensure VS Code is open in `C:\BlackBook`
- [ ] Pull latest from GitHub: `git pull origin main`
- [ ] Create database backup if schema changes planned

### During Development
- [ ] Test locally at http://localhost:8000
- [ ] Create Alembic migration for schema changes
- [ ] Use YYYY.MM.DD format (2025, not 2024!)

### Before Commit
- [ ] Check no `.env` or credential files staged
- [ ] Update/create CHANGELOG entry
- [ ] Move completed task docs to archive/

### Deployment
- [ ] `git push origin main`
- [ ] SSH to Synology and pull
- [ ] Run migrations if schema changed
- [ ] Verify app is healthy: `docker logs blackbook-app --tail 20`

### After Deployment
- [ ] Test critical paths in production
- [ ] Document any manual DB changes needed
