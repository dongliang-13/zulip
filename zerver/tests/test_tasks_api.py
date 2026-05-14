from datetime import timedelta

from django.utils.timezone import now

from zerver.lib.test_classes import ZulipTestCase
from zerver.models.messages import Task


class TasksApiUnitTest(ZulipTestCase):
    def test_create_standalone_task_for_other_assignee(self) -> None:
        hamlet = self.example_user("hamlet")
        othello = self.example_user("othello")

        result = self.api_post(
            hamlet,
            "/api/v1/tasks",
            {
                "title": "Follow up with othello",
                "description": "handoff",
                "assignee": othello.email,
            },
        )
        data = self.assert_json_success(result)

        created_task = Task.objects.get(id=data["task_id"])
        self.assertEqual(created_task.assignee_id, othello.id)
        self.assertEqual(created_task.creator_id, hamlet.id)

        othello_tasks = self.assert_json_success(self.api_get(othello, "/api/v1/users/me/tasks"))
        self.assert_length(othello_tasks["tasks"], 1)
        self.assertEqual(othello_tasks["tasks"][0]["task_id"], created_task.id)

        hamlet_tasks = self.assert_json_success(self.api_get(hamlet, "/api/v1/users/me/tasks"))
        self.assertEqual(hamlet_tasks["tasks"], [])

    def test_list_my_tasks_assignee_query_param(self) -> None:
        hamlet = self.example_user("hamlet")
        iago = self.example_user("iago")
        message_id = self.send_stream_message(
            iago, "Verona", topic_name="api", content="list by assignee"
        )
        Task.objects.create(
            message_id=message_id,
            assignee=hamlet,
            creator=iago,
            title="Hamlet only",
            description="",
        )
        result = self.api_get(iago, "/api/v1/users/me/tasks", {"assignee": hamlet.email})
        data = self.assert_json_success(result)
        self.assert_length(data["tasks"], 1)
        self.assertEqual(data["tasks"][0]["title"], "Hamlet only")

    def test_list_my_tasks_assignee_query_param_delivery_email(self) -> None:
        hamlet = self.example_user("hamlet")
        iago = self.example_user("iago")
        message_id = self.send_stream_message(
            iago, "Verona", topic_name="api", content="list by delivery email"
        )
        Task.objects.create(
            message_id=message_id,
            assignee=hamlet,
            creator=iago,
            title="Hamlet by delivery email",
            description="",
        )

        hamlet.email = "hamlet+api-visible@example.com"
        hamlet.save(update_fields=["email"])

        result = self.api_get(iago, "/api/v1/users/me/tasks", {"assignee": hamlet.delivery_email})
        data = self.assert_json_success(result)
        self.assert_length(data["tasks"], 1)
        self.assertEqual(data["tasks"][0]["title"], "Hamlet by delivery email")

    def test_list_my_tasks_assignee_query_param_case_insensitive(self) -> None:
        hamlet = self.example_user("hamlet")
        iago = self.example_user("iago")
        message_id = self.send_stream_message(
            iago, "Verona", topic_name="api", content="list case insensitive"
        )
        Task.objects.create(
            message_id=message_id,
            assignee=hamlet,
            creator=iago,
            title="Hamlet case insensitive",
            description="",
        )

        result = self.api_get(iago, "/api/v1/users/me/tasks", {"assignee": hamlet.email.upper()})
        data = self.assert_json_success(result)
        self.assert_length(data["tasks"], 1)
        self.assertEqual(data["tasks"][0]["title"], "Hamlet case insensitive")

    def test_list_my_tasks_assignee_unknown_user(self) -> None:
        hamlet = self.example_user("hamlet")
        result = self.api_get(
            hamlet, "/api/v1/users/me/tasks", {"assignee": "not-a-real-user@zulip.com"}
        )
        self.assert_json_error(result, "User not-a-real-user@zulip.com not found")

    def test_create_task_invalid_due_date(self) -> None:
        hamlet = self.example_user("hamlet")
        message_id = self.send_stream_message(hamlet, "Verona", content="due")
        result = self.api_post(
            hamlet,
            f"/api/v1/messages/{message_id}/tasks",
            {"title": "t", "description": "", "due_date": "invalid-date"},
        )
        self.assert_json_error(result, "Invalid due date format")

    def test_create_task_unknown_assignee(self) -> None:
        hamlet = self.example_user("hamlet")
        message_id = self.send_stream_message(hamlet, "Verona", content="assignee bad")
        result = self.api_post(
            hamlet,
            f"/api/v1/messages/{message_id}/tasks",
            {"title": "t", "description": "", "assignee": "ghost@example.com"},
        )
        self.assert_json_error(result, "User ghost@example.com not found")

    def test_create_task_missing_title(self) -> None:
        hamlet = self.example_user("hamlet")
        message_id = self.send_stream_message(hamlet, "Verona", content="no title")
        result = self.api_post(
            hamlet,
            f"/api/v1/messages/{message_id}/tasks",
            {"title": "", "description": ""},
        )
        self.assert_json_error(result, "Missing title")

    def test_create_standalone_task_missing_title(self) -> None:
        hamlet = self.example_user("hamlet")
        result = self.api_post(hamlet, "/api/v1/tasks", {"title": "", "description": ""})
        self.assert_json_error(result, "Missing title")

    # ------------------------------------------------------------------
    # Due-date future-only validation
    # ------------------------------------------------------------------

    def test_create_task_past_due_date_rejected(self) -> None:
        hamlet = self.example_user("hamlet")
        message_id = self.send_stream_message(hamlet, "Verona", content="past date")
        yesterday = (now() - timedelta(days=1)).isoformat()
        result = self.api_post(
            hamlet,
            f"/api/v1/messages/{message_id}/tasks",
            {"title": "Overdue", "description": "", "due_date": yesterday},
        )
        self.assert_json_error(result, "Due date must be in the future")

    def test_create_task_present_due_date_rejected(self) -> None:
        hamlet = self.example_user("hamlet")
        message_id = self.send_stream_message(hamlet, "Verona", content="present date")
        # Subtract a small delta so the timestamp is guaranteed to be <= now()
        # by the time the view processes it.
        just_now = (now() - timedelta(seconds=1)).isoformat()
        result = self.api_post(
            hamlet,
            f"/api/v1/messages/{message_id}/tasks",
            {"title": "Right now", "description": "", "due_date": just_now},
        )
        self.assert_json_error(result, "Due date must be in the future")

    def test_create_task_future_due_date_accepted(self) -> None:
        hamlet = self.example_user("hamlet")
        message_id = self.send_stream_message(hamlet, "Verona", content="future date")
        tomorrow = (now() + timedelta(days=1)).isoformat()
        result = self.api_post(
            hamlet,
            f"/api/v1/messages/{message_id}/tasks",
            {"title": "Future task", "description": "", "due_date": tomorrow},
        )
        data = self.assert_json_success(
            result, ignored_parameters=["title", "description", "due_date"]
        )
        self.assertIsNotNone(data["due_date"])

    def test_create_standalone_task_past_due_date_rejected(self) -> None:
        hamlet = self.example_user("hamlet")
        yesterday = (now() - timedelta(days=1)).isoformat()
        result = self.api_post(
            hamlet,
            "/api/v1/tasks",
            {"title": "Late", "description": "", "due_date": yesterday},
        )
        self.assert_json_error(result, "Due date must be in the future")

    def test_create_standalone_task_future_due_date_accepted(self) -> None:
        hamlet = self.example_user("hamlet")
        tomorrow = (now() + timedelta(days=1)).isoformat()
        result = self.api_post(
            hamlet,
            "/api/v1/tasks",
            {"title": "Future standalone", "description": "", "due_date": tomorrow},
        )
        data = self.assert_json_success(result)
        self.assertIsNotNone(data["due_date"])

    def test_create_task_no_due_date_accepted(self) -> None:
        """Omitting due_date entirely must still succeed."""
        hamlet = self.example_user("hamlet")
        message_id = self.send_stream_message(hamlet, "Verona", content="no date")
        result = self.api_post(
            hamlet,
            f"/api/v1/messages/{message_id}/tasks",
            {"title": "No date", "description": ""},
        )
        data = self.assert_json_success(result, ignored_parameters=["title", "description"])
        self.assertIsNone(data["due_date"])

    def test_create_standalone_task_self_assigned_by_default(self) -> None:
        """When no assignee is provided the task is assigned to the creator."""
        hamlet = self.example_user("hamlet")
        result = self.api_post(hamlet, "/api/v1/tasks", {"title": "Self task", "description": ""})
        data = self.assert_json_success(result)
        task = Task.objects.get(id=data["task_id"])
        self.assertEqual(task.assignee_id, hamlet.id)
        self.assertEqual(task.creator_id, hamlet.id)

    def test_create_standalone_task_unknown_assignee_rejected(self) -> None:
        hamlet = self.example_user("hamlet")
        result = self.api_post(
            hamlet,
            "/api/v1/tasks",
            {"title": "Ghost assign", "description": "", "assignee": "nobody@example.com"},
        )
        self.assert_json_error(result, "User nobody@example.com not found")

    def test_create_standalone_task_invalid_due_date_format(self) -> None:
        hamlet = self.example_user("hamlet")
        result = self.api_post(
            hamlet,
            "/api/v1/tasks",
            {"title": "Bad date", "description": "", "due_date": "not-a-date"},
        )
        self.assert_json_error(result, "Invalid due date format")
