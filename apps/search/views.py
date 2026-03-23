"""
Search API views.
"""

from django.conf import settings
from django.utils.translation import gettext as _
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.ai.models import AIMessage as Message
from apps.calendar.models import CalendarEvent
from apps.circles.models import CirclePost
from apps.dreams.models import Dream, Goal, Task
from apps.search.services import SearchService
from apps.users.models import User


class GlobalSearchView(APIView):
    """
    GET /api/search/?q=<query>&type=dreams,users,messages

    Returns categorized search results powered by Elasticsearch.
    Gated by the USE_SEARCH feature flag — returns 501 when disabled.
    """

    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "search"

    def get(self, request):
        # Feature flag: search requires Elasticsearch which may not be running
        if not getattr(settings, "USE_SEARCH", False):
            return Response(
                {
                    "error": _("Search is not available."),
                    "coming_soon": True,
                },
                status=status.HTTP_501_NOT_IMPLEMENTED,
            )

        query = request.query_params.get("q", "").strip()
        if not query or len(query) < 2:
            return Response(
                {"detail": _("Query must be at least 2 characters.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Parse requested types
        type_param = request.query_params.get("type", "")
        types = [t.strip() for t in type_param.split(",") if t.strip()] or None

        # Run global search
        raw_results = SearchService.global_search(
            request.user, query, types=types, limit=10
        )

        # Hydrate results with minimal serialized data
        response_data = {}

        if "dreams" in raw_results and raw_results["dreams"]:
            dreams = Dream.objects.filter(
                id__in=raw_results["dreams"], user=request.user
            )
            response_data["dreams"] = [
                {"id": str(d.id), "title": d.title, "status": d.status} for d in dreams
            ]

        if "goals" in raw_results and raw_results["goals"]:
            goals = Goal.objects.filter(
                id__in=raw_results["goals"],
                dream__user=request.user,
            ).select_related("dream")
            response_data["goals"] = [
                {"id": str(g.id), "title": g.title, "dream_id": str(g.dream_id)}
                for g in goals
            ]

        if "tasks" in raw_results and raw_results["tasks"]:
            tasks = Task.objects.filter(
                id__in=raw_results["tasks"],
                goal__dream__user=request.user,
            ).select_related("goal")
            response_data["tasks"] = [
                {"id": str(t.id), "title": t.title, "goal_id": str(t.goal_id)}
                for t in tasks
            ]

        if "messages" in raw_results and raw_results["messages"]:
            msgs = Message.objects.filter(
                id__in=raw_results["messages"],
                conversation__user=request.user,
            ).select_related("conversation")
            response_data["messages"] = [
                {
                    "id": str(m.id),
                    "content": m.content[:200],
                    "conversation_id": str(m.conversation_id),
                    "role": m.role,
                }
                for m in msgs
            ]

        if "users" in raw_results and raw_results["users"]:
            users = User.objects.filter(id__in=raw_results["users"])
            response_data["users"] = [
                {
                    "id": str(u.id),
                    "display_name": u.display_name or "",
                    "avatar_url": u.get_effective_avatar_url(),
                }
                for u in users
            ]

        if "calendar" in raw_results and raw_results["calendar"]:
            events = CalendarEvent.objects.filter(
                id__in=raw_results["calendar"],
                user=request.user,
            )
            response_data["calendar"] = [
                {
                    "id": str(e.id),
                    "title": e.title,
                    "start_time": e.start_time.isoformat(),
                }
                for e in events
            ]

        if "circles" in raw_results and raw_results["circles"]:
            from apps.circles.models import CircleMembership

            user_circle_ids = CircleMembership.objects.filter(
                user=request.user
            ).values_list("circle_id", flat=True)
            posts = CirclePost.objects.filter(
                id__in=raw_results["circles"],
                circle_id__in=user_circle_ids,
            ).select_related("circle")
            response_data["circles"] = [
                {
                    "id": str(p.id),
                    "content": p.content[:200],
                    "circle_id": str(p.circle_id),
                    "circle_name": p.circle.name,
                }
                for p in posts
            ]

        return Response(response_data)
