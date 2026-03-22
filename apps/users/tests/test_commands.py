"""
Tests for users app management commands.

Tests:
- create_admin: creates a new superadmin or updates an existing user
"""

from io import StringIO
from unittest.mock import patch

import pytest
from django.core.management import call_command

from apps.users.models import User
from core.auth.models import EmailAddress


@pytest.mark.django_db
class TestCreateAdminCommand:
    """Tests for the create_admin management command."""

    @patch("apps.users.management.commands.create_admin.send_password_reset_email")
    def test_creates_new_admin(self, mock_reset_email):
        """create_admin creates a new superuser when none exists."""
        mock_reset_email.delay.return_value = None

        out = StringIO()
        call_command(
            "create_admin",
            "--email=newadmin@test.com",
            "--name=New Admin",
            stdout=out,
        )

        output = out.getvalue()
        assert "Created superadmin" in output

        user = User.objects.get(email="newadmin@test.com")
        assert user.is_superuser is True
        assert user.is_staff is True
        assert user.is_active is True
        assert user.display_name == "New Admin"

        # Verify EmailAddress was created and verified
        email_addr = EmailAddress.objects.get(user=user, email="newadmin@test.com")
        assert email_addr.verified is True
        assert email_addr.primary is True

        # Verify password reset email was triggered
        mock_reset_email.delay.assert_called_once_with(str(user.id))

    @patch("apps.users.management.commands.create_admin.send_password_reset_email")
    def test_updates_existing_user_to_admin(self, mock_reset_email):
        """create_admin promotes an existing user to superadmin."""
        mock_reset_email.delay.return_value = None

        # Create a regular user first
        user = User.objects.create_user(
            email="existing@test.com",
            password="oldpassword",
            display_name="Existing User",
        )
        assert user.is_superuser is False
        assert user.is_staff is False

        out = StringIO()
        call_command(
            "create_admin",
            "--email=existing@test.com",
            "--name=Promoted Admin",
            stdout=out,
        )

        output = out.getvalue()
        assert "Updated existing user" in output

        user.refresh_from_db()
        assert user.is_superuser is True
        assert user.is_staff is True
        assert user.is_active is True

        # Verify EmailAddress was created and verified
        email_addr = EmailAddress.objects.get(user=user, email="existing@test.com")
        assert email_addr.verified is True

    @patch("apps.users.management.commands.create_admin.send_password_reset_email")
    def test_default_name(self, mock_reset_email):
        """create_admin uses 'Admin' as default name."""
        mock_reset_email.delay.return_value = None

        out = StringIO()
        call_command(
            "create_admin",
            "--email=default@test.com",
            stdout=out,
        )

        user = User.objects.get(email="default@test.com")
        assert user.display_name == "Admin"

    @patch("apps.users.management.commands.create_admin.send_password_reset_email")
    def test_email_case_insensitive(self, mock_reset_email):
        """create_admin normalizes email to lowercase."""
        mock_reset_email.delay.return_value = None

        out = StringIO()
        call_command(
            "create_admin",
            "--email=Admin@TEST.com",
            "--name=Case Test",
            stdout=out,
        )

        assert User.objects.filter(email="admin@test.com").exists()

    @patch("apps.users.management.commands.create_admin.send_password_reset_email")
    def test_updates_existing_email_address(self, mock_reset_email):
        """create_admin updates existing unverified EmailAddress to verified."""
        mock_reset_email.delay.return_value = None

        user = User.objects.create_user(
            email="unverified@test.com",
            password="testpass",
            display_name="Unverified",
        )
        EmailAddress.objects.create(
            user=user,
            email="unverified@test.com",
            verified=False,
            primary=False,
        )

        out = StringIO()
        call_command(
            "create_admin",
            "--email=unverified@test.com",
            stdout=out,
        )

        email_addr = EmailAddress.objects.get(user=user, email="unverified@test.com")
        assert email_addr.verified is True
        assert email_addr.primary is True

    @patch("apps.users.management.commands.create_admin.send_password_reset_email")
    def test_success_message(self, mock_reset_email):
        """create_admin shows success message at the end."""
        mock_reset_email.delay.return_value = None

        out = StringIO()
        call_command(
            "create_admin",
            "--email=success@test.com",
            "--name=Success",
            stdout=out,
        )
        output = out.getvalue()
        assert "Done" in output
        assert "superadmin" in output
        assert "Password reset email sent" in output


@pytest.mark.django_db
class TestSeedDreamTemplatesCommand:
    """Tests for the seed_dream_templates management command."""

    def test_seed_creates_templates(self):
        """seed_dream_templates creates 12 templates."""
        from apps.dreams.models import DreamTemplate

        out = StringIO()
        call_command("seed_dream_templates", stdout=out)

        output = out.getvalue()
        assert "Seeded" in output
        assert DreamTemplate.objects.count() >= 12

    def test_seed_is_idempotent(self):
        """Running seed_dream_templates twice does not duplicate templates."""
        from apps.dreams.models import DreamTemplate

        out1 = StringIO()
        call_command("seed_dream_templates", stdout=out1)
        count1 = DreamTemplate.objects.count()

        out2 = StringIO()
        call_command("seed_dream_templates", stdout=out2)
        count2 = DreamTemplate.objects.count()

        assert count1 == count2

    def test_seed_template_categories(self):
        """seed_dream_templates creates templates across categories."""
        from apps.dreams.models import DreamTemplate

        call_command("seed_dream_templates", stdout=StringIO())

        categories = set(
            DreamTemplate.objects.values_list("category", flat=True)
        )
        # Should include at least health, career, finance, personal, hobbies, relationships
        assert len(categories) >= 5


@pytest.mark.django_db
class TestSeedLeaguesCommand:
    """Tests for the seed_leagues management command."""

    def test_seed_creates_leagues(self):
        """seed_leagues creates 7 league tiers."""
        from apps.leagues.models import League

        out = StringIO()
        call_command("seed_leagues", stdout=out)

        output = out.getvalue()
        assert "Successfully" in output
        assert League.objects.count() == 7

    def test_seed_creates_initial_season(self):
        """seed_leagues creates an active season."""
        from django.core.cache import cache

        from apps.leagues.models import Season

        cache.clear()  # Clear cached active season
        call_command("seed_leagues", stdout=StringIO())

        # Check either is_active=True or status='active'
        active = Season.objects.filter(status="active")
        assert active.exists(), (
            f"No active season found. All seasons: "
            f"{list(Season.objects.values('name', 'status', 'is_active'))}"
        )

    def test_seed_is_idempotent(self):
        """Running seed_leagues twice does not duplicate."""
        from apps.leagues.models import League

        call_command("seed_leagues", stdout=StringIO())
        count1 = League.objects.count()

        call_command("seed_leagues", stdout=StringIO())
        count2 = League.objects.count()

        assert count1 == count2

    def test_seed_force_recreates(self):
        """seed_leagues --force deletes and recreates leagues."""
        from apps.leagues.models import League

        call_command("seed_leagues", stdout=StringIO())
        assert League.objects.count() == 7

        out = StringIO()
        call_command("seed_leagues", "--force", stdout=out)
        output = out.getvalue()
        assert "Deleted" in output
        assert League.objects.count() == 7

    def test_league_tiers(self):
        """seed_leagues creates all expected tiers."""
        from apps.leagues.models import League

        call_command("seed_leagues", stdout=StringIO())

        tiers = set(League.objects.values_list("tier", flat=True))
        expected = {"bronze", "silver", "gold", "platinum", "diamond", "master", "legend"}
        assert tiers == expected

    def test_league_xp_ordering(self):
        """Leagues are seeded with increasing min_xp."""
        from apps.leagues.models import League

        call_command("seed_leagues", stdout=StringIO())

        leagues = list(League.objects.order_by("min_xp"))
        for i in range(1, len(leagues)):
            assert leagues[i].min_xp > leagues[i - 1].min_xp
