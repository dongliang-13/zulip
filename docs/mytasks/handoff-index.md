# My Tasks Feature — Handoff Index

This is the top-level index for the CS 5150 "My Tasks" handoff documentation package.
All documents live in `docs/mytasks/` in the main repository.

---

## Quick Links

| Document | Purpose |
|---|---|
| [User Manual](user-manual.md) | End-user guide: how to create, manage, and track tasks |
| [Maintainer Manual](maintainer-manual.md) | Developer reference: code locations, APIs, migrations, testing |
| [Requirements Spec](requirements-spec.md) | User stories, acceptance criteria, traceability |
| [Architecture](architecture.md) | System components, data flow, deployment overview |
| [Test Plan & Results](test-plan-and-results.md) | Test strategy, commands, coverage, manual checklist |
| [Developer Workflow & Style Guide](developer-workflow-style-guide.md) | Branching, PRs, linting, safe extension patterns |
| [Known Issues & Future Work](known-issues-future-work.md) | Open bugs, edge cases, planned enhancements |

---

## Repository

- **Repo:** `https://github.com/dongliang-13/zulip` (fork of Zulip)
- **Primary branch:** `main`
- **Demo video:** [Demo link](https://youtu.be/ZpG9Rcc9VbM)
- **How to run locally:** See [Maintainer Manual — Running Locally](maintainer-manual.md#running-locally)

---

## Feature Summary

The "My Tasks" feature extends Zulip with a personal task-management system embedded directly in the messaging interface. Users can:

- Convert any channel message or todo-widget item into a task
- Assign tasks to themselves or other realm members
- Set and track due dates
- Filter and search tasks by status, title, description, or creator
- Track time spent on tasks with a built-in start/stop timer
- Navigate from a task directly back to its source message

---

## Team & PR History

The feature was developed iteratively over ~25 pull requests on `main`. Key PRs include:

| PR | Topic |
|---|---|
| #6 | Message-to-task conversion (message popover + todo widget) |
| #8 | Due date backend + frontend |
| #12 | Time tracking (start/stop/logs/stats dashboard) |
| #13 | Custom delete-confirmation modal |
| #15 | Search bar in My Tasks |
| #16 | Due-date timezone fix |
| #17 | "View Message" navigation from task |
| #19 | Backend unit, API, and integration test suite |
| #21 | Block message deletion when tasks exist |
| #22 | Overlay nesting fix |
| #24/#25 | Assignee name/case-insensitivity fixes |

---

