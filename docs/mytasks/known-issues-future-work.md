# My Tasks — Known Issues & Future Work

---

## Table of Contents

1. [Known Issues](#1-known-issues)
2. [Edge Cases Needing More Testing](#2-edge-cases-needing-more-testing)
3. [Future Enhancements](#3-future-enhancements)

---

## 1. Known Issues

### KI-01: No real-time task sync across tabs/users

**Description:** If a task is created, completed, or deleted in one browser tab (or by another user), other open My Tasks modals do not update until they are re-opened.

**Root cause:** Task state changes go through the standard HTTP request cycle, not the Tornado WebSocket event system. There are no task-related events in Zulip's event queue.

**Impact:** Low in most workflows; moderate when a manager and assignee both have My Tasks open simultaneously.

**Workaround:** Reopen the My Tasks modal to refresh.

---

### KI-02: No due date editing after task creation

**Description:** Once a task is created, there is no UI or API to change its due date. The due date is set at creation time and is read-only.

**Root cause:** `update_task` in `tasks.py` only handles the `completed` field; no other fields are updatable via the API.

**Impact:** Users must delete and recreate a task to change its due date.

---

### KI-03: Potential XSS risk in `render_task_item`

**Description:** Task titles and descriptions are inserted into the modal HTML via raw JavaScript string interpolation (`${task.title}`), not via a DOM-safe API or Handlebars escaping. If a task title contains HTML characters (e.g., `<script>`), it could be rendered as HTML.

**Location:** `web/src/tasks_view.ts:render_task_item()` and `render_modal()`

**Risk level:** Medium — Zulip's backend should sanitize text stored in DB fields.

---

### KI-04: `completed_at` not set server-side (uses client time)

**Description:** In `update_task`, `completed_at` is set using `datetime.now()` (local server time without timezone). It should use `timezone_now()` (Django's UTC-aware now) for consistency.

**Location:** `zerver/views/tasks.py:233` — `task.completed_at = datetime.now()`

**Impact:** `completed_at` values may be stored without timezone info, causing potential sorting/display inconsistencies.

---

### KI-05: No E2E tests for time tracking

**Description:** The Puppeteer E2E test suite (`tasks_e2e_tests.test.ts`) does not cover time tracking flows (start/stop timer, view logs, stats dashboard).

**Impact:** Time tracking behavior is only covered by backend unit tests; no browser-level regression coverage exists.

---

### KI-06: Admin cannot manage other users' tasks

**Description:** Realm administrators have no elevated permissions on the task system. They cannot view, delete, or reassign tasks belonging to other users. This is by design per the current implementation but may be unexpected.

**Location:** Permission check in `zerver/views/tasks.py:226`

---

### KI-07: Stream notification posted even when assignee is self

**Description:** When a user creates a task and assigns it to themselves, the stream notification reads "**Task assigned** by Alice to themselves: **title**". This is slightly awkward; "themselves" is a passable string but ideally it would say "you" or omit the notification entirely.

**Location:** `zerver/views/tasks.py:86`

---


## 2. Edge Cases Needing More Testing

### EC-01: Timezone edge cases for due dates

The `format_date_string` fix (PR #16) handles the UTC→local conversion for users behind UTC. Not tested for:
- Users ahead of UTC (e.g., UTC+9, UTC+14) — date could shift forward
- Daylight saving time boundaries
- Due dates set exactly at midnight UTC

**Recommended test:** Set a due date of `2025-01-01` from a UTC+9 browser; verify it displays as `1/1/2025` not `1/2/2025`.

---

### EC-02: Task with a deleted assignee or creator

**Description:** If a `UserProfile` is deactivated or deleted (CASCADE), all tasks where that user is `assignee` or `creator` are cascade-deleted. This means an assignee's My Tasks can silently empty if their creator is removed from the realm.

**Recommended mitigation:** Use `SET_NULL` on creator/assignee FKs and handle `null` in the serializer, rather than CASCADE. This would be a data model change requiring a migration.

---

### EC-03: Very long task title or description

**Description:** `title` and `description` are both `TextField` (unbounded). An extremely long title could break the modal layout.

**Recommended test:** Create a task with a 2000-character title; verify the modal layout is not broken.

---

### EC-04: Multiple active timers in concurrent sessions

**Description:** The backend prevents two timers for the same `task+user` combination. However, the check is a `filter().first()` outside of a row-level lock — a concurrent request race condition could create two active `TaskTimeLog` rows.

**Recommended mitigation:** Add a `unique_together` constraint or use `select_for_update()` in `start_time_tracking`.

---

### EC-05: Task list performance with many tasks

**Description:** `list_my_tasks` fetches all tasks for a user in a single query and computes `TaskTimeLog` aggregates with Python-side `sum()`. With hundreds of tasks and many time logs, this could be slow.

**Recommended improvement:** Use Django `annotate(total_time=Sum('time_logs__duration_seconds'))` at the ORM level to push aggregation to the database.

---

## 3. Future Enhancements

### FE-01: Real-time task updates via Zulip event system

Add task-related events to Zulip's event queue (e.g., `task_created`, `task_updated`, `task_deleted`) so that My Tasks modals update live without polling.

**Effort:** High (requires changes to `zerver/event_types.py`, Tornado handlers, and client-side event consumers).

---

### FE-02: Due date editing

Add a UI and API to change the due date of an existing task. The `update_task` endpoint already exists — it just needs to accept and save a `due_date` parameter.

**Effort:** Low.

---

### FE-03: Task priorities and labels

Allow users to tag tasks with a priority level (High/Medium/Low) or a free-form label. Useful for teams with many tasks.

**Effort:** Medium (DB field + API + UI filtering).

---

### FE-04: More E2E test coverage

Expand `tasks_e2e_tests.test.ts` to cover:
- Completion toggle (check + uncheck)
- Delete flow (confirmation dialog)
- Time tracking start/stop
- "View Message" navigation

**Effort:** Medium.

---

### FE-05: Dark mode polish

The modal HTML is rendered as raw inline styles (no CSS classes for theming). In Zulip's dark mode, some hardcoded colors (white background, black text) may not adapt. Convert inline styles to CSS classes in `web/styles/tasks.css` and add dark-mode variants.

**Effort:** Medium.

---

### FE-06: Bulk task operations

Allow users to select multiple tasks and bulk-complete or bulk-delete them. Useful for users with many accumulated tasks.

**Effort:** Medium.

---

### FE-07: Task assignment via keyboard shortcut

Add a Zulip keyboard shortcut to quickly create a task from the currently focused message, without opening the popover.

**Effort:** Low (hook into Zulip's keyboard shortcut system).

---

### FE-08: Task comments

Allow users to leave comments on a task (threaded or simple). This could be implemented as a lightweight comment model or by re-using Zulip's own DM system (create a DM thread referencing the task_id).

**Effort:** High.

---

### FE-09: Assignee picker UI

Replace the free-text email input for assignee with a typeahead autocomplete picker (reusing Zulip's existing `people` autocomplete component). This would prevent the "User not found" errors from typos.

**Effort:** Medium.
