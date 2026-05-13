# My Tasks — Requirements Specification

---

## Table of Contents

1. [Problem Statement and Goals](#1-problem-statement-and-goals)
2. [In Scope / Out of Scope](#2-in-scope--out-of-scope)
3. [User Stories and Acceptance Criteria](#3-user-stories-and-acceptance-criteria)
4. [Nonfunctional Requirements](#4-nonfunctional-requirements)
5. [Traceability Matrix](#5-traceability-matrix)

---

## 1. Problem Statement and Goals

### Problem

Zulip is a powerful group messaging platform, but it lacks native personal task management. When a message contains an action item, users have no way to track it inside Zulip — they must copy it to an external tool (Jira, Notion, a sticky note) and lose the context of the original conversation.

### Goals

1. Allow users to create tasks directly from Zulip messages and todo-list widgets, preserving a link back to the source.
2. Give users a unified "My Tasks" view where they can see, filter, and manage all tasks assigned to them.
3. Support assigning tasks to other realm members.
4. Support optional due dates with correct display across timezones.
5. Provide lightweight time-tracking so users can measure effort on tasks.
6. Prevent data-loss scenarios (e.g., deleting a message that still has linked tasks).

---

## 2. In Scope / Out of Scope

### In Scope (confirmed implemented)

- Create a task from any channel message via the message action menu
- Create a task from a todo-widget item ("Add to My Tasks" button)
- Create a standalone task not linked to any message
- Assign a task to self or another realm member (by email, case-insensitive)
- Optional due date, preserved from the todo widget and displayed correctly
- My Tasks modal view with All / Pending / Completed filter tabs
- Real-time search bar filtering by title, description, or creator email
- Mark a task complete or incomplete (checkbox toggle)
- Delete a task with a confirmation dialog
- Navigate from a task back to its source message/channel/topic
- Time tracking: start/stop timers, view session logs, view personal statistics dashboard
- Block deletion of a message that has tasks linked to it (with user-friendly explanation)
- Stream notification posted when a task is assigned (channel message tasks only)
- Fix for overlay nesting crash when opening task forms inside the Users overlay

### Out of Scope (not implemented)

- Real-time task updates across browser tabs (no WebSocket event for task state)
- Due date editing after task creation (tasks are read-only after creation except for completion toggle)
- Task priorities or labels
- Task comments / threaded discussion on tasks
- Admin ability to manage other users' tasks
- Mobile native app support (web only)
- Recurring tasks
- Bulk task operations (bulk complete, bulk delete)
- Task export (CSV, etc.)

---

## 3. User Stories and Acceptance Criteria

### US-01: Create task from channel message

**As a** Zulip user,
**I want to** convert a channel message into a personal task,
**so that** I can track action items without leaving Zulip.

**Acceptance Criteria:**
- AC-01.1: The message action menu includes an option to create a task.
- AC-01.2: The task creation form pre-populates or allows entry of title, description, due date, and assignee.
- AC-01.3: After creation, the task appears in the assignee's My Tasks view.
- AC-01.4: A notification is posted to the channel topic announcing the assignment.
- AC-01.5: The task stores a reference to the originating message (message_id, stream_id, topic).

---

### US-02: Create task from todo widget

**As a** Zulip user viewing a todo-list widget,
**I want to** add individual todo items to my personal task list,
**so that** I can track specific action items from a shared list.

**Acceptance Criteria:**
- AC-02.1: Each todo item has an "Add to My Tasks" button.
- AC-02.2: Clicking the button creates a task linked to that message and item title.
- AC-02.3: If the todo item has a due date, it is preserved on the task.
- AC-02.4: The button shows a "Added — click to remove" state after creation.
- AC-02.5: Clicking the button again removes the task.

---

### US-03: View My Tasks

**As a** Zulip user,
**I want to** open a My Tasks panel showing all tasks assigned to me,
**so that** I have a single place to see all my pending work.

**Acceptance Criteria:**
- AC-03.1: A My Tasks button/icon is visible in the left sidebar.
- AC-03.2: Clicking it opens a modal listing all tasks assigned to the current user.
- AC-03.3: Each task shows: title, creator, creation date, due date (if set), and completion status.
- AC-03.4: Tasks from channel messages show a "View Message" navigation link.
- AC-03.5: Tasks from DMs appear but without a stream navigation link.

---

### US-04: Filter and search tasks

**As a** Zulip user,
**I want to** filter and search my tasks by status and keyword,
**so that** I can quickly find relevant tasks.

**Acceptance Criteria:**
- AC-04.1: Three filter tabs (All, Pending, Completed) are available.
- AC-04.2: A search bar filters tasks in real time by title, description, or creator email.
- AC-04.3: Search and filter work together simultaneously.
- AC-04.4: A count shows `Found N of M tasks` while a search is active.
- AC-04.5: Clearing the search bar restores the unfiltered list.

---

### US-05: Mark task complete

**As a** task assignee or creator,
**I want to** mark a task complete (or incomplete),
**so that** I can track my progress.

**Acceptance Criteria:**
- AC-05.1: A checkbox on each task card toggles completion.
- AC-05.2: Completed tasks show a strikethrough title and a "Completed" badge.
- AC-05.3: The `completed_at` timestamp is set when marked complete and cleared when unmarked.
- AC-05.4: If the task came from a todo widget, the corresponding widget checkbox is also toggled for all viewers.
- AC-05.5: Third parties (neither assignee nor creator) cannot toggle completion.

---

### US-06: Delete task

**As a** task assignee or creator,
**I want to** delete a task I no longer need,
**so that** my task list stays clean.

**Acceptance Criteria:**
- AC-06.1: A delete button is available on each task card.
- AC-06.2: A confirmation dialog appears before deletion ("This action cannot be undone").
- AC-06.3: After deletion, the task is removed from the list immediately.
- AC-06.4: Third parties cannot delete tasks they did not create and are not assigned to.
- AC-06.5: Deleting a task reverts any "Add to My Tasks" button in the originating todo widget.

---

### US-07: Navigate to source message

**As a** Zulip user,
**I want to** jump from a task back to the original message,
**so that** I can see the context around the action item.

**Acceptance Criteria:**
- AC-07.1: Channel-message-linked tasks show a "View Message" link.
- AC-07.2: Clicking the link closes My Tasks and navigates to the message in its channel/topic.
- AC-07.3: Standalone tasks (no message link) do not show the navigation link.

---

### US-08: Assign task to another user

**As a** Zulip user,
**I want to** assign a task to another realm member,
**so that** I can delegate action items directly in Zulip.

**Acceptance Criteria:**
- AC-08.1: The task creation form accepts an assignee email (optional; defaults to self).
- AC-08.2: The assignee field is case-insensitive.
- AC-08.3: Both delivery email and display email are accepted.
- AC-08.4: If the email is not a realm member, an error is returned.
- AC-08.5: The created task appears in the assignee's My Tasks, not the creator's.

---

### US-09: Track time on a task

**As a** task assignee or creator,
**I want to** start and stop a timer on a task,
**so that** I can measure effort.

**Acceptance Criteria:**
- AC-09.1: Each task card has Start/Stop timer buttons.
- AC-09.2: Only one active timer per task+user is allowed simultaneously.
- AC-09.3: A "Logs" button shows all recorded sessions (start, end, duration).
- AC-09.4: A "Time Stats" button shows a personal productivity dashboard.
- AC-09.5: Time data appears in the task card (formatted total, active badge).
- AC-09.6: Third parties cannot access time logs.

---

### US-10: Prevent accidental message deletion

**As a** Zulip user,
**I want to** see a clear explanation when I cannot delete a message,
**so that** I understand what to do next.

**Acceptance Criteria:**
- AC-10.1: Deleting a message that has linked tasks is blocked server-side.
- AC-10.2: A user-friendly popup explains that tasks must be removed first.
- AC-10.3: After removing tasks, the message can be deleted.

---

## 4. Nonfunctional Requirements

### Performance

- The My Tasks list endpoint (`GET /api/v1/users/me/tasks`) should return within 500ms for a user with up to 500 tasks (using `.select_related()` to avoid N+1 queries).
- The modal re-renders are synchronous JavaScript string concatenation; no additional server calls are made for filter/search changes.

### Security

- All task endpoints require authentication (Zulip session or API key). Unauthenticated requests receive 401.
- Assignee resolution is scoped to the same realm — cross-realm task assignment is not possible.
- Permission checks (assignee or creator) are enforced server-side on every mutating operation.
- No user-supplied HTML is rendered unsanitized in the modal (task titles/descriptions are inserted as text content via Handlebars or JS string interpolation with `${task.title}` — TODO: verify XSS safety of the raw HTML concatenation in `render_task_item`).

### Reliability

- Time tracking gracefully degrades: if the `TaskTimeLog` table doesn't exist, all time-tracking endpoints return a friendly 400 error rather than a 500.
- `message` FK uses `SET_NULL` on delete so that message deletion (when the guard is bypassed) does not silently delete tasks.

### Maintainability

- All task HTTP handlers are isolated in `zerver/views/tasks.py`.
- All task UI logic is isolated in `web/src/tasks_view.ts`.
- The client-side store (`task_message_store.ts`) is a separate module with a clean public API.

---

## 5. Traceability Matrix

| User Story | Backend file(s) | Frontend file(s) | Tests |
|---|---|---|---|
| US-01 Create from message | `tasks.py:create_task` | `todo_widget.ts`, `task_message_store.ts` | `test_tasks_integration.py:test_create_message_task_via_api_then_listed` |
| US-02 Create from todo widget | `tasks.py:create_task` | `todo_widget.ts:create_task_from_todo` | `PR_DESCRIPTION.md` (manual); `test_tasks_api.py` |
| US-03 View My Tasks | `tasks.py:list_my_tasks` | `tasks_view.ts:load_tasks, render_modal` | `test_tasks.py:test_list_my_tasks_*`, `tasks_e2e_tests.test.ts` |
| US-04 Filter/search | — (client-side) | `tasks_view.ts:get_filtered_tasks, setup_modal_handlers` | `tasks_view_filters.test.cjs`, `tasks_e2e_tests.test.ts` |
| US-05 Complete/uncomplete | `tasks.py:update_task` | `tasks_view.ts:toggle_task_completion` | `test_tasks.py:test_update_task_completion_*` |
| US-06 Delete | `tasks.py:delete_task` | `tasks_view.ts:delete_task, show_delete_confirmation` | `test_tasks.py:test_delete_task_*` |
| US-07 Navigate to message | — (data in list response) | `tasks_view.ts:render_task_item` | `tasks_e2e_tests.test.ts` (link existence check) |
| US-08 Assign to other user | `tasks.py:_resolve_assignee` | `user_tasks_assignment.ts` | `test_tasks_api.py:test_*assignee*`, `test_tasks_integration.py:test_create_on_message_for_other_assignee` |
| US-09 Time tracking | `tasks.py:start/stop/get_task_time_logs/get_my_time_stats` | `tasks_view.ts:start/stop_time_tracking, show_time_logs, show_time_stats` | `test_tasks.py:test_start_time_tracking, test_stop_time_tracking, test_get_task_time_logs, test_get_my_time_stats` |
| US-10 Block deletion | `message_edit.py` (Task check) | `message_delete.ts` (error handler) | `PR_BLOCK_MESSAGE_DELETION.md` (manual test steps) |
