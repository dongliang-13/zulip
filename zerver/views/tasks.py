from __future__ import annotations

from typing import Any

import orjson
from django.db import transaction
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.utils.translation import gettext as _

from zerver.lib.exceptions import JsonableError
from zerver.lib.message import access_message
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import typed_endpoint
from zerver.lib.widget import get_widget_type
from zerver.models.messages import Message, SubMessage, Task
from zerver.models.users import UserProfile


def _get_current_todo_tasks_for_message(message: Message) -> dict[str, dict[str, str]]:
    """
    Reconstruct the current set of todo tasks for a message from its
    widget submessages, mirroring the client-side todo widget logic.
    The returned dict is keyed by task title.
    """

    submessages = (
        SubMessage.objects.filter(message_id=message.id, msg_type="widget")
        .order_by("id")
        .only("content")
    )

    tasks: dict[str, dict[str, str]] = {}

    for index, submessage in enumerate(submessages):
        try:
            data = orjson.loads(submessage.content)
        except orjson.JSONDecodeError:
            continue

        # The first widget submessage is the widget payload containing
        # initial extra_data, including the initial task list.
        if index == 0 and isinstance(data, dict) and "widget_type" in data:
            extra_data = data.get("extra_data") or {}
            if not isinstance(extra_data, dict):
                continue
            raw_tasks = extra_data.get("tasks") or []
            if not isinstance(raw_tasks, list):
                continue
            for task_item in raw_tasks:
                if not isinstance(task_item, dict):
                    continue
                title = task_item.get("task")
                desc = task_item.get("desc", "")
                if not isinstance(title, str) or title in tasks:
                    continue
                if not isinstance(desc, str):
                    desc = ""
                tasks[title] = {"task": title, "desc": desc}
            continue

        # Subsequent submessages are widget events; we only care about
        # new_task events for existence checks.
        if not isinstance(data, dict):
            continue
        if data.get("type") != "new_task":
            continue

        title = data.get("task")
        desc = data.get("desc", "")
        if not isinstance(title, str) or title in tasks:
            continue
        if not isinstance(desc, str):
            desc = ""
        tasks[title] = {"task": title, "desc": desc}

    return tasks


@transaction.atomic(durable=True)
@typed_endpoint
def create_task(
    request: HttpRequest,
    user_profile: UserProfile,
    message_id: int,
    *,
    title: str,
) -> HttpResponse:
    """
    Convert a todo widget item in a message into a Task linked to that message.
    Multiple conversions of the same item by the same user are handled
    idempotently.
    """

    if not title:
        raise JsonableError(_("Missing title"))

    # Enforce that the acting user can view (and thus create a task for) the message.
    message = access_message(
        user_profile,
        message_id,
        lock_message=True,
        is_modifying_message=True,
    )

    widget_type = get_widget_type(message_id=message.id)
    if widget_type != "todo":
        raise JsonableError(_("Message is not a to-do list."))

    todo_tasks = _get_current_todo_tasks_for_message(message)
    if title not in todo_tasks:
        raise JsonableError(_("The specified checklist item does not exist in this message."))

    # Avoid creating duplicate tasks for the same user/message/title.
    task, _created = Task.objects.get_or_create(
        message=message,
        creator=user_profile,
        assignee=user_profile,
        title=title,
        defaults={
            # We don't currently propagate descriptions from the widget,
            # but this can be extended in future stories.
            "description": todo_tasks[title]["desc"],
        },
    )

    data: dict[str, Any] = {
        "task_id": task.id,
        "title": task.title,
        "description": task.description,
        "completed": task.completed,
    }
    return json_success(request, data)


@typed_endpoint
def list_message_tasks(
    request: HttpRequest,
    user_profile: UserProfile,
    message_id: int,
) -> HttpResponse:
    """
    List tasks linked to a message. Visibility is governed by the
    caller's ability to access the underlying message.
    """

    message = access_message(
        user_profile,
        message_id,
        lock_message=False,
        is_modifying_message=False,
    )

    tasks = Task.objects.filter(message=message)
    results: list[dict[str, Any]] = [
        {
            "id": task.id,
            "title": task.title,
            "description": task.description,
            "completed": task.completed,
        }
        for task in tasks
    ]
    return json_success(request, data={"tasks": results})