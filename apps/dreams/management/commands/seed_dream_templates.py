"""Management command to seed dream templates."""

from django.core.management.base import BaseCommand
from apps.dreams.models import DreamTemplate


class Command(BaseCommand):
    help = 'Seed dream templates for all 8 categories'

    def handle(self, *args, **options):
        templates = [
            {
                'title': 'Run a Marathon',
                'description': 'Train progressively to complete a full 42km marathon. From couch to finish line with structured training.',
                'category': 'health',
                'difficulty': 'advanced',
                'estimated_duration_days': 180,
                'icon': 'running',
                'is_featured': True,
                'template_goals': [
                    {'title': 'Build base fitness', 'description': 'Establish a running routine', 'order': 1, 'tasks': [
                        {'title': 'Run 2km three times this week', 'order': 1, 'duration_mins': 20},
                        {'title': 'Do stretching routine after each run', 'order': 2, 'duration_mins': 10},
                        {'title': 'Track runs in a journal', 'order': 3, 'duration_mins': 5},
                    ]},
                    {'title': 'Increase distance', 'description': 'Progressively increase weekly distance', 'order': 2, 'tasks': [
                        {'title': 'Run 5km twice this week', 'order': 1, 'duration_mins': 35},
                        {'title': 'One long run of 8km this week', 'order': 2, 'duration_mins': 55},
                        {'title': 'Cross-train with cycling or swimming', 'order': 3, 'duration_mins': 45},
                    ]},
                    {'title': 'Race preparation', 'description': 'Taper and prepare for race day', 'order': 3, 'tasks': [
                        {'title': 'Register for the marathon event', 'order': 1, 'duration_mins': 15},
                        {'title': 'Do a half-marathon practice run', 'order': 2, 'duration_mins': 120},
                        {'title': 'Plan race day nutrition and gear', 'order': 3, 'duration_mins': 30},
                    ]},
                ],
            },
            {
                'title': 'Get a Promotion',
                'description': 'Strategically position yourself for a career advancement within your current company.',
                'category': 'career',
                'difficulty': 'intermediate',
                'estimated_duration_days': 120,
                'icon': 'briefcase',
                'is_featured': True,
                'template_goals': [
                    {'title': 'Assess current position', 'description': 'Understand what is needed for advancement', 'order': 1, 'tasks': [
                        {'title': 'Research the requirements for the next role', 'order': 1, 'duration_mins': 30},
                        {'title': 'Schedule a 1-on-1 with your manager', 'order': 2, 'duration_mins': 30},
                        {'title': 'Identify skill gaps', 'order': 3, 'duration_mins': 20},
                    ]},
                    {'title': 'Build visibility', 'description': 'Increase your visibility within the organization', 'order': 2, 'tasks': [
                        {'title': 'Volunteer for a high-visibility project', 'order': 1, 'duration_mins': 15},
                        {'title': 'Present at a team meeting', 'order': 2, 'duration_mins': 45},
                        {'title': 'Document your achievements', 'order': 3, 'duration_mins': 20},
                    ]},
                    {'title': 'Make the ask', 'description': 'Formally request the promotion', 'order': 3, 'tasks': [
                        {'title': 'Prepare a promotion case document', 'order': 1, 'duration_mins': 60},
                        {'title': 'Schedule a formal review meeting', 'order': 2, 'duration_mins': 10},
                        {'title': 'Negotiate salary and title', 'order': 3, 'duration_mins': 30},
                    ]},
                ],
            },
            {
                'title': 'Learn a New Language',
                'description': 'Achieve conversational fluency in a new language through daily practice and immersion.',
                'category': 'education',
                'difficulty': 'intermediate',
                'estimated_duration_days': 180,
                'icon': 'book-open',
                'is_featured': True,
                'template_goals': [
                    {'title': 'Build vocabulary foundation', 'description': 'Learn 500 essential words', 'order': 1, 'tasks': [
                        {'title': 'Study 20 new words with flashcards', 'order': 1, 'duration_mins': 20},
                        {'title': 'Practice pronunciation with audio', 'order': 2, 'duration_mins': 15},
                        {'title': 'Complete a grammar lesson', 'order': 3, 'duration_mins': 25},
                    ]},
                    {'title': 'Start conversations', 'description': 'Practice speaking with natives', 'order': 2, 'tasks': [
                        {'title': 'Have a 15-minute conversation exchange', 'order': 1, 'duration_mins': 15},
                        {'title': 'Watch a show in the target language', 'order': 2, 'duration_mins': 30},
                        {'title': 'Write a short journal entry in the language', 'order': 3, 'duration_mins': 15},
                    ]},
                    {'title': 'Achieve fluency goals', 'description': 'Pass a language proficiency test', 'order': 3, 'tasks': [
                        {'title': 'Take a practice proficiency test', 'order': 1, 'duration_mins': 60},
                        {'title': 'Read an article without translation', 'order': 2, 'duration_mins': 30},
                        {'title': 'Have a 30-minute conversation without pausing', 'order': 3, 'duration_mins': 30},
                    ]},
                ],
            },
            {
                'title': 'Save an Emergency Fund',
                'description': 'Build a 6-month emergency fund through systematic saving and expense optimization.',
                'category': 'finance',
                'difficulty': 'beginner',
                'estimated_duration_days': 180,
                'icon': 'piggy-bank',
                'is_featured': False,
                'template_goals': [
                    {'title': 'Analyze finances', 'description': 'Understand your current financial situation', 'order': 1, 'tasks': [
                        {'title': 'Calculate monthly expenses', 'order': 1, 'duration_mins': 30},
                        {'title': 'Set a target emergency fund amount', 'order': 2, 'duration_mins': 15},
                        {'title': 'Identify areas to cut spending', 'order': 3, 'duration_mins': 20},
                    ]},
                    {'title': 'Automate savings', 'description': 'Set up automatic transfers', 'order': 2, 'tasks': [
                        {'title': 'Open a high-yield savings account', 'order': 1, 'duration_mins': 20},
                        {'title': 'Set up automatic monthly transfer', 'order': 2, 'duration_mins': 10},
                        {'title': 'Review and adjust budget weekly', 'order': 3, 'duration_mins': 15},
                    ]},
                    {'title': 'Reach the goal', 'description': 'Complete the emergency fund', 'order': 3, 'tasks': [
                        {'title': 'Track progress monthly', 'order': 1, 'duration_mins': 10},
                        {'title': 'Find one additional income source', 'order': 2, 'duration_mins': 30},
                        {'title': 'Celebrate reaching the milestone', 'order': 3, 'duration_mins': 15},
                    ]},
                ],
            },
            {
                'title': 'Write a Novel',
                'description': 'Complete the first draft of a novel through consistent daily writing sessions.',
                'category': 'creative',
                'difficulty': 'advanced',
                'estimated_duration_days': 120,
                'icon': 'pen-tool',
                'is_featured': True,
                'template_goals': [
                    {'title': 'Outline and plan', 'description': 'Create the story structure', 'order': 1, 'tasks': [
                        {'title': 'Define main characters and their arcs', 'order': 1, 'duration_mins': 45},
                        {'title': 'Outline chapter by chapter', 'order': 2, 'duration_mins': 60},
                        {'title': 'Set a daily word count target', 'order': 3, 'duration_mins': 10},
                    ]},
                    {'title': 'Write the first draft', 'description': 'Hit 50,000 words', 'order': 2, 'tasks': [
                        {'title': 'Write 1,000 words today', 'order': 1, 'duration_mins': 60},
                        {'title': 'Review and revise yesterday\'s writing', 'order': 2, 'duration_mins': 30},
                        {'title': 'Research a topic for an upcoming chapter', 'order': 3, 'duration_mins': 20},
                    ]},
                    {'title': 'Revise and polish', 'description': 'Edit the complete manuscript', 'order': 3, 'tasks': [
                        {'title': 'Read through the entire draft', 'order': 1, 'duration_mins': 120},
                        {'title': 'Revise one chapter', 'order': 2, 'duration_mins': 60},
                        {'title': 'Get feedback from a beta reader', 'order': 3, 'duration_mins': 30},
                    ]},
                ],
            },
            {
                'title': 'Build a Morning Routine',
                'description': 'Design and stick to a powerful morning routine that sets you up for success every day.',
                'category': 'personal',
                'difficulty': 'beginner',
                'estimated_duration_days': 30,
                'icon': 'sunrise',
                'is_featured': False,
                'template_goals': [
                    {'title': 'Design the routine', 'description': 'Plan your ideal morning', 'order': 1, 'tasks': [
                        {'title': 'Research morning routine ideas', 'order': 1, 'duration_mins': 20},
                        {'title': 'Write out your ideal morning hour by hour', 'order': 2, 'duration_mins': 15},
                        {'title': 'Prepare everything the night before', 'order': 3, 'duration_mins': 15},
                    ]},
                    {'title': 'Build the habit', 'description': 'Practice for 21 days', 'order': 2, 'tasks': [
                        {'title': 'Wake up at target time', 'order': 1, 'duration_mins': 5},
                        {'title': 'Complete morning routine', 'order': 2, 'duration_mins': 60},
                        {'title': 'Rate how the morning went (1-10)', 'order': 3, 'duration_mins': 5},
                    ]},
                ],
            },
            {
                'title': 'Strengthen Relationships',
                'description': 'Deepen connections with family and friends through intentional quality time.',
                'category': 'social',
                'difficulty': 'beginner',
                'estimated_duration_days': 60,
                'icon': 'heart',
                'is_featured': False,
                'template_goals': [
                    {'title': 'Reconnect', 'description': 'Reach out to people you have lost touch with', 'order': 1, 'tasks': [
                        {'title': 'Make a list of 10 people to reconnect with', 'order': 1, 'duration_mins': 15},
                        {'title': 'Send a message to 3 people today', 'order': 2, 'duration_mins': 15},
                        {'title': 'Schedule a catch-up call or coffee', 'order': 3, 'duration_mins': 10},
                    ]},
                    {'title': 'Quality time', 'description': 'Plan meaningful experiences', 'order': 2, 'tasks': [
                        {'title': 'Plan a special activity with a loved one', 'order': 1, 'duration_mins': 15},
                        {'title': 'Have a deep conversation (no phones)', 'order': 2, 'duration_mins': 30},
                        {'title': 'Write a heartfelt note to someone', 'order': 3, 'duration_mins': 15},
                    ]},
                ],
            },
            {
                'title': 'Plan a Dream Trip',
                'description': 'Research, budget, and plan the trip of a lifetime step by step.',
                'category': 'travel',
                'difficulty': 'intermediate',
                'estimated_duration_days': 90,
                'icon': 'globe',
                'is_featured': True,
                'template_goals': [
                    {'title': 'Research destination', 'description': 'Choose and research your destination', 'order': 1, 'tasks': [
                        {'title': 'Research top 3 destination options', 'order': 1, 'duration_mins': 30},
                        {'title': 'Set a travel budget', 'order': 2, 'duration_mins': 20},
                        {'title': 'Choose dates and check visa requirements', 'order': 3, 'duration_mins': 20},
                    ]},
                    {'title': 'Book essentials', 'description': 'Book flights, accommodation, and activities', 'order': 2, 'tasks': [
                        {'title': 'Book flights', 'order': 1, 'duration_mins': 30},
                        {'title': 'Book accommodation', 'order': 2, 'duration_mins': 30},
                        {'title': 'Create a day-by-day itinerary', 'order': 3, 'duration_mins': 45},
                    ]},
                    {'title': 'Prepare for departure', 'description': 'Final preparations', 'order': 3, 'tasks': [
                        {'title': 'Pack essentials checklist', 'order': 1, 'duration_mins': 30},
                        {'title': 'Download offline maps and guides', 'order': 2, 'duration_mins': 15},
                        {'title': 'Notify bank and set up travel insurance', 'order': 3, 'duration_mins': 20},
                    ]},
                ],
            },
        ]

        count = 0
        for t in templates:
            _, created = DreamTemplate.objects.update_or_create(
                title=t['title'],
                defaults=t,
            )
            action = 'Created' if created else 'Updated'
            self.stdout.write(f'  {action}: {t["title"]} ({t["category"]})')
            count += 1

        self.stdout.write(self.style.SUCCESS(f'Seeded {count} dream templates.'))
