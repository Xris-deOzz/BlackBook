# Bidirectional Google Contacts Sync Specification

**Document Version:** 2025.12.18.1  
**Created:** 2025-12-18  
**Status:** Draft - Ready for Implementation  
**Phase:** 7 (Post-Deployment Enhancement)

---

## Executive Summary

Enhance BlackBook's Google Contacts integration from one-way import to full bidirectional synchronization. BlackBook becomes the master database, syncing changes to all connected Google accounts while preserving data from both sources.

### Key Principles

1. **BlackBook is Master** - Source of truth for all contact data
2. **Sync to ALL Accounts** - Every contact syncs to all connected Google accounts
3. **Merge, Don't Overwrite** - Conflicts resolved by keeping both values
4. **Archive Before Delete** - Deleted contacts preserved for recovery
5. **Full Audit Trail** - Every sync operation logged for debugging/recovery

---

## Current State

| Capability | Status |
|------------|--------|
| Google → BlackBook import | ✅ Working |
| BlackBook → Google push | ❌ Not implemented |
| Automatic sync | ❌ Manual only |
| Deletion sync | ❌ Not implemented |
| Conflict resolution | ❌ Not implemented |
| Audit trail | ❌ Not implemented |

---

## Target State

| Capability | Target |
|------------|--------|
| Google → BlackBook sync | ✅ Automatic |
| BlackBook → Google sync | ✅ Automatic |
| Sync frequency | 07:00 & 21:00 ET + manual |
| Deletion sync | ✅ Both directions with archive |
| Conflict resolution | ✅ Merge + manual review queue |
| Audit trail | ✅ Full sync_log table |

---

*Note: Full specification content truncated for brevity. See Synology version for complete document.*
