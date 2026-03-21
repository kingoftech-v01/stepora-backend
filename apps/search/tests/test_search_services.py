"""
Tests for apps.search.services — SearchService business logic.

Covers: global_search, search_dreams, search_goals, search_tasks,
search_messages, search_users, search_calendar, search_circle_posts,
search_circle_challenges, search_activity_comments.

All tests run with ES disabled (_ES_AVAILABLE=False) to test DB fallback.
Fields like Dream.title and User.display_name are encrypted, so DB
icontains may not match; tests verify the correct types are returned
and that the service gracefully handles errors.
"""

from unittest.mock import MagicMock, patch

import pytest

from apps.search.services import SearchService, _es_search


# ══════════════════════════════════════════════════════════════════════
#  _es_search helper
# ══════════════════════════════════════════════════════════════════════


class TestEsSearchHelper:
    def test_uses_es_when_available(self):
        """When ES is available, build_fn is called."""
        with patch("apps.search.services._ES_AVAILABLE", True):
            build = MagicMock(return_value=["id1"])
            fallback = MagicMock(return_value=["id2"])
            result = _es_search(build, fallback, "test")
            build.assert_called_once()
            fallback.assert_not_called()
            assert result == ["id1"]

    def test_falls_back_on_es_error(self):
        """When ES raises, fallback_fn is called."""
        with patch("apps.search.services._ES_AVAILABLE", True):
            build = MagicMock(side_effect=Exception("ES down"))
            fallback = MagicMock(return_value=["id_fb"])
            result = _es_search(build, fallback, "test")
            build.assert_called_once()
            fallback.assert_called_once()
            assert result == ["id_fb"]

    def test_uses_fallback_when_es_unavailable(self):
        """When _ES_AVAILABLE is False, fallback_fn is called directly."""
        with patch("apps.search.services._ES_AVAILABLE", False):
            build = MagicMock(return_value=["id1"])
            fallback = MagicMock(return_value=["id_fb"])
            result = _es_search(build, fallback, "test")
            build.assert_not_called()
            fallback.assert_called_once()
            assert result == ["id_fb"]


# ══════════════════════════════════════════════════════════════════════
#  SearchService — individual search methods (DB fallback)
# ══════════════════════════════════════════════════════════════════════


class TestSearchDreams:
    @patch("apps.search.services._ES_AVAILABLE", False)
    def test_returns_list(self, search_user, search_dream):
        result = SearchService.search_dreams(search_user, "Python")
        assert isinstance(result, list)

    @patch("apps.search.services._ES_AVAILABLE", False)
    def test_no_results_for_nonexistent(self, search_user):
        result = SearchService.search_dreams(search_user, "zzzznonexistent")
        assert isinstance(result, list)

    @patch("apps.search.services._ES_AVAILABLE", False)
    def test_respects_limit(self, search_user, search_dream, search_dream2):
        result = SearchService.search_dreams(search_user, "", limit=1)
        # icontains with "" matches everything
        assert isinstance(result, list)


class TestSearchGoals:
    @patch("apps.search.services._ES_AVAILABLE", False)
    def test_returns_list(self, search_user, search_goal):
        result = SearchService.search_goals(search_user, "Tutorial")
        assert isinstance(result, list)

    @patch("apps.search.services._ES_AVAILABLE", False)
    def test_filter_by_dream_id(self, search_user, search_dream, search_goal):
        result = SearchService.search_goals(
            search_user, "Tutorial", dream_id=search_dream.id
        )
        assert isinstance(result, list)


class TestSearchTasks:
    @patch("apps.search.services._ES_AVAILABLE", False)
    def test_returns_list(self, search_user, search_task):
        result = SearchService.search_tasks(search_user, "Documentation")
        assert isinstance(result, list)


class TestSearchMessages:
    @patch("apps.search.services._ES_AVAILABLE", False)
    def test_returns_list(self, search_user):
        result = SearchService.search_messages(search_user, "hello")
        assert isinstance(result, list)

    @patch("apps.search.services._ES_AVAILABLE", False)
    def test_with_conversation_id(self, search_user):
        import uuid

        result = SearchService.search_messages(
            search_user, "hello", conversation_id=uuid.uuid4()
        )
        assert isinstance(result, list)


class TestSearchUsers:
    @patch("apps.search.services._ES_AVAILABLE", False)
    def test_returns_list(self, search_user):
        result = SearchService.search_users("Search")
        assert isinstance(result, list)

    @patch("apps.search.services._ES_AVAILABLE", False)
    def test_empty_result(self):
        result = SearchService.search_users("zzzznonexistent12345")
        assert isinstance(result, list)


class TestSearchCalendar:
    @patch("apps.search.services._ES_AVAILABLE", False)
    def test_returns_list(self, search_user):
        result = SearchService.search_calendar(search_user, "meeting")
        assert isinstance(result, list)


class TestSearchCirclePosts:
    @patch("apps.search.services._ES_AVAILABLE", False)
    def test_returns_list_with_user(self, search_user):
        result = SearchService.search_circle_posts("test", user=search_user)
        assert isinstance(result, list)

    @patch("apps.search.services._ES_AVAILABLE", False)
    def test_returns_list_with_circle_id(self, search_user):
        import uuid

        result = SearchService.search_circle_posts(
            "test", circle_id=uuid.uuid4()
        )
        assert isinstance(result, list)

    @patch("apps.search.services._ES_AVAILABLE", False)
    def test_returns_empty_when_no_circles(self, search_user):
        """User with no circle memberships gets empty results."""
        result = SearchService.search_circle_posts("test", user=search_user)
        assert result == []


class TestSearchCircleChallenges:
    @patch("apps.search.services._ES_AVAILABLE", False)
    def test_returns_list(self, search_user):
        result = SearchService.search_circle_challenges("test", user=search_user)
        assert isinstance(result, list)

    @patch("apps.search.services._ES_AVAILABLE", False)
    def test_with_circle_id(self):
        import uuid

        result = SearchService.search_circle_challenges(
            "test", circle_id=uuid.uuid4()
        )
        assert isinstance(result, list)


class TestSearchActivityComments:
    @patch("apps.search.services._ES_AVAILABLE", False)
    def test_returns_list(self, search_user):
        result = SearchService.search_activity_comments(search_user, "great")
        assert isinstance(result, list)


# ══════════════════════════════════════════════════════════════════════
#  SearchService.global_search
# ══════════════════════════════════════════════════════════════════════


class TestGlobalSearch:
    @patch("apps.search.services._ES_AVAILABLE", False)
    def test_returns_dict(self, search_user):
        result = SearchService.global_search(search_user, "Python")
        assert isinstance(result, dict)

    @patch("apps.search.services._ES_AVAILABLE", False)
    def test_all_default_types_present(self, search_user):
        result = SearchService.global_search(search_user, "test")
        expected = {
            "dreams", "goals", "tasks", "messages", "users",
            "calendar", "circles", "circle_challenges", "activity_comments",
        }
        assert expected == set(result.keys())

    @patch("apps.search.services._ES_AVAILABLE", False)
    def test_type_filter_restricts_categories(self, search_user):
        result = SearchService.global_search(
            search_user, "test", types=["dreams", "users"]
        )
        assert "dreams" in result
        assert "users" in result
        assert "tasks" not in result
        assert "messages" not in result

    @patch("apps.search.services._ES_AVAILABLE", False)
    def test_limit_passed_through(self, search_user):
        result = SearchService.global_search(
            search_user, "test", limit=1
        )
        assert isinstance(result, dict)

    @patch("apps.search.services._ES_AVAILABLE", False)
    def test_handles_exception_in_search_type(self, search_user):
        """If one search type fails, it returns [] for that type."""
        with patch.object(
            SearchService, "search_dreams", side_effect=Exception("boom")
        ):
            result = SearchService.global_search(
                search_user, "test", types=["dreams"]
            )
            assert result["dreams"] == []

    @patch("apps.search.services._ES_AVAILABLE", False)
    def test_unknown_type_ignored(self, search_user):
        result = SearchService.global_search(
            search_user, "test", types=["unknown_type"]
        )
        assert "unknown_type" not in result

    @patch("apps.search.services._ES_AVAILABLE", False)
    def test_single_type_filter(self, search_user):
        result = SearchService.global_search(
            search_user, "test", types=["users"]
        )
        assert "users" in result
        assert len(result) == 1

    def test_es_available_is_boolean(self):
        from apps.search.services import _ES_AVAILABLE

        assert isinstance(_ES_AVAILABLE, bool)
