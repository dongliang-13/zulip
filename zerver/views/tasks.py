from django.http import JsonResponse, HttpRequest, HttpResponse
from django.views.decorators.http import require_POST

from zerver.lib.typed_endpoint import typed_endpoint
from zerver.models.messages import Task, Message
from zerver.models.users import UserProfile

#TASKS.PY BY YANG LU
@require_POST
@typed_endpoint
def create_task(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    message_id: int,
) -> HttpResponse:

    title = request.POST.get("title")

    if not title:
        return JsonResponse({"error": "Missing title"}, status=400)

    try:
        message = Message.objects.get(id=message_id)
    except Message.DoesNotExist:
        return JsonResponse({"error": "Invalid message"}, status=404)

    user = user_profile

    #create a task and insert into postgresql
    task = Task.objects.create(
        message=message,
        assignee=user,
        creator=user,
        title=title,
    )

    return JsonResponse({
        "task_id": task.id,
        "title": task.title,
        "completed": task.completed,
    })