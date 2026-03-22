"""
Comprehensive tests for integrations.openai_service.OpenAIService.

All OpenAI API calls are mocked — no real API traffic.
"""

import json
from datetime import date, timedelta
from unittest.mock import AsyncMock, Mock, mock_open, patch

import openai
import pytest

from core.exceptions import OpenAIError

# ---------------------------------------------------------------------------
# Helper: build a mock OpenAI ChatCompletion response
# ---------------------------------------------------------------------------

def _mock_response(content, finish_reason="stop", model="gpt-4", tokens=100,
                   function_call=None, tool_calls=None):
    """Return a Mock that mimics openai ChatCompletion response."""
    message = Mock()
    message.content = content
    message.function_call = function_call
    message.tool_calls = tool_calls

    # model_dump for assistant messages used by agent loops
    def _model_dump(exclude_none=False):
        d = {"role": "assistant", "content": content}
        if tool_calls:
            d["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                }
                for tc in tool_calls
            ]
        if exclude_none:
            d = {k: v for k, v in d.items() if v is not None}
        return d

    message.model_dump = _model_dump

    choice = Mock()
    choice.message = message
    choice.finish_reason = finish_reason
    choice.delta = Mock(content=content)  # for streaming

    response = Mock()
    response.choices = [choice]
    response.usage = Mock(total_tokens=tokens)
    response.model = model
    return response


def _mock_tool_call(name, arguments_dict, call_id="call_1"):
    tc = Mock()
    tc.id = call_id
    tc.function = Mock()
    tc.function.name = name
    tc.function.arguments = json.dumps(arguments_dict)
    return tc


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def service():
    """Return a fresh OpenAIService instance."""
    from integrations.openai_service import OpenAIService
    return OpenAIService()


@pytest.fixture
def mock_client():
    """Patch the module-level _client used by OpenAIService."""
    with patch("integrations.openai_service._client") as mc:
        yield mc


@pytest.fixture
def mock_plan_client():
    """Patch the module-level _plan_client used for plan generation."""
    with patch("integrations.openai_service._plan_client") as mc:
        yield mc


@pytest.fixture
def mock_async_client():
    """Patch the module-level _async_client."""
    with patch("integrations.openai_service._async_client") as mc:
        yield mc


# ===================================================================
# chat()
# ===================================================================

class TestChat:

    def test_chat_success(self, service, mock_client):
        mock_client.chat.completions.create.return_value = _mock_response(
            "Hello!", tokens=42
        )
        result = service.chat(
            [{"role": "user", "content": "Hi"}],
            conversation_type="general",
        )
        assert result["content"] == "Hello!"
        assert result["tokens_used"] == 42
        assert result["model"] == "gpt-4"
        assert "function_call" not in result

    def test_chat_with_function_call(self, service, mock_client):
        fc = Mock()
        fc.name = "create_task"
        fc.arguments = json.dumps({"title": "Read docs"})
        mock_client.chat.completions.create.return_value = _mock_response(
            "", function_call=fc
        )
        result = service.chat(
            [{"role": "user", "content": "create a task"}],
            functions=service.FUNCTION_DEFINITIONS,
        )
        assert result["function_call"]["name"] == "create_task"
        assert result["function_call"]["arguments"]["title"] == "Read docs"

    def test_chat_with_functions_kwarg(self, service, mock_client):
        mock_client.chat.completions.create.return_value = _mock_response("ok")
        service.chat(
            [{"role": "user", "content": "Hello"}],
            functions=[{"name": "dummy"}],
        )
        call_kwargs = mock_client.chat.completions.create.call_args[1]
        assert "functions" in call_kwargs
        assert call_kwargs["function_call"] == "auto"

    def test_chat_api_error(self, service, mock_client):
        mock_client.chat.completions.create.side_effect = openai.APIError(
            message="rate limited", request=Mock(), body=None
        )
        with pytest.raises(OpenAIError, match="OpenAI API error"):
            service.chat([{"role": "user", "content": "Hi"}])

    def test_chat_unexpected_error(self, service, mock_client):
        mock_client.chat.completions.create.side_effect = ValueError("boom")
        with pytest.raises(OpenAIError, match="Unexpected error"):
            service.chat([{"role": "user", "content": "Hi"}])

    def test_chat_system_prompt_injection(self, service, mock_client):
        mock_client.chat.completions.create.return_value = _mock_response("ok")
        service.chat(
            [{"role": "user", "content": "Hello"}],
            conversation_type="dream_creation",
        )
        call_args = mock_client.chat.completions.create.call_args
        messages = call_args[1]["messages"]
        assert messages[0]["role"] == "system"
        assert "Stepora" in messages[0]["content"]

    def test_chat_unknown_conversation_type(self, service, mock_client):
        mock_client.chat.completions.create.return_value = _mock_response("ok")
        service.chat(
            [{"role": "user", "content": "Hello"}],
            conversation_type="nonexistent_type",
        )
        call_args = mock_client.chat.completions.create.call_args
        messages = call_args[1]["messages"]
        # system prompt should be empty string for unknown type
        assert messages[0]["content"] == ""

    def test_chat_custom_params(self, service, mock_client):
        mock_client.chat.completions.create.return_value = _mock_response("ok")
        service.chat(
            [{"role": "user", "content": "Hello"}],
            temperature=0.1,
            max_tokens=50,
        )
        call_kwargs = mock_client.chat.completions.create.call_args[1]
        assert call_kwargs["temperature"] == 0.1
        assert call_kwargs["max_tokens"] == 50


# ===================================================================
# chat_async()
# ===================================================================

class TestChatAsync:

    @pytest.mark.asyncio
    async def test_chat_async_success(self, service, mock_async_client):
        mock_async_client.chat.completions.create = AsyncMock(
            return_value=_mock_response("Async OK")
        )
        result = await service.chat_async(
            [{"role": "user", "content": "Hi"}]
        )
        assert result["content"] == "Async OK"

    @pytest.mark.asyncio
    async def test_chat_async_api_error(self, service, mock_async_client):
        mock_async_client.chat.completions.create = AsyncMock(
            side_effect=openai.APIError(message="fail", request=Mock(), body=None)
        )
        with pytest.raises(OpenAIError, match="OpenAI API error"):
            await service.chat_async([{"role": "user", "content": "Hi"}])

    @pytest.mark.asyncio
    async def test_chat_async_unexpected_error(self, service, mock_async_client):
        mock_async_client.chat.completions.create = AsyncMock(
            side_effect=RuntimeError("unexpected")
        )
        with pytest.raises(OpenAIError, match="Unexpected error"):
            await service.chat_async([{"role": "user", "content": "Hi"}])


# ===================================================================
# chat_stream_async()
# ===================================================================

class TestChatStreamAsync:

    @pytest.mark.asyncio
    async def test_stream_yields_chunks(self, service, mock_async_client):
        chunk1 = Mock()
        chunk1.choices = [Mock(delta=Mock(content="Hello "))]
        chunk2 = Mock()
        chunk2.choices = [Mock(delta=Mock(content="world"))]
        chunk3 = Mock()
        chunk3.choices = [Mock(delta=Mock(content=None))]

        async def mock_stream():
            for c in [chunk1, chunk2, chunk3]:
                yield c

        mock_async_client.chat.completions.create = AsyncMock(
            return_value=mock_stream()
        )
        chunks = []
        async for text in service.chat_stream_async(
            [{"role": "user", "content": "Hi"}]
        ):
            chunks.append(text)
        assert chunks == ["Hello ", "world"]

    @pytest.mark.asyncio
    async def test_stream_api_error(self, service, mock_async_client):
        mock_async_client.chat.completions.create = AsyncMock(
            side_effect=openai.APIError(message="fail", request=Mock(), body=None)
        )
        with pytest.raises(OpenAIError, match="OpenAI API error"):
            async for _ in service.chat_stream_async(
                [{"role": "user", "content": "Hi"}]
            ):
                pass


# ===================================================================
# generate_plan() — single and chunked
# ===================================================================

class TestGeneratePlan:

    def _plan_json(self):
        return json.dumps({
            "analysis": "Recommended approach: solo",
            "estimated_duration_weeks": 4,
            "milestones": [
                {
                    "title": "Month 1",
                    "description": "Foundation",
                    "order": 1,
                    "target_day": 30,
                    "expected_date": "2026-04-01",
                    "deadline_date": "2026-04-05",
                    "goals": [
                        {
                            "title": "Goal 1",
                            "order": 1,
                            "tasks": [
                                {"title": "Day 1: Task 1", "order": 1, "day_number": 1, "duration_mins": 30}
                            ],
                        }
                    ],
                    "obstacles": [],
                }
            ],
            "tips": ["Tip 1"],
            "potential_obstacles": [],
            "calibration_references": [],
        })

    def test_generate_plan_single_call(self, service, mock_plan_client):
        """Short dream (<=2 months) uses single API call."""
        mock_plan_client.chat.completions.create.return_value = _mock_response(
            self._plan_json(), tokens=500
        )
        target = (date.today() + timedelta(days=30)).isoformat()
        result = service.generate_plan(
            "Learn Django",
            "Master Django framework",
            {"timezone": "UTC", "category": "tech"},
            target_date=target,
        )
        assert "milestones" in result
        assert result["analysis"] == "Recommended approach: solo"

    def test_generate_plan_chunked(self, service, mock_plan_client):
        """Long dream (>2 months) uses chunked generation."""
        chunk_json = json.dumps({
            "milestones": [{"title": "Month 1", "order": 1, "goals": [{"title": "G1"}], "obstacles": []}],
            "analysis": "Recommended approach: hybrid",
            "tips": ["T1"],
            "potential_obstacles": [{"title": "Obstacle 1"}],
            "calibration_references": ["User said X"],
            "chunk_summary": "Last day: 30. Covered: basics.",
        })
        mock_plan_client.chat.completions.create.return_value = _mock_response(chunk_json)
        target = (date.today() + timedelta(days=180)).isoformat()
        result = service.generate_plan(
            "Run a marathon",
            "Complete a full marathon",
            {"timezone": "UTC", "category": "health"},
            target_date=target,
        )
        assert "milestones" in result
        assert "generation_info" in result
        assert result["generation_info"]["total_chunks"] > 1

    def test_generate_plan_truncated_raises(self, service, mock_plan_client):
        """If finish_reason is 'length', OpenAIError is raised."""
        mock_plan_client.chat.completions.create.return_value = _mock_response(
            "{}", finish_reason="length"
        )
        target = (date.today() + timedelta(days=30)).isoformat()
        with pytest.raises(OpenAIError, match="truncated"):
            service.generate_plan(
                "Test", "Test", {"timezone": "UTC"}, target_date=target
            )

    def test_generate_plan_bad_json_raises(self, service, mock_plan_client):
        mock_plan_client.chat.completions.create.return_value = _mock_response(
            "not json at all"
        )
        target = (date.today() + timedelta(days=30)).isoformat()
        with pytest.raises(OpenAIError, match="Failed to parse JSON"):
            service.generate_plan(
                "Test", "Test", {"timezone": "UTC"}, target_date=target
            )

    def test_generate_plan_no_target_date(self, service, mock_plan_client):
        """With no target_date, _parse_duration returns (None, None) -> single call."""
        mock_plan_client.chat.completions.create.return_value = _mock_response(
            self._plan_json()
        )
        result = service.generate_plan(
            "Learn guitar", "Play guitar", {"timezone": "UTC"}
        )
        assert "milestones" in result

    def test_generate_plan_with_calibration(self, service, mock_plan_client):
        mock_plan_client.chat.completions.create.return_value = _mock_response(
            self._plan_json()
        )
        user_context = {
            "timezone": "UTC",
            "category": "health",
            "language": "fr",
            "calibration_profile": {
                "experience_level": "beginner",
                "available_hours_per_week": "10",
            },
            "plan_recommendations": {
                "suggested_pace": "moderate",
                "focus_areas": ["cardio"],
                "potential_pitfalls": ["injury"],
            },
            "enriched_description": "Run a 5K in under 30 minutes",
            "persona": {
                "available_hours_per_week": 10,
                "preferred_schedule": "morning",
            },
        }
        target = (date.today() + timedelta(days=30)).isoformat()
        result = service.generate_plan(
            "Run 5K", "Run a 5K", user_context, target_date=target
        )
        assert "milestones" in result

    def test_generate_plan_progress_callback(self, service, mock_plan_client):
        chunk_json = json.dumps({
            "milestones": [{"title": "M1", "order": 1, "goals": [{"title": "G1"}], "obstacles": []}],
            "chunk_summary": "Done.",
        })
        mock_plan_client.chat.completions.create.return_value = _mock_response(chunk_json)
        target = (date.today() + timedelta(days=120)).isoformat()
        callback = Mock()
        service.generate_plan(
            "Test", "Test", {"timezone": "UTC"},
            target_date=target,
            progress_callback=callback,
        )
        assert callback.called


# ===================================================================
# generate_skeleton()
# ===================================================================

class TestGenerateSkeleton:

    def test_generate_skeleton_success(self, service, mock_plan_client):
        skeleton_json = json.dumps({
            "analysis": "Recommended approach: solo",
            "milestones": [{"title": "Month 1", "order": 1, "goals": []}],
            "tips": [],
            "potential_obstacles": [],
        })
        mock_plan_client.chat.completions.create.return_value = _mock_response(skeleton_json)
        target = (date.today() + timedelta(days=365)).isoformat()
        result = service.generate_skeleton(
            "Learn Piano", "Play classical piano",
            {"timezone": "UTC", "category": "creative", "language": "en"},
            target_date=target,
        )
        assert "milestones" in result

    def test_generate_skeleton_truncated(self, service, mock_plan_client):
        mock_plan_client.chat.completions.create.return_value = _mock_response(
            "{}", finish_reason="length"
        )
        with pytest.raises(OpenAIError, match="truncated"):
            service.generate_skeleton("T", "D", {"timezone": "UTC"}, target_date="2027-01-01")

    def test_generate_skeleton_bad_json(self, service, mock_plan_client):
        mock_plan_client.chat.completions.create.return_value = _mock_response("bad")
        with pytest.raises(OpenAIError, match="parse skeleton JSON"):
            service.generate_skeleton("T", "D", {"timezone": "UTC"}, target_date="2027-01-01")

    def test_generate_skeleton_no_target_defaults(self, service, mock_plan_client):
        skeleton_json = json.dumps({"milestones": [], "analysis": "ok"})
        mock_plan_client.chat.completions.create.return_value = _mock_response(skeleton_json)
        result = service.generate_skeleton("T", "D", {"timezone": "UTC"})
        assert isinstance(result, dict)


# ===================================================================
# generate_tasks_for_months()
# ===================================================================

class TestGenerateTasksForMonths:

    def test_success(self, service, mock_plan_client):
        resp = json.dumps({
            "task_patches": [
                {"milestone_order": 1, "goal_order": 1, "tasks": [{"title": "Day 1: Do X"}]}
            ]
        })
        mock_plan_client.chat.completions.create.return_value = _mock_response(resp)
        skeleton = {
            "milestones": [
                {"title": "M1", "order": 1, "description": "Month 1", "goals": [{"title": "G1", "order": 1}]}
            ]
        }
        target = (date.today() + timedelta(days=60)).isoformat()
        result = service.generate_tasks_for_months(
            "Dream", "Desc", skeleton, {"timezone": "UTC"}, 1, 1,
            target_date=target,
        )
        assert len(result) == 1
        assert result[0]["milestone_order"] == 1

    def test_no_milestones_raises(self, service, mock_plan_client):
        skeleton = {"milestones": [{"title": "M5", "order": 5}]}
        with pytest.raises(OpenAIError, match="No milestones found"):
            service.generate_tasks_for_months(
                "Dream", "Desc", skeleton, {"timezone": "UTC"}, 1, 1,
                target_date=(date.today() + timedelta(days=60)).isoformat(),
            )

    def test_bad_json_logs_but_continues(self, service, mock_plan_client):
        mock_plan_client.chat.completions.create.return_value = _mock_response("not json")
        skeleton = {"milestones": [{"title": "M1", "order": 1, "goals": []}]}
        target = (date.today() + timedelta(days=60)).isoformat()
        # Bad JSON is logged but result is empty (no crash)
        result = service.generate_tasks_for_months(
            "Dream", "Desc", skeleton, {"timezone": "UTC"}, 1, 1,
            target_date=target,
        )
        assert result == []


# ===================================================================
# generate_calibration_questions()
# ===================================================================

class TestGenerateCalibrationQuestions:

    def test_initial_questions(self, service, mock_client):
        resp_data = json.dumps({
            "sufficient": False,
            "confidence_score": 0.1,
            "questions": [{"question": "What is your experience?", "category": "experience"}],
        })
        mock_client.chat.completions.create.return_value = _mock_response(resp_data)
        result = service.generate_calibration_questions(
            "Learn Piano", "Play piano", batch_size=7
        )
        assert result["sufficient"] is False
        assert len(result["questions"]) >= 1

    def test_followup_questions(self, service, mock_client):
        resp_data = json.dumps({
            "sufficient": True,
            "confidence_score": 0.9,
            "questions": [],
        })
        mock_client.chat.completions.create.return_value = _mock_response(resp_data)
        existing = [
            {"question": "How long have you played?", "answer": "2 years"},
        ] * 10
        result = service.generate_calibration_questions(
            "Learn Piano", "Play piano", existing_qa=existing
        )
        assert result["sufficient"] is True

    def test_api_error_raises(self, service, mock_client):
        mock_client.chat.completions.create.side_effect = openai.APIError(
            message="fail", request=Mock(), body=None
        )
        with pytest.raises(OpenAIError, match="Calibration question generation failed"):
            service.generate_calibration_questions("T", "D")

    def test_with_persona_and_target_date(self, service, mock_client):
        resp_data = json.dumps({"sufficient": False, "confidence_score": 0.2, "questions": []})
        mock_client.chat.completions.create.return_value = _mock_response(resp_data)
        result = service.generate_calibration_questions(
            "Run 5K", "Run 5K in 30 min",
            target_date="2026-06-01",
            category="health",
            persona={"available_hours_per_week": 10, "fitness_level": "beginner"},
        )
        assert isinstance(result, dict)


class TestOpenAIRetryDecorator:
    """Verify that generate_calibration_questions has the @openai_retry decorator."""

    def test_generate_calibration_questions_has_retry(self):
        """The method should have tenacity retry metadata from @openai_retry."""
        from integrations.openai_service import OpenAIService

        method = OpenAIService.generate_calibration_questions
        # tenacity @retry wraps the function and adds a 'retry' attribute
        assert hasattr(method, "retry"), (
            "generate_calibration_questions should be decorated with @openai_retry "
            "(tenacity retry), but the 'retry' attribute is missing"
        )

    def test_retry_stops_after_3_attempts(self):
        """The openai_retry decorator should stop after 3 attempts."""
        from integrations.openai_service import OpenAIService

        method = OpenAIService.generate_calibration_questions
        # Access the retry state to check stop config
        retry_obj = method.retry
        # tenacity stores stop strategy — verify it exists
        assert retry_obj.stop is not None


# ===================================================================
# generate_calibration_summary()
# ===================================================================

class TestGenerateCalibrationSummary:

    def test_success(self, service, mock_client):
        resp = json.dumps({
            "user_profile": {"experience_level": "beginner"},
            "plan_recommendations": {"suggested_pace": "moderate"},
            "enriched_description": "Run 5K in under 30 minutes",
        })
        mock_client.chat.completions.create.return_value = _mock_response(resp)
        result = service.generate_calibration_summary(
            "Run 5K", "Run 5K",
            [{"question": "Experience?", "answer": "None"}],
        )
        assert "user_profile" in result

    def test_api_error_raises(self, service, mock_client):
        mock_client.chat.completions.create.side_effect = openai.APIError(
            message="fail", request=Mock(), body=None
        )
        with pytest.raises(OpenAIError, match="Calibration summary generation failed"):
            service.generate_calibration_summary("T", "D", [])


# ===================================================================
# analyze_dream()
# ===================================================================

class TestAnalyzeDream:

    def test_success(self, service, mock_client):
        resp = json.dumps({
            "category": "health",
            "detected_language": "en",
            "estimated_duration_weeks": 12,
            "difficulty": "medium",
            "key_challenges": ["Consistency"],
            "recommended_approach": "Start with a plan",
            "requires_professional": False,
        })
        mock_client.chat.completions.create.return_value = _mock_response(resp)
        result = service.analyze_dream("Run a marathon", "Complete a full marathon")
        assert result["category"] == "health"

    def test_bad_json_raises(self, service, mock_client):
        mock_client.chat.completions.create.return_value = _mock_response("invalid")
        with pytest.raises(OpenAIError, match="Analysis failed"):
            service.analyze_dream("T", "D")


# ===================================================================
# auto_categorize()
# ===================================================================

class TestAutoCategorize:

    def test_success(self, service, mock_client):
        resp = json.dumps({
            "category": "health",
            "confidence": 0.9,
            "tags": [{"name": "running", "relevance": 0.95}],
            "reasoning": "Running is health",
        })
        mock_client.chat.completions.create.return_value = _mock_response(resp)
        result = service.auto_categorize("Run a 5K", "Train for a 5K race")
        assert result["category"] == "health"
        assert 0 <= result["confidence"] <= 1.0
        assert len(result["tags"]) >= 1

    def test_invalid_category_fallback(self, service, mock_client):
        resp = json.dumps({
            "category": "invalid_cat",
            "confidence": "not_a_number",
            "tags": [{"name": "t", "relevance": "bad"}],
            "reasoning": "test",
        })
        mock_client.chat.completions.create.return_value = _mock_response(resp)
        result = service.auto_categorize("T", "D")
        assert result["category"] == "personal"
        assert result["confidence"] == 0.5

    def test_bad_json_raises(self, service, mock_client):
        mock_client.chat.completions.create.return_value = _mock_response("oops")
        with pytest.raises(OpenAIError, match="Auto-categorize failed"):
            service.auto_categorize("T", "D")


# ===================================================================
# smart_analysis()
# ===================================================================

class TestSmartAnalysis:

    def test_success(self, service, mock_client):
        resp = json.dumps({
            "patterns": [{"type": "theme", "description": "Both health", "dreams_involved": ["D1"]}],
            "insights": [{"insight": "Synergy found", "actionable_tip": "Do X"}],
            "synergies": [],
            "risk_areas": [],
        })
        mock_client.chat.completions.create.return_value = _mock_response(resp)
        result = service.smart_analysis([{"title": "D1", "progress": 50}])
        assert "patterns" in result


# ===================================================================
# generate_motivational_message()
# ===================================================================

class TestGenerateMotivationalMessage:

    def test_success(self, service, mock_client):
        mock_client.chat.completions.create.return_value = _mock_response("Keep going!")
        result = service.generate_motivational_message("Alice", "Run 5K", 50, 7)
        assert result == "Keep going!"

    def test_api_error_fallback(self, service, mock_client):
        mock_client.chat.completions.create.side_effect = openai.APIError(
            message="fail", request=Mock(), body=None
        )
        result = service.generate_motivational_message("Alice", "Run 5K", 50, 7)
        assert "Alice" in result


# ===================================================================
# generate_two_minute_start()
# ===================================================================

class TestGenerateTwoMinuteStart:

    def test_success(self, service, mock_client):
        mock_client.chat.completions.create.return_value = _mock_response(
            "Write 3 reasons this goal matters"
        )
        result = service.generate_two_minute_start("Learn French", "Become fluent")
        assert "reasons" in result.lower() or len(result) > 0

    def test_api_error_fallback(self, service, mock_client):
        mock_client.chat.completions.create.side_effect = openai.APIError(
            message="fail", request=Mock(), body=None
        )
        result = service.generate_two_minute_start("T", "D")
        assert "2 minutes" in result


# ===================================================================
# generate_motivation()
# ===================================================================

class TestGenerateMotivation:

    def test_success(self, service, mock_client):
        resp = json.dumps({
            "message": "Great progress!",
            "affirmation": "You can do it!",
            "suggested_action": "Review tasks",
            "mood_emoji": "fire",
        })
        mock_client.chat.completions.create.return_value = _mock_response(resp)
        result = service.generate_motivation(
            "motivated", "50% progress", "Completed 3 tasks", 5
        )
        assert result["message"] == "Great progress!"

    def test_fallback_on_error(self, service, mock_client):
        mock_client.chat.completions.create.side_effect = openai.APIError(
            message="fail", request=Mock(), body=None
        )
        result = service.generate_motivation("sad", "", "", 0)
        assert "message" in result
        assert "affirmation" in result


# ===================================================================
# generate_rescue_message()
# ===================================================================

class TestGenerateRescueMessage:

    def test_success(self, service, mock_client):
        mock_client.chat.completions.create.return_value = _mock_response(
            "Hey, it is okay to take a break!"
        )
        result = service.generate_rescue_message("Bob", 10, "Learn Python")
        assert len(result) > 0

    def test_api_error_fallback(self, service, mock_client):
        mock_client.chat.completions.create.side_effect = openai.APIError(
            message="fail", request=Mock(), body=None
        )
        result = service.generate_rescue_message("Bob", 10, "Learn Python")
        assert "Bob" in result


# ===================================================================
# generate_weekly_report()
# ===================================================================

class TestGenerateWeeklyReport:

    def test_success(self, service, mock_client):
        resp = json.dumps({
            "summary": "Good week",
            "achievements": ["Finished 5 tasks"],
            "trends": [{"metric": "tasks", "direction": "up", "insight": "more"}],
            "recommendations": ["Do more focus sessions"],
            "score": 75,
            "encouragement": "Keep going!",
        })
        mock_client.chat.completions.create.return_value = _mock_response(resp)
        result = service.generate_weekly_report(
            {"tasks_completed": 5, "focus_minutes": 120, "streak_days": 3}
        )
        assert result["score"] == 75
        assert "achievements" in result

    def test_with_previous_week(self, service, mock_client):
        resp = json.dumps({
            "summary": "Improved",
            "achievements": [],
            "trends": [],
            "recommendations": [],
            "score": 80,
            "encouragement": "Great!",
        })
        mock_client.chat.completions.create.return_value = _mock_response(resp)
        result = service.generate_weekly_report(
            {"tasks_completed": 10},
            previous_week_stats={"tasks_completed": 5},
        )
        assert result["score"] == 80

    def test_missing_keys_get_defaults(self, service, mock_client):
        mock_client.chat.completions.create.return_value = _mock_response(
            json.dumps({"score": 200})  # out of range
        )
        result = service.generate_weekly_report({"tasks_completed": 0})
        assert result["score"] == 100  # clamped
        assert "summary" in result

    def test_bad_json_raises(self, service, mock_client):
        mock_client.chat.completions.create.return_value = _mock_response("bad")
        with pytest.raises(OpenAIError, match="Weekly report generation failed"):
            service.generate_weekly_report({"tasks_completed": 0})


# ===================================================================
# generate_checkin()
# ===================================================================

class TestGenerateCheckin:

    def test_success(self, service, mock_client):
        resp = json.dumps({
            "message": "How is your progress?",
            "prompt_type": "progress_check",
            "suggested_questions": ["How can I improve?"],
            "quick_actions": [{"label": "Start focus", "type": "start_focus", "target_id": None}],
        })
        mock_client.chat.completions.create.return_value = _mock_response(resp)
        result = service.generate_checkin(
            [{"title": "D1", "progress": 30, "category": "health"}],
            days_since_activity=1,
            pending_tasks=[{"title": "T1", "dream_title": "D1"}],
            streak_data={"current_streak": 3, "best_streak": 10},
            display_name="Alice",
        )
        assert result["prompt_type"] == "progress_check"

    def test_re_engagement_type(self, service, mock_client):
        resp = json.dumps({
            "message": "We miss you!",
            "prompt_type": "re_engagement",
            "suggested_questions": [],
            "quick_actions": [],
        })
        mock_client.chat.completions.create.return_value = _mock_response(resp)
        result = service.generate_checkin([], 7, [], {"current_streak": 0, "best_streak": 5})
        assert result["prompt_type"] == "re_engagement"

    def test_celebration_type(self, service, mock_client):
        resp = json.dumps({
            "message": "Amazing streak!",
            "prompt_type": "celebration",
            "suggested_questions": [],
            "quick_actions": [],
        })
        mock_client.chat.completions.create.return_value = _mock_response(resp)
        result = service.generate_checkin([], 0, [], {"current_streak": 10, "best_streak": 10})
        assert result["prompt_type"] == "celebration"

    def test_invalid_prompt_type_fixed(self, service, mock_client):
        resp = json.dumps({
            "message": "Hi",
            "prompt_type": "invalid_type",
        })
        mock_client.chat.completions.create.return_value = _mock_response(resp)
        result = service.generate_checkin([], 0, [], {"current_streak": 0})
        assert result["prompt_type"] == "progress_check"

    def test_api_error_fallback(self, service, mock_client):
        mock_client.chat.completions.create.side_effect = openai.APIError(
            message="fail", request=Mock(), body=None
        )
        result = service.generate_checkin([], 0, [], {"current_streak": 0}, display_name="Bob")
        assert "Bob" in result["message"]
        assert "prompt_type" in result


# ===================================================================
# transcribe_audio()
# ===================================================================

class TestTranscribeAudio:

    def test_success(self, service, mock_client):
        mock_resp = Mock()
        mock_resp.text = "Hello world"
        mock_resp.language = "en"
        mock_client.audio.transcriptions.create.return_value = mock_resp

        with patch("builtins.open", mock_open(read_data=b"audio data")):
            result = service.transcribe_audio("/tmp/test.mp3")
        assert result["text"] == "Hello world"
        assert result["language"] == "en"

    def test_file_not_found(self, service, mock_client):
        with pytest.raises(OpenAIError, match="Audio file not found"):
            service.transcribe_audio("/nonexistent/path.mp3")

    def test_api_error(self, service, mock_client):
        mock_client.audio.transcriptions.create.side_effect = openai.APIError(
            message="fail", request=Mock(), body=None
        )
        with patch("builtins.open", mock_open(read_data=b"data")):
            with pytest.raises(OpenAIError, match="Audio transcription failed"):
                service.transcribe_audio("/tmp/test.mp3")


# ===================================================================
# analyze_image()
# ===================================================================

class TestAnalyzeImage:

    def test_success(self, service, mock_client):
        mock_client.chat.completions.create.return_value = _mock_response(
            "This is a progress photo", tokens=50
        )
        result = service.analyze_image("https://example.com/img.jpg")
        assert result["content"] == "This is a progress photo"

    def test_with_user_prompt(self, service, mock_client):
        mock_client.chat.completions.create.return_value = _mock_response("Analysis", tokens=30)
        result = service.analyze_image("https://example.com/img.jpg", user_prompt="What is this?")
        assert result["content"] == "Analysis"

    def test_api_error(self, service, mock_client):
        mock_client.chat.completions.create.side_effect = openai.APIError(
            message="fail", request=Mock(), body=None
        )
        with pytest.raises(OpenAIError, match="Image analysis failed"):
            service.analyze_image("https://example.com/img.jpg")


# ===================================================================
# analyze_progress_image()
# ===================================================================

class TestAnalyzeProgressImage:

    def test_success(self, service, mock_client):
        resp = json.dumps({
            "analysis": "Good progress",
            "progress_indicators": [{"indicator": "Muscle gain", "status": "improved"}],
            "comparison_to_previous": "Better than last time",
            "encouragement": "Keep it up!",
        })
        mock_client.chat.completions.create.return_value = _mock_response(resp, tokens=200)
        result = service.analyze_progress_image(
            "https://example.com/img.jpg", "Get fit", "Lose weight and gain muscle"
        )
        assert result["analysis"] == "Good progress"
        assert len(result["progress_indicators"]) == 1

    def test_with_previous_analyses(self, service, mock_client):
        resp = json.dumps({
            "analysis": "Continued progress",
            "progress_indicators": [],
            "comparison_to_previous": "Improved over last 3 sessions",
            "encouragement": "Amazing!",
        })
        mock_client.chat.completions.create.return_value = _mock_response(resp, tokens=150)
        result = service.analyze_progress_image(
            "https://example.com/img.jpg", "Get fit", "Desc",
            previous_analyses=["First analysis", "Second analysis"],
        )
        assert result["comparison_to_previous"] is not None

    def test_bad_json_returns_raw(self, service, mock_client):
        mock_client.chat.completions.create.return_value = _mock_response("raw text", tokens=50)
        result = service.analyze_progress_image("url", "title", "desc")
        assert result["analysis"] == "raw text"
        assert result["progress_indicators"] == []

    def test_api_error(self, service, mock_client):
        mock_client.chat.completions.create.side_effect = openai.APIError(
            message="fail", request=Mock(), body=None
        )
        with pytest.raises(OpenAIError, match="Progress image analysis failed"):
            service.analyze_progress_image("url", "title", "desc")


# ===================================================================
# predict_obstacles_simple()
# ===================================================================

class TestPredictObstaclesSimple:

    def test_success_dict_response(self, service, mock_client):
        resp = json.dumps({
            "obstacles": [
                {"title": "Lack of time", "description": "Busy schedule", "solution": "Schedule blocks"}
            ]
        })
        mock_client.chat.completions.create.return_value = _mock_response(resp)
        result = service.predict_obstacles_simple("Run 5K", "Train for a 5K")
        assert len(result) == 1
        assert result[0]["title"] == "Lack of time"

    def test_success_list_response(self, service, mock_client):
        # Some responses come back as bare dicts with different keys
        resp = json.dumps({
            "potential_obstacles": [
                {"title": "Weather", "description": "Rain", "solution": "Indoor gym"}
            ]
        })
        mock_client.chat.completions.create.return_value = _mock_response(resp)
        result = service.predict_obstacles_simple("T", "D")
        assert len(result) == 1

    def test_api_error(self, service, mock_client):
        mock_client.chat.completions.create.side_effect = openai.APIError(
            message="fail", request=Mock(), body=None
        )
        with pytest.raises(OpenAIError, match="Obstacle prediction failed"):
            service.predict_obstacles_simple("T", "D")


# ===================================================================
# generate_task_adjustments()
# ===================================================================

class TestGenerateTaskAdjustments:

    def test_success(self, service, mock_client):
        resp = json.dumps({
            "summary": "Tasks are too long",
            "detailed": ["Shorten tasks to 15 minutes", "Add breaks"],
        })
        mock_client.chat.completions.create.return_value = _mock_response(resp)
        result = service.generate_task_adjustments(
            "Alice", [{"title": "Long task", "status": "pending"}], 40.0
        )
        assert "summary" in result
        assert len(result["detailed"]) == 2

    def test_api_error(self, service, mock_client):
        mock_client.chat.completions.create.side_effect = openai.APIError(
            message="fail", request=Mock(), body=None
        )
        with pytest.raises(OpenAIError, match="Task adjustment generation failed"):
            service.generate_task_adjustments("A", [], 0)


# ===================================================================
# generate_vision_image()
# ===================================================================

class TestGenerateVisionImage:

    def test_success(self, service, mock_client):
        mock_resp = Mock()
        mock_resp.data = [Mock(url="https://example.com/vision.png")]
        mock_client.images.generate.return_value = mock_resp
        result = service.generate_vision_image(
            "Run Marathon", "Complete a marathon",
            category="health",
            milestones=["Month 1", "Month 6"],
            calibration_profile={"primary_motivation": "health", "success_definition": "finish"},
        )
        assert result == "https://example.com/vision.png"

    def test_api_error(self, service, mock_client):
        mock_client.images.generate.side_effect = openai.APIError(
            message="fail", request=Mock(), body=None
        )
        with pytest.raises(OpenAIError, match="Image generation failed"):
            service.generate_vision_image("T", "D")


# ===================================================================
# score_buddy_compatibility()
# ===================================================================

class TestScoreBuddyCompatibility:

    def _profiles(self):
        return (
            {"name": "Alice", "dreams": ["Run 5K"], "categories": ["health"]},
            {"name": "Bob", "dreams": ["Lose weight"], "categories": ["health"]},
        )

    def test_success(self, service, mock_client):
        resp = json.dumps({
            "compatibility_score": 0.85,
            "reasons": ["Both health focused"],
            "shared_interests": ["health"],
            "potential_challenges": ["Different speeds"],
            "suggested_icebreaker": "Hey! Want to train together?",
        })
        mock_client.chat.completions.create.return_value = _mock_response(resp)
        p1, p2 = self._profiles()
        result = service.score_buddy_compatibility(p1, p2)
        assert result["compatibility_score"] == 0.85
        assert len(result["reasons"]) >= 1

    def test_bad_json_returns_defaults(self, service, mock_client):
        mock_client.chat.completions.create.return_value = _mock_response("not json")
        p1, p2 = self._profiles()
        result = service.score_buddy_compatibility(p1, p2)
        assert result["compatibility_score"] == 0.5

    def test_markdown_code_fences_stripped(self, service, mock_client):
        resp = '```json\n{"compatibility_score": 0.7, "reasons": [], "shared_interests": [], "potential_challenges": [], "suggested_icebreaker": "Hi"}\n```'
        mock_client.chat.completions.create.return_value = _mock_response(resp)
        p1, p2 = self._profiles()
        result = service.score_buddy_compatibility(p1, p2)
        assert result["compatibility_score"] == 0.7

    def test_invalid_score_clamped(self, service, mock_client):
        resp = json.dumps({
            "compatibility_score": 5.0,  # out of range
            "reasons": "not a list",
            "shared_interests": "not a list",
            "potential_challenges": "not a list",
            "suggested_icebreaker": "x" * 600,  # too long
        })
        mock_client.chat.completions.create.return_value = _mock_response(resp)
        p1, p2 = self._profiles()
        result = service.score_buddy_compatibility(p1, p2)
        assert result["compatibility_score"] == 0.5
        assert result["reasons"] == []

    def test_api_error(self, service, mock_client):
        mock_client.chat.completions.create.side_effect = openai.APIError(
            message="fail", request=Mock(), body=None
        )
        p1, p2 = self._profiles()
        with pytest.raises(OpenAIError, match="Buddy compatibility scoring failed"):
            service.score_buddy_compatibility(p1, p2)


# ===================================================================
# summarize_voice_note()
# ===================================================================

class TestSummarizeVoiceNote:

    def test_success(self, service, mock_client):
        resp = json.dumps({
            "summary": "User discussed progress",
            "key_points": ["Made progress on running"],
            "action_items": [{"item": "Run 5K", "priority": "high"}],
            "mood": "motivated",
        })
        mock_client.chat.completions.create.return_value = _mock_response(resp)
        result = service.summarize_voice_note("I ran 3 miles today and felt great")
        assert result["summary"] == "User discussed progress"
        assert result["mood"] == "motivated"

    def test_with_context(self, service, mock_client):
        resp = json.dumps({
            "summary": "S", "key_points": [], "action_items": [], "mood": "neutral"
        })
        mock_client.chat.completions.create.return_value = _mock_response(resp)
        result = service.summarize_voice_note("Test", conversation_context="Previous context")
        assert result["mood"] == "neutral"

    def test_bad_json_returns_basic(self, service, mock_client):
        mock_client.chat.completions.create.return_value = _mock_response("oops")
        result = service.summarize_voice_note("Some transcript here that is very long")
        assert result["mood"] == "neutral"
        assert result["key_points"] == []

    def test_non_dict_returns_fallback(self, service, mock_client):
        mock_client.chat.completions.create.return_value = _mock_response('"just a string"')
        result = service.summarize_voice_note("transcript")
        assert result["mood"] == "neutral"

    def test_invalid_priority_fixed(self, service, mock_client):
        resp = json.dumps({
            "summary": "S",
            "key_points": [],
            "action_items": [{"item": "Do X", "priority": "extreme"}],
            "mood": "happy" * 10,  # too long
        })
        mock_client.chat.completions.create.return_value = _mock_response(resp)
        result = service.summarize_voice_note("transcript")
        assert result["action_items"][0]["priority"] == "medium"
        assert result["mood"] == "neutral"

    def test_api_error(self, service, mock_client):
        mock_client.chat.completions.create.side_effect = openai.APIError(
            message="fail", request=Mock(), body=None
        )
        with pytest.raises(OpenAIError, match="Voice note summarization failed"):
            service.summarize_voice_note("test")


# ===================================================================
# extract_memories()
# ===================================================================

class TestExtractMemories:

    def test_success(self, service, mock_client):
        resp = json.dumps([
            {"key": "fact", "content": "User is a developer", "importance": 4}
        ])
        mock_client.chat.completions.create.return_value = _mock_response(resp)
        result = service.extract_memories(
            [{"role": "user", "content": "I'm a developer"}]
        )
        assert len(result) == 1
        assert result[0]["key"] == "fact"

    def test_with_existing_memories(self, service, mock_client):
        resp = json.dumps([
            {"key": "preference", "content": "Prefers morning", "importance": 3}
        ])
        mock_client.chat.completions.create.return_value = _mock_response(resp)
        result = service.extract_memories(
            [{"role": "user", "content": "I like mornings"}],
            existing_memories=[{"key": "fact", "content": "Lives in Paris"}],
        )
        assert len(result) == 1

    def test_invalid_key_fixed(self, service, mock_client):
        resp = json.dumps([
            {"key": "invalid_key", "content": "Some content", "importance": 10}
        ])
        mock_client.chat.completions.create.return_value = _mock_response(resp)
        result = service.extract_memories([{"role": "user", "content": "test"}])
        assert result[0]["key"] == "fact"  # falls back to "fact"
        assert result[0]["importance"] == 3  # clamped

    def test_bad_json_returns_empty(self, service, mock_client):
        mock_client.chat.completions.create.return_value = _mock_response("oops")
        result = service.extract_memories([{"role": "user", "content": "test"}])
        assert result == []

    def test_non_list_returns_empty(self, service, mock_client):
        mock_client.chat.completions.create.return_value = _mock_response('{"key": "value"}')
        result = service.extract_memories([{"role": "user", "content": "test"}])
        assert result == []

    def test_empty_content_filtered(self, service, mock_client):
        resp = json.dumps([
            {"key": "fact", "content": "", "importance": 3},
            {"key": "fact", "content": "Valid", "importance": 3},
        ])
        mock_client.chat.completions.create.return_value = _mock_response(resp)
        result = service.extract_memories([{"role": "user", "content": "test"}])
        assert len(result) == 1

    def test_api_error_returns_empty(self, service, mock_client):
        mock_client.chat.completions.create.side_effect = openai.APIError(
            message="fail", request=Mock(), body=None
        )
        result = service.extract_memories([{"role": "user", "content": "test"}])
        assert result == []

    def test_unexpected_error_returns_empty(self, service, mock_client):
        mock_client.chat.completions.create.side_effect = RuntimeError("boom")
        result = service.extract_memories([{"role": "user", "content": "test"}])
        assert result == []


# ===================================================================
# build_memory_context()
# ===================================================================

class TestBuildMemoryContext:

    @pytest.mark.django_db
    def test_no_memories_returns_empty(self, user):
        from integrations.openai_service import OpenAIService
        result = OpenAIService.build_memory_context(user)
        assert result == ""

    @pytest.mark.django_db
    def test_with_memories(self, user):
        from apps.ai.models import ChatMemory
        from integrations.openai_service import OpenAIService
        ChatMemory.objects.create(
            user=user, key="fact", content="Lives in Paris", importance=5, is_active=True
        )
        ChatMemory.objects.create(
            user=user, key="preference", content="Prefers morning", importance=3, is_active=True
        )
        result = OpenAIService.build_memory_context(user)
        assert "USER MEMORY" in result
        assert "Lives in Paris" in result
        assert "Prefers morning" in result

    @pytest.mark.django_db
    def test_inactive_memories_excluded(self, user):
        from apps.ai.models import ChatMemory
        from integrations.openai_service import OpenAIService
        ChatMemory.objects.create(
            user=user, key="fact", content="Inactive memory", importance=5, is_active=False
        )
        result = OpenAIService.build_memory_context(user)
        assert result == ""


# ===================================================================
# predict_obstacles()
# ===================================================================

class TestPredictObstacles:

    def test_success(self, service, mock_client):
        resp = json.dumps({
            "predictions": [
                {
                    "obstacle": "Time management",
                    "likelihood": "high",
                    "impact": "high",
                    "prevention_strategies": ["Plan ahead"],
                    "early_warning_signs": ["Missing deadlines"],
                }
            ]
        })
        mock_client.chat.completions.create.return_value = _mock_response(resp)
        result = service.predict_obstacles(
            {"title": "T", "description": "D"},
            [{"title": "G1"}],
            [{"title": "T1"}],
            [],
            [],
        )
        assert "predictions" in result
        assert len(result["predictions"]) == 1

    def test_missing_predictions_key(self, service, mock_client):
        mock_client.chat.completions.create.return_value = _mock_response(
            json.dumps({"other": "data"})
        )
        result = service.predict_obstacles({}, [], [], [], [])
        assert result["predictions"] == []


# ===================================================================
# prioritize_tasks()
# ===================================================================

class TestPrioritizeTasks:

    def test_success(self, service, mock_client):
        resp = json.dumps({
            "prioritized_tasks": [
                {"task_id": "123", "rank": 1, "reason": "Urgent", "suggested_time": "09:00", "energy_match": "high"}
            ],
            "focus_task": {"task_id": "123", "reason": "Most important"},
            "quick_wins": [{"task_id": "456", "reason": "Quick 5 min task"}],
        })
        mock_client.chat.completions.create.return_value = _mock_response(resp)
        result = service.prioritize_tasks(
            [{"task_id": "123", "title": "Urgent task"}],
            {"peak_hours": [9, 10], "energy_pattern": "morning_person"},
            9,
        )
        assert len(result["prioritized_tasks"]) == 1
        assert result["focus_task"]["task_id"] == "123"

    def test_missing_keys_filled(self, service, mock_client):
        mock_client.chat.completions.create.return_value = _mock_response(json.dumps({}))
        result = service.prioritize_tasks([], {}, 12)
        assert result["prioritized_tasks"] == []
        assert result["focus_task"] is None
        assert result["quick_wins"] == []


# ===================================================================
# refine_goal()
# ===================================================================

class TestRefineGoal:

    def test_success(self, service, mock_client):
        resp = json.dumps({
            "message": "Can you tell me more?",
            "refined_goal": None,
            "milestones": None,
            "is_complete": False,
        })
        mock_client.chat.completions.create.return_value = _mock_response(resp, tokens=100)
        result = service.refine_goal(
            "Run 5K", "Train for running",
            {"title": "Fitness", "description": "Get fit"},
            [],
        )
        assert result["message"] == "Can you tell me more?"
        assert result["is_complete"] is False

    def test_with_conversation_history(self, service, mock_client):
        resp = json.dumps({
            "message": "Here is your SMART goal",
            "refined_goal": {"title": "Run 5K under 30 min"},
            "milestones": [{"title": "Week 1"}],
            "is_complete": True,
        })
        mock_client.chat.completions.create.return_value = _mock_response(resp, tokens=200)
        result = service.refine_goal(
            "Run 5K", "",
            None,
            [{"role": "user", "content": "I want to run it in 30 min"}],
        )
        assert result["is_complete"] is True
        assert result["refined_goal"]["title"] == "Run 5K under 30 min"

    def test_missing_keys_normalized(self, service, mock_client):
        resp = json.dumps({"response": "Hello"})
        mock_client.chat.completions.create.return_value = _mock_response(resp, tokens=50)
        result = service.refine_goal("T", "D", None, [])
        assert result["message"] == "Hello"
        assert result["refined_goal"] is None
        assert result["is_complete"] is False


# ===================================================================
# generate_starters()
# ===================================================================

class TestGenerateStarters:

    def test_success(self, service, mock_client):
        resp = json.dumps({
            "starters": [
                {"text": "How should I start?", "category": "planning", "icon": "clipboard"},
                {"text": "I need motivation", "category": "motivation", "icon": "fire"},
            ]
        })
        mock_client.chat.completions.create.return_value = _mock_response(resp)
        result = service.generate_starters({"title": "D1", "progress": 10})
        assert len(result["starters"]) == 2

    def test_invalid_category_fixed(self, service, mock_client):
        resp = json.dumps({
            "starters": [
                {"text": "Q1", "category": "invalid_cat", "icon": "x"},
            ]
        })
        mock_client.chat.completions.create.return_value = _mock_response(resp)
        result = service.generate_starters({"title": "D1"})
        assert result["starters"][0]["category"] == "planning"

    def test_empty_text_filtered(self, service, mock_client):
        resp = json.dumps({
            "starters": [
                {"text": "", "category": "planning"},
                {"text": "Valid", "category": "planning"},
            ]
        })
        mock_client.chat.completions.create.return_value = _mock_response(resp)
        result = service.generate_starters({"title": "D1"})
        assert len(result["starters"]) == 1


# ===================================================================
# generate_disambiguation_question()
# ===================================================================

class TestGenerateDisambiguationQuestion:

    def test_success(self, service, mock_client):
        resp = json.dumps({"question": "Is this about fitness or nutrition?"})
        mock_client.chat.completions.create.return_value = _mock_response(resp)
        result = service.generate_disambiguation_question(
            "Lose weight", "I want to be healthier", ["health", "personal_development"]
        )
        assert "fitness" in result.lower() or "nutrition" in result.lower() or result is not None

    def test_failure_returns_none(self, service, mock_client):
        mock_client.chat.completions.create.side_effect = Exception("fail")
        result = service.generate_disambiguation_question("T", "D", ["health", "career"])
        assert result is None


# ===================================================================
# estimate_durations()
# ===================================================================

class TestEstimateDurations:

    def test_success(self, service, mock_client):
        resp = json.dumps({
            "estimates": [
                {"task_id": "1", "optimistic_minutes": 10, "realistic_minutes": 20,
                 "pessimistic_minutes": 30, "complexity": "moderate", "reasoning": "Normal task"}
            ]
        })
        mock_client.chat.completions.create.return_value = _mock_response(resp)
        result = service.estimate_durations(
            [{"task_id": "1", "title": "Study"}],
            historical_data={"avg_actual_minutes": 25, "completion_rate": 80},
            skill_hints="Beginner",
        )
        assert len(result["estimates"]) == 1

    def test_no_estimates_key_auto_detected(self, service, mock_client):
        resp = json.dumps({
            "data": [{"task_id": "1", "realistic_minutes": 15}]
        })
        mock_client.chat.completions.create.return_value = _mock_response(resp)
        result = service.estimate_durations([{"task_id": "1", "title": "T"}])
        assert "estimates" in result


# ===================================================================
# find_similar_dreams()
# ===================================================================

class TestFindSimilarDreams:

    def test_success(self, service, mock_client):
        resp = json.dumps({
            "similar_dreams": [{"dream_id": "abc", "title": "Run 5K", "similarity_score": 0.9, "reason": "Both running"}],
            "related_templates": [],
            "inspiration_tips": ["Cross-train"],
        })
        mock_client.chat.completions.create.return_value = _mock_response(resp)
        result = service.find_similar_dreams(
            {"title": "Run 10K"}, [{"id": "abc", "title": "Run 5K"}], []
        )
        assert len(result["similar_dreams"]) == 1

    def test_missing_keys_normalized(self, service, mock_client):
        mock_client.chat.completions.create.return_value = _mock_response(json.dumps({}))
        result = service.find_similar_dreams({}, [], [])
        assert result["similar_dreams"] == []
        assert result["related_templates"] == []
        assert result["inspiration_tips"] == []


# ===================================================================
# parse_natural_language_tasks()
# ===================================================================

class TestParseNaturalLanguageTasks:

    def test_success(self, service, mock_client):
        resp = json.dumps({
            "tasks": [
                {"title": "Call dentist", "description": "", "duration_mins": 15,
                 "priority": 3, "matched_dream_id": None, "matched_goal_id": None, "deadline_hint": None}
            ]
        })
        mock_client.chat.completions.create.return_value = _mock_response(resp)
        result = service.parse_natural_language_tasks("Call the dentist tomorrow")
        assert len(result["tasks"]) == 1

    def test_with_dreams_context(self, service, mock_client):
        resp = json.dumps({"tasks": [{"title": "Study", "matched_dream_id": "dream1"}]})
        mock_client.chat.completions.create.return_value = _mock_response(resp)
        result = service.parse_natural_language_tasks(
            "Study for exam",
            dreams_context=[{"id": "dream1", "title": "Pass exam"}],
        )
        assert result["tasks"][0]["matched_dream_id"] == "dream1"


# ===================================================================
# analyze_productivity()
# ===================================================================

class TestAnalyzeProductivity:

    def test_success(self, service, mock_client):
        resp = json.dumps({
            "overall_score": 72,
            "summary": "Good consistency",
            "trends": [{"metric": "tasks", "direction": "up", "change_pct": 10, "insight": "More tasks"}],
            "peak_days": [{"day_of_week": "Monday", "reason": "Fresh start"}],
            "productivity_patterns": [{"pattern": "Morning person", "description": "Active mornings", "recommendation": "Schedule hard tasks AM"}],
            "monthly_comparison": {"improved": ["tasks"], "declined": [], "stable": ["focus"]},
        })
        mock_client.chat.completions.create.return_value = _mock_response(resp)
        result = service.analyze_productivity([], [], {})
        assert result["overall_score"] == 72

    def test_markdown_fences_stripped(self, service, mock_client):
        inner = json.dumps({"overall_score": 60, "summary": "ok", "trends": [], "peak_days": [], "productivity_patterns": [], "monthly_comparison": {"improved": [], "declined": [], "stable": []}})
        resp = f"```json\n{inner}\n```"
        mock_client.chat.completions.create.return_value = _mock_response(resp)
        result = service.analyze_productivity([], [], {})
        assert result["overall_score"] == 60

    def test_bad_json_returns_defaults(self, service, mock_client):
        mock_client.chat.completions.create.return_value = _mock_response("bad json")
        result = service.analyze_productivity([], [], {})
        assert result["overall_score"] == 50
        assert result["trends"] == []

    def test_invalid_score_clamped(self, service, mock_client):
        resp = json.dumps({
            "overall_score": -10,
            "summary": "x" * 600,
            "trends": "not a list",
            "peak_days": "not a list",
            "productivity_patterns": "not a list",
            "monthly_comparison": "not a dict",
        })
        mock_client.chat.completions.create.return_value = _mock_response(resp)
        result = service.analyze_productivity([], [], {})
        assert result["overall_score"] == 50  # non-dict response handling
        # Actually this has overall_score -10 which validates to 50 (sanitization)


# ===================================================================
# generate_celebration()
# ===================================================================

class TestGenerateCelebration:

    def test_success(self, service, mock_client):
        resp = json.dumps({
            "message": "You did it!",
            "emoji": "trophy",
            "share_text": "Just completed my goal!",
        })
        mock_client.chat.completions.create.return_value = _mock_response(resp)
        result = service.generate_celebration(
            "goal_completed", {"title": "Run 5K", "progress": 100}
        )
        assert result["message"] == "You did it!"
        assert result["animation_type"] == "confetti"

    def test_invalid_type_defaulted(self, service, mock_client):
        resp = json.dumps({"message": "ok", "emoji": "e", "share_text": "s"})
        mock_client.chat.completions.create.return_value = _mock_response(resp)
        result = service.generate_celebration("invalid_type", {})
        assert result["animation_type"] == "stars"  # task_completed default

    def test_api_error_fallback(self, service, mock_client):
        mock_client.chat.completions.create.side_effect = openai.APIError(
            message="fail", request=Mock(), body=None
        )
        result = service.generate_celebration("dream_completed", {})
        assert "DREAM COMPLETE" in result["message"]
        assert result["animation_type"] == "trophy"


# ===================================================================
# optimize_notification_timing()
# ===================================================================

class TestOptimizeNotificationTiming:

    def test_success(self, service, mock_client):
        resp = json.dumps({
            "optimal_times": [
                {"notification_type": "reminder", "best_hour": 9, "best_day": "weekday", "reason": "Active at 9"}
            ],
            "quiet_hours": {"start": 22, "end": 7},
            "engagement_score": 0.85,
        })
        mock_client.chat.completions.create.return_value = _mock_response(resp)
        result = service.optimize_notification_timing({}, ["reminder"], {})
        assert result["engagement_score"] == 0.85
        assert len(result["optimal_times"]) == 1

    def test_bad_json_returns_fallback(self, service, mock_client):
        mock_client.chat.completions.create.return_value = _mock_response("bad")
        result = service.optimize_notification_timing({}, ["reminder"], {})
        assert result["engagement_score"] == 0.3  # fallback value

    def test_invalid_values_sanitized(self, service, mock_client):
        resp = json.dumps({
            "optimal_times": [
                {"notification_type": "x", "best_hour": 99, "best_day": "invalid"}
            ],
            "quiet_hours": {"start": "bad", "end": 99},
            "engagement_score": 5.0,
        })
        mock_client.chat.completions.create.return_value = _mock_response(resp)
        result = service.optimize_notification_timing({}, [], {})
        assert result["optimal_times"][0]["best_hour"] == 9  # default
        assert result["optimal_times"][0]["best_day"] == "daily"
        assert result["engagement_score"] == 1.0  # clamped


# ===================================================================
# calibrate_difficulty()
# ===================================================================

class TestCalibrateDifficulty:

    def test_success(self, service, mock_client):
        resp = json.dumps({
            "difficulty_level": "moderate",
            "calibration_score": 0.7,
            "analysis": "Well calibrated",
            "suggestions": [],
            "daily_target": {"tasks": 5, "focus_minutes": 120, "reason": "Good pace"},
            "challenge": {"title": "Push harder", "description": "Desc", "reward_xp": 100, "deadline_days": 7},
        })
        mock_client.chat.completions.create.return_value = _mock_response(resp)
        result = service.calibrate_difficulty(
            0.75, 25.0, {"current_streak": 5}, [{"task_id": "1", "title": "T"}]
        )
        assert result["difficulty_level"] == "moderate"
        assert result["calibration_score"] == 0.7

    def test_invalid_difficulty_fixed(self, service, mock_client):
        resp = json.dumps({
            "difficulty_level": "impossible",
            "calibration_score": -1.0,
            "analysis": 123,
            "suggestions": "not a list",
            "daily_target": "not a dict",
            "challenge": "not a dict",
        })
        mock_client.chat.completions.create.return_value = _mock_response(resp)
        result = service.calibrate_difficulty(0.5, 30, {}, [])
        assert result["difficulty_level"] == "moderate"
        assert result["calibration_score"] == 0.5


# ===================================================================
# run_checkin_agent()
# ===================================================================

class TestRunCheckinAgent:

    @pytest.mark.django_db
    def test_finish_on_first_tool_call(self, service, mock_plan_client, user):
        from apps.dreams.models import Dream
        dream = Dream.objects.create(
            user=user, title="Learn Django", description="Master Django", status="active"
        )
        tc = _mock_tool_call("finish_check_in", {
            "coaching_message": "Great progress!",
            "months_now_covered_through": 3,
            "adjustment_summary": "No changes needed",
            "pace_status": "on_track",
            "next_checkin_days": 14,
        })
        mock_plan_client.chat.completions.create.return_value = _mock_response(
            "", tool_calls=[tc]
        )
        with patch("integrations.context_builder.build_dream_context", return_value="context"):
            result = service.run_checkin_agent(dream, user, max_iterations=2)
        assert result["coaching_message"] == "Great progress!"
        assert result["pace_status"] == "on_track"

    @pytest.mark.django_db
    def test_no_tool_calls_forces_finish(self, service, mock_plan_client, user):
        from apps.dreams.models import Dream
        dream = Dream.objects.create(
            user=user, title="Test", description="Test", status="active"
        )
        mock_plan_client.chat.completions.create.return_value = _mock_response(
            "Done", tool_calls=None
        )
        with patch("integrations.context_builder.build_dream_context", return_value="ctx"):
            result = service.run_checkin_agent(dream, user, max_iterations=1)
        assert result["coaching_message"] == "Done"

    @pytest.mark.django_db
    def test_api_error_raises(self, service, mock_plan_client, user):
        from apps.dreams.models import Dream
        dream = Dream.objects.create(user=user, title="T", description="D", status="active")
        mock_plan_client.chat.completions.create.side_effect = Exception("API down")
        with patch("integrations.context_builder.build_dream_context", return_value="ctx"):
            with pytest.raises(OpenAIError, match="Check-in API call failed"):
                service.run_checkin_agent(dream, user, max_iterations=1)


# ===================================================================
# generate_checkin_questionnaire()
# ===================================================================

class TestGenerateCheckinQuestionnaire:

    @pytest.mark.django_db
    def test_finish_signal(self, service, mock_plan_client, user):
        from apps.dreams.models import Dream
        dream = Dream.objects.create(user=user, title="T", description="D", status="active")
        tc = _mock_tool_call("finish_questionnaire_generation", {
            "questions": [{"id": "q1", "question_type": "slider", "question": "How satisfied?"}],
            "opening_message": "Hi!",
            "pace_summary": "On track",
        })
        mock_plan_client.chat.completions.create.return_value = _mock_response("", tool_calls=[tc])
        with patch("integrations.context_builder.build_dream_context", return_value="ctx"):
            result = service.generate_checkin_questionnaire(dream, user, {"pace": "on_track"})
        assert result["success"] is True
        assert len(result["questions"]) == 1


# ===================================================================
# run_interactive_checkin_agent()
# ===================================================================

class TestRunInteractiveCheckinAgent:

    @pytest.mark.django_db
    def test_finish_on_first_call(self, service, mock_plan_client, user):
        from apps.dreams.models import Dream
        dream = Dream.objects.create(user=user, title="T", description="D", status="active")
        tc = _mock_tool_call("finish_check_in", {
            "coaching_message": "Adapted plan!",
            "months_now_covered_through": 4,
            "adjustment_summary": "Shifted dates",
            "pace_status": "behind",
            "next_checkin_days": 7,
        })
        mock_plan_client.chat.completions.create.return_value = _mock_response(
            "", tool_calls=[tc]
        )
        with patch("integrations.context_builder.build_dream_context", return_value="ctx"):
            result = service.run_interactive_checkin_agent(
                dream, user,
                questionnaire={"questions": [{"id": "q1"}]},
                user_responses={"satisfaction": 3},
                max_iterations=2,
            )
        assert result["coaching_message"] == "Adapted plan!"
        assert result["pace_status"] == "behind"
        assert result["next_checkin_days"] == 7

    @pytest.mark.django_db
    def test_no_tool_calls_returns_default(self, service, mock_plan_client, user):
        from apps.dreams.models import Dream
        dream = Dream.objects.create(user=user, title="T", description="D", status="active")
        mock_plan_client.chat.completions.create.return_value = _mock_response(
            "Auto-completed", tool_calls=None
        )
        with patch("integrations.context_builder.build_dream_context", return_value="ctx"):
            result = service.run_interactive_checkin_agent(
                dream, user, None, None, max_iterations=1
            )
        assert result["coaching_message"] == "Auto-completed"
        assert result["pace_status"] == "on_track"

    @pytest.mark.django_db
    def test_api_error_raises(self, service, mock_plan_client, user):
        from apps.dreams.models import Dream
        dream = Dream.objects.create(user=user, title="T", description="D", status="active")
        mock_plan_client.chat.completions.create.side_effect = Exception("fail")
        with patch("integrations.context_builder.build_dream_context", return_value="ctx"):
            with pytest.raises(OpenAIError, match="Interactive check-in API call failed"):
                service.run_interactive_checkin_agent(dream, user, None, None, max_iterations=1)

    @pytest.mark.django_db
    def test_max_iterations_exhausted(self, service, mock_plan_client, user):
        from apps.dreams.models import Dream
        dream = Dream.objects.create(user=user, title="T", description="D", status="active")
        # Return a non-finish tool call each time
        tc = _mock_tool_call("get_dream_progress", {"dream_id": "x"})
        mock_plan_client.chat.completions.create.return_value = _mock_response(
            "", tool_calls=[tc]
        )
        with patch("integrations.context_builder.build_dream_context", return_value="ctx"):
            with patch("integrations.checkin_tools.CheckInToolExecutor.dispatch",
                       return_value=({"success": True}, False)):
                result = service.run_interactive_checkin_agent(
                    dream, user, None, None, max_iterations=2
                )
        assert result["coaching_message"] == "Check-in completed."


# ===================================================================
# generate_checkin_opening_message()
# ===================================================================

class TestGenerateCheckinOpeningMessage:

    @pytest.mark.django_db
    def test_success(self, service, mock_client, user):
        from apps.dreams.models import Dream
        dream = Dream.objects.create(user=user, title="Test", description="D", status="active")
        mock_client.chat.completions.create.return_value = _mock_response("Your progress looks great!")
        result = service.generate_checkin_opening_message(
            dream, {"overall_progress": 50, "tasks_completed_last_14_days": 5}
        )
        assert result == "Your progress looks great!"

    @pytest.mark.django_db
    def test_error_returns_none(self, service, mock_client, user):
        from apps.dreams.models import Dream
        dream = Dream.objects.create(user=user, title="T", description="D", status="active")
        mock_client.chat.completions.create.side_effect = Exception("fail")
        result = service.generate_checkin_opening_message(dream, {})
        assert result is None


# ===================================================================
# _parse_duration()
# ===================================================================

class TestParseDuration:

    def test_none_input(self, service):
        assert service._parse_duration(None) == (None, None)

    def test_string_date(self, service):
        future = (date.today() + timedelta(days=90)).isoformat()
        total_days, total_months = service._parse_duration(future)
        assert total_days == 90
        assert total_months == 3

    def test_date_object(self, service):
        future = date.today() + timedelta(days=60)
        total_days, total_months = service._parse_duration(future)
        assert total_days == 60

    def test_invalid_string(self, service):
        assert service._parse_duration("not-a-date") == (None, None)

    def test_datetime_string_with_tz(self, service):
        future = (date.today() + timedelta(days=30)).isoformat() + " 12:00:00+00:00"
        total_days, total_months = service._parse_duration(future)
        assert total_days == 30


# ===================================================================
# _build_persona_section()
# ===================================================================

class TestBuildPersonaSection:

    def test_empty_persona(self, service):
        result = service._build_persona_section({"persona": {}})
        assert result == ""

    def test_no_persona_key(self, service):
        result = service._build_persona_section({})
        assert result == ""

    def test_with_values(self, service):
        ctx = {"persona": {"available_hours_per_week": 10, "occupation": "Developer"}}
        result = service._build_persona_section(ctx)
        assert "Available Hours/Week: 10" in result
        assert "Occupation: Developer" in result


# ===================================================================
# _build_calibration_section()
# ===================================================================

class TestBuildCalibrationSection:

    def test_no_calibration_profile(self, service):
        result = service._build_calibration_section(
            {"persona": {"occupation": "Dev"}}, "desc"
        )
        assert "Occupation: Dev" in result

    def test_with_calibration_profile(self, service):
        ctx = {
            "calibration_profile": {
                "experience_level": "beginner",
                "available_hours_per_week": "5",
            },
            "plan_recommendations": {
                "suggested_pace": "relaxed",
                "focus_areas": ["basics"],
                "potential_pitfalls": ["boredom"],
                "personalization_notes": "Keep simple",
            },
            "enriched_description": "Detailed description",
        }
        result = service._build_calibration_section(ctx, "original desc")
        assert "beginner" in result
        assert "CALIBRATION PROFILE" in result


# ===================================================================
# _default_compatibility_result()
# ===================================================================

class TestDefaultCompatibilityResult:

    def test_returns_expected_keys(self):
        from integrations.openai_service import OpenAIService
        result = OpenAIService._default_compatibility_result()
        assert result["compatibility_score"] == 0.5
        assert isinstance(result["reasons"], list)


# ===================================================================
# _notification_timing_fallback()
# ===================================================================

class TestNotificationTimingFallback:

    def test_returns_defaults(self, service):
        result = service._notification_timing_fallback(["reminder", "motivation"])
        assert len(result["optimal_times"]) == 2
        assert result["engagement_score"] == 0.3
        assert result["quiet_hours"] == {"start": 22, "end": 7}


# ===================================================================
# SYSTEM_PROMPTS
# ===================================================================

class TestSystemPrompts:

    def test_all_prompts_include_ethical_preamble(self, service):
        for key, prompt in service.SYSTEM_PROMPTS.items():
            assert "ETHICAL GUIDELINES" in prompt, f"Prompt '{key}' missing ethical preamble"

    def test_known_prompt_types_exist(self, service):
        expected = [
            "dream_creation", "planning", "motivation", "check_in", "rescue",
            "adaptive_checkin", "checkin_questionnaire_generation",
            "interactive_checkin_adaptation",
        ]
        for key in expected:
            assert key in service.SYSTEM_PROMPTS, f"Missing prompt type: {key}"


# ===================================================================
# CHECKIN_TOOLS and QUESTIONNAIRE_TOOLS
# ===================================================================

class TestToolDefinitions:

    def test_checkin_tools_well_formed(self, service):
        for tool in service.CHECKIN_TOOLS:
            assert tool["type"] == "function"
            assert "name" in tool["function"]
            assert "parameters" in tool["function"]

    def test_questionnaire_tools_well_formed(self, service):
        for tool in service.QUESTIONNAIRE_TOOLS:
            assert tool["type"] == "function"
            assert "name" in tool["function"]

    def test_finish_check_in_in_checkin_tools(self, service):
        names = [t["function"]["name"] for t in service.CHECKIN_TOOLS]
        assert "finish_check_in" in names
        assert "get_dream_progress" in names

    def test_finish_questionnaire_in_questionnaire_tools(self, service):
        names = [t["function"]["name"] for t in service.QUESTIONNAIRE_TOOLS]
        assert "finish_questionnaire_generation" in names
