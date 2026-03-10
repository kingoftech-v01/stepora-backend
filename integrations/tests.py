"""
Tests for integration services (OpenAI).

Updated to match the v1+ OpenAI SDK used by OpenAIService:
- Service uses module-level _client (OpenAI) and _async_client (AsyncOpenAI)
- Sync calls: _client.chat.completions.create(...)
- Async calls: _async_client.chat.completions.create(...)
- Image generation: _client.images.generate(...)
"""

import asyncio
import json
from unittest.mock import AsyncMock, Mock, patch

import pytest

from core.exceptions import OpenAIError

from .openai_service import OpenAIService


class TestOpenAIService:
    """Test OpenAI integration service"""

    def test_init_service(self):
        """Test initializing OpenAI service"""
        service = OpenAIService()
        assert service is not None
        assert hasattr(service, "SYSTEM_PROMPTS")

    def test_system_prompts_exist(self):
        """Test all required system prompts are defined"""
        service = OpenAIService()

        required_prompts = [
            "dream_creation",
            "planning",
            "motivation",
            "check_in",
            "rescue",
        ]

        for prompt_type in required_prompts:
            assert prompt_type in service.SYSTEM_PROMPTS
            assert len(service.SYSTEM_PROMPTS[prompt_type]) > 0

    def test_chat_completion(self, mock_openai):
        """Test synchronous chat completion"""
        service = OpenAIService()

        messages = [{"role": "user", "content": "Hello"}]

        response = service.chat(messages)

        assert response is not None
        assert "content" in response
        assert "tokens_used" in response
        assert "model" in response
        mock_openai["create"].assert_called_once()

    def test_chat_completion_with_functions(self, mock_openai):
        """Test synchronous chat completion with function calling"""
        service = OpenAIService()

        # Override mock to return a function_call response
        # Note: Mock(name=...) sets the mock's internal name, not a .name attribute.
        # We must set .name separately after construction.
        mock_fc = Mock()
        mock_fc.name = "create_task"
        mock_fc.arguments = '{"title": "Read docs", "duration_mins": 30}'

        mock_openai["create"].return_value = Mock(
            choices=[
                Mock(
                    message=Mock(
                        content="",
                        function_call=mock_fc,
                    )
                )
            ],
            usage=Mock(total_tokens=150),
            model="gpt-4",
        )

        messages = [{"role": "user", "content": "Create a task for reading docs"}]
        response = service.chat(messages, functions=service.FUNCTION_DEFINITIONS)

        assert "function_call" in response
        assert response["function_call"]["name"] == "create_task"
        assert response["function_call"]["arguments"]["title"] == "Read docs"

    def test_generate_plan(self, mock_openai):
        """Test generating plan for dream"""
        service = OpenAIService()

        plan_json = json.dumps(
            {
                "analysis": "Feasible goal",
                "estimated_duration_weeks": 12,
                "weekly_time_hours": 5,
                "goals": [
                    {
                        "title": "Goal 1",
                        "description": "Description",
                        "order": 1,
                        "estimated_minutes": 300,
                        "reasoning": "Based on user context",
                        "tasks": [
                            {
                                "title": "Task 1",
                                "order": 1,
                                "duration_mins": 30,
                                "description": "Do it",
                                "reasoning": "Because",
                            }
                        ],
                    }
                ],
                "tips": ["Tip 1"],
                "potential_obstacles": [],
                "calibration_references": [],
            }
        )

        mock_openai["create"].return_value = Mock(
            choices=[
                Mock(
                    message=Mock(
                        content=plan_json,
                        function_call=None,
                    )
                )
            ],
            usage=Mock(total_tokens=500),
            model="gpt-4",
        )

        plan = service.generate_plan(
            dream_title="Learn Django",
            dream_description="Master Django framework",
            user_context={"timezone": "UTC", "work_schedule": {}},
        )

        assert "goals" in plan
        assert len(plan["goals"]) == 1
        assert plan["goals"][0]["title"] == "Goal 1"

    def test_analyze_dream(self, mock_openai):
        """Test analyzing dream with AI"""
        service = OpenAIService()

        analysis_json = json.dumps(
            {
                "category": "personal_development",
                "estimated_duration_weeks": 24,
                "difficulty": "medium",
                "key_challenges": ["Time management", "Consistency"],
                "recommended_approach": "Start with fundamentals",
            }
        )

        mock_openai["create"].return_value = Mock(
            choices=[
                Mock(
                    message=Mock(
                        content=analysis_json,
                        function_call=None,
                    )
                )
            ],
            usage=Mock(total_tokens=200),
            model="gpt-4",
        )

        analysis = service.analyze_dream(
            dream_title="Learn Django",
            dream_description="Master Django framework",
        )

        assert "category" in analysis
        assert analysis["category"] == "personal_development"
        assert "difficulty" in analysis
        assert analysis["difficulty"] == "medium"

    def test_generate_motivational_message(self, mock_openai):
        """Test generating motivational message"""
        service = OpenAIService()

        mock_openai["create"].return_value = Mock(
            choices=[Mock(message=Mock(content="Stay motivated!"))],
            usage=Mock(total_tokens=20),
            model="gpt-3.5-turbo",
        )

        message = service.generate_motivational_message(
            user_name="Test User",
            goal_title="Learn Django",
            progress_percentage=50,
            streak_days=7,
        )

        assert message == "Stay motivated!"
        mock_openai["create"].assert_called_once()

    def test_generate_two_minute_start(self, mock_openai):
        """Test generating 2-minute start action"""
        service = OpenAIService()

        mock_openai["create"].return_value = Mock(
            choices=[Mock(message=Mock(content="Open tutorial website"))],
            usage=Mock(total_tokens=15),
            model="gpt-3.5-turbo",
        )

        action = service.generate_two_minute_start(
            dream_title="Learn Django",
            dream_description="Master Django framework",
        )

        assert action == "Open tutorial website"

    def test_generate_rescue_message(self, mock_openai):
        """Test generating rescue message for inactive user"""
        service = OpenAIService()

        mock_openai["create"].return_value = Mock(
            choices=[
                Mock(message=Mock(content="We miss you! Come back to your dreams."))
            ],
            usage=Mock(total_tokens=25),
            model="gpt-3.5-turbo",
        )

        message = service.generate_rescue_message(
            user_name="Test User",
            days_inactive=5,
            last_goal_title="Learn Django",
        )

        assert "miss you" in message.lower()

    def test_generate_vision_image(self, mock_openai):
        """Test generating vision board image with DALL-E"""
        service = OpenAIService()

        mock_openai["image"].return_value = Mock(
            data=[Mock(url="https://example.com/vision.png")]
        )

        url = service.generate_vision_image(
            dream_title="Learn Django",
            dream_description="Master Django framework",
        )

        assert url == "https://example.com/vision.png"
        mock_openai["image"].assert_called_once()

    def test_generate_calibration_questions(self, mock_openai):
        """Test generating calibration questions for a new dream"""
        service = OpenAIService()

        questions_json = json.dumps(
            {
                "sufficient": False,
                "confidence_score": 0.1,
                "questions": [
                    {
                        "question": "What is your experience level?",
                        "category": "experience",
                    },
                    {
                        "question": "How many hours per week can you dedicate?",
                        "category": "resources",
                    },
                ],
            }
        )

        mock_openai["create"].return_value = Mock(
            choices=[
                Mock(
                    message=Mock(
                        content=questions_json,
                        function_call=None,
                    )
                )
            ],
            usage=Mock(total_tokens=200),
            model="gpt-4",
        )

        result = service.generate_calibration_questions(
            dream_title="Learn Django",
            dream_description="Master Django framework",
        )

        assert "questions" in result
        assert result["sufficient"] is False
        assert len(result["questions"]) == 2

    def test_generate_calibration_questions_with_existing_qa(self, mock_openai):
        """Test generating follow-up calibration questions"""
        service = OpenAIService()

        questions_json = json.dumps(
            {
                "sufficient": True,
                "confidence_score": 0.9,
                "missing_areas": [],
                "questions": [],
            }
        )

        mock_openai["create"].return_value = Mock(
            choices=[
                Mock(
                    message=Mock(
                        content=questions_json,
                        function_call=None,
                    )
                )
            ],
            usage=Mock(total_tokens=150),
            model="gpt-4",
        )

        result = service.generate_calibration_questions(
            dream_title="Learn Django",
            dream_description="Master Django framework",
            existing_qa=[
                {"question": "What is your experience?", "answer": "Beginner"},
                {"question": "How many hours per week?", "answer": "10 hours"},
            ],
        )

        assert result["sufficient"] is True
        assert len(result["questions"]) == 0

    def test_chat_stream_async(self):
        """Test async streaming chat (uses asyncio.run to avoid pytest-asyncio dependency)"""
        service = OpenAIService()

        # Build a mock async iterator that yields chunks with v1+ attribute access
        async def mock_stream():
            chunks = ["Hello", " ", "world"]
            for chunk_text in chunks:
                yield Mock(choices=[Mock(delta=Mock(content=chunk_text))])

        async def run_test():
            with patch(
                "integrations.openai_service._async_client"
            ) as mock_async_client:
                # AsyncOpenAI().chat.completions.create returns an async iterator when stream=True
                mock_async_create = AsyncMock(return_value=mock_stream())
                mock_async_client.chat.completions.create = mock_async_create

                result = []
                async for chunk in service.chat_stream_async(
                    messages=[{"role": "user", "content": "Hi"}],
                    conversation_type="general",
                ):
                    result.append(chunk)

                assert len(result) == 3
                assert "".join(result) == "Hello world"

        asyncio.run(run_test())

    def test_chat_async(self):
        """Test async chat completion (non-streaming, uses asyncio.run)"""
        service = OpenAIService()

        async def run_test():
            with patch(
                "integrations.openai_service._async_client"
            ) as mock_async_client:
                mock_async_create = AsyncMock()
                mock_async_create.return_value = Mock(
                    choices=[Mock(message=Mock(content="Hello from async!"))],
                    usage=Mock(total_tokens=50),
                    model="gpt-4",
                )
                mock_async_client.chat.completions.create = mock_async_create

                response = await service.chat_async(
                    messages=[{"role": "user", "content": "Hi"}],
                    conversation_type="general",
                )

                assert response["content"] == "Hello from async!"
                assert response["tokens_used"] == 50
                assert response["model"] == "gpt-4"

        asyncio.run(run_test())

    def test_openai_error_handling(self):
        """Test OpenAI error handling raises OpenAIError"""
        service = OpenAIService()

        with patch("integrations.openai_service._client") as mock_client:
            mock_client.chat.completions.create.side_effect = Exception("API Error")

            with pytest.raises(OpenAIError):
                service.chat([{"role": "user", "content": "Test"}])

    def test_generate_plan_json_error(self, mock_openai):
        """Test generate_plan raises OpenAIError on invalid JSON"""
        service = OpenAIService()

        mock_openai["create"].return_value = Mock(
            choices=[
                Mock(
                    message=Mock(
                        content="this is not valid json {{{",
                        function_call=None,
                    )
                )
            ],
            usage=Mock(total_tokens=100),
            model="gpt-4",
        )

        with pytest.raises(OpenAIError, match="Failed to parse JSON"):
            service.generate_plan(
                dream_title="Learn Django",
                dream_description="Master Django",
                user_context={"timezone": "UTC"},
            )

    def test_motivational_message_fallback(self):
        """Test motivational message returns fallback on API error"""
        service = OpenAIService()

        import openai

        with patch("integrations.openai_service._client") as mock_client:
            mock_client.chat.completions.create.side_effect = openai.APIError(
                message="Service unavailable",
                request=Mock(),
                body=None,
            )

            message = service.generate_motivational_message(
                user_name="TestUser",
                goal_title="Learn Django",
                progress_percentage=50,
                streak_days=3,
            )

            # Should return fallback message instead of raising
            assert "TestUser" in message

    def test_rescue_message_fallback(self):
        """Test rescue message returns fallback on API error"""
        service = OpenAIService()

        import openai

        with patch("integrations.openai_service._client") as mock_client:
            mock_client.chat.completions.create.side_effect = openai.APIError(
                message="Service unavailable",
                request=Mock(),
                body=None,
            )

            message = service.generate_rescue_message(
                user_name="TestUser",
                days_inactive=7,
                last_goal_title="Learn Django",
            )

            # Should return fallback message
            assert "TestUser" in message

    def test_two_minute_start_fallback(self):
        """Test two-minute start returns fallback on API error"""
        service = OpenAIService()

        import openai

        with patch("integrations.openai_service._client") as mock_client:
            mock_client.chat.completions.create.side_effect = openai.APIError(
                message="Service unavailable",
                request=Mock(),
                body=None,
            )

            action = service.generate_two_minute_start(
                dream_title="Learn Django",
                dream_description="Master Django framework",
            )

            # Should return fallback action
            assert isinstance(action, str)
            assert len(action) > 0
