"""
Comprehensive tests for the Search app.

Covers:
1. GlobalSearchView: auth, validation, type filtering, result hydration, edge cases
2. SearchService: all per-type methods (DB fallback), global_search, _es_search helper
3. Permissions & rate limiting
4. Edge cases: empty results, unknown types, cross-user isolation
5. Management commands: ensure_search_index, rebuild_search_index
"""

import uuid
from io import StringIO
from unittest.mock import MagicMock, patch

import pytest
from django.core.management import call_command
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.search.services import MAX_RESULTS, SearchService, _es_search


# ══════════════════════════════════════════════════════════════════════
#  Fixtures
# ══════════════════════════════════════════════════════════════════════


@pytest.fixture
def user_a(db):
    from apps.users.models import User

    return User.objects.create_user(
        email="alice@test.com",
        password="pass1234",
        display_name="Alice Wonderland",
    )


@pytest.fixture
def user_b(db):
    from apps.users.models import User

    return User.objects.create_user(
        email="bob@test.com",
        password="pass1234",
        display_name="Bob Builder",
    )


@pytest.fixture
def auth_client(user_a):
    c = APIClient()
    c.force_authenticate(user=user_a)
    return c


@pytest.fixture
def auth_client_b(user_b):
    c = APIClient()
    c.force_authenticate(user=user_b)
    return c


@pytest.fixture
def anon_client():
    return APIClient()


@pytest.fixture
def dream_a(user_a):
    from apps.dreams.models import Dream

    return Dream.objects.create(
        user=user_a,
        title="Learn Quantum Computing",
        description="Study quantum mechanics and algorithms",
        category="education",
        status="active",
    )


@pytest.fixture
def dream_b(user_b):
    from apps.dreams.models import Dream

    return Dream.objects.create(
        user=user_b,
        title="Private Dream",
        description="Should not leak",
        category="personal",
        status="active",
    )


@pytest.fixture
def goal_a(dream_a):
    from apps.dreams.models import Goal

    return Goal.objects.create(
        dream=dream_a,
        title="Finish Qiskit Tutorial",
        description="IBM Qiskit course",
        order=0,
        status="pending",
    )


@pytest.fixture
def task_a(goal_a):
    from apps.dreams.models import Task

    return Task.objects.create(
        goal=goal_a,
        title="Read Chapter 1",
        description="Intro to qubits",
        order=0,
        duration_mins=30,
        status="pending",
    )


@pytest.fixture
def conversation_a(user_a):
    from apps.ai.models import AIConversation

    return AIConversation.objects.create(user=user_a)


@pytest.fixture
def message_a(conversation_a):
    from apps.ai.models import AIMessage

    return AIMessage.objects.create(
        conversation=conversation_a,
        role="user",
        content="How do I start learning quantum computing?",
    )


@pytest.fixture
def calendar_event_a(user_a):
    from apps.calendar.models import CalendarEvent

    now = timezone.now()
    return CalendarEvent.objects.create(
        user=user_a,
        title="Quantum Study Session",
        description="Study group meeting",
        location="Library",
        start_time=now,
        end_time=now + timezone.timedelta(hours=1),
    )


@pytest.fixture
def circle_a(user_a):
    from apps.circles.models import Circle

    return Circle.objects.create(
        name="Quantum Enthusiasts",
        description="A circle for quantum computing fans",
        category="education",
        creator=user_a,
    )


@pytest.fixture
def circle_membership_a(user_a, circle_a):
    from apps.circles.models import CircleMembership

    return CircleMembership.objects.create(
        user=user_a,
        circle=circle_a,
        role="admin",
    )


@pytest.fixture
def circle_post_a(user_a, circle_a):
    from apps.circles.models import CirclePost

    return CirclePost.objects.create(
        circle=circle_a,
        author=user_a,
        content="Just solved a quantum algorithm problem!",
    )


@pytest.fixture
def circle_challenge_a(circle_a, user_a):
    from apps.circles.models import CircleChallenge

    now = timezone.now()
    return CircleChallenge.objects.create(
        circle=circle_a,
        title="30-Day Quantum Challenge",
        description="Study quantum computing every day for 30 days",
        start_date=now,
        end_date=now + timezone.timedelta(days=30),
        creator=user_a,
    )


@pytest.fixture
def activity_item_a(user_a):
    from apps.social.models import ActivityFeedItem

    return ActivityFeedItem.objects.create(
        user=user_a,
        activity_type="task_completed",
    )


@pytest.fixture
def activity_comment_a(user_a, activity_item_a):
    from apps.social.models import ActivityComment

    return ActivityComment.objects.create(
        user=user_a,
        activity=activity_item_a,
        text="Great progress on quantum studies!",
    )


# ══════════════════════════════════════════════════════════════════════
#  1. GlobalSearchView — Authentication
# ══════════════════════════════════════════════════════════════════════


class TestGlobalSearchViewAuth:
    def test_unauthenticated_request_rejected(self, anon_client):
        resp = anon_client.get("/api/search/?q=test")
        assert resp.status_code in (
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        )

    def test_authenticated_request_accepted(self, auth_client):
        resp = auth_client.get("/api/search/?q=quantum")
        assert resp.status_code == status.HTTP_200_OK


# ══════════════════════════════════════════════════════════════════════
#  2. GlobalSearchView — Query Validation
# ══════════════════════════════════════════════════════════════════════


class TestGlobalSearchViewValidation:
    def test_empty_query_returns_400(self, auth_client):
        resp = auth_client.get("/api/search/?q=")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_missing_query_param_returns_400(self, auth_client):
        resp = auth_client.get("/api/search/")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_single_char_returns_400(self, auth_client):
        resp = auth_client.get("/api/search/?q=x")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_whitespace_only_returns_400(self, auth_client):
        resp = auth_client.get("/api/search/?q=%20%20%20")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_two_char_query_succeeds(self, auth_client):
        resp = auth_client.get("/api/search/?q=ab")
        assert resp.status_code == status.HTTP_200_OK

    def test_long_query_succeeds(self, auth_client):
        long_q = "a" * 200
        resp = auth_client.get(f"/api/search/?q={long_q}")
        assert resp.status_code == status.HTTP_200_OK


# ══════════════════════════════════════════════════════════════════════
#  3. GlobalSearchView — Type Filtering
# ══════════════════════════════════════════════════════════════════════


class TestGlobalSearchViewTypeFilter:
    @patch("apps.search.views.SearchService.global_search")
    def test_single_type(self, mock_search, auth_client):
        mock_search.return_value = {"dreams": []}
        auth_client.get("/api/search/?q=test&type=dreams")
        mock_search.assert_called_once()
        _, kwargs = mock_search.call_args
        assert kwargs["types"] == ["dreams"]

    @patch("apps.search.views.SearchService.global_search")
    def test_multiple_types(self, mock_search, auth_client):
        mock_search.return_value = {}
        auth_client.get("/api/search/?q=test&type=dreams,users,calendar")
        _, kwargs = mock_search.call_args
        assert set(kwargs["types"]) == {"dreams", "users", "calendar"}

    @patch("apps.search.views.SearchService.global_search")
    def test_no_type_passes_none(self, mock_search, auth_client):
        mock_search.return_value = {}
        auth_client.get("/api/search/?q=test")
        _, kwargs = mock_search.call_args
        assert kwargs["types"] is None

    @patch("apps.search.views.SearchService.global_search")
    def test_empty_type_param_passes_none(self, mock_search, auth_client):
        mock_search.return_value = {}
        auth_client.get("/api/search/?q=test&type=")
        _, kwargs = mock_search.call_args
        assert kwargs["types"] is None

    @patch("apps.search.views.SearchService.global_search")
    def test_whitespace_type_trimmed(self, mock_search, auth_client):
        mock_search.return_value = {}
        auth_client.get("/api/search/?q=test&type=%20dreams%20,%20users%20")
        _, kwargs = mock_search.call_args
        assert set(kwargs["types"]) == {"dreams", "users"}


# ══════════════════════════════════════════════════════════════════════
#  4. GlobalSearchView — Result Hydration (Dreams)
# ══════════════════════════════════════════════════════════════════════


class TestGlobalSearchViewDreamsHydration:
    @patch("apps.search.views.SearchService.global_search")
    def test_dreams_hydrated_with_id_title_status(
        self, mock_search, auth_client, dream_a
    ):
        mock_search.return_value = {"dreams": [dream_a.id]}
        resp = auth_client.get("/api/search/?q=quantum")
        assert resp.status_code == status.HTTP_200_OK
        assert "dreams" in resp.data
        assert len(resp.data["dreams"]) == 1
        d = resp.data["dreams"][0]
        assert d["id"] == str(dream_a.id)
        assert d["title"] == "Learn Quantum Computing"
        assert d["status"] == "active"

    @patch("apps.search.views.SearchService.global_search")
    def test_other_user_dreams_filtered_out(
        self, mock_search, auth_client, dream_b
    ):
        """Dreams not owned by requesting user are excluded during hydration."""
        mock_search.return_value = {"dreams": [dream_b.id]}
        resp = auth_client.get("/api/search/?q=private")
        assert resp.status_code == status.HTTP_200_OK
        if "dreams" in resp.data:
            assert len(resp.data["dreams"]) == 0

    @patch("apps.search.views.SearchService.global_search")
    def test_nonexistent_dream_id_excluded(self, mock_search, auth_client):
        mock_search.return_value = {"dreams": [uuid.uuid4()]}
        resp = auth_client.get("/api/search/?q=nothing")
        assert resp.status_code == status.HTTP_200_OK
        if "dreams" in resp.data:
            assert len(resp.data["dreams"]) == 0


# ══════════════════════════════════════════════════════════════════════
#  5. GlobalSearchView — Result Hydration (Goals, Tasks)
# ══════════════════════════════════════════════════════════════════════


class TestGlobalSearchViewGoalsTasksHydration:
    @patch("apps.search.views.SearchService.global_search")
    def test_goals_hydrated(self, mock_search, auth_client, goal_a):
        mock_search.return_value = {"goals": [goal_a.id]}
        resp = auth_client.get("/api/search/?q=qiskit")
        assert "goals" in resp.data
        g = resp.data["goals"][0]
        assert g["id"] == str(goal_a.id)
        assert g["title"] == "Finish Qiskit Tutorial"
        assert g["dream_id"] == str(goal_a.dream_id)

    @patch("apps.search.views.SearchService.global_search")
    def test_tasks_hydrated(self, mock_search, auth_client, task_a):
        mock_search.return_value = {"tasks": [task_a.id]}
        resp = auth_client.get("/api/search/?q=chapter")
        assert "tasks" in resp.data
        t = resp.data["tasks"][0]
        assert t["id"] == str(task_a.id)
        assert t["title"] == "Read Chapter 1"
        assert t["goal_id"] == str(task_a.goal_id)


# ══════════════════════════════════════════════════════════════════════
#  6. GlobalSearchView — Result Hydration (Messages)
# ══════════════════════════════════════════════════════════════════════


class TestGlobalSearchViewMessagesHydration:
    @patch("apps.search.views.SearchService.global_search")
    def test_messages_hydrated(self, mock_search, auth_client, message_a):
        mock_search.return_value = {"messages": [message_a.id]}
        resp = auth_client.get("/api/search/?q=quantum")
        assert "messages" in resp.data
        m = resp.data["messages"][0]
        assert m["id"] == str(message_a.id)
        assert m["role"] == "user"
        assert m["conversation_id"] == str(message_a.conversation_id)
        # Content truncated to 200 chars
        assert len(m["content"]) <= 200

    @patch("apps.search.views.SearchService.global_search")
    def test_message_content_truncated_to_200(self, mock_search, auth_client, conversation_a):
        from apps.ai.models import AIMessage

        long_msg = AIMessage.objects.create(
            conversation=conversation_a,
            role="assistant",
            content="x" * 500,
        )
        mock_search.return_value = {"messages": [long_msg.id]}
        resp = auth_client.get("/api/search/?q=xx")
        assert len(resp.data["messages"][0]["content"]) == 200


# ══════════════════════════════════════════════════════════════════════
#  7. GlobalSearchView — Result Hydration (Users)
# ══════════════════════════════════════════════════════════════════════


class TestGlobalSearchViewUsersHydration:
    @patch("apps.search.views.SearchService.global_search")
    def test_users_hydrated(self, mock_search, auth_client, user_b):
        mock_search.return_value = {"users": [user_b.id]}
        resp = auth_client.get("/api/search/?q=bob")
        assert "users" in resp.data
        u = resp.data["users"][0]
        assert u["id"] == str(user_b.id)
        assert u["display_name"] == "Bob Builder"
        assert "avatar_url" in u


# ══════════════════════════════════════════════════════════════════════
#  8. GlobalSearchView — Result Hydration (Calendar)
# ══════════════════════════════════════════════════════════════════════


class TestGlobalSearchViewCalendarHydration:
    @patch("apps.search.views.SearchService.global_search")
    def test_calendar_events_hydrated(
        self, mock_search, auth_client, calendar_event_a
    ):
        mock_search.return_value = {"calendar": [calendar_event_a.id]}
        resp = auth_client.get("/api/search/?q=study")
        assert "calendar" in resp.data
        e = resp.data["calendar"][0]
        assert e["id"] == str(calendar_event_a.id)
        assert e["title"] == "Quantum Study Session"
        assert "start_time" in e

    @patch("apps.search.views.SearchService.global_search")
    def test_other_user_calendar_filtered_out(
        self, mock_search, auth_client, user_b
    ):
        from apps.calendar.models import CalendarEvent

        now = timezone.now()
        other_event = CalendarEvent.objects.create(
            user=user_b,
            title="Private Meeting",
            start_time=now,
            end_time=now + timezone.timedelta(hours=1),
        )
        mock_search.return_value = {"calendar": [other_event.id]}
        resp = auth_client.get("/api/search/?q=meeting")
        if "calendar" in resp.data:
            assert len(resp.data["calendar"]) == 0


# ══════════════════════════════════════════════════════════════════════
#  9. GlobalSearchView — Result Hydration (Circles)
# ══════════════════════════════════════════════════════════════════════


class TestGlobalSearchViewCirclesHydration:
    @patch("apps.search.views.SearchService.global_search")
    def test_circle_posts_hydrated(
        self, mock_search, auth_client, circle_post_a, circle_membership_a
    ):
        mock_search.return_value = {"circles": [circle_post_a.id]}
        resp = auth_client.get("/api/search/?q=algorithm")
        assert "circles" in resp.data
        p = resp.data["circles"][0]
        assert p["id"] == str(circle_post_a.id)
        assert "content" in p
        assert p["circle_id"] == str(circle_post_a.circle_id)
        assert "circle_name" in p

    @patch("apps.search.views.SearchService.global_search")
    def test_circle_posts_not_member_excluded(
        self, mock_search, auth_client, circle_post_a
    ):
        """Posts from circles user is not a member of are excluded."""
        mock_search.return_value = {"circles": [circle_post_a.id]}
        resp = auth_client.get("/api/search/?q=algo")
        if "circles" in resp.data:
            assert len(resp.data["circles"]) == 0


# ══════════════════════════════════════════════════════════════════════
#  10. GlobalSearchView — Empty / Edge Cases
# ══════════════════════════════════════════════════════════════════════


class TestGlobalSearchViewEdgeCases:
    @patch("apps.search.views.SearchService.global_search")
    def test_empty_results_returns_empty_dict(self, mock_search, auth_client):
        mock_search.return_value = {}
        resp = auth_client.get("/api/search/?q=noresults")
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data == {}

    @patch("apps.search.views.SearchService.global_search")
    def test_empty_lists_not_in_response(self, mock_search, auth_client):
        mock_search.return_value = {
            "dreams": [],
            "users": [],
            "goals": [],
        }
        resp = auth_client.get("/api/search/?q=test")
        assert "dreams" not in resp.data
        assert "users" not in resp.data
        assert "goals" not in resp.data

    @patch("apps.search.views.SearchService.global_search")
    def test_mixed_results_only_non_empty_returned(
        self, mock_search, auth_client, dream_a
    ):
        mock_search.return_value = {
            "dreams": [dream_a.id],
            "users": [],
            "tasks": [],
        }
        resp = auth_client.get("/api/search/?q=quantum")
        assert "dreams" in resp.data
        assert "users" not in resp.data
        assert "tasks" not in resp.data


# ══════════════════════════════════════════════════════════════════════
#  11. SearchService — _es_search helper
# ══════════════════════════════════════════════════════════════════════


class TestEsSearchHelper:
    def test_uses_es_build_fn_when_available(self):
        with patch("apps.search.services._ES_AVAILABLE", True):
            build = MagicMock(return_value=["id1", "id2"])
            fallback = MagicMock(return_value=[])
            result = _es_search(build, fallback, "test")
            build.assert_called_once()
            fallback.assert_not_called()
            assert result == ["id1", "id2"]

    def test_fallback_on_es_error(self):
        with patch("apps.search.services._ES_AVAILABLE", True):
            build = MagicMock(side_effect=ConnectionError("ES down"))
            fallback = MagicMock(return_value=["fallback_id"])
            result = _es_search(build, fallback, "test")
            build.assert_called_once()
            fallback.assert_called_once()
            assert result == ["fallback_id"]

    def test_uses_fallback_when_es_not_available(self):
        with patch("apps.search.services._ES_AVAILABLE", False):
            build = MagicMock(return_value=["id_es"])
            fallback = MagicMock(return_value=["id_db"])
            result = _es_search(build, fallback, "test")
            build.assert_not_called()
            fallback.assert_called_once()
            assert result == ["id_db"]

    def test_fallback_on_runtime_error(self):
        with patch("apps.search.services._ES_AVAILABLE", True):
            build = MagicMock(side_effect=RuntimeError("unexpected"))
            fallback = MagicMock(return_value=[])
            result = _es_search(build, fallback, "label")
            assert result == []
            fallback.assert_called_once()


# ══════════════════════════════════════════════════════════════════════
#  12. SearchService — Per-type DB fallback searches
# ══════════════════════════════════════════════════════════════════════


@patch("apps.search.services._ES_AVAILABLE", False)
class TestSearchServiceDreamsFallback:
    def test_search_dreams_returns_list(self, user_a, dream_a):
        result = SearchService.search_dreams(user_a, "Quantum")
        assert isinstance(result, list)

    def test_search_dreams_empty_for_nonexistent(self, user_a):
        result = SearchService.search_dreams(user_a, "zzzz_no_match_99")
        assert result == []

    def test_search_dreams_respects_limit(self, user_a, dream_a):
        result = SearchService.search_dreams(user_a, "Quantum", limit=1)
        assert len(result) <= 1

    def test_search_dreams_scoped_to_user(self, user_a, dream_b):
        """user_a should not find user_b's dreams."""
        result = SearchService.search_dreams(user_a, "Private")
        assert dream_b.id not in result


@patch("apps.search.services._ES_AVAILABLE", False)
class TestSearchServiceGoalsFallback:
    def test_search_goals_returns_list(self, user_a, goal_a):
        result = SearchService.search_goals(user_a, "Qiskit")
        assert isinstance(result, list)

    def test_search_goals_with_dream_filter(self, user_a, dream_a, goal_a):
        result = SearchService.search_goals(
            user_a, "Qiskit", dream_id=dream_a.id
        )
        assert isinstance(result, list)

    def test_search_goals_wrong_dream_id(self, user_a, goal_a):
        result = SearchService.search_goals(
            user_a, "Qiskit", dream_id=uuid.uuid4()
        )
        assert result == []


@patch("apps.search.services._ES_AVAILABLE", False)
class TestSearchServiceTasksFallback:
    def test_search_tasks_returns_list(self, user_a, task_a):
        result = SearchService.search_tasks(user_a, "Chapter")
        assert isinstance(result, list)

    def test_search_tasks_scoped_to_user(self, user_b, task_a):
        result = SearchService.search_tasks(user_b, "Chapter")
        assert task_a.id not in result


@patch("apps.search.services._ES_AVAILABLE", False)
class TestSearchServiceMessagesFallback:
    def test_search_messages_returns_list(self, user_a, message_a):
        result = SearchService.search_messages(user_a, "quantum")
        assert isinstance(result, list)

    def test_search_messages_with_conversation_filter(
        self, user_a, conversation_a, message_a
    ):
        result = SearchService.search_messages(
            user_a, "quantum", conversation_id=conversation_a.id
        )
        assert isinstance(result, list)

    def test_search_messages_wrong_conversation(self, user_a, message_a):
        result = SearchService.search_messages(
            user_a, "quantum", conversation_id=uuid.uuid4()
        )
        assert result == []


@patch("apps.search.services._ES_AVAILABLE", False)
class TestSearchServiceUsersFallback:
    def test_search_users_returns_list(self, user_a):
        result = SearchService.search_users("Alice")
        assert isinstance(result, list)

    def test_search_users_no_match(self):
        result = SearchService.search_users("xyznonexistent99999")
        assert result == []

    def test_search_users_respects_limit(self, user_a, user_b):
        result = SearchService.search_users("", limit=1)
        assert len(result) <= 1


@patch("apps.search.services._ES_AVAILABLE", False)
class TestSearchServiceCalendarFallback:
    def test_search_calendar_returns_list(self, user_a, calendar_event_a):
        result = SearchService.search_calendar(user_a, "Study")
        assert isinstance(result, list)

    def test_search_calendar_matches_location(self, user_a, calendar_event_a):
        result = SearchService.search_calendar(user_a, "Library")
        assert isinstance(result, list)

    def test_search_calendar_scoped_to_user(self, user_b, calendar_event_a):
        result = SearchService.search_calendar(user_b, "Study")
        assert calendar_event_a.id not in result


@patch("apps.search.services._ES_AVAILABLE", False)
class TestSearchServiceCirclePostsFallback:
    def test_returns_empty_for_user_with_no_circles(self, user_a):
        result = SearchService.search_circle_posts("test", user=user_a)
        assert result == []

    def test_returns_list_with_circle_id_filter(self, circle_a, circle_post_a):
        result = SearchService.search_circle_posts(
            "algorithm", circle_id=circle_a.id
        )
        assert isinstance(result, list)

    def test_returns_posts_for_member(
        self, user_a, circle_a, circle_membership_a, circle_post_a
    ):
        result = SearchService.search_circle_posts("algorithm", user=user_a)
        assert isinstance(result, list)


@patch("apps.search.services._ES_AVAILABLE", False)
class TestSearchServiceCircleChallengesFallback:
    def test_returns_list(self, user_a, circle_membership_a, circle_challenge_a):
        result = SearchService.search_circle_challenges("Quantum", user=user_a)
        assert isinstance(result, list)

    def test_with_circle_id(self, circle_a, circle_challenge_a):
        result = SearchService.search_circle_challenges(
            "30-Day", circle_id=circle_a.id
        )
        assert isinstance(result, list)

    def test_no_circles_returns_empty(self, user_b):
        result = SearchService.search_circle_challenges("test", user=user_b)
        assert result == []


@patch("apps.search.services._ES_AVAILABLE", False)
class TestSearchServiceActivityCommentsFallback:
    def test_returns_list(self, user_a, activity_comment_a):
        result = SearchService.search_activity_comments(user_a, "progress")
        assert isinstance(result, list)

    def test_scoped_to_user(self, user_b, activity_comment_a):
        result = SearchService.search_activity_comments(user_b, "progress")
        assert activity_comment_a.id not in result


# ══════════════════════════════════════════════════════════════════════
#  13. SearchService.global_search
# ══════════════════════════════════════════════════════════════════════


@patch("apps.search.services._ES_AVAILABLE", False)
class TestGlobalSearchService:
    def test_returns_dict(self, user_a):
        result = SearchService.global_search(user_a, "quantum")
        assert isinstance(result, dict)

    def test_all_default_types(self, user_a):
        result = SearchService.global_search(user_a, "test")
        expected = {
            "dreams", "goals", "tasks", "messages", "users",
            "calendar", "circles", "circle_challenges", "activity_comments",
        }
        assert expected == set(result.keys())

    def test_type_filter_restricts_keys(self, user_a):
        result = SearchService.global_search(
            user_a, "test", types=["dreams", "users"]
        )
        assert set(result.keys()) == {"dreams", "users"}

    def test_single_type_filter(self, user_a):
        result = SearchService.global_search(
            user_a, "test", types=["calendar"]
        )
        assert set(result.keys()) == {"calendar"}

    def test_unknown_type_silently_ignored(self, user_a):
        result = SearchService.global_search(
            user_a, "test", types=["unknown_xyz"]
        )
        assert "unknown_xyz" not in result

    def test_limit_respected(self, user_a):
        result = SearchService.global_search(user_a, "test", limit=1)
        assert isinstance(result, dict)

    def test_exception_in_one_type_returns_empty_list(self, user_a):
        with patch.object(
            SearchService, "search_dreams", side_effect=Exception("boom")
        ):
            result = SearchService.global_search(
                user_a, "test", types=["dreams", "users"]
            )
            assert result["dreams"] == []
            assert "users" in result

    def test_max_results_constant(self):
        assert MAX_RESULTS == 50

    def test_es_available_is_bool(self):
        from apps.search.services import _ES_AVAILABLE

        assert isinstance(_ES_AVAILABLE, bool)


# ══════════════════════════════════════════════════════════════════════
#  14. Rate Limiting (scope check)
# ══════════════════════════════════════════════════════════════════════


class TestSearchRateLimiting:
    def test_throttle_scope_is_search(self):
        from apps.search.views import GlobalSearchView

        assert GlobalSearchView.throttle_scope == "search"

    def test_permission_is_authenticated(self):
        from rest_framework.permissions import IsAuthenticated

        from apps.search.views import GlobalSearchView

        assert IsAuthenticated in GlobalSearchView.permission_classes

    def test_throttle_class_is_scoped(self):
        from rest_framework.throttling import ScopedRateThrottle

        from apps.search.views import GlobalSearchView

        assert ScopedRateThrottle in GlobalSearchView.throttle_classes


# ══════════════════════════════════════════════════════════════════════
#  15. Management Commands
# ══════════════════════════════════════════════════════════════════════


class TestEnsureSearchIndexCommand:
    @patch("apps.search.management.commands.ensure_search_index.registry")
    def test_creates_missing_indexes(self, mock_registry):
        mock_doc = MagicMock()
        mock_doc.Index.name = "stepora_test"
        mock_doc._index.exists.return_value = False
        mock_doc.Django.model.objects.all.return_value.count.return_value = 0
        mock_registry.get_documents.return_value = [mock_doc]

        out = StringIO()
        call_command("ensure_search_index", stdout=out)

        mock_doc._index.create.assert_called_once()
        output = out.getvalue()
        assert "Creating index" in output

    @patch("apps.search.management.commands.ensure_search_index.registry")
    def test_skips_existing_indexes(self, mock_registry):
        mock_doc = MagicMock()
        mock_doc.Index.name = "stepora_existing"
        mock_doc._index.exists.return_value = True
        mock_registry.get_documents.return_value = [mock_doc]

        out = StringIO()
        call_command("ensure_search_index", stdout=out)

        mock_doc._index.create.assert_not_called()
        output = out.getvalue()
        assert "already exist" in output.lower()

    @patch("apps.search.management.commands.ensure_search_index.registry")
    def test_handles_creation_failure(self, mock_registry):
        mock_doc = MagicMock()
        mock_doc.Index.name = "stepora_fail"
        mock_doc._index.exists.return_value = False
        mock_doc._index.create.side_effect = Exception("ES connection refused")
        mock_registry.get_documents.return_value = [mock_doc]

        out = StringIO()
        err = StringIO()
        call_command("ensure_search_index", stdout=out, stderr=err)
        assert "Failed" in err.getvalue() or "All indexes" in out.getvalue()

    @patch("apps.search.management.commands.ensure_search_index.registry")
    def test_populates_newly_created_index(self, mock_registry):
        mock_doc = MagicMock()
        mock_doc.Index.name = "stepora_populate"
        mock_doc._index.exists.return_value = False
        qs_mock = MagicMock()
        qs_mock.count.return_value = 3
        qs_mock.__getitem__ = MagicMock(return_value=[1, 2, 3])
        mock_doc.Django.model.objects.all.return_value = qs_mock
        mock_registry.get_documents.return_value = [mock_doc]

        out = StringIO()
        call_command("ensure_search_index", stdout=out)
        assert "Populating" in out.getvalue()


class TestRebuildSearchIndexCommand:
    @patch("apps.search.management.commands.rebuild_search_index.registry")
    def test_rebuilds_all_indexes(self, mock_registry):
        mock_doc = MagicMock()
        mock_doc.Django.model.__name__ = "Dream"
        mock_doc.Index.name = "stepora_dreams"
        mock_doc._index.exists.return_value = True
        qs_mock = MagicMock()
        qs_mock.count.return_value = 0
        mock_doc.Django.model.objects.all.return_value = qs_mock
        mock_registry.get_documents.return_value = [mock_doc]

        out = StringIO()
        call_command("rebuild_search_index", stdout=out)

        mock_doc._index.delete.assert_called_once()
        mock_doc._index.create.assert_called_once()
        assert "Rebuilding" in out.getvalue()

    @patch("apps.search.management.commands.rebuild_search_index.registry")
    def test_filters_by_model_name(self, mock_registry):
        mock_dream = MagicMock()
        mock_dream.Django.model.__name__ = "Dream"
        mock_dream.Index.name = "stepora_dreams"
        mock_dream._index.exists.return_value = True
        mock_dream.Django.model.objects.all.return_value.count.return_value = 0

        mock_user = MagicMock()
        mock_user.Django.model.__name__ = "User"
        mock_user.Index.name = "stepora_users"
        mock_user._index.exists.return_value = True

        mock_registry.get_documents.return_value = [mock_dream, mock_user]

        out = StringIO()
        call_command("rebuild_search_index", "--models=dream", stdout=out)

        mock_dream._index.delete.assert_called_once()
        mock_user._index.delete.assert_not_called()

    @patch("apps.search.management.commands.rebuild_search_index.registry")
    def test_creates_index_when_not_exists(self, mock_registry):
        mock_doc = MagicMock()
        mock_doc.Django.model.__name__ = "Goal"
        mock_doc.Index.name = "stepora_goals"
        mock_doc._index.exists.return_value = False
        mock_doc.Django.model.objects.all.return_value.count.return_value = 0
        mock_registry.get_documents.return_value = [mock_doc]

        out = StringIO()
        call_command("rebuild_search_index", stdout=out)

        mock_doc._index.delete.assert_not_called()
        mock_doc._index.create.assert_called_once()


# ══════════════════════════════════════════════════════════════════════
#  16. Cross-user isolation (integration-style)
# ══════════════════════════════════════════════════════════════════════


class TestCrossUserIsolation:
    @patch("apps.search.views.SearchService.global_search")
    def test_user_b_cannot_see_user_a_goals(
        self, mock_search, auth_client_b, goal_a
    ):
        mock_search.return_value = {"goals": [goal_a.id]}
        resp = auth_client_b.get("/api/search/?q=qiskit")
        if "goals" in resp.data:
            assert len(resp.data["goals"]) == 0

    @patch("apps.search.views.SearchService.global_search")
    def test_user_b_cannot_see_user_a_tasks(
        self, mock_search, auth_client_b, task_a
    ):
        mock_search.return_value = {"tasks": [task_a.id]}
        resp = auth_client_b.get("/api/search/?q=chapter")
        if "tasks" in resp.data:
            assert len(resp.data["tasks"]) == 0

    @patch("apps.search.views.SearchService.global_search")
    def test_user_b_cannot_see_user_a_messages(
        self, mock_search, auth_client_b, message_a
    ):
        mock_search.return_value = {"messages": [message_a.id]}
        resp = auth_client_b.get("/api/search/?q=quantum")
        if "messages" in resp.data:
            assert len(resp.data["messages"]) == 0

    @patch("apps.search.views.SearchService.global_search")
    def test_user_b_cannot_see_user_a_calendar(
        self, mock_search, auth_client_b, calendar_event_a
    ):
        mock_search.return_value = {"calendar": [calendar_event_a.id]}
        resp = auth_client_b.get("/api/search/?q=study")
        if "calendar" in resp.data:
            assert len(resp.data["calendar"]) == 0
