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
import logging
from django.conf import settings
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from core.exceptions import OpenAIError

logger = logging.getLogger(__name__)

# Retry decorator for OpenAI calls
openai_retry = retry(
    retry=retry_if_exception_type(openai.error.OpenAIError),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    before_sleep=lambda retry_state: logger.warning(
        f"OpenAI call failed, retrying (attempt {retry_state.attempt_number})..."
    ),
)

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

    # --- Function definitions for AI-powered task creation ---
    FUNCTION_DEFINITIONS = [
        {
            "name": "create_task",
            "description": "Create a new task for the user's active goal",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Task title"},
                    "description": {"type": "string", "description": "Task description"},
                    "duration_mins": {"type": "integer", "description": "Estimated duration in minutes"},
                    "scheduled_date": {"type": "string", "description": "ISO date string for when to do it"},
                },
                "required": ["title"],
            },
        },
        {
            "name": "complete_task",
            "description": "Mark a task as completed",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "string", "description": "UUID of the task to complete"},
                },
                "required": ["task_id"],
            },
        },
        {
            "name": "create_goal",
            "description": "Create a new goal within a dream",
            "parameters": {
                "type": "object",
                "properties": {
                    "dream_id": {"type": "string", "description": "UUID of the dream"},
                    "title": {"type": "string", "description": "Goal title"},
                    "description": {"type": "string", "description": "Goal description"},
                    "order": {"type": "integer", "description": "Goal order number"},
                },
                "required": ["dream_id", "title"],
            },
        },
    ]

    @openai_retry
    def chat(self, messages, conversation_type='general', temperature=0.7, max_tokens=1000, functions=None):
        """
        Synchronous chat completion with optional function calling.

        Args:
            messages: List of message dicts with 'role' and 'content'
            conversation_type: Key for system prompt selection
            temperature: Randomness (0-1)
            max_tokens: Maximum response tokens
            functions: Optional list of function definitions for function calling

        Returns:
            Dict with 'content', 'tokens_used', 'model', and optionally 'function_call'
        """
        try:
            system_prompt = self.SYSTEM_PROMPTS.get(conversation_type, '')
            full_messages = [{'role': 'system', 'content': system_prompt}] + messages

            kwargs = {
                'model': self.model,
                'messages': full_messages,
                'temperature': temperature,
                'max_tokens': max_tokens,
                'timeout': self.timeout,
            }

            if functions:
                kwargs['functions'] = functions
                kwargs['function_call'] = 'auto'

            response = openai.ChatCompletion.create(**kwargs)

            result = {
                'content': response.choices[0].message.get('content', ''),
                'tokens_used': response.usage.total_tokens,
                'model': response.model,
            }

            # Check for function call
            if response.choices[0].message.get('function_call'):
                fc = response.choices[0].message['function_call']
                result['function_call'] = {
                    'name': fc['name'],
                    'arguments': json.loads(fc['arguments']),
                }

            return result

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

    @openai_retry
    def generate_plan(self, dream_title, dream_description, user_context):
        """
        Generate a complete structured plan for a dream.

        If calibration data is present in user_context, uses the enriched profile
        for highly personalized plan generation.

        Args:
            dream_title: Title of the dream/goal
            dream_description: Detailed description
            user_context: Dict with timezone, work_schedule, etc.

        Returns:
            Dict with structured plan including goals, tasks, tips, obstacles
        """
        # Build calibration context if available
        calibration_section = ""
        if user_context.get('calibration_profile'):
            profile = user_context['calibration_profile']
            recommendations = user_context.get('plan_recommendations', {})
            enriched = user_context.get('enriched_description', '')

            calibration_section = f"""
CALIBRATION PROFILE (from user interview):
- Experience Level: {profile.get('experience_level', 'unknown')}
- Experience Details: {profile.get('experience_details', 'N/A')}
- Available Hours/Week: {profile.get('available_hours_per_week', 'unknown')}
- Preferred Schedule: {profile.get('preferred_schedule', 'N/A')}
- Budget: {profile.get('budget', 'N/A')}
- Tools Available: {', '.join(profile.get('tools_available', []))}
- Primary Motivation: {profile.get('primary_motivation', 'N/A')}
- Known Constraints: {', '.join(profile.get('known_constraints', []))}
- Success Definition: {profile.get('success_definition', 'N/A')}
- Preferred Learning Style: {profile.get('preferred_learning_style', 'N/A')}
- Timeline: {profile.get('timeline_preference', 'N/A')}
- Risk Tolerance: {profile.get('risk_tolerance', 'medium')}

PLAN RECOMMENDATIONS:
- Suggested Pace: {recommendations.get('suggested_pace', 'moderate')}
- Focus Areas: {', '.join(recommendations.get('focus_areas', []))}
- Potential Pitfalls: {', '.join(recommendations.get('potential_pitfalls', []))}
- Personalization Notes: {recommendations.get('personalization_notes', 'N/A')}

ENRICHED DREAM DESCRIPTION:
{enriched or dream_description}

IMPORTANT: Use ALL the calibration data above to create a HIGHLY PERSONALIZED plan.
- Match task durations to the user's available hours/week
- Respect their constraints and budget
- Align with their preferred learning style
- Set pace according to their timeline and risk tolerance
- Address their specific potential pitfalls proactively"""

        prompt = f"""Generate a detailed plan to achieve this goal:

DREAM/GOAL: {dream_title}
DESCRIPTION: {dream_description}

USER CONTEXT:
- Timezone: {user_context.get('timezone', 'UTC')}
- Work schedule: {json.dumps(user_context.get('work_schedule', {}), ensure_ascii=False)}
{calibration_section}

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

    def generate_calibration_questions(self, dream_title, dream_description, existing_qa=None, batch_size=7):
        """
        Generate calibration questions to deeply understand the user's dream.

        First call generates 7 initial questions. Subsequent calls generate
        follow-up questions based on previous answers (up to 15 total).

        Args:
            dream_title: Title of the dream/goal
            dream_description: User's initial description
            existing_qa: List of dicts with 'question' and 'answer' keys (previous Q&A pairs)
            batch_size: Number of questions to generate (7 for initial, varies for follow-ups)

        Returns:
            Dict with 'questions' list and 'sufficient' boolean
        """
        if existing_qa:
            qa_context = "\n".join([
                f"Q{i+1}: {qa['question']}\nA{i+1}: {qa['answer']}"
                for i, qa in enumerate(existing_qa)
            ])
            prompt = f"""The user wants to achieve this dream/goal:
TITLE: {dream_title}
DESCRIPTION: {dream_description}

Here are the calibration questions already asked and answered:
{qa_context}

Based on the answers above, determine:
1. Do you have ENOUGH information to create a highly personalized, detailed plan? Consider whether you understand their current level, time availability, specific preferences, constraints, resources, and deep motivations.
2. If NOT sufficient, generate {batch_size} MORE follow-up questions that dig deeper into gaps or vague answers.
3. If sufficient, set "sufficient" to true and return an empty questions array.

IMPORTANT: Be thorough. Vague answers like "some experience" or "a few hours" need follow-up. You need concrete, actionable details.

Respond ONLY with JSON:
{{
  "sufficient": false,
  "confidence_score": 0.7,
  "missing_areas": ["specific area needing more info"],
  "questions": [
    {{
      "question": "The question text",
      "category": "experience|timeline|resources|motivation|constraints|specifics|lifestyle|preferences"
    }}
  ]
}}"""
        else:
            prompt = f"""The user wants to achieve this dream/goal:
TITLE: {dream_title}
DESCRIPTION: {dream_description}

Generate exactly {batch_size} calibration questions to deeply understand what the user truly wants. These questions should cover:

1. **Experience Level** - What is their current level/background related to this dream?
2. **Timeline** - When do they want to achieve this? Any deadlines?
3. **Time Availability** - How many hours per day/week can they dedicate? When are they free?
4. **Resources** - What budget, tools, or resources do they have access to?
5. **Motivation** - Why is this dream important? What's driving them?
6. **Constraints** - What obstacles, limitations, or challenges do they foresee?
7. **Specifics** - What exact outcome do they envision? What does "success" look like concretely?

Each question should be clear, specific, and conversational (not robotic). Ask ONE thing per question.

Respond ONLY with JSON:
{{
  "sufficient": false,
  "confidence_score": 0.1,
  "questions": [
    {{
      "question": "The question text",
      "category": "experience|timeline|resources|motivation|constraints|specifics|lifestyle|preferences"
    }}
  ]
}}"""

        try:
            response = openai.ChatCompletion.create(
                model=self.model,
                messages=[
                    {
                        'role': 'system',
                        'content': 'You are a skilled life coach and project planner. Your job is to ask the RIGHT questions to truly understand someone\'s goal before creating a plan. Ask questions that reveal hidden assumptions, unstated preferences, and concrete details. Never accept vague answers - always dig deeper. Respond only in JSON.'
                    },
                    {'role': 'user', 'content': prompt}
                ],
                temperature=0.6,
                max_tokens=2000,
                response_format={"type": "json_object"},
                timeout=self.timeout,
            )

            result = json.loads(response.choices[0].message.content)
            return result

        except (json.JSONDecodeError, openai.error.OpenAIError) as e:
            raise OpenAIError(f"Calibration question generation failed: {str(e)}")

    def generate_calibration_summary(self, dream_title, dream_description, qa_pairs):
        """
        Generate a rich summary from calibration Q&A to feed into plan generation.

        Args:
            dream_title: Title of the dream/goal
            dream_description: User's initial description
            qa_pairs: List of dicts with 'question' and 'answer' keys

        Returns:
            Dict with structured user profile for plan generation
        """
        qa_text = "\n".join([
            f"Q: {qa['question']}\nA: {qa['answer']}"
            for qa in qa_pairs
        ])

        prompt = f"""Based on the following dream and calibration interview, create a structured user profile for personalized plan generation.

DREAM: {dream_title}
DESCRIPTION: {dream_description}

CALIBRATION INTERVIEW:
{qa_text}

Create a structured JSON profile that captures everything needed for a highly personalized plan:

{{
  "user_profile": {{
    "experience_level": "beginner|intermediate|advanced",
    "experience_details": "Specific details about their background",
    "available_hours_per_week": 10,
    "preferred_schedule": "Description of when they're free",
    "budget": "Description of financial resources",
    "tools_available": ["list of tools/resources they have"],
    "primary_motivation": "Their core why",
    "secondary_motivations": ["other motivating factors"],
    "known_constraints": ["specific limitations"],
    "success_definition": "What success looks like concretely to them",
    "preferred_learning_style": "How they prefer to learn/work",
    "timeline_preference": "Their desired timeline",
    "risk_tolerance": "low|medium|high"
  }},
  "plan_recommendations": {{
    "suggested_pace": "aggressive|moderate|relaxed",
    "focus_areas": ["areas to prioritize based on their answers"],
    "potential_pitfalls": ["likely challenges based on their profile"],
    "personalization_notes": "Key things to customize in the plan"
  }},
  "enriched_description": "A much richer, more detailed version of their dream description incorporating all calibration data"
}}"""

        try:
            response = openai.ChatCompletion.create(
                model=self.model,
                messages=[
                    {
                        'role': 'system',
                        'content': 'You are an expert at synthesizing interview data into actionable profiles. Extract maximum insight from the Q&A pairs and create a comprehensive profile. Respond only in JSON.'
                    },
                    {'role': 'user', 'content': prompt}
                ],
                temperature=0.3,
                max_tokens=1500,
                response_format={"type": "json_object"},
                timeout=self.timeout,
            )

            return json.loads(response.choices[0].message.content)

        except (json.JSONDecodeError, openai.error.OpenAIError) as e:
            raise OpenAIError(f"Calibration summary generation failed: {str(e)}")

    @openai_retry
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

    @openai_retry
    def transcribe_audio(self, audio_file_path):
        """
        Transcribe an audio file using OpenAI Whisper API.

        Args:
            audio_file_path: Path to the audio file on disk.

        Returns:
            Dict with 'text' (transcription) and 'language'.
        """
        try:
            with open(audio_file_path, 'rb') as audio_file:
                response = openai.Audio.transcribe(
                    model='whisper-1',
                    file=audio_file,
                    response_format='verbose_json',
                    timeout=self.timeout,
                )

            return {
                'text': response.get('text', ''),
                'language': response.get('language', ''),
            }

        except openai.error.OpenAIError as e:
            raise OpenAIError(f"Audio transcription failed: {str(e)}")
        except FileNotFoundError:
            raise OpenAIError(f"Audio file not found: {audio_file_path}")

    @openai_retry
    def analyze_image(self, image_url, user_prompt=''):
        """
        Analyze an image using GPT-4 Vision.

        Args:
            image_url: URL of the image to analyze.
            user_prompt: Optional user message to accompany the image.

        Returns:
            Dict with 'content' and 'tokens_used'.
        """
        try:
            user_content = [
                {
                    'type': 'image_url',
                    'image_url': {'url': image_url},
                },
            ]
            if user_prompt:
                user_content.insert(0, {'type': 'text', 'text': user_prompt})
            else:
                user_content.insert(0, {
                    'type': 'text',
                    'text': 'Describe this image and how it relates to the user\'s goals or dreams. Provide motivational insights if relevant.',
                })

            response = openai.ChatCompletion.create(
                model='gpt-4-vision-preview',
                messages=[
                    {
                        'role': 'system',
                        'content': 'You are DreamPlanner, a helpful assistant. Analyze images the user shares and relate them to their personal goals and dreams.',
                    },
                    {
                        'role': 'user',
                        'content': user_content,
                    },
                ],
                max_tokens=500,
                timeout=self.timeout,
            )

            return {
                'content': response.choices[0].message.content,
                'tokens_used': response.usage.total_tokens,
            }

        except openai.error.OpenAIError as e:
            raise OpenAIError(f"Image analysis failed: {str(e)}")

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
