# Changelog - 2025.12.22

## Dashboard Redesign Phase 1: Two-Panel Layout

### Overview
Major redesign of the dashboard to a modern two-panel layout with improved task management and calendar integration. The new layout matches the design mockup with a left panel for calendar/schedule and a right panel for tasks.

### New Features

#### Two-Panel Layout
- **Left Panel (~35% width):**
  - Tab navigation to switch between Calendar view and Tasks kanban view
  - CALENDAR section with mini calendar grid, month navigation
  - SCHEDULE section showing today's timed events
  - BIRTHDAYS section with compact list and "Send" email buttons

- **Right Panel (~65% width):**
  - TODAY header with current date, timezone indicator, and task count badge
  - Tab navigation: Today | Tomorrow | Next 7 Days | All Lists
  - URGENT section (red styling) for overdue tasks
  - SCHEDULED section for tasks due within selected timeframe

#### Keyboard Navigation
- Bottom footer bar showing available keyboard shortcuts
- `c` - Switch to Calendar view
- `1` - View Today's tasks
- `2` - View Tomorrow's tasks
- `3` - View Next 7 Days
- `4` - View All Lists (kanban)
- `n` - Add new task
- `j/k` - Navigate tasks
- `x` - Complete task
- `e` - Edit task

#### New Backend Endpoints
- `GET /dashboard/mini-calendar` - Mini calendar widget with month navigation
- `GET /dashboard/schedule-widget` - Today's scheduled events
- `GET /dashboard/birthdays-compact` - Compact birthday list with Send buttons
- `GET /dashboard/tasks-panel?view={today|tomorrow|week}` - Filtered task view

### Files Modified
- `app/templates/dashboard.html` - Complete rewrite with two-panel layout
- `app/routers/dashboard.py` - Added 4 new widget endpoints

### Files Added
- `app/templates/dashboard/_mini_calendar.html` - Mini calendar grid template
- `app/templates/dashboard/_schedule_widget.html` - Schedule events template
- `app/templates/dashboard/_birthdays_compact.html` - Compact birthdays template
- `app/templates/dashboard/_tasks_panel.html` - Task panel with urgent/scheduled sections

### UI/UX Improvements
- Collapsible sections for calendar, schedule, and birthdays
- Real-time date/time display with timezone abbreviation
- Task count badges with color coding
- Hover states for task completion
- Mobile-responsive design (panels stack vertically on small screens)

### Technical Notes
- Uses Alpine.js for reactive state management
- HTMX for dynamic widget loading
- Existing Google Tasks integration preserved
- All existing task toggle/edit functionality maintained

### Testing
After restarting the server, verify:
1. Two-panel layout renders correctly at http://localhost:8000/
2. Calendar month navigation works
3. Task tabs load correct filtered data
4. Task toggle/edit functionality works
5. Keyboard shortcuts function properly
6. Mobile view stacks panels correctly

---

## Dashboard Redesign Phase 2: Add Task Modal & Keyboard Navigation

### Overview
Added Add Task modal functionality, vim-style keyboard navigation for tasks, and Sync Tasks button.

### New Features

#### Add Task Modal
- Click "+ Add task" button or press `n` to open modal
- Task list dropdown populated from Google Tasks lists
- Title (required), Notes, and Due Date fields
- Creates task via POST to `/tasks/{list_id}` endpoint
- Auto-refreshes task panel after creation

#### Vim-Style Keyboard Navigation
- `j` - Move selection down to next task
- `k` - Move selection up to previous task
- `x` - Complete the currently selected task
- `e` - Edit the currently selected task (opens edit modal)
- `Escape` - Clear task selection
- Selection wraps around (last→first, first→last)
- Visual ring indicator on selected task

#### Sync Tasks Button
- Sync button in right panel header next to Add task
- Triggers Google Tasks sync via POST `/tasks/sync`
- Shows sync status (success/error message)
- Automatically refreshes task panel and kanban after sync
- Spinning icon animation during sync request

### Files Modified
- `app/templates/dashboard.html` - Added keyboard nav handlers, task selection state, Sync button
- `app/routers/dashboard.py` - Added `/dashboard/add-task-modal` endpoint
- `app/routers/tasks.py` - Updated sync endpoint to refresh new tasks panel

### Files Added
- `app/templates/dashboard/_add_task_modal.html` - Add task modal template

### New Backend Endpoints
- `GET /dashboard/add-task-modal` - Returns add task modal with task lists dropdown

### CSS Changes
- Added `.task-selected` class for keyboard selection ring indicator

### Technical Notes
- `window.dashboardCurrentView` tracks current task view for refreshes
- Modal skipped during keyboard navigation when open
- htmx:afterSwap listener resets selection when task list changes
- Selection persists when completing task (index maintained)

### Testing
After restarting the server, verify:
1. Click "+ Add task" button opens modal with task lists dropdown
2. Press `n` key opens add task modal
3. Creating task closes modal and refreshes list
4. Press `j`/`k` to navigate tasks (watch for ring selection)
5. Press `x` to complete selected task
6. Press `e` to edit selected task
7. Press `Escape` to clear selection
8. Click "Sync" button shows status and refreshes tasks

---

## Dashboard Redesign Phase 3: Add Event Modal, Quick Dates & Mobile Polish

### Overview
Added Add Event modal for creating calendar events, quick date buttons for task modals, clickable mini calendar days, and mobile-responsive improvements.

### New Features

#### Add Event Modal
- Click "Add" in SCHEDULE section to open modal
- Google Account dropdown (which calendar to add to)
- Title (required), Date, Start Time, End Time fields
- Quick date buttons: Today, Tomorrow, +1 Week
- Location and Description fields
- Guests input (comma-separated emails)
- "Add Google Meet" checkbox for video conferencing
- Submits via existing `POST /calendar/create` endpoint
- Auto-refreshes schedule widget on success

#### Quick Date Buttons for Tasks
- Added to Add Task modal: Today, Tmrw (Tomorrow), +1Wk (Next Week)
- Added to Edit Task modal: Today, Tmrw, +1Wk, Clear
- One-click date setting for common due dates

#### Mini Calendar Day Click
- Click any day in the mini calendar to view that day's events
- Schedule widget updates to show selected day's events
- "Back to Today" button to return to current day
- Days with birthdays show event count in tooltip

#### Mobile Polish
- Keyboard shortcuts footer hidden on mobile (below lg breakpoint)
- All modals (Add Task, Edit Task, Add Event) have max-height 90vh
- Modals are scrollable on small screens with overflow-y-auto

### Files Added
- `app/templates/dashboard/_add_event_modal.html` - Add event modal template

### Files Modified
- `app/routers/dashboard.py`:
  - Added `GET /dashboard/add-event-form` endpoint
  - Updated `GET /dashboard/schedule-widget` to accept optional `selected_date` param
- `app/templates/dashboard/_add_task_modal.html`:
  - Added quick date buttons (Today, Tmrw, +1Wk)
  - Added max-h-[90vh] overflow-y-auto for mobile
- `app/templates/dashboard/_tasks_panel.html`:
  - Added quick date buttons to edit modal
  - Added max-h-[90vh] overflow-y-auto for mobile
- `app/templates/dashboard/_mini_calendar.html`:
  - Made day cells clickable with hx-get
  - Days load schedule widget for selected date
- `app/templates/dashboard/_schedule_widget.html`:
  - Shows selected date header when viewing non-today dates
  - "Back to Today" button for navigation
- `app/templates/dashboard.html`:
  - Keyboard footer now uses `hidden lg:flex` (hidden on mobile)

### New Backend Endpoints
- `GET /dashboard/add-event-form` - Returns add event modal with Google accounts dropdown
- `GET /dashboard/schedule-widget?selected_date=YYYY-MM-DD` - Events for specific date (optional param)

### Technical Notes
- Add Event modal uses existing `POST /calendar/create` endpoint
- Schedule widget filters events by selected date using `get_upcoming_events()`
- Quick date functions use JavaScript Date object for calculation
- Mobile hiding uses Tailwind responsive prefixes (hidden lg:flex)

### Testing
After restarting the server, verify:
1. Click "Add" in SCHEDULE section opens event modal
2. Create event with title, date, time - appears in Google Calendar
3. Toggle "Add Google Meet" checkbox works
4. Quick date buttons in Add Task modal work (Today/Tmrw/+1Wk)
5. Quick date buttons in Edit Task modal work
6. Click day in mini calendar - schedule shows that day's events
7. "Back to Today" button returns to current day's events
8. Mobile view: keyboard footer hidden (resize browser to test)
9. Mobile view: modals scroll properly on small screens

---
*Generated: 2025-12-22*
