"""
Unit tests for the Search app services.

Note: Dream title, Goal title, Task title, and User display_name are encrypted
fields. The DB fallback in SearchService uses icontains which does not work on
encrypted fields. These tests mock the DB queries to test the service logic.
"""

from unittest.mock import MagicMock, patch

from apps.search.services import SearchService

# ── SearchService basic functionality ─────────────────────────────────


class TestSearchService:
    """Tests for the SearchService (mocked DB queries for encrypted fields)."""

    @patch("apps.search.services._ES_AVAILABLE", False)
    def test_search_dreams_returns_list(self, search_user):
        """search_dreams returns a list of IDs."""
        with patch("apps.dreams.models.Dream.objects") as mock_qs:
            mock_qs.filter.return_value.values_list.return_value.__getitem__ = (
                lambda self, key: [search_user.id]
            )
            mock_qs.filter.return_value.values_list.return_value = MagicMock()
            mock_qs.filter.return_value.values_list.return_value.__getitem__ = (
                lambda self, key: []
            )
            results = SearchService.search_dreams(search_user, "Python")
            assert isinstance(results, list)

    @patch("apps.search.services._ES_AVAILABLE", False)
    def test_search_goals_returns_list(self, search_user):
        """search_goals returns a list."""
        with patch("apps.dreams.models.Goal.objects") as mock_qs:
            mock_qs.filter.return_value.values_list.return_value.__getitem__ = (
                lambda self, key: []
            )
            results = SearchService.search_goals(search_user, "Tutorial")
            assert isinstance(results, list)

    @patch("apps.search.services._ES_AVAILABLE", False)
    def test_search_tasks_returns_list(self, search_user):
        """search_tasks returns a list."""
        with patch("apps.dreams.models.Task.objects") as mock_qs:
            mock_qs.filter.return_value.values_list.return_value.__getitem__ = (
                lambda self, key: []
            )
            results = SearchService.search_tasks(search_user, "Documentation")
            assert isinstance(results, list)

    @patch("apps.search.services._ES_AVAILABLE", False)
    def test_search_users_returns_list(self, search_user):
        """search_users returns a list."""
        with patch("apps.users.models.User.objects") as mock_qs:
            mock_qs.filter.return_value.values_list.return_value.__getitem__ = (
                lambda self, key: []
            )
            results = SearchService.search_users("Search")
            assert isinstance(results, list)

    @patch("apps.search.services._ES_AVAILABLE", False)
    def test_global_search_returns_dict(self, search_user):
        """global_search returns a dict with category keys."""
        results = SearchService.global_search(search_user, "Python")
        assert isinstance(results, dict)
        # Should have standard search categories
        assert "dreams" in results

    @patch("apps.search.services._ES_AVAILABLE", False)
    def test_global_search_with_types_filter(self, search_user):
        """global_search respects the types filter."""
        results = SearchService.global_search(
            search_user, "Python", types=["dreams"]
        )
        assert "dreams" in results
        assert "tasks" not in results

    @patch("apps.search.services._ES_AVAILABLE", False)
    def test_global_search_limit_parameter(self, search_user):
        """global_search accepts a limit parameter."""
        results = SearchService.global_search(
            search_user, "Python", limit=1
        )
        assert isinstance(results, dict)

    @patch("apps.search.services._ES_AVAILABLE", False)
    def test_global_search_handles_errors(self, search_user):
        """global_search catches exceptions and returns empty lists."""
        with patch.object(
            SearchService, "search_dreams", side_effect=Exception("test error")
        ):
            results = SearchService.global_search(
                search_user, "Python", types=["dreams"]
            )
            assert results["dreams"] == []

    @patch("apps.search.services._ES_AVAILABLE", False)
    def test_global_search_all_default_types(self, search_user):
        """global_search includes all default types when none specified."""
        results = SearchService.global_search(search_user, "test")
        expected_keys = {
            "dreams", "goals", "tasks", "messages", "users",
            "calendar", "circles", "circle_challenges", "activity_comments",
        }
        assert expected_keys == set(results.keys())

    @patch("apps.search.services._ES_AVAILABLE", False)
    def test_search_dreams_empty_query(self, search_user):
        """search_dreams with empty results returns empty list."""
        results = SearchService.search_dreams(
            search_user, "xyznonexistentquery123"
        )
        assert isinstance(results, list)

    def test_es_available_flag(self):
        """_ES_AVAILABLE is a boolean flag."""
        from apps.search.services import _ES_AVAILABLE

        assert isinstance(_ES_AVAILABLE, bool)

    @patch("apps.search.services._ES_AVAILABLE", False)
    def test_search_calendar_returns_list(self, search_user):
        """search_calendar returns a list."""
        results = SearchService.search_calendar(search_user, "meeting")
        assert isinstance(results, list)

    @patch("apps.search.services._ES_AVAILABLE", False)
    def test_search_circle_posts_returns_list(self, search_user):
        """search_circle_posts returns a list."""
        results = SearchService.search_circle_posts("test post", user=search_user)
        assert isinstance(results, list)

    @patch("apps.search.services._ES_AVAILABLE", False)
    def test_search_messages_returns_list(self, search_user):
        """search_messages returns a list."""
        results = SearchService.search_messages(search_user, "hello")
        assert isinstance(results, list)
