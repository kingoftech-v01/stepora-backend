"""
Check-in tool executor for the adaptive plan generation system.

Each method corresponds to a tool the AI can call during check-ins.
All methods return JSON-serializable dicts that get fed back to the AI as tool results.
"""

import logging
from datetime import date, timedelta

from django.db.models import Count, F, Q
from django.utils import timezone

logger = logging.getLogger(__name__)


class CheckInToolExecutor:
    """Executes tool calls from the AI check-in agent."""

    def __init__(self, dream, user):
        self.dream = dream
        self.user = user

    def _assert_owned(self, model_class, pk, field="dream"):
        """Verify that the object belongs to this dream. Raises ValueError if not."""
        obj = model_class.objects.filter(pk=pk).first()
        if not obj:
            raise ValueError(f"{model_class.__name__} {pk} not found")
        owner = getattr(obj, field, None)
        if field == "dream" and owner != self.dream:
            raise ValueError(
                f"{model_class.__name__} {pk} does not belong to this dream"
            )
        if field == "goal":
            if obj.goal.dream != self.dream:
                raise ValueError(
                    f"{model_class.__name__} {pk} does not belong to this dream"
                )
        return obj

    def dispatch(self, tool_name, args):
        """
        Route a tool call to the correct method.
        Returns (result_dict, is_finish_signal).
        """
        method = getattr(self, tool_name, None)
        if not method:
            return {"error": f"Unknown tool: {tool_name}", "success": False}, False

        try:
            result = method(**args)
            is_finish = tool_name in (
                "finish_check_in",
                "finish_questionnaire_generation",
            )
            return result, is_finish
        except Exception as e:
            logger.warning(f"Tool {tool_name} failed: {e}")
            return {"error": str(e), "success": False}, False

    def get_dream_progress(self, dream_id=None):
        """Returns current progress statistics for the dream, including full skeleton."""
        from apps.dreams.models import DreamMilestone, Goal, Task

        d = self.dream
        milestones = DreamMilestone.objects.filter(dream=d).order_by("order")
        total_tasks = Task.objects.filter(goal__dream=d).count()
        completed_tasks = Task.objects.filter(goal__dream=d, status="completed").count()
        pending_tasks = Task.objects.filter(goal__dream=d, status="pending").count()
        overdue = Task.objects.filter(
            goal__dream=d, status="pending", deadline_date__lt=timezone.now().date()
        ).count()

        # Tasks completed in the last 14 days
        two_weeks_ago = timezone.now() - timedelta(days=14)
        recent_completed = Task.objects.filter(
            goal__dream=d, status="completed", completed_at__gte=two_weeks_ago
        ).count()

        # Bulk-load goals and task counts to avoid N+1 queries
        from collections import defaultdict

        all_goals = (
            Goal.objects.filter(dream=d)
            .select_related("milestone")
            .order_by("milestone__order", "order")
        )
        goals_by_milestone = defaultdict(list)
        for g in all_goals:
            if g.milestone_id:
                goals_by_milestone[g.milestone_id].append(g)

        # Build task stats lookup: {goal_id: (total, done)}
        _raw = (
            Task.objects.filter(goal__dream=d)
            .values("goal_id")
            .annotate(total=Count("id"), done=Count("id", filter=Q(status="completed")))
        )
        task_stats = {row["goal_id"]: (row["total"], row["done"]) for row in _raw}

        # Milestone progress with goals nested
        ms_progress = []
        for ms in milestones:
            ms_total = 0
            ms_done = 0

            goals_data = []
            for g in goals_by_milestone.get(ms.id, []):
                g_total, g_done = task_stats.get(g.id, (0, 0))
                ms_total += g_total
                ms_done += g_done
                goals_data.append(
                    {
                        "goal_id": str(g.id),
                        "title": g.title,
                        "description": g.description[:200] if g.description else "",
                        "order": g.order,
                        "status": g.status,
                        "expected_date": (
                            str(g.expected_date) if g.expected_date else None
                        ),
                        "deadline_date": (
                            str(g.deadline_date) if g.deadline_date else None
                        ),
                        "total_tasks": g_total,
                        "completed_tasks": g_done,
                    }
                )

            ms_progress.append(
                {
                    "milestone_id": str(ms.id),
                    "title": ms.title,
                    "description": ms.description[:200] if ms.description else "",
                    "order": ms.order,
                    "has_tasks": ms.has_tasks,
                    "status": ms.status,
                    "expected_date": (
                        str(ms.expected_date) if ms.expected_date else None
                    ),
                    "deadline_date": (
                        str(ms.deadline_date) if ms.deadline_date else None
                    ),
                    "total_tasks": ms_total,
                    "completed_tasks": ms_done,
                    "progress": (
                        round(ms_done / ms_total * 100, 1) if ms_total > 0 else 0
                    ),
                    "goals": goals_data,
                }
            )

        # Calculate velocity (tasks/week over last 4 weeks)
        four_weeks_ago = timezone.now() - timedelta(days=28)
        recent_4w = Task.objects.filter(
            goal__dream=d, status="completed", completed_at__gte=four_weeks_ago
        ).count()
        velocity = round(recent_4w / 4, 1)

        return {
            "success": True,
            "dream_title": d.title,
            "overall_progress": round(d.progress_percentage, 1),
            "total_tasks": total_tasks,
            "completed_tasks": completed_tasks,
            "pending_tasks": pending_tasks,
            "overdue_tasks": overdue,
            "tasks_completed_last_14_days": recent_completed,
            "velocity_tasks_per_week": velocity,
            "tasks_generated_through_month": d.tasks_generated_through_month,
            "target_date": str(d.target_date.date()) if d.target_date else None,
            "milestones": ms_progress,
        }

    def get_completed_tasks(self, dream_id=None, since_date=None):
        """Returns tasks completed since a given date."""
        from apps.dreams.models import Task

        try:
            since = date.fromisoformat(since_date) if since_date else None
        except (ValueError, TypeError):
            since = None
        if not since:
            since = (timezone.now() - timedelta(days=14)).date()

        tasks = (
            Task.objects.filter(
                goal__dream=self.dream,
                status="completed",
                completed_at__date__gte=since,
            )
            .select_related("goal", "goal__milestone")
            .order_by("completed_at")[:50]
        )

        return {
            "success": True,
            "count": len(tasks),
            "tasks": [
                {
                    "title": t.title,
                    "goal": t.goal.title,
                    "goal_id": str(t.goal.id),
                    "milestone": t.goal.milestone.title if t.goal.milestone else None,
                    "duration_mins": t.duration_mins,
                    "completed_at": (
                        t.completed_at.isoformat() if t.completed_at else None
                    ),
                }
                for t in tasks
            ],
        }

    def get_overdue_tasks(self, dream_id=None):
        """Returns tasks that are past their deadline and still pending."""
        from apps.dreams.models import Task

        today = timezone.now().date()
        tasks = (
            Task.objects.filter(
                goal__dream=self.dream,
                status="pending",
                deadline_date__lt=today,
            )
            .select_related("goal", "goal__milestone")
            .order_by("deadline_date")[:30]
        )

        return {
            "success": True,
            "count": len(tasks),
            "tasks": [
                {
                    "task_id": str(t.id),
                    "title": t.title,
                    "goal": t.goal.title,
                    "goal_id": str(t.goal.id),
                    "milestone": t.goal.milestone.title if t.goal.milestone else None,
                    "deadline_date": str(t.deadline_date),
                    "days_overdue": (today - t.deadline_date).days,
                    "duration_mins": t.duration_mins,
                }
                for t in tasks
            ],
        }

    def create_tasks(self, goal_id, tasks):
        """Creates new tasks for a specific goal."""
        from apps.dreams.models import Goal, Task

        goal = Goal.objects.filter(pk=goal_id, dream=self.dream).first()
        if not goal:
            return {
                "error": f"Goal {goal_id} not found or not owned by this dream",
                "success": False,
            }

        plan_start = self.dream.created_at or timezone.now()
        max_order = Task.objects.filter(goal=goal).count()

        created = []
        for i, t in enumerate(tasks):
            scheduled = None
            if t.get("day_number"):
                scheduled = plan_start + timedelta(days=t["day_number"] - 1)

            exp_date = None
            dead_date = None
            try:
                if t.get("expected_date"):
                    exp_date = date.fromisoformat(t["expected_date"])
                if t.get("deadline_date"):
                    dead_date = date.fromisoformat(t["deadline_date"])
            except (ValueError, TypeError):
                pass

            task = Task.objects.create(
                goal=goal,
                title=t["title"],
                description=t.get("description", ""),
                order=max_order + i + 1,
                duration_mins=t.get("duration_mins", 30),
                scheduled_date=scheduled,
                expected_date=exp_date,
                deadline_date=dead_date,
                status="pending",
            )
            created.append({"id": str(task.id), "title": task.title})

        # Mark milestone as having tasks
        if goal.milestone and not goal.milestone.has_tasks:
            goal.milestone.has_tasks = True
            goal.milestone.save(update_fields=["has_tasks"])

        return {
            "success": True,
            "tasks_created": len(created),
            "tasks": created,
        }

    def update_milestone(
        self,
        milestone_id,
        new_expected_date=None,
        new_deadline_date=None,
        new_description=None,
    ):
        """Adjusts a milestone's dates or description."""
        from apps.dreams.models import DreamMilestone

        ms = DreamMilestone.objects.filter(pk=milestone_id, dream=self.dream).first()
        if not ms:
            return {"error": f"Milestone {milestone_id} not found", "success": False}

        updates = []
        if new_expected_date:
            try:
                ms.expected_date = date.fromisoformat(new_expected_date)
                updates.append("expected_date")
            except (ValueError, TypeError):
                pass
        if new_deadline_date:
            try:
                ms.deadline_date = date.fromisoformat(new_deadline_date)
                updates.append("deadline_date")
            except (ValueError, TypeError):
                pass
        if new_description:
            ms.description = new_description
            updates.append("description")

        if updates:
            ms.save(update_fields=updates)

        return {
            "success": True,
            "milestone_id": str(ms.id),
            "title": ms.title,
            "updated_fields": updates,
        }

    def get_calendar_availability(self, user_id=None, start_date=None, end_date=None):
        """Returns the user's free time slots."""
        from apps.calendar.models import CalendarEvent, TimeBlock

        try:
            start = date.fromisoformat(start_date) if start_date else None
            end = date.fromisoformat(end_date) if end_date else None
        except (ValueError, TypeError):
            start = None
            end = None
        if not start:
            start = timezone.now().date()
        if not end:
            end = start + timedelta(days=14)

        # Get time blocks (recurring availability)
        blocks = TimeBlock.objects.filter(user=self.user)
        availability = {}
        for b in blocks:
            day_name = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][b.day_of_week]
            if day_name not in availability:
                availability[day_name] = []
            availability[day_name].append(
                {
                    "start": str(b.start_time),
                    "end": str(b.end_time),
                    "type": b.block_type,
                }
            )

        # Get existing calendar events in the range
        events = CalendarEvent.objects.filter(
            user=self.user,
            start_time__date__gte=start,
            start_time__date__lte=end,
        ).count()

        # Work schedule from user profile
        work_schedule = self.user.work_schedule or {}
        persona = self.user.persona or {}

        return {
            "success": True,
            "recurring_availability": availability,
            "events_in_range": events,
            "work_schedule": work_schedule,
            "available_hours_per_week": persona.get(
                "available_hours_per_week", "unknown"
            ),
            "preferred_schedule": persona.get("preferred_schedule", "unknown"),
            "occupation": persona.get("occupation", "unknown"),
            "fitness_level": persona.get("fitness_level", "unknown"),
            "learning_style": persona.get("learning_style", "unknown"),
            "global_constraints": persona.get("global_constraints", ""),
            "global_motivation": persona.get("global_motivation", ""),
        }

    def mark_goal_completed(self, goal_id):
        """Marks a goal as completed."""
        from apps.dreams.models import Goal

        goal = Goal.objects.filter(pk=goal_id, dream=self.dream).first()
        if not goal:
            return {"error": f"Goal {goal_id} not found", "success": False}

        goal.status = "completed"
        goal.progress_percentage = 100.0
        goal.save(update_fields=["status", "progress_percentage"])

        return {
            "success": True,
            "goal_id": str(goal.id),
            "title": goal.title,
        }

    def create_new_goal(
        self,
        milestone_id,
        title,
        description,
        expected_date=None,
        deadline_date=None,
        estimated_minutes=None,
    ):
        """Adds a new goal to a milestone."""
        from apps.dreams.models import DreamMilestone, Goal

        ms = DreamMilestone.objects.filter(pk=milestone_id, dream=self.dream).first()
        if not ms:
            return {"error": f"Milestone {milestone_id} not found", "success": False}

        max_order = Goal.objects.filter(milestone=ms).count()

        exp_date = None
        dead_date = None
        try:
            if expected_date:
                exp_date = date.fromisoformat(expected_date)
            if deadline_date:
                dead_date = date.fromisoformat(deadline_date)
        except (ValueError, TypeError):
            pass

        goal = Goal.objects.create(
            dream=self.dream,
            milestone=ms,
            title=title,
            description=description,
            order=max_order + 1,
            estimated_minutes=estimated_minutes,
            expected_date=exp_date,
            deadline_date=dead_date,
            status="pending",
        )

        return {
            "success": True,
            "goal_id": str(goal.id),
            "title": goal.title,
            "milestone": ms.title,
        }

    # ---------------------------------------------------------------
    # Skeleton evolution tools (added for interactive check-ins)
    # ---------------------------------------------------------------

    def add_milestone(
        self, title, description, order, expected_date=None, deadline_date=None
    ):
        """Insert a new milestone at the given order, shifting existing ones."""
        from apps.dreams.models import DreamMilestone

        # Shift existing milestones at or after this order
        DreamMilestone.objects.filter(dream=self.dream, order__gte=order).update(
            order=F("order") + 1
        )

        exp_date = None
        dead_date = None
        try:
            if expected_date:
                exp_date = date.fromisoformat(expected_date)
            if deadline_date:
                dead_date = date.fromisoformat(deadline_date)
        except (ValueError, TypeError):
            pass

        ms = DreamMilestone.objects.create(
            dream=self.dream,
            title=title,
            description=description,
            order=order,
            expected_date=exp_date,
            deadline_date=dead_date,
            has_tasks=False,
        )

        return {
            "success": True,
            "milestone_id": str(ms.id),
            "title": ms.title,
            "order": ms.order,
        }

    def remove_milestone(self, milestone_id, reason=""):
        """Remove or skip a milestone. Skips instead of deleting if it has completed tasks."""
        from apps.dreams.models import DreamMilestone, Goal, Task

        ms = DreamMilestone.objects.filter(pk=milestone_id, dream=self.dream).first()
        if not ms:
            return {"error": f"Milestone {milestone_id} not found", "success": False}

        has_completed = Task.objects.filter(
            goal__milestone=ms, status="completed"
        ).exists()

        title = ms.title
        if has_completed:
            ms.status = "skipped"
            ms.save(update_fields=["status"])
            action = "skipped"
        else:
            Task.objects.filter(goal__milestone=ms).delete()
            Goal.objects.filter(milestone=ms).delete()
            ms.delete()
            action = "deleted"

        # Re-sequence remaining milestones
        for i, m in enumerate(
            DreamMilestone.objects.filter(dream=self.dream).order_by("order"), 1
        ):
            if m.order != i:
                m.order = i
                m.save(update_fields=["order"])

        return {
            "success": True,
            "action": action,
            "title": title,
            "reason": reason,
        }

    def reorder_milestone(self, milestone_id, new_order):
        """Move a milestone to a new position."""
        from apps.dreams.models import DreamMilestone

        ms = DreamMilestone.objects.filter(pk=milestone_id, dream=self.dream).first()
        if not ms:
            return {"error": f"Milestone {milestone_id} not found", "success": False}

        old_order = ms.order
        new_order = int(new_order)

        if old_order == new_order:
            return {"success": True, "old_order": old_order, "new_order": new_order}

        # Shift milestones between old and new positions
        if old_order < new_order:
            DreamMilestone.objects.filter(
                dream=self.dream, order__gt=old_order, order__lte=new_order
            ).update(order=F("order") - 1)
        else:
            DreamMilestone.objects.filter(
                dream=self.dream, order__gte=new_order, order__lt=old_order
            ).update(order=F("order") + 1)

        ms.order = new_order
        ms.save(update_fields=["order"])

        return {"success": True, "old_order": old_order, "new_order": new_order}

    def shift_milestone_dates(self, milestone_id, shift_days):
        """Shift all dates for a milestone and its goals/tasks by N days."""
        from apps.dreams.models import DreamMilestone, Goal, Task

        ms = DreamMilestone.objects.filter(pk=milestone_id, dream=self.dream).first()
        if not ms:
            return {"error": f"Milestone {milestone_id} not found", "success": False}

        shift = timedelta(days=int(shift_days))

        # Shift milestone dates
        updates = []
        if ms.expected_date:
            ms.expected_date = ms.expected_date + shift
            updates.append("expected_date")
        if ms.deadline_date:
            ms.deadline_date = ms.deadline_date + shift
            updates.append("deadline_date")
        if ms.target_date:
            ms.target_date = ms.target_date + shift
            updates.append("target_date")
        if updates:
            ms.save(update_fields=updates)

        # Shift goal dates (bulk update instead of N+1)
        goals_qs = Goal.objects.filter(milestone=ms)
        goals_shifted = goals_qs.filter(
            Q(expected_date__isnull=False) | Q(deadline_date__isnull=False)
        ).count()
        goals_qs.update(
            expected_date=F("expected_date") + shift,
            deadline_date=F("deadline_date") + shift,
        )

        # Shift task dates (bulk update instead of N+1)
        tasks_qs = Task.objects.filter(goal__milestone=ms)
        tasks_shifted = tasks_qs.filter(
            Q(expected_date__isnull=False)
            | Q(deadline_date__isnull=False)
            | Q(scheduled_date__isnull=False)
        ).count()
        tasks_qs.update(
            expected_date=F("expected_date") + shift,
            deadline_date=F("deadline_date") + shift,
            scheduled_date=F("scheduled_date") + shift,
        )

        return {
            "success": True,
            "milestone": ms.title,
            "shift_days": int(shift_days),
            "goals_shifted": goals_shifted,
            "tasks_shifted": tasks_shifted,
        }

    def get_goals_for_milestone(self, milestone_id):
        """Returns all goals for a specific milestone, with IDs and task counts."""
        from apps.dreams.models import DreamMilestone, Goal

        ms = DreamMilestone.objects.filter(pk=milestone_id, dream=self.dream).first()
        if not ms:
            return {"error": f"Milestone {milestone_id} not found", "success": False}

        goals = (
            Goal.objects.filter(milestone=ms)
            .annotate(
                total_tasks=Count("tasks"),
                completed_tasks=Count("tasks", filter=Q(tasks__status="completed")),
                pending_tasks=Count("tasks", filter=Q(tasks__status="pending")),
            )
            .order_by("order")
        )
        goals_data = []
        for g in goals:
            goals_data.append(
                {
                    "goal_id": str(g.id),
                    "title": g.title,
                    "description": g.description[:300] if g.description else "",
                    "order": g.order,
                    "status": g.status,
                    "expected_date": str(g.expected_date) if g.expected_date else None,
                    "deadline_date": str(g.deadline_date) if g.deadline_date else None,
                    "total_tasks": g.total_tasks,
                    "completed_tasks": g.completed_tasks,
                    "pending_tasks": g.pending_tasks,
                }
            )

        return {
            "success": True,
            "milestone_id": str(ms.id),
            "milestone_title": ms.title,
            "goals": goals_data,
        }

    def generate_extension_tasks(self, goal_id, tasks):
        """Create tasks to extend coverage window. Delegates to create_tasks."""
        return self.create_tasks(goal_id, tasks)

    # ---------------------------------------------------------------
    # Finish signals
    # ---------------------------------------------------------------

    def finish_check_in(
        self,
        coaching_message,
        months_now_covered_through,
        adjustment_summary="",
        pace_status="on_track",
        next_checkin_days=14,
    ):
        """Signal that the check-in is complete."""
        return {
            "success": True,
            "coaching_message": coaching_message,
            "months_now_covered_through": months_now_covered_through,
            "adjustment_summary": adjustment_summary,
            "pace_status": pace_status,
            "next_checkin_days": int(next_checkin_days),
        }

    def finish_questionnaire_generation(
        self, questions, opening_message="", pace_summary=""
    ):
        """Signal that questionnaire generation is complete."""
        return {
            "success": True,
            "questions": questions,
            "opening_message": opening_message,
            "pace_summary": pace_summary,
        }
