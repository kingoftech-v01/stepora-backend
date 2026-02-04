"""
OpenAI GPT-4 integration service for AI-powered features.

Handles all OpenAI API interactions including:
- Chat conversations with streaming support
- Dream plan generation (structured JSON output)
- Dream analysis and categorization
- Motivational message generation
- Micro-action generation for quick starts
- Rescue messages for inactive users
- Vision board image generation via DALL-E
"""

import openai
import json
import asyncio
from django.conf import settings
from core.exceptions import OpenAIError

openai.api_key = settings.OPENAI_API_KEY
if hasattr(settings, 'OPENAI_ORGANIZATION_ID'):
    openai.organization = settings.OPENAI_ORGANIZATION_ID


class OpenAIService:
    """Service for interacting with OpenAI API for all AI features."""

    # System prompts for different conversation types
    SYSTEM_PROMPTS = {
        'dream_creation': """You are DreamPlanner, a caring and motivating personal assistant that helps users transform their dreams into concrete action plans.

Your role in dream creation:
1. Listen actively and ask clarifying questions
2. Help define a SMART goal (Specific, Measurable, Achievable, Realistic, Time-bound)
3. Explore deep motivations
4. Identify potential obstacles
5. Encourage and motivate

Your tone: empathetic, positive, encouraging but realistic.
IMPORTANT: Always respond in the user's language. Detect the language they write in and match it.""",

        'planning': """You are DreamPlanner, an expert in strategic planning and goal decomposition.

Your role:
1. Analyze the user's goal
2. Break it down into concrete, achievable steps
3. Account for time constraints and schedule
4. Propose a progressive and motivating plan

IMPORTANT: You must respond ONLY with a valid JSON object, NO text before or after.

Required JSON format:
{
  "analysis": "Brief analysis of the goal and its feasibility",
  "estimated_duration_weeks": 12,
  "weekly_time_hours": 5,
  "goals": [
    {
      "title": "Step title",
      "description": "Detailed description",
      "order": 1,
      "estimated_minutes": 300,
      "tasks": [
        {
          "title": "Specific task",
          "order": 1,
          "duration_mins": 30,
          "description": "Task description"
        }
      ]
    }
  ],
  "tips": ["Practical tip 1", "Practical tip 2"],
  "potential_obstacles": [
    {
      "title": "Possible obstacle",
      "solution": "How to overcome it"
    }
  ]
}""",

        'motivation': """You generate short, personalized motivational messages (1-2 sentences max).

Consider:
- The user's name
- Their progress level
- Their consecutive day streak
- The current goal

Your tone: energetic, encouraging, personal. Use emojis sparingly (1-2 max).
IMPORTANT: Respond in the user's language.""",

        'check_in': """You are DreamPlanner, performing a regular check-in with the user to:
1. Understand their progress
2. Identify difficulties
3. Adjust the plan if needed
4. Maintain motivation

Ask 1-2 open questions. Be empathetic and encouraging.
IMPORTANT: Respond in the user's language.""",

        'rescue': """You are DreamPlanner in "rescue mode" - the user has been inactive for several days.

Your role:
1. Show empathy (no guilt-tripping)
2. Understand what's blocking them
3. Suggest a simple action to restart
4. Remind them why it matters

Your message should be short (2-3 sentences), empathetic, and propose ONE concrete action.
IMPORTANT: Respond in the user's language.""",
    }

    def __init__(self):
        """Initialize OpenAI service with model and timeout from settings."""
        self.model = settings.OPENAI_MODEL
        self.timeout = getattr(settings, 'OPENAI_TIMEOUT', 30)

    def chat(self, messages, conversation_type='general', temperature=0.7, max_tokens=1000):
        """
        Synchronous chat completion.

        Args:
            messages: List of message dicts with 'role' and 'content'
            conversation_type: Key for system prompt selection
            temperature: Randomness (0-1)
            max_tokens: Maximum response tokens

        Returns:
            Dict with 'content', 'tokens_used', and 'model'
        """
        try:
            system_prompt = self.SYSTEM_PROMPTS.get(conversation_type, '')
            full_messages = [{'role': 'system', 'content': system_prompt}] + messages

            response = openai.ChatCompletion.create(
                model=self.model,
                messages=full_messages,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=self.timeout,
            )

            return {
                'content': response.choices[0].message.content,
                'tokens_used': response.usage.total_tokens,
                'model': response.model,
            }

        except openai.error.OpenAIError as e:
            raise OpenAIError(f"OpenAI API error: {str(e)}")
        except Exception as e:
            raise OpenAIError(f"Unexpected error: {str(e)}")

    async def chat_async(self, messages, conversation_type='general', temperature=0.7, max_tokens=1000):
        """Async version of chat completion."""
        try:
            system_prompt = self.SYSTEM_PROMPTS.get(conversation_type, '')
            full_messages = [{'role': 'system', 'content': system_prompt}] + messages

            response = await openai.ChatCompletion.acreate(
                model=self.model,
                messages=full_messages,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=self.timeout,
            )

            return {
                'content': response.choices[0].message.content,
                'tokens_used': response.usage.total_tokens,
                'model': response.model,
            }

        except openai.error.OpenAIError as e:
            raise OpenAIError(f"OpenAI API error: {str(e)}")
        except Exception as e:
            raise OpenAIError(f"Unexpected error: {str(e)}")

    async def chat_stream_async(self, messages, conversation_type='general', temperature=0.7):
        """
        Async streaming chat completion. Yields response chunks as they arrive.

        Yields:
            String chunks of the streamed response
        """
        try:
            system_prompt = self.SYSTEM_PROMPTS.get(conversation_type, '')
            full_messages = [{'role': 'system', 'content': system_prompt}] + messages

            response = await openai.ChatCompletion.acreate(
                model=self.model,
                messages=full_messages,
                temperature=temperature,
                stream=True,
                timeout=self.timeout,
            )

            async for chunk in response:
                if chunk.choices[0].delta.get('content'):
                    yield chunk.choices[0].delta.content

        except openai.error.OpenAIError as e:
            raise OpenAIError(f"OpenAI API error: {str(e)}")
        except Exception as e:
            raise OpenAIError(f"Unexpected error: {str(e)}")

    def generate_plan(self, dream_title, dream_description, user_context):
        """
        Generate a complete structured plan for a dream.

        Args:
            dream_title: Title of the dream/goal
            dream_description: Detailed description
            user_context: Dict with timezone, work_schedule, etc.

        Returns:
            Dict with structured plan including goals, tasks, tips, obstacles
        """
        prompt = f"""Generate a detailed plan to achieve this goal:

DREAM/GOAL: {dream_title}
DESCRIPTION: {dream_description}

USER CONTEXT:
- Timezone: {user_context.get('timezone', 'UTC')}
- Work schedule: {json.dumps(user_context.get('work_schedule', {}), ensure_ascii=False)}

Respond ONLY with the plan JSON."""

        try:
            response = openai.ChatCompletion.create(
                model=self.model,
                messages=[
                    {'role': 'system', 'content': self.SYSTEM_PROMPTS['planning']},
                    {'role': 'user', 'content': prompt}
                ],
                temperature=0.5,
                max_tokens=3000,
                response_format={"type": "json_object"},
                timeout=self.timeout,
            )

            content = response.choices[0].message.content
            plan = json.loads(content)

            return plan

        except json.JSONDecodeError as e:
            raise OpenAIError(f"Failed to parse JSON response: {str(e)}")
        except openai.error.OpenAIError as e:
            raise OpenAIError(f"OpenAI API error: {str(e)}")
        except Exception as e:
            raise OpenAIError(f"Unexpected error: {str(e)}")

    def analyze_dream(self, dream_title, dream_description):
        """
        Analyze a dream and extract category, difficulty, and recommendations.

        Returns:
            Dict with category, duration estimate, difficulty, challenges, approach
        """
        prompt = f"""Analyze this dream/goal and respond with JSON:

TITLE: {dream_title}
DESCRIPTION: {dream_description}

Required JSON format:
{{
  "category": "health|career|relationships|finance|personal_development|hobbies|other",
  "estimated_duration_weeks": 12,
  "difficulty": "easy|medium|hard",
  "key_challenges": ["Challenge 1", "Challenge 2"],
  "recommended_approach": "Recommended approach in 1-2 sentences"
}}"""

        try:
            response = openai.ChatCompletion.create(
                model=self.model,
                messages=[
                    {'role': 'system', 'content': 'You analyze goals and respond only in JSON.'},
                    {'role': 'user', 'content': prompt}
                ],
                temperature=0.3,
                max_tokens=500,
                response_format={"type": "json_object"},
                timeout=self.timeout,
            )

            return json.loads(response.choices[0].message.content)

        except (json.JSONDecodeError, openai.error.OpenAIError) as e:
            raise OpenAIError(f"Analysis failed: {str(e)}")

    def generate_motivational_message(self, user_name, goal_title, progress_percentage, streak_days):
        """Generate a short motivational message personalized for the user."""
        prompt = f"""User: {user_name}
Goal: {goal_title}
Progress: {progress_percentage}%
Streak: {streak_days} days

Generate a short motivational message (1-2 sentences, 1-2 emojis max)."""

        try:
            response = openai.ChatCompletion.create(
                model='gpt-3.5-turbo',  # Use cheaper model for short messages
                messages=[
                    {'role': 'system', 'content': self.SYSTEM_PROMPTS['motivation']},
                    {'role': 'user', 'content': prompt}
                ],
                temperature=0.8,
                max_tokens=60,
                timeout=self.timeout,
            )

            return response.choices[0].message.content

        except openai.error.OpenAIError as e:
            # Fallback message if API fails
            return f"Great job {user_name}! Keep going!"

    def generate_two_minute_start(self, dream_title, dream_description):
        """Generate a micro-action (30s-2min) to help the user get started."""
        prompt = f"""For the goal "{dream_title}" ({dream_description}), generate ONE very simple micro-action that takes 30 seconds to 2 minutes maximum. Respond with just the action, no explanation."""

        try:
            response = openai.ChatCompletion.create(
                model='gpt-3.5-turbo',
                messages=[
                    {'role': 'system', 'content': 'You generate quick micro-actions (30s-2min).'},
                    {'role': 'user', 'content': prompt}
                ],
                temperature=0.7,
                max_tokens=50,
                timeout=self.timeout,
            )

            return response.choices[0].message.content

        except openai.error.OpenAIError as e:
            # Fallback
            return "Take 2 minutes to write down 3 reasons why this goal is important to you"

    def generate_rescue_message(self, user_name, days_inactive, last_goal_title):
        """Generate an empathetic rescue message for inactive users."""
        prompt = f"""User {user_name} has been inactive for {days_inactive} days on their goal "{last_goal_title}".

Generate an empathetic message (2-3 sentences) that:
1. Does not guilt-trip
2. Acknowledges it's normal
3. Proposes ONE simple micro-action to restart"""

        try:
            response = openai.ChatCompletion.create(
                model='gpt-3.5-turbo',
                messages=[
                    {'role': 'system', 'content': self.SYSTEM_PROMPTS['rescue']},
                    {'role': 'user', 'content': prompt}
                ],
                temperature=0.7,
                max_tokens=150,
                timeout=self.timeout,
            )

            return response.choices[0].message.content

        except openai.error.OpenAIError:
            return f"Hey {user_name}, we're still here! Life is full of surprises, and that's okay. How about starting fresh with just 5 minutes today?"

    def generate_vision_image(self, dream_title, dream_description):
        """
        Generate a vision board image using DALL-E 3.

        Returns:
            URL of the generated image
        """
        prompt = f"""Create an inspiring, photorealistic image representing someone who has successfully achieved: {dream_title}. {dream_description}.

The image should be positive, motivating, and show the end result/success state. Photorealistic style, bright and inspiring."""

        try:
            response = openai.Image.create(
                model="dall-e-3",
                prompt=prompt,
                size="1024x1024",
                quality="standard",
                n=1,
            )

            return response.data[0].url

        except openai.error.OpenAIError as e:
            raise OpenAIError(f"Image generation failed: {str(e)}")
