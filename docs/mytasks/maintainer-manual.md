# My Tasks — Maintainer Manual

**Audience:** Developers maintaining or extending the My Tasks feature
**Branch:** `main`

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Data Model](#2-data-model)
3. [API Endpoints](#3-api-endpoints)
4. [Frontend Architecture](#4-frontend-architecture)
5. [Backend Architecture](#5-backend-architecture)
6. [Permission Model](#6-permission-model)
7. [Real-Time Sync](#7-real-time-sync)
8. [Running Locally](#8-running-locally)
9. [Running Tests](#9-running-tests)
10. [Debugging Tips](#10-debugging-tips)

---

## 1. System Overview

The My Tasks feature adds a personal task layer on top of Zulip's existing messaging system. All new code is concentrated in the following locations:

**Backend (Python/Django)**

| File | Purpose |
|---|---|
| `zerver/models/messages.py:844` | `Task` and `TaskTimeLog` model definitions |
| `zerver/views/tasks.py` | All HTTP view handlers |
| `zerver/migrations/0777_task.py` | Initial `Task` table migration |
| `zerver/migrations/0778_task_message_nullable.py` | Made `message` FK nullable (standalone tasks) |
| `zerver/migrations/0778_task_time_log.py` | `TaskTimeLog` table migration |
| `zerver/migrations/0779_merge_*.py` | Merge of the two 0778 migrations |
| `zproject/urls.py:454–464` | URL routing for all task endpoints |
| `zerver/views/message_edit.py` | Added task-existence check before message deletion |

**Frontend (TypeScript)**

| File | Purpose |
|---|---|
| `web/src/tasks_view.ts` | `TasksView` class — modal UI, filtering, event handlers |
| `web/src/task_message_store.ts` | Client-side in-memory store of message→task mappings |
| `web/src/user_tasks_assignment.ts` | Email normalization helper for assignee resolution |
| `web/src/todo_widget.ts` | "Add to My Tasks" integration in todo widgets |
| `web/src/overlays.ts` | Modified to fix nested overlay close bug |
| `web/src/message_delete.ts` | Modified to show user-friendly error when deletion is blocked |
| `web/styles/tasks.css` | Task-specific CSS |
| `web/templates/todo_modal_task.hbs` | Handlebars template for the task creation modal |
| `web/templates/widgets/todo_widget_tasks.hbs` | Per-item buttons in todo widget |

---

## 2. Data Model

### `Task` (`zerver/models/messages.py:844`)

| Field | Type | Nullable | Description |
|---|---|---|---|
| `id` | BigAutoField | No | Primary key |
| `message` | FK → Message | Yes | Source message; `null` for standalone tasks |
| `assignee` | FK → UserProfile | No | The user the task is assigned to |
| `creator` | FK → UserProfile | No | The user who created the task |
| `title` | TextField | No | Required task title |
| `description` | TextField | No (blank=True) | Optional description |
| `completed` | BooleanField | No | Default `False` |
| `due_date` | DateTimeField | Yes | Stored as UTC datetime, displayed as date only |
| `created_at` | DateTimeField | No | Auto-set on creation |
| `completed_at` | DateTimeField | Yes | Set when `completed` flips to `True`; cleared on unmark |

**Key invariants:**
- `assignee` and `creator` are from the same Zulip realm (enforced by `_resolve_assignee` looking up users filtered by `realm`).
- Deleting a `Message` cascades to delete all linked `Task` rows (before the block-deletion PR, this was silent; now it's blocked by a UI check).
- `message` FK uses `SET_NULL` on delete (as of migration 0778_task_message_nullable), so if a message is deleted after the check is bypassed, the task becomes standalone rather than being deleted.

### `TaskTimeLog` (`zerver/models/messages.py:863`)

| Field | Type | Nullable | Description |
|---|---|---|---|
| `id` | BigAutoField | No | Primary key |
| `task` | FK → Task | No | Parent task (CASCADE on delete) |
| `user` | FK → UserProfile | No | Who tracked the time |
| `start_time` | DateTimeField | No | UTC timestamp when timer started |
| `end_time` | DateTimeField | Yes | UTC timestamp when timer stopped; `null` = active |
| `duration_seconds` | PositiveIntegerField | No | Computed on stop; default 0 |
| `description` | TextField | No (blank=True) | Optional session notes |
| `created_at` | DateTimeField | No | Auto-set |
| `updated_at` | DateTimeField | No | Auto-updated |

**Key invariant:** An active timer has `end_time=None`. The system prevents starting a second timer if one is already active for the same task+user combination.

---

## 3. API Endpoints

All endpoints are in `zproject/urls.py:454–464` and handled by `zerver/views/tasks.py`. They follow the standard Zulip API convention: authenticated via session cookie or API key; responses are `{"result": "success", ...}` on success and `{"result": "error", "msg": "..."}` on failure.

### Create task from message

```
POST /api/v1/messages/<message_id>/tasks
```

**Request fields:** `title` (required), `description`, `assignee` (email, defaults to self), `due_date` (ISO 8601 string)
**Response:** `{task_id, title, description, completed, due_date}`
**Side effect:** Posts a stream notification to the originating channel topic.

### Create standalone task

```
POST /api/v1/tasks
```

Same fields as above, no `message_id`. `message` FK will be `null`.

### List tasks for current user

```
GET /api/v1/users/me/tasks
GET /api/v1/users/me/tasks?assignee=<email>
```

Returns all tasks assigned to the current user (or specified assignee). The `assignee` query param accepts delivery email or display email, case-insensitively.

**Response:** `{tasks: [{task_id, title, description, completed, completed_at, due_date, message_id, stream_id, topic, creator_email, creator_full_name, created_at, total_time_seconds, total_time_formatted, active_timer}]}`

### Update task (toggle completion)

```
POST /api/v1/tasks/<task_id>
```

**Request fields:** `completed` ("true" or "false")
**Permission:** assignee or creator only.

### Delete task

```
POST /api/v1/tasks/<task_id>/delete
```

No request body required.
**Permission:** assignee or creator only.

### Start time tracking

```
POST /api/v1/tasks/<task_id>/time/start
```

Optional: `description` (session notes).
**Response:** `{time_log_id, task_id, start_time, is_active}`
**Error 400:** "Timer already running for this task"

### Stop time tracking

```
POST /api/v1/tasks/<task_id>/time/stop
```

**Response:** `{time_log_id, task_id, start_time, end_time, duration_seconds, duration_formatted}`
**Error 400:** "No active timer found for this task"

### Get time logs

```
GET /api/v1/tasks/<task_id>/time/logs
```

**Response:** `{task_id, time_logs: [...], total_time_seconds, total_time_formatted, active_timer_count}`

### Get time statistics

```
GET /api/v1/users/me/time/stats
```

**Response:** `{total_time_seconds, total_time_formatted, completed_sessions, active_sessions, recent_week_seconds, recent_week_formatted, task_breakdown: [top 10 tasks]}`

---

## 4. Frontend Architecture

### `TasksView` class (`web/src/tasks_view.ts`)

The main UI controller. A singleton instance `tasks_view` is exported and initialized in `initialize()`.

**Key methods:**

| Method | What it does |
|---|---|
| `show()` | Calls `load_tasks()` then `render_modal()` |
| `load_tasks()` | GET `/json/users/me/tasks`, populates `this.tasks` |
| `render_modal()` | Destroys and recreates `#tasks-modal` DOM node with current state |
| `render_task_item(task)` | Returns HTML string for one task card |
| `get_filtered_tasks()` | Applies `search_query` + `current_filter` to `this.tasks` |
| `toggle_task_completion(id)` | POST to update endpoint; syncs todo-widget checkbox via submessage |
| `show_delete_confirmation(id)` | Shows custom confirmation modal before calling `delete_task` |
| `delete_task(id)` | POST to delete endpoint; updates store + reverts todo button |
| `start_time_tracking(id)` | POST to time/start; reloads tasks |
| `stop_time_tracking(id)` | POST to time/stop; reloads tasks |
| `show_time_logs(id)` | GET time/logs; renders inline modal |
| `show_time_stats()` | GET users/me/time/stats; renders stats modal |

**Date formatting:** `format_date_string(iso_string)` slices the `YYYY-MM-DD` portion from the ISO string and constructs a `new Date(year, month-1, day)` to avoid UTC→local timezone shifts. This fixes the "off by one day" bug for users behind UTC.

### `task_message_store.ts`

Maintains two client-side Maps:
- `message_tasks: Map<message_id, task_id>` — tracks which messages have a task (used by message action popover to show "already added" state)
- `todo_item_tasks: Map<"messageId:title", {task_id, key}>` — tracks individual todo-widget items

Populated at startup via `GET /json/users/me/tasks`. Kept in sync as the user adds/removes tasks.

### `user_tasks_assignment.ts`

Exports `resolve_assignee_email(user)`: given a user object, returns `delivery_email` if present (non-empty after trimming), otherwise falls back to `email`. Used to normalize the email passed to the backend's `assignee` field.

---

## 5. Backend Architecture

### `_resolve_assignee` (`zerver/views/tasks.py:17`)

Shared helper. Given an email string and the current user's profile:
- If blank → return `current_user` (assign to self)
- Otherwise → look up `UserProfile` by `delivery_email__iexact`, then fallback to `email__iexact`, both filtered to the same realm
- Raises `JsonableError` if user not found

### `format_duration` (`zerver/views/tasks.py:482`)

Formats an integer number of seconds to a human-readable string: `"Xs"`, `"Xm Ys"`, or `"Xh Ym"`.

### Message deletion guard (`zerver/views/message_edit.py`)

Before deleting a message, checks `Task.objects.filter(message=message, assignee=user_profile).exists()`. If true, raises `JsonableError` with the explanation message. Client-side (`message_delete.ts`) catches errors containing "My Tasks" and shows a custom popup.

---

## 6. Permission Model

| Action | Who can do it |
|---|---|
| Create task from message | Any authenticated realm member |
| Create standalone task | Any authenticated realm member |
| List own tasks | Any authenticated realm member (their own tasks) |
| List another user's tasks | Any authenticated realm member (via `?assignee=`) |
| Toggle task completion | Assignee or creator only |
| Delete task | Assignee or creator only |
| Start/stop timer | Assignee or creator only |
| View time logs | Assignee or creator only |
| View time stats | Any authenticated realm member (own stats only) |

Enforcement is in `zerver/views/tasks.py` with the pattern:
```python
if user_profile.id not in [task.assignee.id, task.creator.id]:
    raise JsonableError("Permission denied")
```

There is currently no admin override — realm admins cannot delete other users' tasks via the API without impersonation. This is a known gap; see [Known Issues](known-issues-future-work.md).

---

## 7. Real-Time Sync

There is no WebSocket/event-driven sync for task state across sessions. The My Tasks modal fetches fresh data on every `show()` call. The one real-time interaction is:

- When a task is marked complete and it has a `message_id`, the frontend posts a `{"type": "strike", "key": "<widget_key>"}` submessage to `/json/submessage`. This causes the corresponding checkbox in all viewers' todo widget to toggle (Zulip's existing submessage broadcast handles distribution).

If a second browser tab has My Tasks open, it will not see updates until the modal is re-opened.

---

## 8. Running Locally

Follow the standard [Zulip development setup](../development/setup-recommended.md). Once you have a dev environment:

```bash
# Apply all migrations (including task migrations)
python manage.py migrate

# Start the dev server
tools/run-dev

# (Optional) Apply time-tracking migration explicitly if needed
python manage.py migrate zerver 0779_merge_0778_task_message_nullable_0778_task_time_log
```

The My Tasks button should appear in the left sidebar after login.

---

## 9. Running Tests

### Backend unit + integration tests

```bash
# Run all task-related backend tests
tools/test-backend zerver.tests.test_tasks zerver.tests.test_tasks_api zerver.tests.test_tasks_integration

# Run with coverage (produces line + branch coverage for zerver/views/tasks.py)
python tools/write_tasks_coverage_metrics.py
```

### Frontend unit tests (node)

```bash
# Run all frontend unit tests
tools/test-js-with-node

# Run specific task test files
tools/test-js-with-node web/tests/tasks_view.test.cjs
tools/test-js-with-node web/tests/tasks_view_filters.test.cjs
tools/test-js-with-node web/tests/tasks_view_time_api.test.cjs
tools/test-js-with-node web/tests/user_tasks_assignment.test.cjs
tools/test-js-with-node web/tests/background_task.test.cjs
```

### E2E tests (Puppeteer)

```bash
# Run the My Tasks E2E test suite
tools/test-js-with-puppeteer web/e2e-tests/tasks_e2e_tests.test.ts
```

> **Note:** E2E tests require a running dev server and a seeded test database. See the standard Zulip E2E setup docs.

---

## 10. Debugging Tips

### "Time tracking feature not available" (503 error)

The `TaskTimeLog` table does not exist. Run the migration:
```bash
python manage.py migrate zerver 0779_merge_0778_task_message_nullable_0778_task_time_log
```

### Due date shows one day early

This was fixed in PR #16. If it recurs, check that `format_date_string()` in `tasks_view.ts:10` is being called for all due-date display paths (not `new Date(iso).toLocaleDateString()`).

### Overlay throws `BlueslipError: Trying to close overlay with another open`

This was fixed in PR #22 by adding a guard in `web/src/overlays.ts`. If it recurs, check that the guard `if (target_name !== open_overlay_name) { return; }` is still in place in the overlay click handler.

### Tasks not appearing after creation

The modal loads tasks fresh on `show()`. If a task is created programmatically, reopen the modal. The `task_message_store` is updated synchronously on create/delete so button states should be correct without a reload.

### Assignee not found error

Check that the email passed is from the same Zulip realm. `_resolve_assignee` scopes lookups by `realm`. Cross realm assignment is not supported.

### "Permission denied" on task update/delete

Only the assignee or creator can modify a task. Verify which user is logged in and which users are stored as `task.assignee` and `task.creator` in the database.
