"""
Tests for the search app.

Covers SearchService methods, GlobalSearchView, and the rebuild_search_index
management command.
"""

from io import StringIO
from unittest.mock import MagicMock, Mock, patch

from django.core.management import call_command
from rest_framework import status

from apps.dreams.models import Dream, Goal
from apps.search.services import SearchService

# ── SearchService unit tests ─────────────────────────────────────────


class TestSearchService:
    """Tests for SearchService — all ES calls are mocked."""

    @patch("apps.search.services.DreamDocument")
    def test_search_dreams_returns_ids(self, mock_doc, user):
        mock_search = MagicMock()
        mock_doc.search.return_value = mock_search
        mock_search.filter.return_value = mock_search
        mock_search.query.return_value = mock_search
        mock_search.__getitem__ = Mock(return_value=mock_search)

        hit1 = Mock()
        hit1.meta.id = "id-1"
        hit2 = Mock()
        hit2.meta.id = "id-2"
        mock_search.execute.return_value = [hit1, hit2]

        result = SearchService.search_dreams(user, "django")

        assert result == ["id-1", "id-2"]
        mock_search.filter.assert_called_once_with("term", user_id=str(user.id))

    @patch("apps.search.services.GoalDocument")
    def test_search_goals_with_dream_filter(self, mock_doc, user):
        mock_search = MagicMock()
        mock_doc.search.return_value = mock_search
        mock_search.filter.return_value = mock_search
        mock_search.query.return_value = mock_search
        mock_search.__getitem__ = Mock(return_value=mock_search)
        mock_search.execute.return_value = []

        SearchService.search_goals(user, "fitness", dream_id="dream-123")

        # Two filter calls: one for user_id, one for dream_id
        assert mock_search.filter.call_count == 2

    @patch("apps.search.services.TaskDocument")
    def test_search_tasks_respects_limit(self, mock_doc, user):
        mock_search = MagicMock()
        mock_doc.search.return_value = mock_search
        mock_search.filter.return_value = mock_search
        mock_search.query.return_value = mock_search
        mock_search.__getitem__ = Mock(return_value=mock_search)
        mock_search.execute.return_value = []

        SearchService.search_tasks(user, "read", limit=5)

        mock_search.__getitem__.assert_called_with(slice(None, 5))

    @patch("apps.search.services.MessageDocument")
    def test_search_messages_sorted_by_created_at(self, mock_doc, user):
        mock_search = MagicMock()
        mock_doc.search.return_value = mock_search
        mock_search.filter.return_value = mock_search
        mock_search.query.return_value = mock_search
        mock_search.sort.return_value = mock_search
        mock_search.__getitem__ = Mock(return_value=mock_search)
        mock_search.execute.return_value = []

        SearchService.search_messages(user, "hello")

        mock_search.sort.assert_called_once_with("-created_at")

    @patch("apps.search.services.UserDocument")
    def test_search_users_no_user_filter(self, mock_doc):
        mock_search = MagicMock()
        mock_doc.search.return_value = mock_search
        mock_search.query.return_value = mock_search
        mock_search.__getitem__ = Mock(return_value=mock_search)
        mock_search.execute.return_value = []

        SearchService.search_users("john")

        # search_users does NOT call .filter (no user scope)
        mock_search.filter.assert_not_called()

    @patch("apps.search.services.CalendarEventDocument")
    def test_search_calendar(self, mock_doc, user):
        mock_search = MagicMock()
        mock_doc.search.return_value = mock_search
        mock_search.filter.return_value = mock_search
        mock_search.query.return_value = mock_search
        mock_search.__getitem__ = Mock(return_value=mock_search)
        mock_search.execute.return_value = []

        SearchService.search_calendar(user, "meeting")

        mock_search.filter.assert_called_once_with("term", user_id=str(user.id))

    @patch("apps.search.services.CirclePostDocument")
    def test_search_circle_posts_with_circle_filter(self, mock_doc):
        mock_search = MagicMock()
        mock_doc.search.return_value = mock_search
        mock_search.filter.return_value = mock_search
        mock_search.query.return_value = mock_search
        mock_search.__getitem__ = Mock(return_value=mock_search)
        mock_search.execute.return_value = []

        SearchService.search_circle_posts("topic", circle_id="circle-1")

        mock_search.filter.assert_called_once_with("term", circle_id="circle-1")

    def test_global_search_default_types(self, user):
        with patch.object(
            SearchService, "search_dreams", return_value=["d1"]
        ), patch.object(
            SearchService, "search_goals", return_value=["g1"]
        ), patch.object(
            SearchService, "search_tasks", return_value=[]
        ), patch.object(
            SearchService, "search_messages", return_value=[]
        ), patch.object(
            SearchService, "search_users", return_value=[]
        ), patch.object(
            SearchService, "search_calendar", return_value=[]
        ):
            results = SearchService.global_search(user, "test")

        assert "dreams" in results
        assert "goals" in results
        assert "tasks" in results
        assert "messages" in results
        assert "users" in results
        assert "calendar" in results
        # circles not included by default
        assert "circles" not in results

    @patch.object(SearchService, "search_dreams", return_value=["d1"])
    def test_global_search_specific_types(self, mock_dreams, user):
        results = SearchService.global_search(user, "test", types=["dreams"])

        assert "dreams" in results
        assert results["dreams"] == ["d1"]
        assert "goals" not in results

    @patch.object(SearchService, "search_dreams", side_effect=Exception("ES down"))
    def test_global_search_handles_es_failure(self, mock_dreams, user):
        results = SearchService.global_search(user, "test", types=["dreams"])

        assert results["dreams"] == []


# ── GlobalSearchView tests ───────────────────────────────────────────


class TestGlobalSearchView:
    """Tests for the /api/search/ endpoint."""

    def test_search_requires_authentication(self, api_client):
        response = api_client.get("/api/search/?q=test")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_search_rejects_short_query(self, authenticated_client):
        response = authenticated_client.get("/api/search/?q=a")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "at least 2 characters" in response.data["detail"]

    def test_search_rejects_empty_query(self, authenticated_client):
        response = authenticated_client.get("/api/search/?q=")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_search_rejects_missing_query(self, authenticated_client):
        response = authenticated_client.get("/api/search/")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    @patch.object(SearchService, "global_search")
    def test_search_returns_dreams(self, mock_search, authenticated_client, user):
        dream = Dream.objects.create(user=user, title="Learn Python", status="active")
        mock_search.return_value = {"dreams": [str(dream.id)]}

        response = authenticated_client.get("/api/search/?q=python")

        assert response.status_code == status.HTTP_200_OK
        assert "dreams" in response.data
        assert len(response.data["dreams"]) == 1
        assert response.data["dreams"][0]["title"] == "Learn Python"

    @patch.object(SearchService, "global_search")
    def test_search_returns_goals(self, mock_search, authenticated_client, user):
        dream = Dream.objects.create(user=user, title="Dream", status="active")
        goal = Goal.objects.create(dream=dream, title="Read books", order=0)
        mock_search.return_value = {"goals": [str(goal.id)]}

        response = authenticated_client.get("/api/search/?q=books")

        assert response.status_code == status.HTTP_200_OK
        assert "goals" in response.data
        assert response.data["goals"][0]["title"] == "Read books"

    @patch.object(SearchService, "global_search")
    def test_search_type_filter(self, mock_search, authenticated_client, user):
        mock_search.return_value = {"dreams": []}

        authenticated_client.get("/api/search/?q=test&type=dreams")

        mock_search.assert_called_once_with(user, "test", types=["dreams"], limit=10)

    @patch.object(SearchService, "global_search")
    def test_search_multiple_type_filter(self, mock_search, authenticated_client, user):
        mock_search.return_value = {"dreams": [], "users": []}

        authenticated_client.get("/api/search/?q=test&type=dreams,users")

        mock_search.assert_called_once_with(
            user, "test", types=["dreams", "users"], limit=10
        )

    @patch.object(SearchService, "global_search")
    def test_search_empty_results(self, mock_search, authenticated_client):
        mock_search.return_value = {}

        response = authenticated_client.get("/api/search/?q=nonexistent")

        assert response.status_code == status.HTTP_200_OK
        assert response.data == {}


# ── Management command tests ─────────────────────────────────────────


class TestRebuildSearchIndexCommand:
    """Tests for the rebuild_search_index management command."""

    @patch("apps.search.management.commands.rebuild_search_index.registry")
    def test_rebuild_all_indexes(self, mock_registry):
        mock_index = MagicMock()
        mock_index.exists.return_value = True

        mock_qs = MagicMock()
        mock_qs.count.return_value = 0
        mock_qs.__getitem__ = Mock(return_value=[])

        mock_doc = MagicMock()
        mock_doc.Django.model.__name__ = "Dream"
        mock_doc.Index.name = "dreams"
        mock_doc._index = mock_index
        mock_doc.Django.model.objects.all.return_value = mock_qs

        mock_registry.get_documents.return_value = [mock_doc]

        out = StringIO()
        call_command("rebuild_search_index", stdout=out)

        output = out.getvalue()
        assert "dreams" in output
        assert "All indexes rebuilt" in output
        mock_index.delete.assert_called_once()
        mock_index.create.assert_called_once()

    @patch("apps.search.management.commands.rebuild_search_index.registry")
    def test_rebuild_filtered_models(self, mock_registry):
        mock_index1 = MagicMock()
        mock_index1.exists.return_value = True

        mock_doc1 = MagicMock()
        mock_doc1.Django.model.__name__ = "Dream"
        mock_doc1.Index.name = "dreams"
        mock_doc1._index = mock_index1
        mock_doc1.Django.model.objects.all.return_value.count = Mock(return_value=0)

        mock_index2 = MagicMock()
        mock_doc2 = MagicMock()
        mock_doc2.Django.model.__name__ = "User"
        mock_doc2.Index.name = "users"
        mock_doc2._index = mock_index2

        mock_registry.get_documents.return_value = [mock_doc1, mock_doc2]

        out = StringIO()
        call_command("rebuild_search_index", "--models=dream", stdout=out)

        # Only dream should be rebuilt
        mock_index1.delete.assert_called_once()
        mock_index2.delete.assert_not_called()

    @patch("apps.search.management.commands.rebuild_search_index.registry")
    def test_rebuild_creates_index_if_not_exists(self, mock_registry):
        mock_index = MagicMock()
        mock_index.exists.return_value = False

        mock_doc = MagicMock()
        mock_doc.Django.model.__name__ = "Dream"
        mock_doc.Index.name = "dreams"
        mock_doc._index = mock_index
        mock_doc.Django.model.objects.all.return_value.count = Mock(return_value=0)

        mock_registry.get_documents.return_value = [mock_doc]

        call_command("rebuild_search_index", stdout=StringIO())

        mock_index.delete.assert_not_called()
        mock_index.create.assert_called_once()
