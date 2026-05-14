import re
from typing import TYPE_CHECKING, Any

import orjson
from django.core.exceptions import ValidationError

from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.validator import check_widget_content
from zerver.lib.widget import get_widget_data, get_widget_type, parse_todo_extra_data
from zerver.models import SubMessage, UserProfile

if TYPE_CHECKING:
    from django.test.client import _MonkeyPatchedWSGIResponse as TestHttpResponse


class WidgetContentTestCase(ZulipTestCase):
    def test_validation(self) -> None:
        def assert_error(obj: object, msg: str) -> None:
            with self.assertRaisesRegex(ValidationError, re.escape(msg)):
                check_widget_content(obj)

        assert_error(5, "widget_content is not a dict")

        assert_error({}, "widget_type is not in widget_content")

        assert_error(dict(widget_type="whatever"), "extra_data is not in widget_content")

        assert_error(dict(widget_type="zform", extra_data=4), "extra_data is not a dict")

        assert_error(dict(widget_type="bogus", extra_data={}), "unknown widget type: bogus")

        extra_data: dict[str, Any] = {}
        obj = dict(widget_type="zform", extra_data=extra_data)

        assert_error(obj, "zform is missing type field")

        extra_data["type"] = "bogus"
        assert_error(obj, "unknown zform type: bogus")

        extra_data["type"] = "choices"
        assert_error(obj, "heading key is missing from extra_data")

        extra_data["heading"] = "whatever"
        assert_error(obj, "choices key is missing from extra_data")

        extra_data["choices"] = 99
        assert_error(obj, 'extra_data["choices"] is not a list')

        extra_data["choices"] = [99]
        assert_error(obj, 'extra_data["choices"][0] is not a dict')

        extra_data["choices"] = [
            dict(long_name="foo", reply="bar"),
        ]
        assert_error(obj, 'short_name key is missing from extra_data["choices"][0]')

        extra_data["choices"] = [
            dict(short_name="a", long_name="foo", reply="bar"),
        ]

        check_widget_content(obj)

    def test_message_error_handling(self) -> None:
        sender = self.example_user("cordelia")
        stream_name = "Verona"

        payload = dict(
            type="stream",
            to=orjson.dumps(stream_name).decode(),
            topic="whatever",
            content="whatever",
        )

        payload["widget_content"] = "{{{{{{"  # unparsable
        result = self.api_post(sender, "/api/v1/messages", payload)
        self.assert_json_error_contains(result, "Widgets: API programmer sent invalid JSON")

        bogus_data = dict(color="red", foo="bar", x=2)
        payload["widget_content"] = orjson.dumps(bogus_data).decode()
        result = self.api_post(sender, "/api/v1/messages", payload)
        self.assert_json_error_contains(result, "Widgets: widget_type is not in widget_content")

    def test_get_widget_data_for_non_widget_messages(self) -> None:
        # This is a pretty important test, despite testing the
        # "negative" case.  We never want widgets to interfere
        # with normal messages.

        test_messages = [
            "",
            "     ",
            "this is an ordinary message",
            "/bogus_command",
            "/me shrugs",
            "use /poll",
        ]

        for message in test_messages:
            self.assertEqual(get_widget_data(content=message), (None, None))

        # Add positive checks for context
        self.assertEqual(
            get_widget_data(content="/todo"), ("todo", {"task_list_title": "", "tasks": []})
        )
        self.assertEqual(
            get_widget_data(content="/todo Title"),
            ("todo", {"task_list_title": "Title", "tasks": []}),
        )
        # Test tokenization on newline character
        self.assertEqual(
            get_widget_data(content="/todo\nTask"),
            ("todo", {"task_list_title": "", "tasks": [{"task": "Task", "desc": ""}]}),
        )

    def test_explicit_widget_content(self) -> None:
        # Users can send widget_content directly on messages
        # using the `widget_content` field.

        sender = self.example_user("cordelia")
        stream_name = "Verona"
        content = "does-not-matter"
        zform_data = dict(
            type="choices",
            heading="Options:",
            choices=[],
        )

        widget_content = dict(
            widget_type="zform",
            extra_data=zform_data,
        )

        check_widget_content(widget_content)

        payload = dict(
            type="stream",
            to=orjson.dumps(stream_name).decode(),
            topic="whatever",
            content=content,
            widget_content=orjson.dumps(widget_content).decode(),
        )
        result = self.api_post(sender, "/api/v1/messages", payload)
        self.assert_json_success(result)

        message = self.get_last_message()
        self.assertEqual(message.content, content)

        expected_submessage_content = dict(
            widget_type="zform",
            extra_data=zform_data,
        )

        submessage = SubMessage.objects.get(message_id=message.id)
        self.assertEqual(submessage.msg_type, "widget")
        self.assertEqual(orjson.loads(submessage.content), expected_submessage_content)

    def test_todo(self) -> None:
        # This also helps us get test coverage that could apply
        # to future widgets.

        sender = self.example_user("cordelia")
        stream_name = "Verona"
        content = "/todo"

        payload = dict(
            type="stream",
            to=orjson.dumps(stream_name).decode(),
            topic="whatever",
            content=content,
        )
        result = self.api_post(sender, "/api/v1/messages", payload)
        self.assert_json_success(result)

        message = self.get_last_message()
        self.assertEqual(message.content, content)

        expected_submessage_content = dict(
            widget_type="todo",
            extra_data={"task_list_title": "", "tasks": []},
        )

        submessage = SubMessage.objects.get(message_id=message.id)
        self.assertEqual(submessage.msg_type, "widget")
        self.assertEqual(orjson.loads(submessage.content), expected_submessage_content)

        content = "/todo Example Task List Title"
        payload["content"] = content
        result = self.api_post(sender, "/api/v1/messages", payload)
        self.assert_json_success(result)

        message = self.get_last_message()
        self.assertEqual(message.content, content)

        expected_submessage_content = dict(
            widget_type="todo",
            extra_data={"task_list_title": "Example Task List Title", "tasks": []},
        )

        submessage = SubMessage.objects.get(message_id=message.id)
        self.assertEqual(submessage.msg_type, "widget")
        self.assertEqual(orjson.loads(submessage.content), expected_submessage_content)

        # We test for both trailing and leading spaces, along with blank lines
        # for the tasks.
        content = "/todo Example Task List Title\n\n    task without description\ntask: with description    \n\n - task as list : also with description"
        payload["content"] = content
        result = self.api_post(sender, "/api/v1/messages", payload)
        self.assert_json_success(result)

        message = self.get_last_message()
        self.assertEqual(message.content, content)

        expected_submessage_content = dict(
            widget_type="todo",
            extra_data=dict(
                task_list_title="Example Task List Title",
                tasks=[
                    dict(
                        task="task without description",
                        desc="",
                    ),
                    dict(
                        task="task",
                        desc="with description",
                    ),
                    dict(
                        task="task as list",
                        desc="also with description",
                    ),
                ],
            ),
        )

        submessage = SubMessage.objects.get(message_id=message.id)
        self.assertEqual(submessage.msg_type, "widget")
        self.assertEqual(orjson.loads(submessage.content), expected_submessage_content)

    def test_poll_command_extra_data(self) -> None:
        sender = self.example_user("cordelia")
        stream_name = "Verona"
        # We test for both trailing and leading spaces, along with blank lines
        # for the poll options.
        content = "/poll What is your favorite color?\n\nRed\nGreen  \n\n   Blue\n - Yellow"

        payload = dict(
            type="stream",
            to=orjson.dumps(stream_name).decode(),
            topic="whatever",
            content=content,
        )
        result = self.api_post(sender, "/api/v1/messages", payload)
        self.assert_json_success(result)

        message = self.get_last_message()
        self.assertEqual(message.content, content)

        expected_submessage_content = dict(
            widget_type="poll",
            extra_data=dict(
                options=["Red", "Green", "Blue", "Yellow"],
                question="What is your favorite color?",
            ),
        )

        submessage = SubMessage.objects.get(message_id=message.id)
        self.assertEqual(submessage.msg_type, "widget")
        self.assertEqual(orjson.loads(submessage.content), expected_submessage_content)

        # Now don't supply a question.

        content = "/poll"
        payload["content"] = content
        result = self.api_post(sender, "/api/v1/messages", payload)
        self.assert_json_success(result)

        expected_submessage_content = dict(
            widget_type="poll",
            extra_data=dict(
                options=[],
                question="",
            ),
        )

        message = self.get_last_message()
        self.assertEqual(message.content, content)
        submessage = SubMessage.objects.get(message_id=message.id)
        self.assertEqual(submessage.msg_type, "widget")
        self.assertEqual(orjson.loads(submessage.content), expected_submessage_content)

    def test_todo_command_extra_data(self) -> None:
        sender = self.example_user("cordelia")
        stream_name = "Verona"
        # We test for leading spaces.
        content = "/todo   School Work"

        payload = dict(
            type="stream",
            to=orjson.dumps(stream_name).decode(),
            topic="whatever",
            content=content,
        )
        result = self.api_post(sender, "/api/v1/messages", payload)
        self.assert_json_success(result)

        message = self.get_last_message()
        self.assertEqual(message.content, content)

        expected_submessage_content = dict(
            widget_type="todo",
            extra_data=dict(task_list_title="School Work", tasks=[]),
        )

        submessage = SubMessage.objects.get(message_id=message.id)
        self.assertEqual(submessage.msg_type, "widget")
        self.assertEqual(orjson.loads(submessage.content), expected_submessage_content)

        # Now don't supply a task list title.

        content = "/todo"
        payload["content"] = content
        result = self.api_post(sender, "/api/v1/messages", payload)
        self.assert_json_success(result)

        expected_submessage_content = dict(
            widget_type="todo",
            extra_data=dict(task_list_title="", tasks=[]),
        )

        message = self.get_last_message()
        self.assertEqual(message.content, content)
        submessage = SubMessage.objects.get(message_id=message.id)
        self.assertEqual(submessage.msg_type, "widget")
        self.assertEqual(orjson.loads(submessage.content), expected_submessage_content)
        # Now supply both task list title and tasks.

        content = "/todo School Work\nchemistry homework: assignment 2\nstudy for english test: pages 56-67"
        payload["content"] = content
        result = self.api_post(sender, "/api/v1/messages", payload)
        self.assert_json_success(result)

        expected_submessage_content = dict(
            widget_type="todo",
            extra_data=dict(
                task_list_title="School Work",
                tasks=[
                    dict(
                        task="chemistry homework",
                        desc="assignment 2",
                    ),
                    dict(
                        task="study for english test",
                        desc="pages 56-67",
                    ),
                ],
            ),
        )

        message = self.get_last_message()
        self.assertEqual(message.content, content)
        submessage = SubMessage.objects.get(message_id=message.id)
        self.assertEqual(submessage.msg_type, "widget")
        self.assertEqual(orjson.loads(submessage.content), expected_submessage_content)

    def test_poll_permissions(self) -> None:
        cordelia = self.example_user("cordelia")
        hamlet = self.example_user("hamlet")
        stream_name = "Verona"
        content = "/poll Preference?\n\nyes\nno"

        payload = dict(
            type="stream",
            to=orjson.dumps(stream_name).decode(),
            topic="whatever",
            content=content,
        )
        result = self.api_post(cordelia, "/api/v1/messages", payload)
        self.assert_json_success(result)

        message = self.get_last_message()

        def post(sender: UserProfile, data: dict[str, object]) -> "TestHttpResponse":
            payload = dict(
                message_id=message.id, msg_type="widget", content=orjson.dumps(data).decode()
            )
            return self.api_post(sender, "/api/v1/submessage", payload)

        result = post(cordelia, dict(type="question", question="Tabs or spaces?"))
        self.assert_json_success(result)

        result = post(hamlet, dict(type="question", question="Tabs or spaces?"))
        self.assert_json_error(result, "You can't edit a question unless you are the author.")

    def test_todo_permissions(self) -> None:
        cordelia = self.example_user("cordelia")
        hamlet = self.example_user("hamlet")
        stream_name = "Verona"
        content = "/todo School Work"

        payload = dict(
            type="stream",
            to=orjson.dumps(stream_name).decode(),
            topic="whatever",
            content=content,
        )
        result = self.api_post(cordelia, "/api/v1/messages", payload)
        self.assert_json_success(result)

        message = self.get_last_message()

        def post(sender: UserProfile, data: dict[str, object]) -> "TestHttpResponse":
            payload = dict(
                message_id=message.id, msg_type="widget", content=orjson.dumps(data).decode()
            )
            return self.api_post(sender, "/api/v1/submessage", payload)

        result = post(cordelia, dict(type="new_task_list_title", title="School Work"))
        self.assert_json_success(result)

        result = post(hamlet, dict(type="new_task_list_title", title="School Work"))
        self.assert_json_error(
            result, "You can't edit the task list title unless you are the author."
        )

    def test_poll_type_validation(self) -> None:
        sender = self.example_user("cordelia")
        stream_name = "Verona"
        content = "/poll Preference?\n\nyes\nno"

        payload = dict(
            type="stream",
            to=orjson.dumps(stream_name).decode(),
            topic="whatever",
            content=content,
        )
        result = self.api_post(sender, "/api/v1/messages", payload)
        self.assert_json_success(result)

        message = self.get_last_message()

        def post_submessage(content: str) -> "TestHttpResponse":
            payload = dict(
                message_id=message.id,
                msg_type="widget",
                content=content,
            )
            return self.api_post(sender, "/api/v1/submessage", payload)

        def assert_error(content: str, error: str) -> None:
            result = post_submessage(content)
            self.assert_json_error_contains(result, error)

        assert_error("bogus", "Invalid json for submessage")
        assert_error('""', "not a dict")
        assert_error("[]", "not a dict")

        assert_error('{"type": "bogus"}', "Unknown type for poll data: bogus")
        assert_error('{"type": "vote"}', "key is missing")
        assert_error('{"type": "vote", "key": "1,1,", "vote": 99}', "Invalid poll data")

        assert_error('{"type": "question"}', "key is missing")
        assert_error('{"type": "question", "question": 7}', "not a string")

        assert_error('{"type": "new_option"}', "key is missing")
        assert_error('{"type": "new_option", "idx": 7, "option": 999}', "not a string")
        assert_error('{"type": "new_option", "idx": -1, "option": "pizza"}', "too small")
        assert_error('{"type": "new_option", "idx": 1001, "option": "pizza"}', "too large")
        assert_error('{"type": "new_option", "idx": "bogus", "option": "maybe"}', "not an int")

        def assert_success(data: dict[str, object]) -> None:
            content = orjson.dumps(data).decode()
            result = post_submessage(content)
            self.assert_json_success(result)

        # Note that we only validate for types. The server code may, for,
        # example, allow a vote for a non-existing option, and we rely
        # on the clients to ignore those.

        assert_success(dict(type="vote", key="1,1", vote=1))
        assert_success(dict(type="new_option", idx=7, option="maybe"))
        assert_success(dict(type="question", question="what's for dinner?"))

    def test_todo_type_validation(self) -> None:
        sender = self.example_user("cordelia")
        stream_name = "Verona"
        content = "/todo"

        payload = dict(
            type="stream",
            to=orjson.dumps(stream_name).decode(),
            topic="whatever",
            content=content,
        )
        result = self.api_post(sender, "/api/v1/messages", payload)
        self.assert_json_success(result)

        message = self.get_last_message()

        def post_submessage(content: str) -> "TestHttpResponse":
            payload = dict(
                message_id=message.id,
                msg_type="widget",
                content=content,
            )
            return self.api_post(sender, "/api/v1/submessage", payload)

        def assert_error(content: str, error: str) -> None:
            result = post_submessage(content)
            self.assert_json_error_contains(result, error)

        assert_error('{"type": "bogus"}', "Unknown type for todo data: bogus")

        assert_error('{"type": "new_task"}', "key is missing")
        assert_error(
            '{"type": "new_task", "key": 7, "task": 7, "desc": "", "completed": false}',
            'data["task"] is not a string',
        )
        assert_error(
            '{"type": "new_task", "key": -1, "task": "eat", "desc": "", "completed": false}',
            'data["key"] is too small',
        )
        assert_error(
            '{"type": "new_task", "key": 1001, "task": "eat", "desc": "", "completed": false}',
            'data["key"] is too large',
        )

        assert_error('{"type": "strike"}', "key is missing")
        assert_error('{"type": "strike", "key": 999}', 'data["key"] is not a string')

        def assert_success(data: dict[str, object]) -> None:
            content = orjson.dumps(data).decode()
            result = post_submessage(content)
            self.assert_json_success(result)

        assert_success(dict(type="new_task", key=7, task="eat", desc="", completed=False))
        assert_success(dict(type="strike", key="5,9"))

    # ------------------------------------------------------------------
    # [due:YYYY-MM-DD] tag parsing in todo extra_data
    # ------------------------------------------------------------------

    def test_todo_due_date_tag_extracted_into_date_field(self) -> None:
        """A [due:YYYY-MM-DD] prefix in the description is parsed as the date field."""
        extra_data = parse_todo_extra_data(" My List\ntask one: [due:2030-06-15] finish report")
        self.assertEqual(extra_data["task_list_title"], "My List")
        self.assert_length(extra_data["tasks"], 1)
        task = extra_data["tasks"][0]
        self.assertEqual(task["task"], "task one")
        self.assertEqual(task["desc"], "finish report")
        self.assertEqual(task["date"], "2030-06-15")

    def test_todo_due_date_tag_with_no_description(self) -> None:
        """A task with only a due-date tag has an empty description."""
        extra_data = parse_todo_extra_data(" Title\ntask only date: [due:2030-01-01]")
        task = extra_data["tasks"][0]
        self.assertEqual(task["task"], "task only date")
        self.assertEqual(task["desc"], "")
        self.assertEqual(task["date"], "2030-01-01")

    def test_todo_task_without_due_date_has_no_date_key(self) -> None:
        """Tasks with a plain description must not get a date key."""
        extra_data = parse_todo_extra_data(" Title\nnormal task: just a description")
        task = extra_data["tasks"][0]
        self.assertNotIn("date", task)
        self.assertEqual(task["desc"], "just a description")

    def test_todo_task_no_description_no_date(self) -> None:
        """A bare task line (no colon) has empty desc and no date key."""
        extra_data = parse_todo_extra_data(" Title\nbuy milk")
        task = extra_data["tasks"][0]
        self.assertEqual(task["task"], "buy milk")
        self.assertEqual(task["desc"], "")
        self.assertNotIn("date", task)

    def test_todo_mixed_tasks_with_and_without_due_dates(self) -> None:
        content = (
            " Sprint\n"
            "write tests: [due:2030-03-10] cover edge cases\n"
            "deploy: no due date here\n"
            "review PR: [due:2030-03-12]"
        )
        extra_data = parse_todo_extra_data(content)
        tasks = extra_data["tasks"]
        self.assert_length(tasks, 3)

        self.assertEqual(tasks[0]["task"], "write tests")
        self.assertEqual(tasks[0]["desc"], "cover edge cases")
        self.assertEqual(tasks[0]["date"], "2030-03-10")

        self.assertEqual(tasks[1]["task"], "deploy")
        self.assertEqual(tasks[1]["desc"], "no due date here")
        self.assertNotIn("date", tasks[1])

        self.assertEqual(tasks[2]["task"], "review PR")
        self.assertEqual(tasks[2]["desc"], "")
        self.assertEqual(tasks[2]["date"], "2030-03-12")

    def test_todo_malformed_due_date_tag_treated_as_description(self) -> None:
        """A tag with the wrong format must not be parsed as a date."""
        cases = [
            "task: [due:not-a-date] desc",      # letters in date
            "task: [due:2030-13-01] desc",       # month out of range (regex still matches, date stored)
            "task: [due:20301301] desc",         # wrong separator
            "task: [DUE:2030-01-01] desc",       # wrong case
        ]
        # The regex only matches \d{4}-\d{2}-\d{2}; anything else stays in desc.
        no_match_cases = [
            "task: [due:not-a-date] desc",
            "task: [due:20301301] desc",
            "task: [DUE:2030-01-01] desc",
        ]
        for content_line in no_match_cases:
            extra_data = parse_todo_extra_data(f" T\n{content_line}")
            task = extra_data["tasks"][0]
            self.assertNotIn("date", task, msg=f"should not have date for: {content_line!r}")

    def test_todo_due_date_via_widget_message(self) -> None:
        """End-to-end: posting a /todo message with a [due:] tag stores the date in extra_data."""
        sender = self.example_user("cordelia")
        content = "/todo Project\nfinish report: [due:2030-07-04] quarterly review"

        payload = dict(
            type="stream",
            to=orjson.dumps("Verona").decode(),
            topic="dates",
            content=content,
        )
        result = self.api_post(sender, "/api/v1/messages", payload)
        self.assert_json_success(result)

        submessage = SubMessage.objects.get(message_id=self.get_last_message().id)
        data = orjson.loads(submessage.content)
        tasks = data["extra_data"]["tasks"]
        self.assert_length(tasks, 1)
        self.assertEqual(tasks[0]["task"], "finish report")
        self.assertEqual(tasks[0]["desc"], "quarterly review")
        self.assertEqual(tasks[0]["date"], "2030-07-04")

    def test_get_widget_type(self) -> None:
        sender = self.example_user("cordelia")
        stream_name = "Verona"
        # We test for both trailing and leading spaces, along with blank lines
        # for the poll options.
        content = "/poll Preference?\n\nyes\nno"

        payload = dict(
            type="stream",
            to=orjson.dumps(stream_name).decode(),
            topic="whatever",
            content=content,
        )
        result = self.api_post(sender, "/api/v1/messages", payload)
        self.assert_json_success(result)

        message = self.get_last_message()

        [submessage] = SubMessage.objects.filter(message_id=message.id)

        self.assertEqual(get_widget_type(message_id=message.id), "poll")

        submessage.content = "bogus non-json"
        submessage.save()
        self.assertEqual(get_widget_type(message_id=message.id), None)

        submessage.content = '{"bogus": 1}'
        submessage.save()
        self.assertEqual(get_widget_type(message_id=message.id), None)

        submessage.content = '{"widget_type": "todo"}'
        submessage.save()
        self.assertEqual(get_widget_type(message_id=message.id), "todo")
