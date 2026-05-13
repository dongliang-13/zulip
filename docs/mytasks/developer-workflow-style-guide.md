# My Tasks — Developer Workflow & Style Guide

---

## Table of Contents

1. [Branching Strategy](#1-branching-strategy)
2. [PR Process](#2-pr-process)
3. [Commit Message Conventions](#3-commit-message-conventions)
4. [Linting and Formatting](#4-linting-and-formatting)
5. [Adding New Task Features Safely](#5-adding-new-task-features-safely)
6. [Regression Prevention](#6-regression-prevention)

---

## 1. Branching Strategy

The project uses a **feature-branch workflow** branching from `main`.

- `main` — the primary integration branch; all PRs target this branch.
- Feature branches — named by author/feature (e.g., `dongliang-13/feature/task-search-bar`, `yang/due-date`).

There are no long-lived release branches. The convention from the commit history is:
```
<github-username>/<brief-description>
```
or
```
<github-username>/<category>/<brief-description>
```

Examples observed:
- `dongliang-13/feature/task-time-tracking`
- `dongliang-13/fix/task-due-date-timezone`
- `dongliang-13/block-message-deletion-with-tasks`

---

## 2. PR Process

### Creating a PR

1. Create a feature branch from `main`.
2. Make changes and ensure all tests pass (see [Regression Prevention](#6-regression-prevention)).
3. Push the branch and open a PR targeting `main`.
4. Fill in a PR description using one of the template formats in the repo root (e.g., `PR_DESCRIPTION.md`, `PR_SEARCH_BAR.md` serve as templates for what good PR descriptions look like):
   - **Problem** — what was wrong or missing
   - **Solution / Changes** — what you changed and why
   - **Testing** — manual test steps
5. Request a code review from at least one teammate.

### PR description quality bar

Good PR descriptions in this repo include:
- The root cause (not just the symptom)
- Specific file + function names that were changed
- A manual testing checklist that a reviewer can follow

### Review expectations

- Reviewers should run the relevant test files locally, not just read the diff.
- For UI changes, a screenshot or screen recording is strongly encouraged.
- For backend changes, the reviewer should verify that `_resolve_assignee` is used for any new assignee input (not raw `UserProfile.objects.get`).

### Merging

- Squash-merge or merge commit — both are acceptable.
- The `main` branch should remain green at all times.

---

## 3. Commit Message Conventions

The project does not enforce a strict conventional-commit format, but the observed style is:

```
<short imperative summary> (≤72 chars)

[optional body: what problem, what changed, why]
```

Examples from the commit log:
```
Fix due date showing one day before actual date in My Tasks view
Add search bar to My Tasks view
Block message deletion when message has tasks in My Tasks view
Fixed assign behavior to ignore case sensitivity
Replace browser confirm() with custom Zulip-style confirmation modal
```

**Avoid:**
- "WIP" commits in merged PRs
- Commits like "fixed bug" without context (these appear in the history and are hard to bisect against)
- Amending commits that have already been pushed to a shared branch

---

## 4. Linting and Formatting

The project uses the standard Zulip linting stack. All these tools are already configured:

### Python

```bash
# Run mypy type checking
tools/run-mypy zerver/views/tasks.py

# Run Ruff linter
tools/lint --only=ruff zerver/views/tasks.py

# Auto-format with Black (via pyproject.toml)
python -m black zerver/views/tasks.py
```

### TypeScript / JavaScript

```bash
# ESLint (config: eslint.config.js)
pnpm eslint web/src/tasks_view.ts web/src/task_message_store.ts

# Prettier formatting (config: prettier.config.js)
pnpm prettier --write web/src/tasks_view.ts

# Stylelint for CSS (config: stylelint.config.js)
pnpm stylelint web/styles/tasks.css
```

### Run all linters at once

```bash
tools/lint
```

> **Note:** The Zulip CI pipeline runs all linters. A PR that introduces lint errors will be blocked. Always run `tools/lint` before opening a PR.

---

## 5. Adding New Task Features Safely

Follow these patterns when extending the My Tasks feature.

### Adding a new backend endpoint

1. Add the view function to `zerver/views/tasks.py`.
   - Use `@require_POST` or `@require_GET` as appropriate.
   - Use `@typed_endpoint` if your handler accepts URL/query parameters.
   - Use `@transaction.atomic(durable=True)` for any write operations.
   - Use `_resolve_assignee()` for any user email input.
   - Check permissions with `if user_profile.id not in [task.assignee.id, task.creator.id]`.
   - Return `json_success(request, {...})` on success; raise `JsonableError(...)` on error.
2. Register the route in `zproject/urls.py` using `rest_path()`.
3. Write tests in the appropriate test file (`test_tasks.py`, `test_tasks_api.py`, or `test_tasks_integration.py`).

### Adding a new frontend action

1. Add the method to `TasksView` in `web/src/tasks_view.ts`.
2. Add a button to `render_task_item()` or `render_modal()`.
3. Register the event handler in `setup_modal_handlers()` using jQuery event delegation on `#tasks-modal`.
4. Use `channel.post()` / `channel.get()` for API calls (not raw `fetch`).
5. Handle the `error` callback with `blueslip.error(...)`.
6. Write a unit test in `web/tests/tasks_view.test.cjs` or a new test file.

### Updating the Task model

1. Add or modify a field in `zerver/models/messages.py:Task`.
2. Generate a migration: `python manage.py makemigrations zerver`.
3. If adding a non-nullable column, provide a default or make it nullable.
4. Update the `list_my_tasks` response serialization in `tasks.py` to include the new field.
5. Update the `_assert_my_tasks_payload_shape` helper in `test_tasks.py` to include the new key.
6. Update the `Task` TypeScript type in `tasks_view.ts`.

### Modifying the client-side store

When adding a new kind of task-to-message association:
1. Add it to `task_message_store.ts` with a clean getter/setter/remover API.
2. Populate it in `initialize()` from the existing `GET /json/users/me/tasks` call (avoid adding new startup requests).
3. Keep the two Maps (`message_tasks` and `todo_item_tasks`) in sync when you add/remove entries.

---

## 6. Regression Prevention

Run these before every PR merge:

### Required

```bash
# Backend task tests (fast, ~10 seconds)
tools/test-backend zerver.tests.test_tasks zerver.tests.test_tasks_api zerver.tests.test_tasks_integration

# Frontend unit tests (fast)
tools/test-js-with-node web/tests/tasks_view.test.cjs
tools/test-js-with-node web/tests/tasks_view_filters.test.cjs
tools/test-js-with-node web/tests/tasks_view_time_api.test.cjs
tools/test-js-with-node web/tests/user_tasks_assignment.test.cjs

# Linting
tools/lint
```

### Recommended for UI changes

```bash
# E2E test (slower, requires running server)
tools/test-js-with-puppeteer web/e2e-tests/tasks_e2e_tests.test.ts
```

### Recommended for backend changes

```bash
# Full backend suite (catch regressions in Zulip core that interact with tasks)
tools/test-backend zerver

# Coverage check
python tools/write_tasks_coverage_metrics.py
```

### Specific regression risks to watch

| Change type | What to check |
|---|---|
| Modifying `_resolve_assignee` | `test_tasks_api.py:test_list_my_tasks_assignee_*` + `test_*_case_insensitive` |
| Modifying `update_task` | `test_tasks.py:test_update_task_completion_*` (all 4 variants) |
| Modifying `render_task_item` | Check due-date display for UTC+0, UTC-4, UTC+9 timezones |
| Modifying todo widget buttons | `test_tasks.py` (create from todo) + manual toggle test |
| Adding a migration | Verify `python manage.py migrate` runs clean from scratch |
| Modifying overlay behavior | `PR_OVERLAY_FIX.md` manual steps (nested overlay open/close) |
| Modifying `message_edit.py` | `PR_BLOCK_MESSAGE_DELETION.md` manual steps |
