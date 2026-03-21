"""
Tests for apps.search.views — GlobalSearchView API endpoint.

Covers: GET /api/search/?q=<query>&type=<types>
- Authentication required
- Minimum query length validation
- Type filtering (dreams, users, all)
- Empty results
- Hydration of results with model data
"""

from unittest.mock import patch

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from apps.dreams.models import Dream, Goal, Task
from apps.users.models import User


@pytest.fixture
def search_client(search_user):
    client = APIClient()
    client.force_authenticate(user=search_user)
    return client


@pytest.fixture
def unauthenticated_client():
    return APIClient()


# ══════════════════════════════════════════════════════════════════════
#  Authentication
# ══════════════════════════════════════════════════════════════════════


class TestGlobalSearchAuth:
    def test_unauthenticated_returns_401(self, unauthenticated_client):
        resp = unauthenticated_client.get("/api/search/?q=test")
        assert resp.status_code in (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN)

    def test_authenticated_succeeds(self, search_client):
        resp = search_client.get("/api/search/?q=test")
        # Might be 200 or 400 depending on query, but not 401/403
        assert resp.status_code in (
            status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST,
        )


# ══════════════════════════════════════════════════════════════════════
#  Query Validation
# ══════════════════════════════════════════════════════════════════════


class TestGlobalSearchValidation:
    def test_empty_query_returns_400(self, search_client):
        resp = search_client.get("/api/search/?q=")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        assert "2 characters" in resp.data["detail"].lower() or "2 char" in resp.data["detail"].lower()

    def test_single_char_query_returns_400(self, search_client):
        resp = search_client.get("/api/search/?q=a")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_missing_q_param_returns_400(self, search_client):
        resp = search_client.get("/api/search/")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_whitespace_only_query_returns_400(self, search_client):
        resp = search_client.get("/api/search/?q=   ")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_valid_query_returns_200(self, search_client):
        resp = search_client.get("/api/search/?q=python")
        assert resp.status_code == status.HTTP_200_OK


# ══════════════════════════════════════════════════════════════════════
#  Type Filtering
# ══════════════════════════════════════════════════════════════════════


class TestGlobalSearchTypeFiltering:
    @patch("apps.search.views.SearchService.global_search")
    def test_type_filter_passed_to_service(
        self, mock_search, search_client
    ):
        mock_search.return_value = {}
        search_client.get("/api/search/?q=test&type=dreams")
        mock_search.assert_called_once()
        call_args = mock_search.call_args
        assert call_args[1].get("types") == ["dreams"] or call_args[0][2] == ["dreams"]  # positional or kw

    @patch("apps.search.views.SearchService.global_search")
    def test_multiple_types(self, mock_search, search_client):
        mock_search.return_value = {}
        search_client.get("/api/search/?q=test&type=dreams,users")
        mock_search.assert_called_once()

    @patch("apps.search.views.SearchService.global_search")
    def test_empty_type_passes_none(self, mock_search, search_client):
        mock_search.return_value = {}
        search_client.get("/api/search/?q=test")
        mock_search.assert_called_once()
        call_kwargs = mock_search.call_args
        # types should be None when not specified
        types_arg = call_kwargs[1].get("types") if call_kwargs[1] else call_kwargs[0][2] if len(call_kwargs[0]) > 2 else None
        assert types_arg is None


# ══════════════════════════════════════════════════════════════════════
#  Result Hydration
# ══════════════════════════════════════════════════════════════════════


class TestGlobalSearchResults:
    @patch("apps.search.views.SearchService.global_search")
    def test_dreams_hydrated(
        self, mock_search, search_client, search_dream
    ):
        mock_search.return_value = {
            "dreams": [search_dream.id],
        }
        resp = search_client.get("/api/search/?q=python")
        assert resp.status_code == status.HTTP_200_OK
        assert "dreams" in resp.data
        assert len(resp.data["dreams"]) == 1
        assert resp.data["dreams"][0]["title"] == "Learn Python Programming"

    @patch("apps.search.views.SearchService.global_search")
    def test_goals_hydrated(
        self, mock_search, search_client, search_goal
    ):
        mock_search.return_value = {
            "goals": [search_goal.id],
        }
        resp = search_client.get("/api/search/?q=tutorial")
        assert resp.status_code == status.HTTP_200_OK
        assert "goals" in resp.data
        assert resp.data["goals"][0]["title"] == "Complete Python Tutorial"

    @patch("apps.search.views.SearchService.global_search")
    def test_tasks_hydrated(
        self, mock_search, search_client, search_task
    ):
        mock_search.return_value = {
            "tasks": [search_task.id],
        }
        resp = search_client.get("/api/search/?q=documentation")
        assert resp.status_code == status.HTTP_200_OK
        assert "tasks" in resp.data
        assert resp.data["tasks"][0]["title"] == "Read Python Documentation"

    @patch("apps.search.views.SearchService.global_search")
    def test_users_hydrated(self, mock_search, search_client, search_user2):
        mock_search.return_value = {
            "users": [search_user2.id],
        }
        resp = search_client.get("/api/search/?q=another")
        assert resp.status_code == status.HTTP_200_OK
        assert "users" in resp.data
        assert resp.data["users"][0]["display_name"] == "Another User"

    @patch("apps.search.views.SearchService.global_search")
    def test_empty_results(self, mock_search, search_client):
        mock_search.return_value = {}
        resp = search_client.get("/api/search/?q=nonexistent")
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data == {}

    @patch("apps.search.views.SearchService.global_search")
    def test_empty_list_results_excluded(
        self, mock_search, search_client
    ):
        mock_search.return_value = {
            "dreams": [],
            "users": [],
        }
        resp = search_client.get("/api/search/?q=test")
        assert resp.status_code == status.HTTP_200_OK
        # Empty lists are falsy, so they should not appear in response
        assert "dreams" not in resp.data
        assert "users" not in resp.data

    @patch("apps.search.views.SearchService.global_search")
    def test_other_user_dreams_not_returned(
        self, mock_search, search_client, search_user2
    ):
        """Dreams owned by another user are filtered out during hydration."""
        other_dream = Dream.objects.create(
            user=search_user2,
            title="Secret Dream",
            description="Not mine",
            category="personal",
            status="active",
        )
        mock_search.return_value = {
            "dreams": [other_dream.id],
        }
        resp = search_client.get("/api/search/?q=secret")
        assert resp.status_code == status.HTTP_200_OK
        # The dream should be filtered because it belongs to search_user2,
        # not search_user (the authenticated user)
        if "dreams" in resp.data:
            assert len(resp.data["dreams"]) == 0
