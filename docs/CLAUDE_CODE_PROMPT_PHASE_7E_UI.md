# Claude Code Prompt: Phase 7E - Sync UI Components

**Document Version:** 2025.12.18.2  
**Created:** 2025-12-18  
**Prerequisites:** Phases 7A-7D are COMPLETE (migration, models, service, scheduler, API)

---

## Overview

Implement the UI components for bidirectional Google Contacts sync. The backend is fully functional - this phase adds the user interface.

## Project Context

- **Tech Stack:** Python 3.11, FastAPI, PostgreSQL, SQLAlchemy, HTMX, TailwindCSS
- **Location:** `Synology via SSH` (Synology NAS via MCP)
- **Existing Settings Page:** `app/templates/settings/index.html` (has 9 tabs, need to add 10th)
- **Sync API:** `app/routers/sync.py` (all endpoints already working)
- **Settings Router:** `app/routers/settings.py` (needs sync tab handler)

---

## What's Already Done

✅ Database tables created (sync_log, archived_persons, sync_review_queue, sync_settings)
✅ SQLAlchemy models (SyncLog, ArchivedPerson, SyncReviewQueue, SyncSettings)
✅ BidirectionalSyncService with full implementation
✅ APScheduler for 7am/9pm sync jobs
✅ All API endpoints in /api/sync/*
✅ Scheduler starts on app startup

---

## Tasks to Implement

### Task 7E.1: Add Sync Tab to Settings Page

**File:** `app/templates/settings/index.html`

Add a 10th tab "Sync" after "AI Chat" in the tab navigation:

```html
<a href="/settings?tab=sync"
   class="{% if active_tab == 'sync' %}border-blackbook-600 text-blackbook-900{% else %}border-transparent text-blackbook-500 hover:text-blackbook-700 hover:border-blackbook-300{% endif %} whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm">
    Contacts Sync
</a>
```

Add the tab content section (after the `ai-chat` elif block):

```html
{% elif active_tab == 'sync' %}
<!-- Contacts Sync Tab -->
<div class="space-y-6">
    <!-- Sync Status Card -->
    <div class="bg-white rounded-lg shadow-md p-6">
        <div class="flex items-center justify-between mb-4">
            <div>
                <h2 class="text-lg font-semibold text-blackbook-900">Bidirectional Contacts Sync</h2>
                <p class="text-sm text-blackbook-500 mt-1">
                    Sync contacts between BlackBook and all connected Google accounts
                </p>
            </div>
            <div class="flex items-center gap-2">
                {% if sync_status.scheduler_running %}
                <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
                    <span class="w-2 h-2 bg-green-500 rounded-full mr-1.5 animate-pulse"></span>
                    Scheduler Active
                </span>
                {% else %}
                <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-yellow-100 text-yellow-800">
                    Scheduler Inactive
                </span>
                {% endif %}
            </div>
        </div>

        <!-- Last Sync Info -->
        <div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
            <div class="bg-blackbook-50 rounded-lg p-4">
                <p class="text-xs text-blackbook-500 uppercase">Last Sync</p>
                <p class="text-sm font-medium text-blackbook-900 mt-1">
                    {{ sync_status.last_sync | default('Never', true) }}
                </p>
            </div>
            <div class="bg-blackbook-50 rounded-lg p-4">
                <p class="text-xs text-blackbook-500 uppercase">Status</p>
                <p class="text-sm font-medium mt-1 {% if sync_status.last_sync_status == 'success' %}text-green-600{% elif sync_status.last_sync_status == 'failed' %}text-red-600{% else %}text-blackbook-900{% endif %}">
                    {{ sync_status.last_sync_status | default('N/A', true) | title }}
                </p>
            </div>
            <div class="bg-blackbook-50 rounded-lg p-4">
                <p class="text-xs text-blackbook-500 uppercase">Next Morning Sync</p>
                <p class="text-sm font-medium text-blackbook-900 mt-1">
                    {{ sync_status.schedule.time_1 }} {{ sync_status.schedule.timezone }}
                </p>
            </div>
            <div class="bg-blackbook-50 rounded-lg p-4">
                <p class="text-xs text-blackbook-500 uppercase">Next Evening Sync</p>
                <p class="text-sm font-medium text-blackbook-900 mt-1">
                    {{ sync_status.schedule.time_2 }} {{ sync_status.schedule.timezone }}
                </p>
            </div>
        </div>

        <!-- Manual Sync Button -->
        <div class="flex items-center gap-4">
            <button hx-post="/api/sync/now"
                    hx-target="#sync-result"
                    hx-swap="innerHTML"
                    hx-indicator="#sync-spinner"
                    class="inline-flex items-center px-4 py-2 bg-blue-600 text-white font-medium rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2">
                <svg id="sync-spinner" class="htmx-indicator animate-spin -ml-1 mr-2 h-4 w-4 text-white" fill="none" viewBox="0 0 24 24">
                    <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                    <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                🔄 Sync Now
            </button>
            <div id="sync-result"></div>
        </div>

        {% if sync_status.pending_reviews > 0 %}
        <div class="mt-4 p-4 bg-orange-50 rounded-lg">
            <div class="flex items-center">
                <svg class="h-5 w-5 text-orange-400 mr-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/>
                </svg>
                <p class="text-sm text-orange-700">
                    <strong>{{ sync_status.pending_reviews }}</strong> conflict(s) need review.
                    <a href="/settings/sync/review" class="underline hover:text-orange-900">Review now →</a>
                </p>
            </div>
        </div>
        {% endif %}
    </div>

    <!-- Sync Settings Card -->
    <div class="bg-white rounded-lg shadow-md p-6">
        <h3 class="text-base font-semibold text-blackbook-900 mb-4">Sync Settings</h3>
        
        <!-- Auto-sync Toggle -->
        <div class="flex items-center justify-between py-3 border-b border-blackbook-200">
            <div>
                <p class="font-medium text-blackbook-900">Automatic Sync</p>
                <p class="text-sm text-blackbook-500">Sync contacts at scheduled times</p>
            </div>
            <label class="relative inline-flex items-center cursor-pointer">
                <input type="checkbox" 
                       id="auto-sync-toggle"
                       {% if sync_settings.auto_sync_enabled %}checked{% endif %}
                       hx-put="/api/sync/settings"
                       hx-vals='js:{"auto_sync_enabled": document.getElementById("auto-sync-toggle").checked}'
                       hx-swap="none"
                       class="sr-only peer">
                <div class="w-11 h-6 bg-blackbook-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-blackbook-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
            </label>
        </div>

        <!-- Schedule Times -->
        <div class="grid grid-cols-2 gap-4 py-4 border-b border-blackbook-200">
            <div>
                <label class="block text-sm font-medium text-blackbook-700 mb-1">Morning Sync Time</label>
                <input type="time" 
                       id="sync-time-1"
                       value="{{ sync_settings.sync_time_1 }}"
                       class="block w-full rounded-md border-blackbook-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 text-sm">
            </div>
            <div>
                <label class="block text-sm font-medium text-blackbook-700 mb-1">Evening Sync Time</label>
                <input type="time" 
                       id="sync-time-2"
                       value="{{ sync_settings.sync_time_2 }}"
                       class="block w-full rounded-md border-blackbook-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 text-sm">
            </div>
        </div>

        <!-- Timezone -->
        <div class="py-4 border-b border-blackbook-200">
            <label class="block text-sm font-medium text-blackbook-700 mb-1">Timezone</label>
            <select id="sync-timezone"
                    class="block w-full rounded-md border-blackbook-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 text-sm">
                {% for tz_value, tz_display in sync_timezones %}
                <option value="{{ tz_value }}" {% if sync_settings.sync_timezone == tz_value %}selected{% endif %}>
                    {{ tz_display }}
                </option>
                {% endfor %}
            </select>
        </div>

        <!-- Archive Retention -->
        <div class="py-4 border-b border-blackbook-200">
            <label class="block text-sm font-medium text-blackbook-700 mb-1">Archive Retention</label>
            <div class="flex items-center gap-2">
                <input type="number" 
                       id="archive-retention"
                       value="{{ sync_settings.archive_retention_days }}"
                       min="1" max="365"
                       class="block w-24 rounded-md border-blackbook-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 text-sm">
                <span class="text-sm text-blackbook-500">days</span>
            </div>
            <p class="text-xs text-blackbook-400 mt-1">Deleted contacts are archived and can be restored within this period</p>
        </div>

        <!-- Save Button -->
        <div class="pt-4">
            <button onclick="saveSyncSettings()"
                    class="inline-flex items-center px-4 py-2 bg-blackbook-600 text-white font-medium rounded-md hover:bg-blackbook-700 focus:outline-none focus:ring-2 focus:ring-blackbook-500 focus:ring-offset-2">
                Save Settings
            </button>
            <span id="settings-save-status" class="ml-3 text-sm"></span>
        </div>
    </div>

    <!-- Quick Links -->
    <div class="bg-white rounded-lg shadow-md p-6">
        <h3 class="text-base font-semibold text-blackbook-900 mb-4">Sync Management</h3>
        <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
            <a href="/settings/sync/log" 
               class="flex items-center p-4 bg-blackbook-50 rounded-lg hover:bg-blackbook-100 transition-colors">
                <svg class="w-8 h-8 text-blackbook-400 mr-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/>
                </svg>
                <div>
                    <p class="font-medium text-blackbook-900">Sync Log</p>
                    <p class="text-sm text-blackbook-500">View sync history</p>
                </div>
            </a>
            <a href="/settings/sync/review" 
               class="flex items-center p-4 bg-blackbook-50 rounded-lg hover:bg-blackbook-100 transition-colors">
                <svg class="w-8 h-8 text-blackbook-400 mr-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4"/>
                </svg>
                <div>
                    <p class="font-medium text-blackbook-900">Review Queue</p>
                    <p class="text-sm text-blackbook-500">
                        {% if sync_status.pending_reviews > 0 %}
                        <span class="text-orange-600">{{ sync_status.pending_reviews }} pending</span>
                        {% else %}
                        No conflicts
                        {% endif %}
                    </p>
                </div>
            </a>
            <a href="/settings/sync/archive" 
               class="flex items-center p-4 bg-blackbook-50 rounded-lg hover:bg-blackbook-100 transition-colors">
                <svg class="w-8 h-8 text-blackbook-400 mr-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 8h14M5 8a2 2 0 110-4h14a2 2 0 110 4M5 8v10a2 2 0 002 2h10a2 2 0 002-2V8m-9 4h4"/>
                </svg>
                <div>
                    <p class="font-medium text-blackbook-900">Archive</p>
                    <p class="text-sm text-blackbook-500">Restore deleted contacts</p>
                </div>
            </a>
        </div>
    </div>
</div>

<script>
function saveSyncSettings() {
    const data = {
        sync_time_1: document.getElementById('sync-time-1').value,
        sync_time_2: document.getElementById('sync-time-2').value,
        sync_timezone: document.getElementById('sync-timezone').value,
        archive_retention_days: parseInt(document.getElementById('archive-retention').value)
    };
    
    fetch('/api/sync/settings', {
        method: 'PUT',
        headers: {'Content-Type': 'application/x-www-form-urlencoded'},
        body: new URLSearchParams(data)
    })
    .then(response => response.json())
    .then(result => {
        document.getElementById('settings-save-status').innerHTML = 
            '<span class="text-green-600">✓ Settings saved</span>';
        setTimeout(() => {
            document.getElementById('settings-save-status').innerHTML = '';
        }, 3000);
    })
    .catch(error => {
        document.getElementById('settings-save-status').innerHTML = 
            '<span class="text-red-600">Error saving settings</span>';
    });
}
</script>
{% endif %}
```

---

### Task 7E.2: Update Settings Router

**File:** `app/routers/settings.py`

Add imports at top:
```python
from app.models.sync_settings import SyncSettings, SYNC_TIMEZONES
from app.models.sync_review import SyncReviewQueue
from app.services.scheduler import is_scheduler_running
```

In the `get_settings_page()` function, add handling for the sync tab:

```python
# Add to the context dict for sync tab
if active_tab == "sync":
    # Get sync settings
    sync_settings = db.query(SyncSettings).first()
    if not sync_settings:
        # Create default settings if not exists
        sync_settings = SyncSettings()
        db.add(sync_settings)
        db.commit()
    
    # Get sync status from API
    from app.models.sync_log import SyncLog
    last_log = db.query(SyncLog).order_by(SyncLog.created_at.desc()).first()
    pending_reviews = db.query(SyncReviewQueue).filter_by(status="pending").count()
    
    context["sync_settings"] = {
        "auto_sync_enabled": sync_settings.auto_sync_enabled,
        "sync_time_1": sync_settings.sync_time_1_str,
        "sync_time_2": sync_settings.sync_time_2_str,
        "sync_timezone": sync_settings.sync_timezone,
        "archive_retention_days": sync_settings.archive_retention_days,
    }
    context["sync_timezones"] = SYNC_TIMEZONES
    context["sync_status"] = {
        "scheduler_running": is_scheduler_running(),
        "last_sync": last_log.created_at.strftime('%b %d, %Y at %I:%M %p') if last_log else None,
        "last_sync_status": last_log.status if last_log else None,
        "pending_reviews": pending_reviews,
        "schedule": {
            "time_1": sync_settings.sync_time_1_str,
            "time_2": sync_settings.sync_time_2_str,
            "timezone": sync_settings.sync_timezone,
        }
    }
```

---

### Task 7E.3: Create Sync Log Page

**File:** `app/templates/settings/sync_log.html`

```html
{% extends "base.html" %}

{% block breadcrumb %}
<nav class="bg-white border-b border-blackbook-200">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-3">
        <ol class="flex items-center space-x-2 text-sm">
            <li><a href="/" class="text-blackbook-500 hover:text-blackbook-700">Home</a></li>
            <li><svg class="h-4 w-4 text-blackbook-400" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z" clip-rule="evenodd"/></svg></li>
            <li><a href="/settings?tab=sync" class="text-blackbook-500 hover:text-blackbook-700">Sync Settings</a></li>
            <li><svg class="h-4 w-4 text-blackbook-400" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z" clip-rule="evenodd"/></svg></li>
            <li class="text-blackbook-900 font-medium">Sync Log</li>
        </ol>
    </div>
</nav>
{% endblock %}

{% block content %}
<div class="space-y-6">
    <div class="flex items-center justify-between">
        <div>
            <h1 class="text-2xl font-bold text-blackbook-900">Sync Log</h1>
            <p class="text-blackbook-500 mt-1">History of all sync operations</p>
        </div>
        <div class="flex items-center gap-4">
            <!-- Filters -->
            <select id="status-filter" onchange="filterLogs()" 
                    class="rounded-md border-blackbook-300 text-sm">
                <option value="">All Statuses</option>
                <option value="success">Success</option>
                <option value="failed">Failed</option>
                <option value="pending_review">Pending Review</option>
            </select>
            <select id="direction-filter" onchange="filterLogs()"
                    class="rounded-md border-blackbook-300 text-sm">
                <option value="">All Directions</option>
                <option value="google_to_blackbook">Google → BlackBook</option>
                <option value="blackbook_to_google">BlackBook → Google</option>
            </select>
        </div>
    </div>

    <div class="bg-white rounded-lg shadow-md overflow-hidden">
        <div id="sync-log-table"
             hx-get="/settings/sync/log/data"
             hx-trigger="load"
             hx-swap="innerHTML">
            <div class="p-8 text-center text-blackbook-400">
                <svg class="animate-spin mx-auto h-8 w-8" fill="none" viewBox="0 0 24 24">
                    <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                    <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path>
                </svg>
                <p class="mt-2">Loading sync log...</p>
            </div>
        </div>
    </div>
</div>

<script>
function filterLogs() {
    const status = document.getElementById('status-filter').value;
    const direction = document.getElementById('direction-filter').value;
    let url = '/settings/sync/log/data?';
    if (status) url += 'status=' + status + '&';
    if (direction) url += 'direction=' + direction;
    htmx.ajax('GET', url, '#sync-log-table');
}
</script>
{% endblock %}
```

**File:** `app/templates/settings/_sync_log_table.html` (partial for HTMX)

```html
<table class="min-w-full divide-y divide-blackbook-200">
    <thead class="bg-blackbook-50">
        <tr>
            <th class="px-6 py-3 text-left text-xs font-medium text-blackbook-500 uppercase">Time</th>
            <th class="px-6 py-3 text-left text-xs font-medium text-blackbook-500 uppercase">Person</th>
            <th class="px-6 py-3 text-left text-xs font-medium text-blackbook-500 uppercase">Direction</th>
            <th class="px-6 py-3 text-left text-xs font-medium text-blackbook-500 uppercase">Action</th>
            <th class="px-6 py-3 text-left text-xs font-medium text-blackbook-500 uppercase">Status</th>
            <th class="px-6 py-3 text-left text-xs font-medium text-blackbook-500 uppercase">Account</th>
        </tr>
    </thead>
    <tbody class="bg-white divide-y divide-blackbook-200">
        {% for log in logs %}
        <tr class="hover:bg-blackbook-50">
            <td class="px-6 py-4 whitespace-nowrap text-sm text-blackbook-500">
                {{ log.created_at }}
            </td>
            <td class="px-6 py-4 whitespace-nowrap">
                {% if log.person_name %}
                <a href="/people/{{ log.person_id }}" class="text-blue-600 hover:underline">{{ log.person_name }}</a>
                {% else %}
                <span class="text-blackbook-400">-</span>
                {% endif %}
            </td>
            <td class="px-6 py-4 whitespace-nowrap text-sm">
                {% if log.direction == 'google_to_blackbook' %}
                <span class="text-blue-600">Google → BlackBook</span>
                {% else %}
                <span class="text-green-600">BlackBook → Google</span>
                {% endif %}
            </td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-blackbook-900">
                {{ log.action | title }}
            </td>
            <td class="px-6 py-4 whitespace-nowrap">
                {% if log.status == 'success' %}
                <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">Success</span>
                {% elif log.status == 'failed' %}
                <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-800" title="{{ log.error_message }}">Failed</span>
                {% else %}
                <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-yellow-100 text-yellow-800">Review</span>
                {% endif %}
            </td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-blackbook-500">
                {{ log.google_account | default('-', true) }}
            </td>
        </tr>
        {% else %}
        <tr>
            <td colspan="6" class="px-6 py-8 text-center text-blackbook-500">
                No sync operations recorded yet
            </td>
        </tr>
        {% endfor %}
    </tbody>
</table>

{% if pages > 1 %}
<div class="bg-blackbook-50 px-6 py-3 flex items-center justify-between border-t border-blackbook-200">
    <p class="text-sm text-blackbook-500">
        Showing page {{ page }} of {{ pages }} ({{ total }} total)
    </p>
    <div class="flex gap-2">
        {% if page > 1 %}
        <button hx-get="/settings/sync/log/data?page={{ page - 1 }}" hx-target="#sync-log-table"
                class="px-3 py-1 text-sm bg-white border rounded hover:bg-blackbook-50">Previous</button>
        {% endif %}
        {% if page < pages %}
        <button hx-get="/settings/sync/log/data?page={{ page + 1 }}" hx-target="#sync-log-table"
                class="px-3 py-1 text-sm bg-white border rounded hover:bg-blackbook-50">Next</button>
        {% endif %}
    </div>
</div>
{% endif %}
```

---

### Task 7E.4: Create Review Queue Page

**File:** `app/templates/settings/sync_review.html`

```html
{% extends "base.html" %}

{% block breadcrumb %}
<nav class="bg-white border-b border-blackbook-200">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-3">
        <ol class="flex items-center space-x-2 text-sm">
            <li><a href="/" class="text-blackbook-500 hover:text-blackbook-700">Home</a></li>
            <li><svg class="h-4 w-4 text-blackbook-400" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z" clip-rule="evenodd"/></svg></li>
            <li><a href="/settings?tab=sync" class="text-blackbook-500 hover:text-blackbook-700">Sync Settings</a></li>
            <li><svg class="h-4 w-4 text-blackbook-400" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z" clip-rule="evenodd"/></svg></li>
            <li class="text-blackbook-900 font-medium">Review Queue</li>
        </ol>
    </div>
</nav>
{% endblock %}

{% block content %}
<div class="space-y-6">
    <div>
        <h1 class="text-2xl font-bold text-blackbook-900">Sync Review Queue</h1>
        <p class="text-blackbook-500 mt-1">Resolve conflicts between BlackBook and Google Contacts</p>
    </div>

    {% if review_items %}
    <div class="space-y-4">
        {% for item in review_items %}
        <div id="review-{{ item.id }}" class="bg-white rounded-lg shadow-md p-6">
            <div class="flex items-start justify-between mb-4">
                <div>
                    <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-orange-100 text-orange-800 mb-2">
                        {{ item.review_type | replace('_', ' ') | title }}
                    </span>
                    <h3 class="text-lg font-semibold text-blackbook-900">
                        {% if item.person_name %}{{ item.person_name }}{% else %}New Contact{% endif %}
                    </h3>
                    <p class="text-sm text-blackbook-500">From: {{ item.google_account }}</p>
                </div>
                <p class="text-xs text-blackbook-400">{{ item.created_at }}</p>
            </div>

            <!-- Comparison Table -->
            <div class="grid grid-cols-2 gap-4 mb-4">
                <div class="bg-blue-50 rounded-lg p-4">
                    <h4 class="text-sm font-medium text-blue-800 mb-2">Google Data</h4>
                    <dl class="text-sm space-y-1">
                        <div><dt class="inline text-blue-600">Name:</dt> <dd class="inline">{{ item.google_data.full_name }}</dd></div>
                        {% if item.google_data.first_name %}
                        <div><dt class="inline text-blue-600">First:</dt> <dd class="inline">{{ item.google_data.first_name }}</dd></div>
                        {% endif %}
                        {% if item.google_data.last_name %}
                        <div><dt class="inline text-blue-600">Last:</dt> <dd class="inline">{{ item.google_data.last_name }}</dd></div>
                        {% endif %}
                    </dl>
                </div>
                <div class="bg-green-50 rounded-lg p-4">
                    <h4 class="text-sm font-medium text-green-800 mb-2">BlackBook Data</h4>
                    <dl class="text-sm space-y-1">
                        <div><dt class="inline text-green-600">Name:</dt> <dd class="inline">{{ item.blackbook_data.full_name }}</dd></div>
                        {% if item.blackbook_data.first_name %}
                        <div><dt class="inline text-green-600">First:</dt> <dd class="inline">{{ item.blackbook_data.first_name }}</dd></div>
                        {% endif %}
                        {% if item.blackbook_data.last_name %}
                        <div><dt class="inline text-green-600">Last:</dt> <dd class="inline">{{ item.blackbook_data.last_name }}</dd></div>
                        {% endif %}
                    </dl>
                </div>
            </div>

            <!-- Action Buttons -->
            <div class="flex items-center gap-3">
                <button hx-post="/api/sync/review/{{ item.id }}/resolve"
                        hx-vals='{"choice": "blackbook"}'
                        hx-target="#review-{{ item.id }}"
                        hx-swap="outerHTML"
                        class="px-4 py-2 bg-green-600 text-white text-sm font-medium rounded-md hover:bg-green-700">
                    Use BlackBook
                </button>
                <button hx-post="/api/sync/review/{{ item.id }}/resolve"
                        hx-vals='{"choice": "google"}'
                        hx-target="#review-{{ item.id }}"
                        hx-swap="outerHTML"
                        class="px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-md hover:bg-blue-700">
                    Use Google
                </button>
                <button hx-post="/api/sync/review/{{ item.id }}/resolve"
                        hx-vals='{"choice": "both"}'
                        hx-target="#review-{{ item.id }}"
                        hx-swap="outerHTML"
                        class="px-4 py-2 bg-purple-600 text-white text-sm font-medium rounded-md hover:bg-purple-700">
                    Keep Both
                </button>
                <button hx-post="/api/sync/review/{{ item.id }}/dismiss"
                        hx-target="#review-{{ item.id }}"
                        hx-swap="outerHTML"
                        class="px-4 py-2 bg-blackbook-200 text-blackbook-700 text-sm font-medium rounded-md hover:bg-blackbook-300">
                    Dismiss
                </button>
            </div>
        </div>
        {% endfor %}
    </div>
    {% else %}
    <div class="bg-white rounded-lg shadow-md p-12 text-center">
        <svg class="mx-auto h-12 w-12 text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/>
        </svg>
        <h3 class="mt-4 text-lg font-medium text-blackbook-900">No conflicts to review</h3>
        <p class="mt-2 text-sm text-blackbook-500">All sync operations are up to date</p>
    </div>
    {% endif %}
</div>
{% endblock %}
```

---

### Task 7E.5: Create Archive Browser Page

**File:** `app/templates/settings/sync_archive.html`

```html
{% extends "base.html" %}

{% block breadcrumb %}
<nav class="bg-white border-b border-blackbook-200">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-3">
        <ol class="flex items-center space-x-2 text-sm">
            <li><a href="/" class="text-blackbook-500 hover:text-blackbook-700">Home</a></li>
            <li><svg class="h-4 w-4 text-blackbook-400" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z" clip-rule="evenodd"/></svg></li>
            <li><a href="/settings?tab=sync" class="text-blackbook-500 hover:text-blackbook-700">Sync Settings</a></li>
            <li><svg class="h-4 w-4 text-blackbook-400" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z" clip-rule="evenodd"/></svg></li>
            <li class="text-blackbook-900 font-medium">Archive</li>
        </ol>
    </div>
</nav>
{% endblock %}

{% block content %}
<div class="space-y-6">
    <div>
        <h1 class="text-2xl font-bold text-blackbook-900">Archived Contacts</h1>
        <p class="text-blackbook-500 mt-1">Deleted contacts that can be restored</p>
    </div>

    {% if archived %}
    <div class="bg-white rounded-lg shadow-md overflow-hidden">
        <table class="min-w-full divide-y divide-blackbook-200">
            <thead class="bg-blackbook-50">
                <tr>
                    <th class="px-6 py-3 text-left text-xs font-medium text-blackbook-500 uppercase">Name</th>
                    <th class="px-6 py-3 text-left text-xs font-medium text-blackbook-500 uppercase">Deleted From</th>
                    <th class="px-6 py-3 text-left text-xs font-medium text-blackbook-500 uppercase">Archived</th>
                    <th class="px-6 py-3 text-left text-xs font-medium text-blackbook-500 uppercase">Expires</th>
                    <th class="px-6 py-3 text-right text-xs font-medium text-blackbook-500 uppercase">Actions</th>
                </tr>
            </thead>
            <tbody class="bg-white divide-y divide-blackbook-200">
                {% for item in archived %}
                <tr id="archive-{{ item.id }}" class="hover:bg-blackbook-50">
                    <td class="px-6 py-4 whitespace-nowrap">
                        <div class="font-medium text-blackbook-900">{{ item.full_name }}</div>
                        {% if item.person_data.email %}
                        <div class="text-sm text-blackbook-500">{{ item.person_data.email }}</div>
                        {% endif %}
                    </td>
                    <td class="px-6 py-4 whitespace-nowrap text-sm">
                        {% if item.deleted_from == 'google' %}
                        <span class="text-blue-600">Google</span>
                        {% else %}
                        <span class="text-green-600">BlackBook</span>
                        {% endif %}
                    </td>
                    <td class="px-6 py-4 whitespace-nowrap text-sm text-blackbook-500">
                        {{ item.archived_at }}
                    </td>
                    <td class="px-6 py-4 whitespace-nowrap text-sm text-blackbook-500">
                        {{ item.expires_at }}
                    </td>
                    <td class="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                        <button hx-post="/api/sync/archive/{{ item.id }}/restore"
                                hx-target="#archive-{{ item.id }}"
                                hx-swap="outerHTML"
                                class="text-blue-600 hover:text-blue-900 mr-3">
                            Restore
                        </button>
                        <button hx-delete="/api/sync/archive/{{ item.id }}"
                                hx-target="#archive-{{ item.id }}"
                                hx-swap="outerHTML"
                                hx-confirm="Permanently delete this archived contact? This cannot be undone."
                                class="text-red-600 hover:text-red-900">
                            Delete
                        </button>
                    </td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
    {% else %}
    <div class="bg-white rounded-lg shadow-md p-12 text-center">
        <svg class="mx-auto h-12 w-12 text-blackbook-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 8h14M5 8a2 2 0 110-4h14a2 2 0 110 4M5 8v10a2 2 0 002 2h10a2 2 0 002-2V8m-9 4h4"/>
        </svg>
        <h3 class="mt-4 text-lg font-medium text-blackbook-900">No archived contacts</h3>
        <p class="mt-2 text-sm text-blackbook-500">Deleted contacts will appear here for {{ retention_days }} days</p>
    </div>
    {% endif %}
</div>
{% endblock %}
```

---

### Task 7E.6: Add Routes for Sub-Pages

**File:** `app/routers/settings.py`

Add these routes:

```python
@router.get("/settings/sync/log", response_class=HTMLResponse)
async def sync_log_page(request: Request, db: Session = Depends(get_db)):
    """Sync log page."""
    return templates.TemplateResponse(
        request,
        "settings/sync_log.html",
        {"title": "Sync Log - Settings"},
    )


@router.get("/settings/sync/log/data", response_class=HTMLResponse)
async def sync_log_data(
    request: Request,
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    status: str | None = None,
    direction: str | None = None,
):
    """Sync log data partial for HTMX."""
    from app.models.sync_log import SyncLog
    
    query = db.query(SyncLog).order_by(SyncLog.created_at.desc())
    if status:
        query = query.filter(SyncLog.status == status)
    if direction:
        query = query.filter(SyncLog.direction == direction)
    
    per_page = 50
    total = query.count()
    logs = query.offset((page - 1) * per_page).limit(per_page).all()
    
    return templates.TemplateResponse(
        request,
        "settings/_sync_log_table.html",
        {
            "logs": [
                {
                    "id": str(log.id),
                    "person_id": str(log.person_id) if log.person_id else None,
                    "person_name": log.person.full_name if log.person else None,
                    "direction": log.direction,
                    "action": log.action,
                    "status": log.status,
                    "error_message": log.error_message,
                    "google_account": log.google_account.email if log.google_account else None,
                    "created_at": log.created_at.strftime('%b %d, %Y %I:%M %p'),
                }
                for log in logs
            ],
            "page": page,
            "pages": (total + per_page - 1) // per_page,
            "total": total,
        },
    )


@router.get("/settings/sync/review", response_class=HTMLResponse)
async def sync_review_page(request: Request, db: Session = Depends(get_db)):
    """Review queue page."""
    from app.models.sync_review import SyncReviewQueue
    
    items = db.query(SyncReviewQueue).filter_by(status="pending").order_by(
        SyncReviewQueue.created_at.desc()
    ).all()
    
    return templates.TemplateResponse(
        request,
        "settings/sync_review.html",
        {
            "title": "Review Queue - Settings",
            "review_items": [
                {
                    "id": str(item.id),
                    "person_id": str(item.person_id) if item.person_id else None,
                    "person_name": item.person.full_name if item.person else None,
                    "review_type": item.review_type,
                    "google_account": item.google_account.email if item.google_account else None,
                    "google_data": item.google_data,
                    "blackbook_data": item.blackbook_data,
                    "created_at": item.created_at.strftime('%b %d, %Y %I:%M %p'),
                }
                for item in items
            ],
        },
    )


@router.get("/settings/sync/archive", response_class=HTMLResponse)
async def sync_archive_page(request: Request, db: Session = Depends(get_db)):
    """Archive browser page."""
    from app.models.archived_person import ArchivedPerson
    from app.models.sync_settings import SyncSettings
    
    archived = db.query(ArchivedPerson).filter(
        ArchivedPerson.restored_at.is_(None)
    ).order_by(ArchivedPerson.archived_at.desc()).all()
    
    settings = db.query(SyncSettings).first()
    
    return templates.TemplateResponse(
        request,
        "settings/sync_archive.html",
        {
            "title": "Archive - Settings",
            "archived": [
                {
                    "id": str(item.id),
                    "full_name": item.display_name,
                    "person_data": item.person_data,
                    "deleted_from": item.deleted_from,
                    "archived_at": item.archived_at.strftime('%b %d, %Y'),
                    "expires_at": item.expires_at.strftime('%b %d, %Y') if item.expires_at else "Never",
                }
                for item in archived
            ],
            "retention_days": settings.archive_retention_days if settings else 90,
        },
    )
```

---

### Task 7E.7: Add Person Card Sync Badge (Optional Enhancement)

**File:** Find person card template (likely `app/templates/persons/_card.html` or similar)

Add near the person name:

```html
{% if person.sync_enabled %}
<span class="ml-2" title="Syncs to Google Contacts">
    {% if person.sync_status == 'synced' %}
    <span class="text-green-500">✓</span>
    {% elif person.sync_status == 'pending' %}
    <span class="text-yellow-500">⏳</span>
    {% elif person.sync_status == 'error' %}
    <span class="text-red-500">⚠</span>
    {% endif %}
</span>
{% endif %}
```

---

## Testing Checklist

After implementation, verify:

- [ ] Sync tab appears in Settings page
- [ ] Sync status card shows scheduler state and last sync
- [ ] "Sync Now" button triggers sync and shows result
- [ ] Auto-sync toggle updates setting
- [ ] Schedule times can be changed and saved
- [ ] Timezone selector works
- [ ] Archive retention can be changed
- [ ] Sync Log page loads with pagination
- [ ] Filters work on Sync Log page
- [ ] Review Queue shows pending conflicts
- [ ] Resolve/Dismiss buttons work
- [ ] Archive page shows deleted contacts
- [ ] Restore button works
- [ ] Permanent delete with confirmation works

---

## Notes

1. **Run migration first** if not already done: `alembic upgrade head`
2. All API endpoints are already functional in `/api/sync/*`
3. The scheduler will auto-start when the app starts (if auto_sync_enabled)
4. Test on local dev before deploying to Synology

---

*End of Phase 7E Claude Code Prompt*
