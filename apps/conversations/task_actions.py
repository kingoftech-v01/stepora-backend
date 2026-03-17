"""
Task action functions callable by the AI coach during chat conversations.

These functions allow the AI to create, update, complete, delete, and list
tasks on behalf of the user directly from the chat interface.
"""

import json
import logging
from datetime import datetime

from django.db.models import Q
from django.utils import timezone

from apps.dreams.models import Dream, Goal, Task
from apps.dreams.serializers import TaskSerializer

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Tool definitions (OpenAI tools format) for the chat AI
# ---------------------------------------------------------------------------

TASK_MANAGEMENT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "list_tasks",
            "description": (
                "List the user's tasks. Can filter by date, date range, dream, "
                "or status. Returns up to 20 tasks."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "date": {
                        "type": "string",
                        "description": "Filter tasks for a specific date (YYYY-MM-DD)",
                    },
                    "date_from": {
                        "type": "string",
                        "description": "Start of date range (YYYY-MM-DD)",
                    },
                    "date_to": {
                        "type": "string",
                        "description": "End of date range (YYYY-MM-DD)",
                    },
                    "dream_id": {
                        "type": "string",
                        "description": "Filter by dream UUID",
                    },
                    "status": {
                        "type": "string",
                        "enum": ["pending", "completed", "skipped"],
                        "description": "Filter by task status",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_task",
            "description": (
                "Create a new task for the user. Requires a title. "
                "If dream_id is not provided, uses the user's most recent active dream. "
                "If goal_id is not provided, uses the first pending goal of that dream."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "Task title (short, actionable)",
                    },
                    "description": {
                        "type": "string",
                        "description": "Detailed task description with instructions",
                    },
                    "due_date": {
                        "type": "string",
                        "description": "Scheduled date in YYYY-MM-DD format",
                    },
                    "due_time": {
                        "type": "string",
                        "description": "Scheduled time in HH:MM format",
                    },
                    "duration_minutes": {
                        "type": "integer",
                        "description": "Estimated duration in minutes",
                    },
                    "dream_id": {
                        "type": "string",
                        "description": "UUID of the dream to associate with",
                    },
                    "goal_id": {
                        "type": "string",
                        "description": "UUID of the goal to create the task under",
                    },
                },
                "required": ["title"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_task",
            "description": (
                "Update an existing task. Provide the task_id and any fields to change. "
                "Can update title, description, scheduled date/time, duration, or status."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "string",
                        "description": "UUID of the task to update",
                    },
                    "title": {
                        "type": "string",
                        "description": "New title",
                    },
                    "description": {
                        "type": "string",
                        "description": "New description",
                    },
                    "due_date": {
                        "type": "string",
                        "description": "New scheduled date (YYYY-MM-DD)",
                    },
                    "due_time": {
                        "type": "string",
                        "description": "New scheduled time (HH:MM)",
                    },
                    "duration_minutes": {
                        "type": "integer",
                        "description": "New duration in minutes",
                    },
                    "status": {
                        "type": "string",
                        "enum": ["pending", "completed", "skipped"],
                        "description": "New status",
                    },
                },
                "required": ["task_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "complete_task",
            "description": (
                "Mark a task as completed. Can find the task by ID or by searching "
                "the title/description with an optional date filter."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "string",
                        "description": "UUID of the task to complete",
                    },
                    "search_title": {
                        "type": "string",
                        "description": (
                            "Search for the task by title keywords "
                            "(used when task_id is not known)"
                        ),
                    },
                    "search_date": {
                        "type": "string",
                        "description": "Date to narrow the search (YYYY-MM-DD)",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_task",
            "description": (
                "Delete a task. Can find the task by ID or by searching "
                "the title/description with an optional date filter."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "string",
                        "description": "UUID of the task to delete",
                    },
                    "search_title": {
                        "type": "string",
                        "description": (
                            "Search for the task by title keywords "
                            "(used when task_id is not known)"
                        ),
                    },
                    "search_date": {
                        "type": "string",
                        "description": "Date to narrow the search (YYYY-MM-DD)",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "find_tasks",
            "description": (
                "Search for tasks by title/description keywords. "
                "Returns matching tasks so the AI can reference them."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search keywords to match against task titles",
                    },
                    "date": {
                        "type": "string",
                        "description": "Optional date filter (YYYY-MM-DD)",
                    },
                    "status": {
                        "type": "string",
                        "enum": ["pending", "completed", "skipped"],
                        "description": "Optional status filter",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_dreams",
            "description": (
                "List the user's active dreams with their IDs. "
                "Useful when the AI needs to know which dreams exist "
                "before creating a task."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
]


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------

def _serialize_task_data(data):
    """Convert DRF serializer output to plain JSON-safe dicts.

    ``TaskSerializer.data`` returns ``ReturnDict`` / ``ReturnList`` objects
    that may contain ``uuid.UUID``, ``datetime``, ``date``, or ``Decimal``
    values which are not natively JSON-serialisable by psycopg2.  Round-
    tripping through ``json.dumps(default=str)`` guarantees plain types.
    """
    return json.loads(json.dumps(data, default=str))


def _parse_date(date_str):
    """Parse a date string in YYYY-MM-DD format, returns a date object or None."""
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def _user_tasks_qs(user):
    """Base queryset for tasks belonging to the user."""
    return Task.objects.filter(goal__dream__user=user)


def _find_task_by_search(user, search_title, search_date=None):
    """
    Find a task by fuzzy matching on the title.
    Since title/description are encrypted, we fetch candidates and filter in Python.
    Returns (task, error_message).
    """
    qs = _user_tasks_qs(user).filter(status="pending")

    if search_date:
        d = _parse_date(search_date)
        if d:
            qs = qs.filter(
                Q(scheduled_date__date=d)
                | Q(expected_date=d)
                | Q(deadline_date=d)
            )

    # Encrypted fields cannot be searched with icontains in DB,
    # so fetch candidates and filter in Python
    keywords = [kw.lower() for kw in search_title.strip().split() if kw]
    candidates = list(qs.order_by("-created_at")[:100])

    results = []
    for task in candidates:
        title_lower = (task.title or "").lower()
        desc_lower = (task.description or "").lower()
        if all(kw in title_lower or kw in desc_lower for kw in keywords):
            results.append(task)
        if len(results) >= 5:
            break

    if len(results) == 0:
        return None, "No task found matching the search criteria."
    if len(results) == 1:
        return results[0], None
    # Multiple matches — return list for disambiguation
    task_list = ", ".join(
        f'"{t.title}" (id: {t.id})' for t in results
    )
    return None, f"Multiple tasks found: {task_list}. Please specify which one."


def _get_default_goal(user, dream_id=None):
    """Get a suitable goal to create a task under."""
    if dream_id:
        dream = Dream.objects.filter(id=dream_id, user=user).first()
        if not dream:
            return None, "Dream not found."
    else:
        dream = (
            Dream.objects.filter(user=user, status="active")
            .order_by("-updated_at")
            .first()
        )
        if not dream:
            return None, "No active dream found. Please create a dream first."

    # Find a goal — prefer pending, then in_progress, then any
    goal = (
        dream.goals.filter(status__in=["pending", "in_progress"])
        .order_by("order")
        .first()
    )
    if not goal:
        goal = dream.goals.order_by("order").first()
    if not goal:
        # Auto-create a default goal
        max_order = dream.goals.count()
        goal = Goal.objects.create(
            dream=dream,
            title="Tasks from AI Coach",
            description="Tasks created by the AI coach during chat conversations.",
            order=max_order + 1,
            status="in_progress",
        )
    return goal, None


# ---------------------------------------------------------------------------
# Action functions (called by the AI via tool use)
# ---------------------------------------------------------------------------

def list_tasks(user, date=None, date_from=None, date_to=None,
               dream_id=None, status=None, **kwargs):
    """List tasks for the user, optionally filtered."""
    qs = _user_tasks_qs(user)

    if date:
        d = _parse_date(date)
        if d:
            qs = qs.filter(
                Q(scheduled_date__date=d)
                | Q(expected_date=d)
                | Q(deadline_date=d)
            )

    if date_from:
        d = _parse_date(date_from)
        if d:
            qs = qs.filter(
                Q(scheduled_date__date__gte=d)
                | Q(expected_date__gte=d)
            )

    if date_to:
        d = _parse_date(date_to)
        if d:
            qs = qs.filter(
                Q(scheduled_date__date__lte=d)
                | Q(expected_date__lte=d)
            )

    if dream_id:
        qs = qs.filter(goal__dream_id=dream_id)

    if status:
        qs = qs.filter(status=status)

    tasks = list(qs.select_related("goal", "goal__dream")[:20])
    serialized = _serialize_task_data(TaskSerializer(tasks, many=True).data)

    return {
        "success": True,
        "action": "listed",
        "count": len(serialized),
        "tasks": serialized,
    }


def create_task(user, title, description=None, due_date=None, due_time=None,
                duration_minutes=None, dream_id=None, goal_id=None, **kwargs):
    """Create a new task for the user."""
    if goal_id:
        goal = Goal.objects.filter(id=goal_id, dream__user=user).first()
        if not goal:
            return {"success": False, "error": "Goal not found or access denied."}
    else:
        goal, error = _get_default_goal(user, dream_id)
        if error:
            return {"success": False, "error": error}

    # Determine order
    max_order = goal.tasks.count()

    task_data = {
        "goal": goal,
        "title": title[:255],
        "description": description or "",
        "order": max_order + 1,
    }

    if due_date:
        d = _parse_date(due_date)
        if d:
            task_data["scheduled_date"] = timezone.make_aware(
                datetime.combine(d, datetime.min.time())
            )
            task_data["expected_date"] = d

    if due_time:
        task_data["scheduled_time"] = due_time[:5]

    if duration_minutes:
        task_data["duration_mins"] = max(1, min(duration_minutes, 1440))

    task = Task.objects.create(**task_data)
    serialized = _serialize_task_data(TaskSerializer(task).data)

    return {
        "success": True,
        "action": "created",
        "task": serialized,
        "dream_title": goal.dream.title,
        "goal_title": goal.title,
    }


def update_task(user, task_id, title=None, description=None, due_date=None,
                due_time=None, duration_minutes=None, status=None, **kwargs):
    """Update an existing task."""
    task = _user_tasks_qs(user).filter(id=task_id).first()
    if not task:
        return {"success": False, "error": "Task not found or access denied."}

    if title:
        task.title = title[:255]
    if description is not None:
        task.description = description
    if due_date:
        d = _parse_date(due_date)
        if d:
            task.scheduled_date = timezone.make_aware(
                datetime.combine(d, datetime.min.time())
            )
            task.expected_date = d
    if due_time:
        task.scheduled_time = due_time[:5]
    if duration_minutes is not None:
        task.duration_mins = max(1, min(duration_minutes, 1440))
    if status and status in ("pending", "completed", "skipped"):
        if status == "completed" and task.status != "completed":
            task.complete()
            serialized = _serialize_task_data(TaskSerializer(task).data)
            return {
                "success": True,
                "action": "completed",
                "task": serialized,
            }
        task.status = status

    task.save()
    serialized = _serialize_task_data(TaskSerializer(task).data)

    return {
        "success": True,
        "action": "updated",
        "task": serialized,
    }


def complete_task(user, task_id=None, search_title=None, search_date=None, **kwargs):
    """Mark a task as completed."""
    if task_id:
        task = _user_tasks_qs(user).filter(id=task_id).first()
        if not task:
            return {"success": False, "error": "Task not found or access denied."}
    elif search_title:
        task, error = _find_task_by_search(user, search_title, search_date)
        if error:
            return {"success": False, "error": error}
    else:
        return {"success": False, "error": "Provide task_id or search_title."}

    if task.status == "completed":
        return {
            "success": True,
            "action": "completed",
            "task": _serialize_task_data(TaskSerializer(task).data),
            "note": "Task was already completed.",
        }

    task.complete()
    serialized = _serialize_task_data(TaskSerializer(task).data)

    return {
        "success": True,
        "action": "completed",
        "task": serialized,
    }


def delete_task(user, task_id=None, search_title=None, search_date=None, **kwargs):
    """Delete a task."""
    if task_id:
        task = _user_tasks_qs(user).filter(id=task_id).first()
        if not task:
            return {"success": False, "error": "Task not found or access denied."}
    elif search_title:
        task, error = _find_task_by_search(user, search_title, search_date)
        if error:
            return {"success": False, "error": error}
    else:
        return {"success": False, "error": "Provide task_id or search_title."}

    task_data = _serialize_task_data(TaskSerializer(task).data)
    task_title = task.title
    task.delete()

    return {
        "success": True,
        "action": "deleted",
        "task": task_data,
        "deleted_title": task_title,
    }


def find_tasks(user, query, date=None, status=None, **kwargs):
    """Search for tasks by title/description keywords.
    Since title/description are encrypted, we filter in Python."""
    qs = _user_tasks_qs(user)

    if status:
        qs = qs.filter(status=status)

    if date:
        d = _parse_date(date)
        if d:
            qs = qs.filter(
                Q(scheduled_date__date=d)
                | Q(expected_date=d)
                | Q(deadline_date=d)
            )

    # Encrypted fields: fetch candidates, filter in Python
    keywords = [kw.lower() for kw in query.strip().split() if kw]
    candidates = list(qs.select_related("goal", "goal__dream").order_by("-created_at")[:100])

    results = []
    for task in candidates:
        title_lower = (task.title or "").lower()
        desc_lower = (task.description or "").lower()
        if all(kw in title_lower or kw in desc_lower for kw in keywords):
            results.append(task)
        if len(results) >= 10:
            break

    serialized = _serialize_task_data(TaskSerializer(results, many=True).data)

    return {
        "success": True,
        "action": "found",
        "count": len(serialized),
        "tasks": serialized,
    }


def list_dreams(user, **kwargs):
    """List the user's active dreams."""
    dreams = Dream.objects.filter(user=user, status="active").order_by("-updated_at")[:10]
    dream_list = [
        {
            "id": str(d.id),
            "title": d.title,
            "category": d.category,
            "progress": round(d.progress_percentage, 1),
            "goal_count": d.goals.count(),
        }
        for d in dreams
    ]

    return {
        "success": True,
        "action": "listed_dreams",
        "count": len(dream_list),
        "dreams": dream_list,
    }


# ---------------------------------------------------------------------------
# Dispatcher — maps tool call names to functions
# ---------------------------------------------------------------------------

TOOL_DISPATCH = {
    "list_tasks": list_tasks,
    "create_task": create_task,
    "update_task": update_task,
    "complete_task": complete_task,
    "delete_task": delete_task,
    "find_tasks": find_tasks,
    "list_dreams": list_dreams,
}


def execute_tool_call(user, tool_name, arguments):
    """
    Execute a tool call from the AI.
    Returns a dict with the result.
    """
    func = TOOL_DISPATCH.get(tool_name)
    if not func:
        logger.warning("Unknown task tool called: %s", tool_name)
        return {"success": False, "error": f"Unknown tool: {tool_name}"}

    try:
        result = func(user, **arguments)
        logger.info(
            "Task tool %s executed for user %s: success=%s",
            tool_name, user.id, result.get("success"),
        )
        return result
    except Exception as e:
        logger.error(
            "Task tool %s failed for user %s: %s",
            tool_name, user.id, str(e), exc_info=True,
        )
        return {"success": False, "error": f"Tool execution error: {str(e)}"}
