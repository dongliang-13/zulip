# My Tasks — Test Plan and Results

---

## Table of Contents

1. [Test Strategy](#1-test-strategy)
2. [Test File Inventory](#2-test-file-inventory)
3. [Running Tests](#3-running-tests)
4. [Coverage](#4-coverage)
5. [Test Results Summary](#5-test-results-summary)
6. [Manual Acceptance Checklist](#6-manual-acceptance-checklist)

---

## 1. Test Strategy

| Level | What is tested | Tooling | Automated? |
|---|---|---|---|
| Backend unit | Individual view handlers, model queries, permission checks | Django test runner (`ZulipTestCase`) | Yes |
| Backend API | API contract: request validation, error responses, field shapes | Django test runner | Yes |
| Backend integration | Multi-step flows: create → list → delete | Django test runner | Yes |
| Frontend unit | `TasksView` methods, store helpers, email resolution | Node.js test runner (Zulip custom) | Yes |
| E2E / browser | Full user flow: open modal, create task, search, filter | Puppeteer | Yes (partial) |
| Manual | Visual correctness, timezone display, overlay interactions | Human | No |
| Coverage measurement | Line + branch coverage for `zerver/views/tasks.py` | `coverage.py` via `tools/write_tasks_coverage_metrics.py` | Yes |

---

## 2. Test File Inventory

### Backend (Python)

| File | Test class | What it covers |
|---|---|---|
| `zerver/tests/test_tasks.py` | `TasksViewTest` | list_my_tasks (empty, filtered, nav fields, DM/stream/group-DM, visibility, creator, completion serialization, time tracking fields); update_task (complete/uncomplete by assignee/creator/third-party); delete_task (assignee, creator, third-party, not-found); start/stop time tracking; get_task_time_logs; get_my_time_stats |
| `zerver/tests/test_tasks_api.py` | `TasksApiUnitTest` | Standalone task creation; assignee query param (email, delivery email, case-insensitive, unknown user); invalid due date; unknown assignee; missing title (message task + standalone) |
| `zerver/tests/test_tasks_integration.py` | `TasksIntegrationTest` | Create-then-list (message task); standalone create-then-list; create for other assignee then they see it; create-delete-list-empty |

### Frontend (JavaScript/TypeScript)

| File | What it covers |
|---|---|
| `web/tests/tasks_view.test.cjs` | `toggle_task_completion` API call; strike submessage fired when widget key known; no submessage for standalone tasks; `delete_task` API call + store update + button revert |
| `web/tests/tasks_view_filters.test.cjs` | `get_filtered_tasks` with all/pending/completed filter; search query filtering by title/description/creator; combined search + filter |
| `web/tests/tasks_view_time_api.test.cjs` | Time tracking API calls (start, stop, logs) — correct URLs and data shapes |
| `web/tests/user_tasks_assignment.test.cjs` | `resolve_assignee_email` — delivery_email preferred, falls back to email, handles null/undefined |
| `web/tests/background_task.test.cjs` | Background task module behavior |

### E2E (Puppeteer)

| File | Scenarios |
|---|---|
| `web/e2e-tests/tasks_e2e_tests.test.ts` | Open/close My Tasks; empty state; create task from message API; task appears in list; "View Message" link present; search bar filters (findme/other); filter tabs (pending, completed, all); modal persists across re-opens |

---

## 3. Running Tests

### All backend task tests

```bash
tools/test-backend zerver.tests.test_tasks zerver.tests.test_tasks_api zerver.tests.test_tasks_integration
```

### Backend tests with coverage report

```bash
# Runs tests + generates coverage data + prints line/branch % for tasks.py
python tools/write_tasks_coverage_metrics.py
```

### Specific frontend unit test files

```bash
tools/test-js-with-node web/tests/tasks_view.test.cjs
tools/test-js-with-node web/tests/tasks_view_filters.test.cjs
tools/test-js-with-node web/tests/tasks_view_time_api.test.cjs
tools/test-js-with-node web/tests/user_tasks_assignment.test.cjs
tools/test-js-with-node web/tests/background_task.test.cjs
```

### All frontend unit tests

```bash
tools/test-js-with-node
```

### E2E tests

```bash
# Requires running dev server
tools/test-js-with-puppeteer web/e2e-tests/tasks_e2e_tests.test.ts
```

---

## 4. Coverage

### Backend coverage

Run `python tools/write_tasks_coverage_metrics.py` (inside `vagrant ssh`) to generate live metrics.

**Last measured: 2026-05-13 — run from inside `vagrant ssh`**

```
Task backend coverage (from task-related unit tests + coverage.py)

  coverage.py version: 7.13.1
  zerver/views/tasks.py line coverage: 84.07%

  zerver/views/tasks.py
    line coverage:    84.07%

  Full-run totals (all code measured in this coverage session):
    percent_covered: 12.39%
    covered_lines: 19440
    num_statements: 156841
    missing_lines: 137401
```

The 36 uncovered statements are primarily in the time-tracking error-fallback branches (the `except Exception: raise JsonableError("Time tracking feature not available")` paths that guard against a missing `TaskTimeLog` table). These are defensive branches that are not exercised because migrations are always applied before tests run.

### Frontend coverage

Zulip's node test runner does not currently generate a coverage report by default. To add coverage instrumentation, run inside `vagrant ssh`:

```bash
# Istanbul/c8 coverage
npx c8 tools/test-js-with-node web/tests/tasks_view.test.cjs
```

---

## 5. Test Results Summary

**Last run: 2026-05-13 inside `vagrant ssh` against commit `ea015f5cb7` (`main`)**

### Backend — 36/36 PASSED

```
Ran 36 tests in 2.168s
OK
```

| Test class | Tests run | Result |
|---|---|---|
| `TasksViewTest` (test_tasks.py) | 23 | PASSED |
| `TasksApiUnitTest` (test_tasks_api.py) | 9 | PASSED |
| `TasksIntegrationTest` (test_tasks_integration.py) | 4 | PASSED |

**Warnings observed (non-blocking):**
Two tests (`test_update_task_completion_by_assignee`, `test_update_task_completion_by_creator`) emit:
```
RuntimeWarning: DateTimeField Task.completed_at received a naive datetime
  while time zone support is active.
```
This confirms **KI-04** (`datetime.now()` should be `timezone_now()`). The tests pass because Django still writes the value, but the stored timestamp lacks timezone info.

### Frontend unit tests — 4/5 PASSED, 1 FAILED

| Test file | Status | Notes |
|---|---|---|
| `tasks_view.test.cjs` | PASSED | Mock warnings (non-blocking, see below) |
| `tasks_view_filters.test.cjs` | PASSED | |
| `tasks_view_time_api.test.cjs` | PASSED | Mock warnings (non-blocking) |
| `user_tasks_assignment.test.cjs` | **FAILED** | See failure detail below |
| `background_task.test.cjs` | PASSED | |

**Failure detail — `user_tasks_assignment.test.cjs`:**

```
test failed: resolve_assignee_email preserves email casing

AssertionError: Expected values to be strictly equal:
+ actual   - expected

+ 'aaron@zulip.com'
- 'AARON@zulip.com'
```

**Root cause:** The test expects `resolve_assignee_email()` to return the email with its original casing, but `normalize_email()` in `user_tasks_assignment.ts` calls `.toLowerCase()`. The feature works correctly end-to-end because the backend uses `__iexact` for lookups, but the unit test asserts case preservation which the implementation does not guarantee. Either the test should be updated to expect lowercase output, or `normalize_email()` should stop lowercasing (relying solely on the backend's `__iexact`). This is tracked as **KI-08**.

**Mock warnings (non-blocking):**
```
You asked to mock web/src/channel.ts but we never saw it during compilation.
You asked to mock web/src/task_message_store.ts but we never saw it during compilation.
```
These appear in `tasks_view.test.cjs` and `tasks_view_time_api.test.cjs`. The mocks are declared but the bundler did not see those modules during its compilation pass for those specific test files. Tests still run and pass because the mock framework degrades gracefully. This should be investigated as a test hygiene issue.

### E2E tests

The Puppeteer E2E test (`tasks_e2e_tests.test.ts`) requires a running dev server (`tools/run-dev`) and cannot be run in a headless CI pass without a display. Run manually with:

```bash
# inside vagrant ssh, with tools/run-dev running in another terminal
tools/test-js-with-puppeteer web/e2e-tests/tasks_e2e_tests.test.ts
```

Last confirmed passing: manually at time of PR #17 merge. Status on `main` as of 2026-05-13: **not re-run** — see manual acceptance checklist in §6.

---

## 6. Manual Acceptance Checklist

Use this checklist before any release or major merge.

### Setup

- [ ] Dev server running (`tools/run-dev`)
- [ ] Migrations applied (`python manage.py migrate`)
- [ ] Time-tracking migration applied (`python manage.py migrate zerver 0779_merge_0778_task_message_nullable_0778_task_time_log`)
- [ ] Logged in as a test user with access to a stream

### Core task creation

- [ ] Open message action menu → "Add to My Tasks" creates a task
- [ ] A stream notification appears in the channel topic after task creation
- [ ] Task appears in My Tasks for the assignee
- [ ] Creating a task for another user: task appears in their My Tasks, not yours

### Todo widget integration

- [ ] Todo list item with a due date → "Add to My Tasks" → due date appears in My Tasks
- [ ] Button changes to "✓ Added — click to remove" after creation
- [ ] Clicking button again removes the task
- [ ] Completing task in My Tasks strikes the todo widget checkbox for all viewers

### My Tasks view

- [ ] My Tasks modal opens and loads tasks
- [ ] All / Pending / Completed filter tabs work correctly
- [ ] Search bar filters in real time by title
- [ ] Search bar filters by description
- [ ] Search bar filters by creator email
- [ ] "Found N of M tasks" count shown during search
- [ ] Clearing search restores full list
- [ ] Search + filter tab work together

### Due dates

- [ ] Due date set in todo widget appears correctly in My Tasks (no off-by-one)
- [ ] Due date shown in blue; "No due date" shown in grey italic when absent
- [ ] Test with a timezone behind UTC (e.g., EDT) to verify no day-shift

### Completion & deletion

- [ ] Checkbox marks task complete; title gets strikethrough
- [ ] Unchecking re-opens task
- [ ] Delete button shows confirmation dialog (not browser native confirm)
- [ ] Confirming deletion removes task from list
- [ ] Cancelling deletion leaves task intact
- [ ] Third-party user gets "Permission denied" if they try to delete via API

### Navigation

- [ ] "View Message ↗" link appears for channel-message tasks
- [ ] Clicking it closes My Tasks and scrolls to the message
- [ ] Standalone tasks (created via the Users overlay form) have no navigation link
- [ ] DM-linked tasks have no stream navigation link

### Time tracking

- [ ] "Start" button starts a timer; button changes to "Stop" + "Timer Active" badge
- [ ] "Stop" stops the timer; elapsed time appears in task card
- [ ] "Logs" button shows session log
- [ ] "Time Stats" button shows productivity dashboard
- [ ] Only assignee/creator can access time controls (verify via API with a third user)

### Block message deletion

- [ ] Create a task from a todo-list message
- [ ] Attempt to delete the message → popup explains it cannot be deleted
- [ ] Remove the task from My Tasks
- [ ] Message can now be deleted

### Overlay behavior

- [ ] Open Users overlay → click "Assign Task" → second overlay opens
- [ ] Click outside second overlay → it closes without a BlueslipError
- [ ] First overlay remains visible and usable
