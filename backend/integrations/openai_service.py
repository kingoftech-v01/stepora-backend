"""
OpenAI GPT-4 integration service for AI features.
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
    """Service for interacting with OpenAI API."""

    # System prompts for different conversation types
    SYSTEM_PROMPTS = {
        'dream_creation': """Tu es DreamPlanner, un assistant personnel bienveillant et motivant qui aide les utilisateurs à transformer leurs rêves en plans d'action concrets.

Ton rôle dans la création d'un rêve:
1. Écoute activement et pose des questions de clarification
2. Aide à définir un objectif SMART (Spécifique, Mesurable, Atteignable, Réaliste, Temporel)
3. Explore les motivations profondes
4. Identifie les obstacles potentiels
5. Encourage et motive

Ton ton: empathique, positif, encourageant mais réaliste.
Réponds en français de manière concise (2-3 phrases maximum).""",

        'planning': """Tu es DreamPlanner, un expert en planification stratégique et décomposition d'objectifs.

Ton rôle:
1. Analyser l'objectif de l'utilisateur
2. Le décomposer en étapes concrètes et réalisables
3. Tenir compte des contraintes de temps et d'emploi du temps
4. Proposer un plan progressif et motivant

IMPORTANT: Tu dois répondre UNIQUEMENT avec un objet JSON valide, SANS texte avant ou après.

Format JSON requis:
{
  "analysis": "Analyse brève de l'objectif et sa faisabilité",
  "estimated_duration_weeks": 12,
  "weekly_time_hours": 5,
  "goals": [
    {
      "title": "Titre de l'étape",
      "description": "Description détaillée",
      "order": 1,
      "estimated_minutes": 300,
      "tasks": [
        {
          "title": "Tâche spécifique",
          "order": 1,
          "duration_mins": 30,
          "description": "Description de la tâche"
        }
      ]
    }
  ],
  "tips": ["Conseil pratique 1", "Conseil pratique 2"],
  "potential_obstacles": [
    {
      "title": "Obstacle possible",
      "solution": "Comment le surmonter"
    }
  ]
}""",

        'motivation': """Tu génères des messages de motivation courts et personnalisés (1-2 phrases maximum).

Prends en compte:
- Le prénom de l'utilisateur
- Son niveau de progression
- Sa série de jours consécutifs
- L'objectif en cours

Ton ton: énergique, encourageant, personnel. Utilise des emojis avec parcimonie (1-2 max).""",

        'check_in': """Tu es DreamPlanner, tu fais un check-in régulier avec l'utilisateur pour:
1. Comprendre sa progression
2. Identifier les difficultés
3. Ajuster le plan si nécessaire
4. Maintenir la motivation

Pose 1-2 questions ouvertes. Sois empathique et encourageant.""",

        'rescue': """Tu es DreamPlanner en "mode rescue" - l'utilisateur est inactif depuis plusieurs jours.

Ton rôle:
1. Montrer de l'empathie (pas de culpabilisation)
2. Comprendre ce qui bloque
3. Proposer une action simple pour redémarrer
4. Rappeler pourquoi c'est important

Ton message doit être court (2-3 phrases), empathique et proposer UNE action concrète.""",
    }

    def __init__(self):
        """Initialize OpenAI service."""
        self.model = settings.OPENAI_MODEL
        self.timeout = getattr(settings, 'OPENAI_TIMEOUT', 30)

    def chat(self, messages, conversation_type='general', temperature=0.7, max_tokens=1000):
        """
        Synchronous chat completion.

        Args:
            messages: List of message dictionaries with 'role' and 'content'
            conversation_type: Type of conversation for system prompt
            temperature: Randomness (0-1)
            max_tokens: Maximum tokens in response

        Returns:
            Dict with 'content' and 'tokens_used'
        """
        try:
            # Add system prompt
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
        """Async version of chat."""
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
        Async streaming chat completion.

        Yields:
            String chunks of the response
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
        Generate complete plan for a dream.

        Args:
            dream_title: Title of the dream
            dream_description: Description of the dream
            user_context: Dict with user info (work_schedule, timezone, etc.)

        Returns:
            Dict with plan structure
        """
        prompt = f"""Génère un plan détaillé pour atteindre cet objectif:

RÊVE/OBJECTIF: {dream_title}
DESCRIPTION: {dream_description}

CONTEXTE UTILISATEUR:
- Fuseau horaire: {user_context.get('timezone', 'Europe/Paris')}
- Horaires de travail: {json.dumps(user_context.get('work_schedule', {}), ensure_ascii=False)}

Réponds UNIQUEMENT avec le JSON du plan."""

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
        Analyze a dream and extract key information.

        Returns:
            Dict with analysis results
        """
        prompt = f"""Analyse ce rêve/objectif et réponds avec un JSON:

TITRE: {dream_title}
DESCRIPTION: {dream_description}

Format JSON requis:
{{
  "category": "santé|carrière|relations|finances|développement_personnel|loisirs|autre",
  "estimated_duration_weeks": 12,
  "difficulty": "facile|moyen|difficile",
  "key_challenges": ["Défi 1", "Défi 2"],
  "recommended_approach": "Approche recommandée en 1-2 phrases"
}}"""

        try:
            response = openai.ChatCompletion.create(
                model=self.model,
                messages=[
                    {'role': 'system', 'content': 'Tu analyses des objectifs et réponds uniquement en JSON.'},
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
        """Generate short motivational message."""
        prompt = f"""Utilisateur: {user_name}
Objectif: {goal_title}
Progression: {progress_percentage}%
Série: {streak_days} jours

Génère un message de motivation court (1-2 phrases, 1-2 emojis max)."""

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
            return f"Bravo {user_name}! Continue comme ça! 💪"

    def generate_two_minute_start(self, dream_title, dream_description):
        """Generate a 2-minute micro-action to start."""
        prompt = f"""Pour l'objectif "{dream_title}" ({dream_description}), génère UNE micro-action très simple qui prend 30 secondes à 2 minutes maximum. Réponds avec juste l'action, sans explication."""

        try:
            response = openai.ChatCompletion.create(
                model='gpt-3.5-turbo',
                messages=[
                    {'role': 'system', 'content': 'Tu génères des micro-actions rapides (30s-2min).'},
                    {'role': 'user', 'content': prompt}
                ],
                temperature=0.7,
                max_tokens=50,
                timeout=self.timeout,
            )

            return response.choices[0].message.content

        except openai.error.OpenAIError as e:
            # Fallback
            return "Prends 2 minutes pour noter 3 raisons pourquoi cet objectif est important pour toi"

    def generate_rescue_message(self, user_name, days_inactive, last_goal_title):
        """Generate rescue message for inactive users."""
        prompt = f"""L'utilisateur {user_name} est inactif depuis {days_inactive} jours sur son objectif "{last_goal_title}".

Génère un message empathique (2-3 phrases) qui:
1. Ne culpabilise pas
2. Comprend que c'est normal
3. Propose UNE micro-action simple pour redémarrer"""

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
            return f"Hey {user_name}, on est toujours là! La vie est pleine d'imprévus, c'est normal. Que dirais-tu de recommencer doucement avec juste 5 minutes aujourd'hui? 💪"

    def generate_vision_image(self, dream_title, dream_description):
        """
        Generate vision board image with DALL-E.

        Returns:
            URL of generated image
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
