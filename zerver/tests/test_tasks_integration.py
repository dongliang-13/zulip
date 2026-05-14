from datetime import timedelta

from django.utils.timezone import now

from zerver.lib.test_classes import ZulipTestCase
from zerver.models.messages import TaskTimeLog


class TasksIntegrationTest(ZulipTestCase):
    def test_create_message_task_via_api_then_listed(self) -> None:
        hamlet = self.example_user("hamlet")
        message_id = self.send_stream_message(
            hamlet, "Verona", topic_name="int", content="integration body"
        )
        create = self.api_post(
            hamlet,
            f"/api/v1/messages/{message_id}/tasks",
            {"title": "Api created", "description": "d1"},
        )
        created = self.assert_json_success(create, ignored_parameters=["title", "description"])
        self.assertEqual(created["title"], "Api created")
        listed = self.assert_json_success(self.api_get(hamlet, "/api/v1/users/me/tasks"))
        self.assert_length(listed["tasks"], 1)
        row = listed["tasks"][0]
        self.assertEqual(row["task_id"], created["task_id"])
        self.assertEqual(row["message_id"], message_id)
        self.assertEqual(row["title"], "Api created")

    def test_standalone_task_create_then_listed(self) -> None:
        hamlet = self.example_user("hamlet")
        create = self.api_post(hamlet, "/api/v1/tasks", {"title": "Standalone", "description": "s"})
        created = self.assert_json_success(create)
        listed = self.assert_json_success(self.api_get(hamlet, "/api/v1/users/me/tasks"))
        self.assert_length(listed["tasks"], 1)
        self.assertEqual(listed["tasks"][0]["task_id"], created["task_id"])
        self.assertIsNone(listed["tasks"][0]["message_id"])

    def test_create_on_message_for_other_assignee_then_they_see_it(self) -> None:
        iago = self.example_user("iago")
        othello = self.example_user("othello")
        message_id = self.send_stream_message(iago, "Verona", content="handoff")
        self.assert_json_success(
            self.api_post(
                iago,
                f"/api/v1/messages/{message_id}/tasks",
                {"title": "For Othello", "description": "", "assignee": othello.email},
            ),
            ignored_parameters=["title", "description", "assignee"],
        )
        othello_list = self.assert_json_success(self.api_get(othello, "/api/v1/users/me/tasks"))
        self.assert_length(othello_list["tasks"], 1)
        self.assertEqual(othello_list["tasks"][0]["title"], "For Othello")

    def test_create_then_delete_then_list_empty(self) -> None:
        hamlet = self.example_user("hamlet")
        message_id = self.send_stream_message(hamlet, "Verona", content="delete flow")
        created = self.assert_json_success(
            self.api_post(
                hamlet,
                f"/api/v1/messages/{message_id}/tasks",
                {"title": "Tmp", "description": ""},
            ),
            ignored_parameters=["title", "description"],
        )
        task_id = created["task_id"]
        self.assert_json_success(self.api_post(hamlet, f"/api/v1/tasks/{task_id}/delete", {}))
        listed = self.assert_json_success(self.api_get(hamlet, "/api/v1/users/me/tasks"))
        self.assertEqual(listed["tasks"], [])

    # ------------------------------------------------------------------ #
    # Lifecycle and permission integration tests
    # ------------------------------------------------------------------ #

    def test_full_lifecycle_create_complete_uncomplete_delete(self) -> None:
        """Create → complete → uncomplete → delete; list reflects state at each step."""
        hamlet = self.example_user("hamlet")
        message_id = self.send_stream_message(hamlet, "Verona", content="lifecycle")

        created = self.assert_json_success(
            self.api_post(
                hamlet,
                f"/api/v1/messages/{message_id}/tasks",
                {"title": "Lifecycle", "description": ""},
            ),
            ignored_parameters=["title", "description"],
        )
        task_id = created["task_id"]

        listed = self.assert_json_success(self.api_get(hamlet, "/api/v1/users/me/tasks"))
        self.assert_length(listed["tasks"], 1)
        self.assertFalse(listed["tasks"][0]["completed"])

        self.assert_json_success(
            self.api_post(hamlet, f"/api/v1/tasks/{task_id}", {"completed": "true"})
        )
        listed = self.assert_json_success(self.api_get(hamlet, "/api/v1/users/me/tasks"))
        self.assertTrue(listed["tasks"][0]["completed"])
        self.assertIsNotNone(listed["tasks"][0]["completed_at"])

        self.assert_json_success(
            self.api_post(hamlet, f"/api/v1/tasks/{task_id}", {"completed": "false"})
        )
        listed = self.assert_json_success(self.api_get(hamlet, "/api/v1/users/me/tasks"))
        self.assertFalse(listed["tasks"][0]["completed"])
        self.assertIsNone(listed["tasks"][0]["completed_at"])

        self.assert_json_success(self.api_post(hamlet, f"/api/v1/tasks/{task_id}/delete", {}))
        listed = self.assert_json_success(self.api_get(hamlet, "/api/v1/users/me/tasks"))
        self.assertEqual(listed["tasks"], [])

    def test_creator_and_assignee_both_have_modify_permission(self) -> None:
        """Both creator and assignee can toggle completion and delete the task."""
        hamlet = self.example_user("hamlet")
        iago = self.example_user("iago")

        message_id = self.send_stream_message(hamlet, "Verona", content="perm integration")
        created = self.assert_json_success(
            self.api_post(
                hamlet,
                f"/api/v1/messages/{message_id}/tasks",
                {"title": "Shared perm", "description": "", "assignee": iago.email},
            ),
            ignored_parameters=["title", "description", "assignee"],
        )
        task_id = created["task_id"]

        # Assignee marks complete
        self.assert_json_success(
            self.api_post(iago, f"/api/v1/tasks/{task_id}", {"completed": "true"})
        )
        # Creator unmarks
        self.assert_json_success(
            self.api_post(hamlet, f"/api/v1/tasks/{task_id}", {"completed": "false"})
        )
        # Creator deletes
        self.assert_json_success(self.api_post(hamlet, f"/api/v1/tasks/{task_id}/delete", {}))
        # Task is gone from assignee's list
        listed = self.assert_json_success(self.api_get(iago, "/api/v1/users/me/tasks"))
        self.assertEqual(listed["tasks"], [])

    def test_future_due_date_stored_and_returned_in_list(self) -> None:
        """A future due date set at creation appears correctly in list_my_tasks."""
        hamlet = self.example_user("hamlet")
        message_id = self.send_stream_message(hamlet, "Verona", content="due date list")
        tomorrow = (now() + timedelta(days=1)).replace(microsecond=0)

        self.assert_json_success(
            self.api_post(
                hamlet,
                f"/api/v1/messages/{message_id}/tasks",
                {"title": "Dated", "description": "", "due_date": tomorrow.isoformat()},
            ),
            ignored_parameters=["title", "description", "due_date"],
        )

        listed = self.assert_json_success(self.api_get(hamlet, "/api/v1/users/me/tasks"))
        self.assert_length(listed["tasks"], 1)
        self.assertIsNotNone(listed["tasks"][0]["due_date"])

    def test_past_due_date_rejected_standalone(self) -> None:
        """A past due date on a standalone task is rejected end-to-end."""
        hamlet = self.example_user("hamlet")
        yesterday = (now() - timedelta(days=1)).isoformat()
        result = self.api_post(
            hamlet,
            "/api/v1/tasks",
            {"title": "Overdue", "description": "", "due_date": yesterday},
        )
        self.assert_json_error(result, "Due date must be in the future")
        listed = self.assert_json_success(self.api_get(hamlet, "/api/v1/users/me/tasks"))
        self.assertEqual(listed["tasks"], [])

    def test_time_tracking_full_flow(self) -> None:
        """Start → stop → logs shows a completed session; list reflects tracked time."""
        hamlet = self.example_user("hamlet")
        message_id = self.send_stream_message(hamlet, "Verona", content="time flow")
        task_id = self.assert_json_success(
            self.api_post(
                hamlet,
                f"/api/v1/messages/{message_id}/tasks",
                {"title": "Timed", "description": ""},
            ),
            ignored_parameters=["title", "description"],
        )["task_id"]

        start_data = self.assert_json_success(
            self.api_post(hamlet, f"/api/v1/tasks/{task_id}/time/start", {})
        )
        self.assertTrue(start_data["is_active"])

        # Back-date start so the computed duration is nonzero
        TaskTimeLog.objects.filter(task_id=task_id, end_time__isnull=True).update(
            start_time=now() - timedelta(seconds=10)
        )

        stop_data = self.assert_json_success(
            self.api_post(hamlet, f"/api/v1/tasks/{task_id}/time/stop", {})
        )
        self.assertGreater(stop_data["duration_seconds"], 0)
        self.assertIsNotNone(stop_data["end_time"])

        logs_data = self.assert_json_success(
            self.api_get(hamlet, f"/api/v1/tasks/{task_id}/time/logs")
        )
        self.assertEqual(logs_data["active_timer_count"], 0)
        self.assert_length(logs_data["time_logs"], 1)
        self.assertGreater(logs_data["total_time_seconds"], 0)

        listed = self.assert_json_success(self.api_get(hamlet, "/api/v1/users/me/tasks"))
        self.assertGreater(listed["tasks"][0]["total_time_seconds"], 0)
        self.assertFalse(listed["tasks"][0]["active_timer"])

    def test_two_users_can_independently_track_time_on_same_task(self) -> None:
        """Assignee and creator can each run their own concurrent timer."""
        hamlet = self.example_user("hamlet")
        iago = self.example_user("iago")

        message_id = self.send_stream_message(hamlet, "Verona", content="multi timer")
        created = self.assert_json_success(
            self.api_post(
                hamlet,
                f"/api/v1/messages/{message_id}/tasks",
                {"title": "Multi-timer", "description": "", "assignee": iago.email},
            ),
            ignored_parameters=["title", "description", "assignee"],
        )
        task_id = created["task_id"]

        self.assert_json_success(
            self.api_post(iago, f"/api/v1/tasks/{task_id}/time/start", {})
        )
        self.assert_json_success(
            self.api_post(hamlet, f"/api/v1/tasks/{task_id}/time/start", {})
        )

        logs_data = self.assert_json_success(
            self.api_get(iago, f"/api/v1/tasks/{task_id}/time/logs")
        )
        self.assertEqual(logs_data["active_timer_count"], 2)
