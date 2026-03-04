"""Management command to seed dream templates."""

from django.core.management.base import BaseCommand
from apps.dreams.models import DreamTemplate


class Command(BaseCommand):
    help = 'Seed 12 dream templates covering all major categories'

    def handle(self, *args, **options):
        templates = [
            # ── Health (2) ──────────────────────────────────────────
            {
                'title': 'Run a Marathon',
                'description': 'Train progressively to complete a full 42km marathon. From couch to finish line with structured training.',
                'category': 'health',
                'difficulty': 'advanced',
                'estimated_duration_days': 180,
                'suggested_timeline': '6 months',
                'icon': 'running',
                'color': '#EF4444',
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
                'title': 'Build a Meditation Practice',
                'description': 'Develop a consistent daily meditation habit starting from just 5 minutes a day, building up to 30-minute sessions.',
                'category': 'health',
                'difficulty': 'beginner',
                'estimated_duration_days': 60,
                'suggested_timeline': '2 months',
                'icon': 'brain',
                'color': '#10B981',
                'is_featured': False,
                'template_goals': [
                    {'title': 'Start with 5-minute sessions', 'description': 'Build the daily habit with short sessions', 'order': 1, 'tasks': [
                        {'title': 'Download a meditation app', 'order': 1, 'duration_mins': 10},
                        {'title': 'Meditate for 5 minutes', 'order': 2, 'duration_mins': 5},
                        {'title': 'Journal how you feel after each session', 'order': 3, 'duration_mins': 5},
                    ]},
                    {'title': 'Extend to 15 minutes', 'description': 'Gradually increase session length', 'order': 2, 'tasks': [
                        {'title': 'Try a guided body scan meditation', 'order': 1, 'duration_mins': 15},
                        {'title': 'Practice breathing exercises', 'order': 2, 'duration_mins': 10},
                        {'title': 'Meditate without guidance for 10 minutes', 'order': 3, 'duration_mins': 10},
                    ]},
                    {'title': 'Reach 30-minute sessions', 'description': 'Sustain longer focused meditation', 'order': 3, 'tasks': [
                        {'title': 'Complete a 30-minute seated meditation', 'order': 1, 'duration_mins': 30},
                        {'title': 'Try a walking meditation outdoors', 'order': 2, 'duration_mins': 20},
                        {'title': 'Teach someone else a basic technique', 'order': 3, 'duration_mins': 15},
                    ]},
                ],
            },
            # ── Career (2) ──────────────────────────────────────────
            {
                'title': 'Get a Promotion',
                'description': 'Strategically position yourself for a career advancement within your current company.',
                'category': 'career',
                'difficulty': 'intermediate',
                'estimated_duration_days': 120,
                'suggested_timeline': '4 months',
                'icon': 'briefcase',
                'color': '#3B82F6',
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
                'title': 'Launch a Side Business',
                'description': 'Go from idea to first paying customer. Validate your business idea and build an MVP.',
                'category': 'career',
                'difficulty': 'advanced',
                'estimated_duration_days': 90,
                'suggested_timeline': '3 months',
                'icon': 'rocket',
                'color': '#6366F1',
                'is_featured': True,
                'template_goals': [
                    {'title': 'Validate the idea', 'description': 'Research market fit and demand', 'order': 1, 'tasks': [
                        {'title': 'Interview 5 potential customers', 'order': 1, 'duration_mins': 60},
                        {'title': 'Research competitors and pricing', 'order': 2, 'duration_mins': 45},
                        {'title': 'Write a one-page business plan', 'order': 3, 'duration_mins': 30},
                    ]},
                    {'title': 'Build the MVP', 'description': 'Create a minimum viable product', 'order': 2, 'tasks': [
                        {'title': 'Define the core feature set', 'order': 1, 'duration_mins': 30},
                        {'title': 'Build or prototype the product', 'order': 2, 'duration_mins': 120},
                        {'title': 'Set up a simple landing page', 'order': 3, 'duration_mins': 60},
                    ]},
                    {'title': 'Get first customers', 'description': 'Launch and acquire initial users', 'order': 3, 'tasks': [
                        {'title': 'Announce to your network', 'order': 1, 'duration_mins': 20},
                        {'title': 'Reach out to 10 potential customers', 'order': 2, 'duration_mins': 45},
                        {'title': 'Collect feedback and iterate', 'order': 3, 'duration_mins': 30},
                    ]},
                ],
            },
            # ── Finance (1) ─────────────────────────────────────────
            {
                'title': 'Save an Emergency Fund',
                'description': 'Build a 6-month emergency fund through systematic saving and expense optimization.',
                'category': 'finance',
                'difficulty': 'beginner',
                'estimated_duration_days': 180,
                'suggested_timeline': '6 months',
                'icon': 'piggy-bank',
                'color': '#F59E0B',
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
            # ── Personal (2) ────────────────────────────────────────
            {
                'title': 'Build a Morning Routine',
                'description': 'Design and stick to a powerful morning routine that sets you up for success every day.',
                'category': 'personal',
                'difficulty': 'beginner',
                'estimated_duration_days': 30,
                'suggested_timeline': '1 month',
                'icon': 'sunrise',
                'color': '#F97316',
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
                'title': 'Read 20 Books This Year',
                'description': 'Cultivate a consistent reading habit and expand your knowledge by completing 20 books.',
                'category': 'personal',
                'difficulty': 'intermediate',
                'estimated_duration_days': 365,
                'suggested_timeline': '1 year',
                'icon': 'book-open',
                'color': '#8B5CF6',
                'is_featured': True,
                'template_goals': [
                    {'title': 'Set up your reading system', 'description': 'Create a reading list and schedule', 'order': 1, 'tasks': [
                        {'title': 'Create a list of 25 books to choose from', 'order': 1, 'duration_mins': 30},
                        {'title': 'Set a daily reading time (30 min minimum)', 'order': 2, 'duration_mins': 10},
                        {'title': 'Join a book club or find a reading buddy', 'order': 3, 'duration_mins': 15},
                    ]},
                    {'title': 'Build the habit', 'description': 'Read consistently for the first month', 'order': 2, 'tasks': [
                        {'title': 'Read for 30 minutes today', 'order': 1, 'duration_mins': 30},
                        {'title': 'Write a brief summary of what you read', 'order': 2, 'duration_mins': 10},
                        {'title': 'Finish your first book', 'order': 3, 'duration_mins': 30},
                    ]},
                    {'title': 'Stay on track', 'description': 'Maintain pace of ~2 books per month', 'order': 3, 'tasks': [
                        {'title': 'Review your reading log', 'order': 1, 'duration_mins': 10},
                        {'title': 'Share a book recommendation with someone', 'order': 2, 'duration_mins': 10},
                        {'title': 'Adjust your reading list based on interests', 'order': 3, 'duration_mins': 15},
                    ]},
                ],
            },
            # ── Hobbies (2) ─────────────────────────────────────────
            {
                'title': 'Learn to Play Guitar',
                'description': 'Go from zero to playing your first song. Learn chords, strumming patterns, and basic music theory.',
                'category': 'hobbies',
                'difficulty': 'beginner',
                'estimated_duration_days': 90,
                'suggested_timeline': '3 months',
                'icon': 'music',
                'color': '#EC4899',
                'is_featured': False,
                'template_goals': [
                    {'title': 'Get started', 'description': 'Set up your instrument and learn basics', 'order': 1, 'tasks': [
                        {'title': 'Get a guitar (buy or borrow)', 'order': 1, 'duration_mins': 30},
                        {'title': 'Learn to tune the guitar', 'order': 2, 'duration_mins': 15},
                        {'title': 'Learn 3 basic chords (G, C, D)', 'order': 3, 'duration_mins': 30},
                    ]},
                    {'title': 'Practice chord transitions', 'description': 'Build muscle memory and fluidity', 'order': 2, 'tasks': [
                        {'title': 'Practice switching between chords for 15 minutes', 'order': 1, 'duration_mins': 15},
                        {'title': 'Learn a basic strumming pattern', 'order': 2, 'duration_mins': 20},
                        {'title': 'Learn 3 more chords (Am, Em, F)', 'order': 3, 'duration_mins': 30},
                    ]},
                    {'title': 'Play your first song', 'description': 'Put it all together', 'order': 3, 'tasks': [
                        {'title': 'Choose a simple song to learn', 'order': 1, 'duration_mins': 10},
                        {'title': 'Practice the song section by section', 'order': 2, 'duration_mins': 30},
                        {'title': 'Play the full song start to finish', 'order': 3, 'duration_mins': 20},
                    ]},
                ],
            },
            {
                'title': 'Start a Photography Hobby',
                'description': 'Learn photography fundamentals and build a portfolio of shots you are proud of.',
                'category': 'hobbies',
                'difficulty': 'intermediate',
                'estimated_duration_days': 60,
                'suggested_timeline': '2 months',
                'icon': 'camera',
                'color': '#14B8A6',
                'is_featured': False,
                'template_goals': [
                    {'title': 'Learn the basics', 'description': 'Understand camera settings and composition', 'order': 1, 'tasks': [
                        {'title': 'Learn about aperture, shutter speed, and ISO', 'order': 1, 'duration_mins': 30},
                        {'title': 'Practice the rule of thirds composition', 'order': 2, 'duration_mins': 20},
                        {'title': 'Take 50 photos exploring different settings', 'order': 3, 'duration_mins': 45},
                    ]},
                    {'title': 'Develop your eye', 'description': 'Practice different genres and styles', 'order': 2, 'tasks': [
                        {'title': 'Do a golden hour photo walk', 'order': 1, 'duration_mins': 60},
                        {'title': 'Try street photography for 30 minutes', 'order': 2, 'duration_mins': 30},
                        {'title': 'Learn basic photo editing', 'order': 3, 'duration_mins': 45},
                    ]},
                    {'title': 'Build your portfolio', 'description': 'Select and present your best work', 'order': 3, 'tasks': [
                        {'title': 'Select your 10 best photos', 'order': 1, 'duration_mins': 20},
                        {'title': 'Edit and finalize each photo', 'order': 2, 'duration_mins': 60},
                        {'title': 'Create an online portfolio or Instagram', 'order': 3, 'duration_mins': 30},
                    ]},
                ],
            },
            # ── Relationships (2) ───────────────────────────────────
            {
                'title': 'Strengthen Relationships',
                'description': 'Deepen connections with family and friends through intentional quality time and meaningful gestures.',
                'category': 'relationships',
                'difficulty': 'beginner',
                'estimated_duration_days': 60,
                'suggested_timeline': '2 months',
                'icon': 'heart',
                'color': '#F43F5E',
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
                'title': 'Become a Better Listener',
                'description': 'Improve your listening and communication skills to build deeper, more meaningful relationships.',
                'category': 'relationships',
                'difficulty': 'beginner',
                'estimated_duration_days': 30,
                'suggested_timeline': '1 month',
                'icon': 'ear',
                'color': '#A855F7',
                'is_featured': False,
                'template_goals': [
                    {'title': 'Learn active listening', 'description': 'Study and practice core techniques', 'order': 1, 'tasks': [
                        {'title': 'Read about active listening techniques', 'order': 1, 'duration_mins': 20},
                        {'title': 'Practice mirroring in a conversation', 'order': 2, 'duration_mins': 15},
                        {'title': 'Ask 3 open-ended questions in your next chat', 'order': 3, 'duration_mins': 10},
                    ]},
                    {'title': 'Apply daily', 'description': 'Use techniques in real conversations', 'order': 2, 'tasks': [
                        {'title': 'Have a conversation where you only listen', 'order': 1, 'duration_mins': 20},
                        {'title': 'Summarize what someone said back to them', 'order': 2, 'duration_mins': 10},
                        {'title': 'Journal about what you learned from listening', 'order': 3, 'duration_mins': 10},
                    ]},
                ],
            },
            # ── Finance (1 more) ────────────────────────────────────
            {
                'title': 'Start Investing',
                'description': 'Learn the fundamentals of investing and make your first investment with confidence.',
                'category': 'finance',
                'difficulty': 'intermediate',
                'estimated_duration_days': 60,
                'suggested_timeline': '2 months',
                'icon': 'trending-up',
                'color': '#22C55E',
                'is_featured': True,
                'template_goals': [
                    {'title': 'Learn the basics', 'description': 'Understand investment fundamentals', 'order': 1, 'tasks': [
                        {'title': 'Learn the difference between stocks, bonds, and ETFs', 'order': 1, 'duration_mins': 30},
                        {'title': 'Understand risk tolerance and asset allocation', 'order': 2, 'duration_mins': 25},
                        {'title': 'Research low-cost index fund options', 'order': 3, 'duration_mins': 20},
                    ]},
                    {'title': 'Set up your accounts', 'description': 'Open brokerage and start contributing', 'order': 2, 'tasks': [
                        {'title': 'Open a brokerage account', 'order': 1, 'duration_mins': 20},
                        {'title': 'Set up automatic monthly contributions', 'order': 2, 'duration_mins': 10},
                        {'title': 'Make your first investment', 'order': 3, 'duration_mins': 15},
                    ]},
                    {'title': 'Build long-term habits', 'description': 'Create a sustainable investing routine', 'order': 3, 'tasks': [
                        {'title': 'Review your portfolio monthly', 'order': 1, 'duration_mins': 15},
                        {'title': 'Read one investing article per week', 'order': 2, 'duration_mins': 15},
                        {'title': 'Rebalance portfolio if needed', 'order': 3, 'duration_mins': 20},
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
