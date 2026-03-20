"""
Services for the Plans system.

Provides business logic for plan generation, check-in processing,
and progress management.
"""

import logging

from django.utils import timezone

logger = logging.getLogger(__name__)


class PlanService:
    """Service for plan-related business logic."""

    @staticmethod
    def process_checkin(checkin):
        """Process a check-in after user responses are submitted.

        Analyzes progress, adjusts plan if needed, and generates coaching message.
        """
        dream = checkin.dream

        # Compute progress snapshot
        checkin.progress_at_checkin = dream.progress_percentage

        # Count tasks completed since last check-in
        from .models import Task

        last_checkin_date = dream.last_checkin_at or dream.created_at
        completed_since = Task.objects.filter(
            goal__dream=dream,
            status="completed",
            completed_at__gte=last_checkin_date,
        ).count()
        checkin.tasks_completed_since_last = completed_since

        # Count overdue tasks
        overdue = Task.objects.filter(
            goal__dream=dream,
            status="pending",
            scheduled_date__lt=timezone.now(),
        ).count()
        checkin.tasks_overdue_at_checkin = overdue

        # Determine pace
        checkin.pace_status = PlanService._compute_pace(dream, overdue)

        # Adjust check-in interval based on pace
        if checkin.pace_status in ("significantly_behind", "behind"):
            checkin.next_checkin_interval_days = 7
        elif checkin.pace_status in ("significantly_ahead", "ahead"):
            checkin.next_checkin_interval_days = 21
        else:
            checkin.next_checkin_interval_days = 14

        # Update dream check-in metadata
        dream.last_checkin_at = timezone.now()
        dream.checkin_count += 1
        dream.checkin_interval_days = checkin.next_checkin_interval_days
        dream.next_checkin_at = timezone.now() + timezone.timedelta(
            days=checkin.next_checkin_interval_days
        )
        dream.save(
            update_fields=[
                "last_checkin_at",
                "checkin_count",
                "checkin_interval_days",
                "next_checkin_at",
            ]
        )

        checkin.coaching_message = PlanService._generate_coaching_message(
            checkin.pace_status, completed_since, overdue
        )
        checkin.save()

    @staticmethod
    def _compute_pace(dream, overdue_count):
        """Compute pace status based on progress and overdue tasks."""
        progress = dream.progress_percentage

        # Simple heuristic based on target_date
        if dream.target_date:
            total_days = (dream.target_date - dream.created_at).days or 1
            elapsed_days = (timezone.now() - dream.created_at).days
            expected_progress = (elapsed_days / total_days) * 100

            diff = progress - expected_progress
            if diff >= 20:
                return "significantly_ahead"
            elif diff >= 5:
                return "ahead"
            elif diff >= -10:
                return "on_track"
            elif diff >= -25:
                return "behind"
            else:
                return "significantly_behind"

        # Without target_date, use overdue tasks as indicator
        if overdue_count == 0:
            return "on_track"
        elif overdue_count <= 3:
            return "behind"
        else:
            return "significantly_behind"

    @staticmethod
    def _generate_coaching_message(pace_status, completed, overdue):
        """Generate a basic coaching message based on pace."""
        messages = {
            "significantly_ahead": f"Outstanding progress! You've completed {completed} tasks and are well ahead of schedule.",
            "ahead": f"Great work! {completed} tasks completed. You're ahead of schedule.",
            "on_track": f"You're on track with {completed} tasks completed. Keep up the momentum!",
            "behind": f"You have {overdue} overdue tasks. Let's focus on catching up.",
            "significantly_behind": f"You have {overdue} overdue tasks and are falling behind. Consider adjusting your plan.",
        }
        return messages.get(pace_status, "Keep going!")

    @staticmethod
    def get_dream_plan_summary(dream):
        """Get a summary of the dream's plan structure."""
        from .models import DreamMilestone, Goal, Task

        milestones = DreamMilestone.objects.filter(dream=dream).count()
        goals = Goal.objects.filter(dream=dream).count()
        tasks = Task.objects.filter(goal__dream=dream).count()
        completed_tasks = Task.objects.filter(
            goal__dream=dream, status="completed"
        ).count()

        return {
            "milestones": milestones,
            "goals": goals,
            "total_tasks": tasks,
            "completed_tasks": completed_tasks,
            "progress": dream.progress_percentage,
            "plan_phase": dream.plan_phase,
        }
