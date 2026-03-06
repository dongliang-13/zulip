from __future__ import annotations

from typing import Any

import orjson

from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.widget import get_widget_data
from zerver.models import Message, SubMessage, Task


class TaskConversionTestCase(ZulipTestCase):
    def _send_todo_message(self, content: str = "/todo School Work") -> Message:
        sender = self.example_user("cordelia")
        stream_name = "Verona"
        payload: dict[str, Any] = dict(
            type="stream",
            to=orjson.dumps(stream_name).decode(),
            topic="whatever",
            content=content,
        )
        result = self.api_post(sender, "/api/v1/messages", payload)
        self.assert_json_success(result)
        return self.get_last_message()

    def test_successful_conversion_creates_task(self) -> None:
        message = self._send_todo_message(
            "/todo School Work\nchemistry homework: assignment 2\nstudy for english test",
        )
        # Sanity-check that this is a todo widget message with the expected tasks.
        widget_type, extra_data = get_widget_data(content=message.content)
        self.assertEqual(widget_type, "todo")
        self.assertIn(
            {"task": "chemistry homework", "desc": "assignment 2"},
            extra_data["tasks"],
        )

        cordelia = self.example_user("cordelia")
        self.login_user(cordelia)

        result = self.client_post(
            f"/json/messages/{message.id}/tasks",
            {"title": "chemistry homework"},
        )
        self.assert_json_success(result)
        data = result.json()
        self.assertIn("task_id", data)
        task = Task.objects.get(id=data["task_id"])
        self.assertEqual(task.message_id, message.id)
        self.assertEqual(task.creator_id, cordelia.id)
        self.assertEqual(task.assignee_id, cordelia.id)
        self.assertEqual(task.title, "chemistry homework")

        # The task should be visible via the list endpoint.
        list_result = self.client_get(f"/json/messages/{message.id}/tasks")
        self.assert_json_success(list_result)
        list_data = list_result.json()
        titles = {row["title"] for row in list_data["tasks"]}
        self.assertIn("chemistry homework", titles)

    def test_permission_denied_when_cannot_access_message(self) -> None:
        message = self._send_todo_message("/todo School Work\nprivate task")

        # Unsubscribed user should not be able to access the message or create a task.
        self.login("othello")
        result = self.client_post(
            f"/json/messages/{message.id}/tasks",
            {"title": "private task"},
        )
        self.assert_json_error(result, "Invalid message(s)")

        # Likewise, listing tasks should be denied.
        list_result = self.client_get(f"/json/messages/{message.id}/tasks")
        self.assert_json_error(list_result, "Invalid message(s)")

    def test_invalid_checklist_item_reference(self) -> None:
        message = self._send_todo_message("/todo School Work\nchemistry homework")

        self.login("cordelia")
        result = self.client_post(
            f"/json/messages/{message.id}/tasks",
            {"title": "nonexistent task"},
        )
        self.assert_json_error_contains(
            result,
            "specified checklist item does not exist",
        )

    def test_duplicate_conversion_is_idempotent(self) -> None:
        message = self._send_todo_message("/todo School Work\nchemistry homework")

        self.login("cordelia")

        first = self.client_post(
            f"/json/messages/{message.id}/tasks",
            {"title": "chemistry homework"},
        )
        self.assert_json_success(first)
        first_id = first.json()["task_id"]

        second = self.client_post(
            f"/json/messages/{message.id}/tasks",
            {"title": "chemistry homework"},
        )
        self.assert_json_success(second)
        second_id = second.json()["task_id"]

        self.assertEqual(first_id, second_id)
        self.assertEqual(
            Task.objects.filter(
                message_id=message.id,
                creator=self.example_user("cordelia"),
                title="chemistry homework",
            ).count(),
            1,
        )

