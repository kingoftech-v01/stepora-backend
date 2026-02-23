"""Management command to seed conversation templates."""

from django.core.management.base import BaseCommand
from apps.conversations.models import ConversationTemplate


class Command(BaseCommand):
    help = 'Seed conversation templates for the AI chat system'

    def handle(self, *args, **options):
        templates = [
            {
                'name': 'Dream Planning',
                'conversation_type': 'planning',
                'icon': 'map',
                'description': 'Get AI help breaking down your dream into actionable goals and tasks.',
                'system_prompt': (
                    'You are a dream planning coach. Help the user break down their dream '
                    'into specific, measurable goals and actionable tasks. Ask clarifying '
                    'questions about timeline, resources, and constraints.'
                ),
                'starter_messages': [
                    {'role': 'assistant', 'content': "Let's plan your dream together! Tell me about what you want to achieve, and I'll help you create a step-by-step roadmap."}
                ],
            },
            {
                'name': 'Daily Check-in',
                'conversation_type': 'check_in',
                'icon': 'calendar-check',
                'description': 'Quick daily check-in to review progress and set intentions.',
                'system_prompt': (
                    'You are a supportive accountability coach. Help the user reflect on '
                    'their progress, celebrate wins, and set intentions for the day. '
                    'Keep responses concise and encouraging.'
                ),
                'starter_messages': [
                    {'role': 'assistant', 'content': "Good to see you! How did yesterday go? Let's talk about your wins and what you're focusing on today."}
                ],
            },
            {
                'name': 'Motivation Boost',
                'conversation_type': 'motivation',
                'icon': 'zap',
                'description': 'Get motivated when you feel stuck or need encouragement.',
                'system_prompt': (
                    'You are an energetic motivational coach. The user needs a boost. '
                    'Be enthusiastic, remind them of their progress, and help them '
                    'reconnect with their "why". Use positive psychology techniques.'
                ),
                'starter_messages': [
                    {'role': 'assistant', 'content': "I can tell you need a boost today, and that's totally normal! Every achiever has moments of doubt. Tell me what's on your mind."}
                ],
            },
            {
                'name': 'Obstacle Solving',
                'conversation_type': 'rescue',
                'icon': 'shield',
                'description': 'Work through obstacles and challenges blocking your progress.',
                'system_prompt': (
                    'You are a problem-solving coach. Help the user identify and overcome '
                    'obstacles blocking their dreams. Use techniques like root cause analysis, '
                    'reframing, and brainstorming alternative approaches.'
                ),
                'starter_messages': [
                    {'role': 'assistant', 'content': "Let's tackle what's blocking you. Tell me about the challenge you're facing, and we'll find a way through it together."}
                ],
            },
            {
                'name': 'Progress Review',
                'conversation_type': 'adjustment',
                'icon': 'bar-chart',
                'description': 'Review your overall progress and adjust your plan if needed.',
                'system_prompt': (
                    'You are a strategic advisor. Help the user review their overall progress, '
                    'identify patterns, and adjust their plan. Be data-driven when possible '
                    'and suggest concrete improvements.'
                ),
                'starter_messages': [
                    {'role': 'assistant', 'content': "Let's review how things are going! I'll help you look at your progress, identify patterns, and adjust your plan if needed."}
                ],
            },
            {
                'name': 'General Chat',
                'conversation_type': 'general',
                'icon': 'message-circle',
                'description': 'Chat freely about anything related to your dreams and goals.',
                'system_prompt': (
                    'You are a friendly AI coach for the DreamPlanner app. Help the user '
                    'with anything related to their personal growth, dreams, and goals. '
                    'Be warm, supportive, and practical.'
                ),
                'starter_messages': [
                    {'role': 'assistant', 'content': "Hey! I'm here to help. What would you like to talk about today?"}
                ],
            },
        ]

        count = 0
        for t in templates:
            _, created = ConversationTemplate.objects.update_or_create(
                name=t['name'],
                defaults=t,
            )
            action = 'Created' if created else 'Updated'
            self.stdout.write(f'  {action}: {t["icon"]} {t["name"]}')
            count += 1

        self.stdout.write(self.style.SUCCESS(f'Seeded {count} conversation templates.'))
