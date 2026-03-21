#!/usr/bin/env python3
"""
Stepora API Health Check / Smoke Test
======================================

Comprehensive endpoint tester for the Stepora backend API.
Tests all API endpoints against a running backend, handling authentication,
resource creation, and cleanup.

Usage:
    python scripts/qa_api_health_check.py
    python scripts/qa_api_health_check.py --base-url https://dpapi.jhpetitfrere.com
    python scripts/qa_api_health_check.py --base-url https://api.stepora.app

Environment variables:
    API_BASE         Base URL (default: http://localhost:8000)
    ADMIN_EMAIL      Admin email for authenticated tests
    ADMIN_PASSWORD   Admin password for authenticated tests
"""

import argparse
import os
import sys
import time
import uuid
from dataclasses import dataclass, field
from typing import Optional

try:
    import requests
except ImportError:
    print("ERROR: 'requests' library is required. Install with: pip install requests")
    sys.exit(2)


# ---------------------------------------------------------------------------
# ANSI color helpers
# ---------------------------------------------------------------------------

class Color:
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    CYAN = "\033[96m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RESET = "\033[0m"

    @staticmethod
    def disable():
        Color.GREEN = ""
        Color.RED = ""
        Color.YELLOW = ""
        Color.CYAN = ""
        Color.BOLD = ""
        Color.DIM = ""
        Color.RESET = ""


# ---------------------------------------------------------------------------
# Result tracking
# ---------------------------------------------------------------------------

@dataclass
class TestResult:
    method: str
    path: str
    expected_status: int
    actual_status: Optional[int]
    elapsed_ms: float
    passed: bool
    error: Optional[str] = None


@dataclass
class TestContext:
    """Shared state across test categories."""
    base_url: str
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    test_user_email: Optional[str] = None
    test_user_password: Optional[str] = None
    dream_id: Optional[str] = None
    milestone_id: Optional[str] = None
    goal_id: Optional[str] = None
    task_id: Optional[str] = None
    post_id: Optional[str] = None
    event_id: Optional[str] = None
    results: list = field(default_factory=list)
    cleanup_items: list = field(default_factory=list)


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

REQUEST_TIMEOUT = 10  # seconds


def make_request(
    ctx: TestContext,
    method: str,
    path: str,
    expected_status: int,
    authenticated: bool = False,
    json_data: dict = None,
    params: dict = None,
    allow_statuses: list = None,
) -> TestResult:
    """Execute a single API request and record the result."""
    url = f"{ctx.base_url}{path}"
    headers = {"Content-Type": "application/json"}
    if authenticated and ctx.access_token:
        headers["Authorization"] = f"Bearer {ctx.access_token}"
        headers["X-Client-Platform"] = "native"

    start = time.time()
    actual_status = None
    error = None
    response = None

    try:
        response = requests.request(
            method=method,
            url=url,
            headers=headers,
            json=json_data,
            params=params,
            timeout=REQUEST_TIMEOUT,
        )
        actual_status = response.status_code
    except requests.Timeout:
        error = "TIMEOUT"
    except requests.ConnectionError:
        error = "CONNECTION_REFUSED"
    except requests.RequestException as exc:
        error = str(exc)[:80]

    elapsed_ms = (time.time() - start) * 1000

    acceptable = allow_statuses or [expected_status]
    passed = actual_status in acceptable if actual_status is not None else False

    result = TestResult(
        method=method.upper(),
        path=path,
        expected_status=expected_status,
        actual_status=actual_status,
        elapsed_ms=elapsed_ms,
        passed=passed,
        error=error,
    )
    ctx.results.append(result)

    return result, response


def print_result(result: TestResult):
    """Print a single test result line."""
    if result.passed:
        icon = f"{Color.GREEN}  ✓{Color.RESET}"
        status_str = f"{result.actual_status}"
        timing = f"{Color.DIM}({result.elapsed_ms:.0f}ms){Color.RESET}"
        print(f"{icon} {result.method:<6} {result.path:<50} {status_str:<5} {timing}")
    else:
        icon = f"{Color.RED}  ✗{Color.RESET}"
        if result.error:
            detail = f"{Color.RED}{result.error}{Color.RESET}"
        else:
            detail = (
                f"{Color.RED}EXPECTED {result.expected_status}, "
                f"GOT {result.actual_status}{Color.RESET}"
            )
        print(f"{icon} {result.method:<6} {result.path:<50} {detail}")


def print_section(name: str):
    """Print a section header."""
    print(f"\n{Color.CYAN}{Color.BOLD}[{name}]{Color.RESET}")


# ---------------------------------------------------------------------------
# Test categories
# ---------------------------------------------------------------------------

def test_health(ctx: TestContext):
    """Test health check endpoints (unauthenticated)."""
    print_section("HEALTH")

    for path, status in [
        ("/health/", 200),
        ("/health/liveness/", 200),
        ("/health/readiness/", 200),
    ]:
        result, _ = make_request(ctx, "GET", path, status)
        print_result(result)


def test_auth(ctx: TestContext):
    """Test authentication endpoints."""
    print_section("AUTH")

    # Generate unique test user
    unique = uuid.uuid4().hex[:8]
    ctx.test_user_email = f"qa_test_{unique}@stepora-healthcheck.test"
    ctx.test_user_password = f"QaT3st!{unique}Pwd"

    # --- Register ---
    result, resp = make_request(
        ctx, "POST", "/api/v1/auth/registration/", 201,
        json_data={
            "email": ctx.test_user_email,
            "password1": ctx.test_user_password,
            "password2": ctx.test_user_password,
            "display_name": f"QA Bot {unique}",
        },
        allow_statuses=[201, 204],
    )
    print_result(result)

    # --- Login ---
    result, resp = make_request(
        ctx, "POST", "/api/v1/auth/login/", 200,
        json_data={
            "email": ctx.test_user_email,
            "password": ctx.test_user_password,
        },
    )
    print_result(result)

    if resp and resp.status_code == 200:
        data = resp.json()
        ctx.access_token = data.get("access_token") or data.get("access")
        ctx.refresh_token = data.get("refresh_token") or data.get("refresh")

    # --- Token refresh ---
    if ctx.refresh_token:
        result, resp = make_request(
            ctx, "POST", "/api/v1/auth/token/refresh/", 200,
            json_data={"refresh": ctx.refresh_token},
        )
        print_result(result)
        if resp and resp.status_code == 200:
            data = resp.json()
            new_access = data.get("access_token") or data.get("access")
            if new_access:
                ctx.access_token = new_access
    else:
        result, _ = make_request(ctx, "POST", "/api/v1/auth/token/refresh/", 200,
                                 json_data={"refresh": "invalid"})
        print_result(result)

    # --- Password reset request (does not need auth) ---
    result, _ = make_request(
        ctx, "POST", "/api/v1/auth/password/reset/", 200,
        json_data={"email": ctx.test_user_email},
        allow_statuses=[200, 204],
    )
    print_result(result)

    # --- Auth user detail ---
    result, _ = make_request(
        ctx, "GET", "/api/v1/auth/user/", 200,
        authenticated=True,
    )
    print_result(result)


def test_users(ctx: TestContext):
    """Test user endpoints (authenticated)."""
    print_section("USERS")

    result, _ = make_request(ctx, "GET", "/api/v1/users/me/", 200, authenticated=True)
    print_result(result)

    result, _ = make_request(
        ctx, "PATCH", "/api/v1/users/update_profile/", 200,
        authenticated=True,
        json_data={"bio": "QA health check test"},
        allow_statuses=[200],
    )
    print_result(result)

    result, _ = make_request(ctx, "GET", "/api/v1/users/persona/", 200, authenticated=True)
    print_result(result)

    result, _ = make_request(ctx, "GET", "/api/v1/users/dashboard/", 200, authenticated=True)
    print_result(result)

    result, _ = make_request(ctx, "GET", "/api/v1/users/stats/", 200, authenticated=True)
    print_result(result)

    result, _ = make_request(ctx, "GET", "/api/v1/users/achievements/", 200, authenticated=True)
    print_result(result)

    result, _ = make_request(ctx, "GET", "/api/v1/users/profile-completeness/", 200, authenticated=True)
    print_result(result)


def test_dreams(ctx: TestContext):
    """Test dream CRUD endpoints."""
    print_section("DREAMS")

    # --- Create dream ---
    result, resp = make_request(
        ctx, "POST", "/api/v1/dreams/dreams/", 201,
        authenticated=True,
        json_data={
            "title": "QA Health Check Dream",
            "description": "Automated test dream for API health check",
            "category": "career",
            "target_date": "2027-12-31",
        },
    )
    print_result(result)

    if resp and resp.status_code == 201:
        data = resp.json()
        ctx.dream_id = data.get("id")

    # --- List dreams ---
    result, _ = make_request(
        ctx, "GET", "/api/v1/dreams/dreams/", 200,
        authenticated=True,
    )
    print_result(result)

    # --- Dream detail ---
    if ctx.dream_id:
        result, _ = make_request(
            ctx, "GET", f"/api/v1/dreams/dreams/{ctx.dream_id}/", 200,
            authenticated=True,
        )
        print_result(result)

        # --- Update dream ---
        result, _ = make_request(
            ctx, "PATCH", f"/api/v1/dreams/dreams/{ctx.dream_id}/", 200,
            authenticated=True,
            json_data={"description": "Updated by QA health check"},
        )
        print_result(result)

        # --- Favorite (like) ---
        result, _ = make_request(
            ctx, "POST", f"/api/v1/dreams/dreams/{ctx.dream_id}/like/", 200,
            authenticated=True,
            allow_statuses=[200, 201],
        )
        print_result(result)

        # --- Explore ---
        result, _ = make_request(
            ctx, "GET", "/api/v1/dreams/dreams/explore/", 200,
            authenticated=True,
        )
        print_result(result)

    # --- Tags list ---
    result, _ = make_request(
        ctx, "GET", "/api/v1/dreams/dreams/tags/", 200,
        authenticated=True,
    )
    print_result(result)

    # --- Templates list ---
    result, _ = make_request(
        ctx, "GET", "/api/v1/dreams/dreams/templates/", 200,
        authenticated=True,
    )
    print_result(result)

    # --- Shared with me ---
    result, _ = make_request(
        ctx, "GET", "/api/v1/dreams/dreams/shared-with-me/", 200,
        authenticated=True,
    )
    print_result(result)


def test_plans(ctx: TestContext):
    """Test plan endpoints (milestones, goals, tasks)."""
    print_section("PLANS")

    # --- Milestones ---
    params = {"dream": ctx.dream_id} if ctx.dream_id else {}
    result, resp = make_request(
        ctx, "GET", "/api/v1/plans/milestones/", 200,
        authenticated=True,
        params=params,
    )
    print_result(result)

    # --- Goals ---
    result, resp = make_request(
        ctx, "GET", "/api/v1/plans/goals/", 200,
        authenticated=True,
        params=params,
    )
    print_result(result)

    # --- Tasks ---
    result, _ = make_request(
        ctx, "GET", "/api/v1/plans/tasks/", 200,
        authenticated=True,
    )
    print_result(result)

    # --- Obstacles ---
    result, _ = make_request(
        ctx, "GET", "/api/v1/plans/obstacles/", 200,
        authenticated=True,
    )
    print_result(result)

    # --- Check-ins ---
    result, _ = make_request(
        ctx, "GET", "/api/v1/plans/checkins/", 200,
        authenticated=True,
    )
    print_result(result)

    # --- Focus stats ---
    result, _ = make_request(
        ctx, "GET", "/api/v1/dreams/focus/stats/", 200,
        authenticated=True,
    )
    print_result(result)

    # --- Focus history ---
    result, _ = make_request(
        ctx, "GET", "/api/v1/dreams/focus/history/", 200,
        authenticated=True,
    )
    print_result(result)


def test_social(ctx: TestContext):
    """Test social / posts endpoints."""
    print_section("SOCIAL")

    # --- Create post ---
    result, resp = make_request(
        ctx, "POST", "/api/v1/social/posts/", 201,
        authenticated=True,
        json_data={
            "content": "QA health check post",
            "visibility": "public",
        },
        allow_statuses=[201, 200],
    )
    print_result(result)

    if resp and resp.status_code in (200, 201):
        data = resp.json()
        ctx.post_id = data.get("id")

    # --- List posts ---
    result, _ = make_request(
        ctx, "GET", "/api/v1/social/posts/", 200,
        authenticated=True,
    )
    print_result(result)

    # --- Feed ---
    result, _ = make_request(
        ctx, "GET", "/api/v1/social/posts/feed/", 200,
        authenticated=True,
    )
    print_result(result)

    # --- Saved posts ---
    result, _ = make_request(
        ctx, "GET", "/api/v1/social/posts/saved/", 200,
        authenticated=True,
    )
    print_result(result)

    # --- Events list ---
    result, _ = make_request(
        ctx, "GET", "/api/v1/social/events/", 200,
        authenticated=True,
    )
    print_result(result)

    # --- Events feed ---
    result, _ = make_request(
        ctx, "GET", "/api/v1/social/events/feed/", 200,
        authenticated=True,
    )
    print_result(result)

    # --- Stories feed ---
    result, _ = make_request(
        ctx, "GET", "/api/v1/social/stories/feed/", 200,
        authenticated=True,
    )
    print_result(result)

    # --- User search ---
    result, _ = make_request(
        ctx, "GET", "/api/v1/social/users/search", 200,
        authenticated=True,
        params={"q": "test"},
    )
    print_result(result)

    # --- Friend suggestions ---
    result, _ = make_request(
        ctx, "GET", "/api/v1/social/friend-suggestions/", 200,
        authenticated=True,
    )
    print_result(result)

    # --- Follow suggestions ---
    result, _ = make_request(
        ctx, "GET", "/api/v1/social/follow-suggestions/", 200,
        authenticated=True,
    )
    print_result(result)

    # --- Friends activity feed ---
    result, _ = make_request(
        ctx, "GET", "/api/v1/social/feed/friends/", 200,
        authenticated=True,
    )
    print_result(result)

    # --- Social friends list ---
    result, _ = make_request(
        ctx, "GET", "/api/v1/social/friends/", 200,
        authenticated=True,
    )
    print_result(result)


def test_friends(ctx: TestContext):
    """Test dedicated friends endpoints."""
    print_section("FRIENDS")

    result, _ = make_request(
        ctx, "GET", "/api/v1/friends/friends/", 200,
        authenticated=True,
    )
    print_result(result)

    result, _ = make_request(
        ctx, "GET", "/api/v1/friends/requests/pending/", 200,
        authenticated=True,
    )
    print_result(result)


def test_gamification(ctx: TestContext):
    """Test gamification endpoints."""
    print_section("GAMIFICATION")

    result, _ = make_request(
        ctx, "GET", "/api/v1/gamification/profile/", 200,
        authenticated=True,
    )
    print_result(result)

    result, _ = make_request(
        ctx, "GET", "/api/v1/gamification/achievements/", 200,
        authenticated=True,
    )
    print_result(result)

    result, _ = make_request(
        ctx, "GET", "/api/v1/gamification/heatmap/", 200,
        authenticated=True,
    )
    print_result(result)

    result, _ = make_request(
        ctx, "GET", "/api/v1/gamification/daily-stats/", 200,
        authenticated=True,
    )
    print_result(result)

    result, _ = make_request(
        ctx, "GET", "/api/v1/gamification/streak-details/", 200,
        authenticated=True,
    )
    print_result(result)

    result, _ = make_request(
        ctx, "GET", "/api/v1/gamification/leaderboard/", 200,
        authenticated=True,
    )
    print_result(result)


def test_notifications(ctx: TestContext):
    """Test notification endpoints."""
    print_section("NOTIFICATIONS")

    result, _ = make_request(
        ctx, "GET", "/api/v1/notifications/", 200,
        authenticated=True,
    )
    print_result(result)

    result, _ = make_request(
        ctx, "GET", "/api/v1/notifications/unread_count/", 200,
        authenticated=True,
    )
    print_result(result)

    result, _ = make_request(
        ctx, "GET", "/api/v1/notifications/grouped/", 200,
        authenticated=True,
    )
    print_result(result)

    result, _ = make_request(
        ctx, "POST", "/api/v1/notifications/mark_all_read/", 200,
        authenticated=True,
        allow_statuses=[200, 204],
    )
    print_result(result)


def test_subscriptions(ctx: TestContext):
    """Test subscription endpoints."""
    print_section("SUBSCRIPTIONS")

    # Plans is public (AllowAny)
    result, _ = make_request(
        ctx, "GET", "/api/v1/subscriptions/plans/", 200,
    )
    print_result(result)

    # Current subscription
    result, _ = make_request(
        ctx, "GET", "/api/v1/subscriptions/subscription/current/", 200,
        authenticated=True,
    )
    print_result(result)

    # Invoices
    result, _ = make_request(
        ctx, "GET", "/api/v1/subscriptions/subscription/invoices/", 200,
        authenticated=True,
    )
    print_result(result)

    # Active promotions
    result, _ = make_request(
        ctx, "GET", "/api/v1/subscriptions/promotions/active/", 200,
        authenticated=True,
    )
    print_result(result)


def test_calendar(ctx: TestContext):
    """Test calendar endpoints."""
    print_section("CALENDAR")

    result, _ = make_request(
        ctx, "GET", "/api/v1/calendar/events/", 200,
        authenticated=True,
    )
    print_result(result)

    # Create event
    result, resp = make_request(
        ctx, "POST", "/api/v1/calendar/events/", 201,
        authenticated=True,
        json_data={
            "title": "QA Health Check Event",
            "start_time": "2027-06-01T10:00:00Z",
            "end_time": "2027-06-01T11:00:00Z",
        },
        allow_statuses=[201, 200],
    )
    print_result(result)

    if resp and resp.status_code in (200, 201):
        data = resp.json()
        ctx.event_id = data.get("id")

    # Timeblocks
    result, _ = make_request(
        ctx, "GET", "/api/v1/calendar/timeblocks/", 200,
        authenticated=True,
    )
    print_result(result)

    # Habits
    result, _ = make_request(
        ctx, "GET", "/api/v1/calendar/habits/", 200,
        authenticated=True,
    )
    print_result(result)

    # Google calendar status
    result, _ = make_request(
        ctx, "GET", "/api/v1/calendar/google/status/", 200,
        authenticated=True,
        allow_statuses=[200, 400],
    )
    print_result(result)

    # Shared with me
    result, _ = make_request(
        ctx, "GET", "/api/v1/calendar/shared-with-me/", 200,
        authenticated=True,
    )
    print_result(result)

    # My shares
    result, _ = make_request(
        ctx, "GET", "/api/v1/calendar/my-shares/", 200,
        authenticated=True,
    )
    print_result(result)


def test_chat(ctx: TestContext):
    """Test chat endpoints."""
    print_section("CHAT")

    result, _ = make_request(
        ctx, "GET", "/api/v1/chat/", 200,
        authenticated=True,
    )
    print_result(result)

    result, _ = make_request(
        ctx, "GET", "/api/v1/chat/calls/", 200,
        authenticated=True,
    )
    print_result(result)


def test_circles(ctx: TestContext):
    """Test circles endpoints."""
    print_section("CIRCLES")

    result, _ = make_request(
        ctx, "GET", "/api/v1/circles/circles/", 200,
        authenticated=True,
    )
    print_result(result)


def test_leagues(ctx: TestContext):
    """Test leagues & ranking endpoints."""
    print_section("LEAGUES")

    result, _ = make_request(
        ctx, "GET", "/api/v1/leagues/leagues/", 200,
        authenticated=True,
    )
    print_result(result)

    result, _ = make_request(
        ctx, "GET", "/api/v1/leagues/seasons/", 200,
        authenticated=True,
    )
    print_result(result)

    result, _ = make_request(
        ctx, "GET", "/api/v1/leagues/league-seasons/", 200,
        authenticated=True,
    )
    print_result(result)

    result, _ = make_request(
        ctx, "GET", "/api/v1/leagues/groups/", 200,
        authenticated=True,
    )
    print_result(result)

    result, _ = make_request(
        ctx, "GET", "/api/v1/leagues/leaderboard/", 200,
        authenticated=True,
        allow_statuses=[200, 405],
    )
    print_result(result)


def test_referrals(ctx: TestContext):
    """Test referral endpoints."""
    print_section("REFERRALS")

    result, _ = make_request(
        ctx, "GET", "/api/v1/referrals/code/", 200,
        authenticated=True,
    )
    print_result(result)

    result, _ = make_request(
        ctx, "GET", "/api/v1/referrals/my-referrals/", 200,
        authenticated=True,
    )
    print_result(result)

    result, _ = make_request(
        ctx, "GET", "/api/v1/referrals/rewards/", 200,
        authenticated=True,
    )
    print_result(result)


def test_store(ctx: TestContext):
    """Test store endpoints."""
    print_section("STORE")

    result, _ = make_request(
        ctx, "GET", "/api/v1/store/categories/", 200,
        authenticated=True,
    )
    print_result(result)

    result, _ = make_request(
        ctx, "GET", "/api/v1/store/items/", 200,
        authenticated=True,
    )
    print_result(result)

    result, _ = make_request(
        ctx, "GET", "/api/v1/store/items/featured/", 200,
        authenticated=True,
    )
    print_result(result)

    result, _ = make_request(
        ctx, "GET", "/api/v1/store/inventory/", 200,
        authenticated=True,
    )
    print_result(result)

    result, _ = make_request(
        ctx, "GET", "/api/v1/store/wishlist/", 200,
        authenticated=True,
    )
    print_result(result)

    result, _ = make_request(
        ctx, "GET", "/api/v1/store/gifts/", 200,
        authenticated=True,
    )
    print_result(result)


def test_ai(ctx: TestContext):
    """Test AI coaching endpoints."""
    print_section("AI")

    result, _ = make_request(
        ctx, "GET", "/api/v1/ai/conversations/", 200,
        authenticated=True,
    )
    print_result(result)

    result, _ = make_request(
        ctx, "GET", "/api/v1/ai/templates/", 200,
        authenticated=True,
    )
    print_result(result)


def test_buddies(ctx: TestContext):
    """Test buddies endpoints."""
    print_section("BUDDIES")

    result, _ = make_request(
        ctx, "GET", "/api/v1/buddies/", 200,
        authenticated=True,
    )
    print_result(result)

    result, _ = make_request(
        ctx, "GET", "/api/v1/buddies/contracts/", 200,
        authenticated=True,
    )
    print_result(result)


def test_search(ctx: TestContext):
    """Test search endpoint."""
    print_section("SEARCH")

    result, _ = make_request(
        ctx, "GET", "/api/v1/search/", 200,
        authenticated=True,
        params={"q": "test"},
        allow_statuses=[200, 503],  # 503 if ES is disabled
    )
    print_result(result)


def test_updates(ctx: TestContext):
    """Test OTA updates endpoint."""
    print_section("UPDATES")

    result, _ = make_request(
        ctx, "POST", "/api/v1/updates/check/", 200,
        authenticated=True,
        json_data={
            "app_version": "1.0.0",
            "platform": "android",
        },
        allow_statuses=[200, 204, 400],
    )
    print_result(result)


# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------

def cleanup(ctx: TestContext):
    """Delete test resources created during the run."""
    print_section("CLEANUP")
    cleaned = 0

    # Delete post
    if ctx.post_id:
        result, _ = make_request(
            ctx, "DELETE", f"/api/v1/social/posts/{ctx.post_id}/", 204,
            authenticated=True,
            allow_statuses=[204, 200, 404],
        )
        print_result(result)
        cleaned += 1

    # Delete event
    if ctx.event_id:
        result, _ = make_request(
            ctx, "DELETE", f"/api/v1/calendar/events/{ctx.event_id}/", 204,
            authenticated=True,
            allow_statuses=[204, 200, 404],
        )
        print_result(result)
        cleaned += 1

    # Delete dream (cascades to milestones/goals/tasks)
    if ctx.dream_id:
        result, _ = make_request(
            ctx, "DELETE", f"/api/v1/dreams/dreams/{ctx.dream_id}/", 204,
            authenticated=True,
            allow_statuses=[204, 200, 404],
        )
        print_result(result)
        cleaned += 1

    # Delete test user account
    if ctx.access_token:
        result, _ = make_request(
            ctx, "POST", "/api/v1/users/delete-account/", 204,
            authenticated=True,
            json_data={"password": ctx.test_user_password},
            allow_statuses=[204, 200, 400],
        )
        print_result(result)
        cleaned += 1

    if cleaned == 0:
        print(f"  {Color.DIM}(nothing to clean up){Color.RESET}")


# ---------------------------------------------------------------------------
# Logout test (run after cleanup to invalidate tokens)
# ---------------------------------------------------------------------------

def test_logout(ctx: TestContext):
    """Test logout endpoint (run last, after cleanup)."""
    if ctx.access_token:
        result, _ = make_request(
            ctx, "POST", "/api/v1/auth/logout/", 200,
            authenticated=True,
            json_data={"refresh": ctx.refresh_token} if ctx.refresh_token else {},
            allow_statuses=[200, 204],
        )
        # Print under AUTH section retroactively
        print(f"\n{Color.CYAN}{Color.BOLD}[AUTH - LOGOUT]{Color.RESET}")
        print_result(result)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Stepora API Health Check / Smoke Test",
    )
    parser.add_argument(
        "--base-url",
        default=os.environ.get("API_BASE", "http://localhost:8000"),
        help="Base URL of the API (default: $API_BASE or http://localhost:8000)",
    )
    parser.add_argument(
        "--no-color",
        action="store_true",
        help="Disable colored output",
    )
    parser.add_argument(
        "--no-cleanup",
        action="store_true",
        help="Skip cleanup of test data (for debugging)",
    )
    args = parser.parse_args()

    if args.no_color or not sys.stdout.isatty():
        Color.disable()

    base_url = args.base_url.rstrip("/")

    print(f"\n{Color.BOLD}{'=' * 60}")
    print(f"  Stepora API Health Check")
    print(f"{'=' * 60}{Color.RESET}")
    print(f"  Target: {Color.CYAN}{base_url}{Color.RESET}")
    print(f"  Time:   {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{Color.BOLD}{'=' * 60}{Color.RESET}")

    ctx = TestContext(base_url=base_url)

    # Run all test categories in order
    test_health(ctx)
    test_auth(ctx)

    # Only proceed with authenticated tests if we have a token
    if ctx.access_token:
        test_users(ctx)
        test_dreams(ctx)
        test_plans(ctx)
        test_social(ctx)
        test_friends(ctx)
        test_gamification(ctx)
        test_notifications(ctx)
        test_subscriptions(ctx)
        test_calendar(ctx)
        test_chat(ctx)
        test_circles(ctx)
        test_leagues(ctx)
        test_referrals(ctx)
        test_store(ctx)
        test_ai(ctx)
        test_buddies(ctx)
        test_search(ctx)
        test_updates(ctx)

        # Cleanup before logout
        if not args.no_cleanup:
            cleanup(ctx)

        # Logout last
        test_logout(ctx)
    else:
        print(f"\n  {Color.YELLOW}WARNING: No access token obtained. "
              f"Skipping authenticated tests.{Color.RESET}")

    # --------------- Summary ---------------
    total = len(ctx.results)
    passed = sum(1 for r in ctx.results if r.passed)
    failed = total - passed
    score = (passed / total * 100) if total > 0 else 0

    print(f"\n{Color.BOLD}{'=' * 60}")
    print(f"  RESULTS")
    print(f"{'=' * 60}{Color.RESET}")
    print(f"  Total:   {total} endpoints tested")
    print(f"  Passed:  {Color.GREEN}{passed}{Color.RESET}")
    print(f"  Failed:  {Color.RED}{failed}{Color.RESET}")
    print(f"  Score:   {Color.BOLD}{score:.1f}%{Color.RESET}")
    print(f"{Color.BOLD}{'=' * 60}{Color.RESET}\n")

    if failed > 0:
        print(f"{Color.RED}{Color.BOLD}  FAILED ENDPOINTS:{Color.RESET}")
        for r in ctx.results:
            if not r.passed:
                if r.error:
                    detail = r.error
                else:
                    detail = f"expected {r.expected_status}, got {r.actual_status}"
                print(f"  {Color.RED}  - {r.method} {r.path} ({detail}){Color.RESET}")
        print()

    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
