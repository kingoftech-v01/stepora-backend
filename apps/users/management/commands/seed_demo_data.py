"""
Management command to seed the database with comprehensive demo data.

Creates ~12,000 records across all models: 40 diverse users, dreams with
goals/tasks, conversations, circles, buddy pairings, social graph, league
standings, store purchases, notifications, and calendar events.

Usage:
    python manage.py seed_demo_data
    python manage.py seed_demo_data --flush
    python manage.py seed_demo_data --skip-prerequisites
"""

import random
import uuid
from datetime import date, time, timedelta
from decimal import Decimal

from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from django.utils.crypto import get_random_string

from apps.buddies.models import BuddyEncouragement, BuddyPairing
from apps.calendar.models import CalendarEvent, TimeBlock
from apps.circles.models import (
    ChallengeProgress,
    Circle,
    CircleCall,
    CircleCallParticipant,
    CircleChallenge,
    CircleInvitation,
    CircleMembership,
    CircleMessage,
    CirclePost,
    PostReaction,
)
from apps.conversations.models import Call, Conversation, Message, MessageReadStatus
from apps.dreams.models import (
    CalibrationResponse,
    Dream,
    DreamCollaborator,
    DreamProgressSnapshot,
    DreamTag,
    DreamTagging,
    Goal,
    Obstacle,
    SharedDream,
    Task,
    VisionBoardImage,
)
from apps.leagues.models import League, LeagueStanding, RankSnapshot, Season
from apps.notifications.models import Notification
from apps.social.models import (
    ActivityFeedItem,
    BlockedUser,
    DreamEncouragement,
    DreamPost,
    DreamPostComment,
    DreamPostLike,
    Friendship,
    RecentSearch,
    ReportedUser,
    UserFollow,
)
from apps.store.models import Gift, RefundRequest, StoreItem, UserInventory, Wishlist
from apps.subscriptions.models import StripeCustomer, Subscription, SubscriptionPlan
from apps.users.models import (
    Achievement,
    DailyActivity,
    GamificationProfile,
    User,
    UserAchievement,
)

DEMO_EMAIL_DOMAIN = 'demo.dreamplanner.app'
DEMO_PASSWORD = 'DemoPass123!'
NOW = None

# ---------------------------------------------------------------------------
# User persona definitions
# ---------------------------------------------------------------------------
USER_PERSONAS = [
    # Archetype A: Power Users (6)
    {'display_name': 'Sophia Chen', 'slug': 'sophia.chen', 'sub': 'pro', 'xp': 22500, 'level': 226, 'streak': 87, 'tz': 'America/New_York', 'vis': 'public', 'bio': 'Dream architect. Marathon runner. Building the life I envision.', 'loc': 'New York, NY', 'arch': 'power', 'days_ago': 88},
    {'display_name': 'Marcus Williams', 'slug': 'marcus.williams', 'sub': 'pro', 'xp': 18200, 'level': 183, 'streak': 62, 'tz': 'America/Chicago', 'vis': 'public', 'bio': 'Career coach by day, dream chaser by night.', 'loc': 'Chicago, IL', 'arch': 'power', 'days_ago': 82},
    {'display_name': 'Aisha Patel', 'slug': 'aisha.patel', 'sub': 'pro', 'xp': 15400, 'level': 155, 'streak': 45, 'tz': 'Europe/London', 'vis': 'friends', 'bio': 'Mindfulness practitioner. AI enthusiast. Lifelong learner.', 'loc': 'London, UK', 'arch': 'power', 'days_ago': 75},
    {'display_name': 'Kenji Tanaka', 'slug': 'kenji.tanaka', 'sub': 'pro', 'xp': 13500, 'level': 136, 'streak': 38, 'tz': 'Asia/Tokyo', 'vis': 'public', 'bio': 'Fitness obsessed. 100 pushups a day keeps the doctor away.', 'loc': 'Tokyo, Japan', 'arch': 'power', 'days_ago': 70},
    {'display_name': 'Isabella Costa', 'slug': 'isabella.costa', 'sub': 'pro', 'xp': 12800, 'level': 129, 'streak': 52, 'tz': 'America/Sao_Paulo', 'vis': 'public', 'bio': 'Writer, artist, creative soul. Words are my superpower.', 'loc': 'Sao Paulo, Brazil', 'arch': 'power', 'days_ago': 85},
    {'display_name': 'Dmitri Volkov', 'slug': 'dmitri.volkov', 'sub': 'pro', 'xp': 20100, 'level': 202, 'streak': 73, 'tz': 'Europe/Moscow', 'vis': 'public', 'bio': 'Finance wizard. Building wealth one habit at a time.', 'loc': 'Moscow, Russia', 'arch': 'power', 'days_ago': 90},
    # Archetype B: Active Premium (8)
    {'display_name': 'Emma Laurent', 'slug': 'emma.laurent', 'sub': 'premium', 'xp': 5200, 'level': 53, 'streak': 21, 'tz': 'Europe/Paris', 'vis': 'public', 'bio': 'Budgeting queen. Financial freedom is my dream.', 'loc': 'Paris, France', 'arch': 'premium', 'days_ago': 55},
    {'display_name': 'James O\'Brien', 'slug': 'james.obrien', 'sub': 'premium', 'xp': 4800, 'level': 49, 'streak': 18, 'tz': 'Europe/Dublin', 'vis': 'friends', 'bio': 'Software dev learning to balance code and life.', 'loc': 'Dublin, Ireland', 'arch': 'premium', 'days_ago': 48},
    {'display_name': 'Fatima Al-Rashid', 'slug': 'fatima.alrashid', 'sub': 'premium', 'xp': 6100, 'level': 62, 'streak': 28, 'tz': 'Asia/Dubai', 'vis': 'public', 'bio': 'Education advocate. Knowledge is the best investment.', 'loc': 'Dubai, UAE', 'arch': 'premium', 'days_ago': 52},
    {'display_name': 'Lucas Santos', 'slug': 'lucas.santos', 'sub': 'premium', 'xp': 3800, 'level': 39, 'streak': 14, 'tz': 'America/Sao_Paulo', 'vis': 'public', 'bio': 'Photographer and travel enthusiast.', 'loc': 'Rio de Janeiro, Brazil', 'arch': 'premium', 'days_ago': 40},
    {'display_name': 'Yuki Nakamura', 'slug': 'yuki.nakamura', 'sub': 'premium', 'xp': 4500, 'level': 46, 'streak': 16, 'tz': 'Asia/Tokyo', 'vis': 'friends', 'bio': 'Language learner. Currently: Spanish and French.', 'loc': 'Osaka, Japan', 'arch': 'premium', 'days_ago': 45},
    {'display_name': 'Amara Okafor', 'slug': 'amara.okafor', 'sub': 'premium', 'xp': 5600, 'level': 57, 'streak': 24, 'tz': 'Africa/Lagos', 'vis': 'public', 'bio': 'Entrepreneur building Africa\'s future.', 'loc': 'Lagos, Nigeria', 'arch': 'premium', 'days_ago': 50},
    {'display_name': 'Oliver Schmidt', 'slug': 'oliver.schmidt', 'sub': 'premium', 'xp': 4100, 'level': 42, 'streak': 12, 'tz': 'Europe/Berlin', 'vis': 'public', 'bio': 'Mechanical engineer with a creative side.', 'loc': 'Berlin, Germany', 'arch': 'premium', 'days_ago': 38},
    {'display_name': 'Priya Sharma', 'slug': 'priya.sharma', 'sub': 'premium', 'xp': 7200, 'level': 73, 'streak': 31, 'tz': 'Asia/Kolkata', 'vis': 'public', 'bio': 'Bookworm and aspiring data scientist.', 'loc': 'Mumbai, India', 'arch': 'premium', 'days_ago': 58},
    # Archetype C: Casual Free (8)
    {'display_name': 'Noah Jackson', 'slug': 'noah.jackson', 'sub': 'free', 'xp': 800, 'level': 9, 'streak': 5, 'tz': 'America/New_York', 'vis': 'public', 'bio': 'Just getting started on my journey.', 'loc': 'Boston, MA', 'arch': 'casual', 'days_ago': 30},
    {'display_name': 'Mia Fernandez', 'slug': 'mia.fernandez', 'sub': 'free', 'xp': 1200, 'level': 13, 'streak': 8, 'tz': 'America/Mexico_City', 'vis': 'public', 'bio': 'Health and wellness enthusiast.', 'loc': 'Mexico City, Mexico', 'arch': 'casual', 'days_ago': 35},
    {'display_name': 'Ethan Kim', 'slug': 'ethan.kim', 'sub': 'free', 'xp': 600, 'level': 7, 'streak': 3, 'tz': 'America/Los_Angeles', 'vis': 'friends', 'bio': 'College student exploring goals.', 'loc': 'Los Angeles, CA', 'arch': 'casual', 'days_ago': 22},
    {'display_name': 'Chloe Dubois', 'slug': 'chloe.dubois', 'sub': 'free', 'xp': 950, 'level': 10, 'streak': 6, 'tz': 'Europe/Paris', 'vis': 'public', 'bio': 'Art student with big dreams.', 'loc': 'Lyon, France', 'arch': 'casual', 'days_ago': 28},
    {'display_name': 'Liam Chen', 'slug': 'liam.chen', 'sub': 'free', 'xp': 1500, 'level': 16, 'streak': 10, 'tz': 'Asia/Singapore', 'vis': 'public', 'bio': 'Startup founder in the making.', 'loc': 'Singapore', 'arch': 'casual', 'days_ago': 42},
    {'display_name': 'Ava Petrov', 'slug': 'ava.petrov', 'sub': 'free', 'xp': 400, 'level': 5, 'streak': 2, 'tz': 'Europe/Moscow', 'vis': 'private', 'bio': '', 'loc': 'St. Petersburg, Russia', 'arch': 'casual', 'days_ago': 18},
    {'display_name': 'Benjamin Adler', 'slug': 'benjamin.adler', 'sub': 'free', 'xp': 700, 'level': 8, 'streak': 4, 'tz': 'Europe/Berlin', 'vis': 'public', 'bio': 'Music lover and part-time DJ.', 'loc': 'Hamburg, Germany', 'arch': 'casual', 'days_ago': 25},
    {'display_name': 'Zara Hassan', 'slug': 'zara.hassan', 'sub': 'free', 'xp': 1100, 'level': 12, 'streak': 7, 'tz': 'Africa/Cairo', 'vis': 'public', 'bio': 'Medical student with a plan.', 'loc': 'Cairo, Egypt', 'arch': 'casual', 'days_ago': 33},
    # Archetype D: New Users (8)
    {'display_name': 'Daniel Park', 'slug': 'daniel.park', 'sub': 'free', 'xp': 50, 'level': 1, 'streak': 1, 'tz': 'Asia/Seoul', 'vis': 'public', 'bio': '', 'loc': 'Seoul, South Korea', 'arch': 'new', 'days_ago': 3},
    {'display_name': 'Sophie Martin', 'slug': 'sophie.martin', 'sub': 'free', 'xp': 120, 'level': 2, 'streak': 2, 'tz': 'Europe/Paris', 'vis': 'public', 'bio': 'Excited to start!', 'loc': 'Marseille, France', 'arch': 'new', 'days_ago': 5},
    {'display_name': 'Ryan Cooper', 'slug': 'ryan.cooper', 'sub': 'free', 'xp': 0, 'level': 1, 'streak': 0, 'tz': 'America/Denver', 'vis': 'public', 'bio': '', 'loc': 'Denver, CO', 'arch': 'new', 'days_ago': 1},
    {'display_name': 'Nina Johansson', 'slug': 'nina.johansson', 'sub': 'premium', 'xp': 80, 'level': 1, 'streak': 1, 'tz': 'Europe/Stockholm', 'vis': 'public', 'bio': 'New premium member.', 'loc': 'Stockholm, Sweden', 'arch': 'new', 'days_ago': 4},
    {'display_name': 'Ahmed Khalil', 'slug': 'ahmed.khalil', 'sub': 'free', 'xp': 30, 'level': 1, 'streak': 0, 'tz': 'Asia/Riyadh', 'vis': 'private', 'bio': '', 'loc': 'Riyadh, Saudi Arabia', 'arch': 'new', 'days_ago': 2},
    {'display_name': 'Lily Wang', 'slug': 'lily.wang', 'sub': 'free', 'xp': 150, 'level': 2, 'streak': 2, 'tz': 'Asia/Shanghai', 'vis': 'public', 'bio': 'Tech worker looking for balance.', 'loc': 'Shanghai, China', 'arch': 'new', 'days_ago': 6},
    {'display_name': 'Oscar Rivera', 'slug': 'oscar.rivera', 'sub': 'free', 'xp': 10, 'level': 1, 'streak': 0, 'tz': 'America/Mexico_City', 'vis': 'public', 'bio': '', 'loc': 'Guadalajara, Mexico', 'arch': 'new', 'days_ago': 1},
    {'display_name': 'Freya Nielsen', 'slug': 'freya.nielsen', 'sub': 'premium', 'xp': 200, 'level': 3, 'streak': 3, 'tz': 'Europe/Copenhagen', 'vis': 'public', 'bio': 'Hygge and personal growth.', 'loc': 'Copenhagen, Denmark', 'arch': 'new', 'days_ago': 7},
    # Archetype E: Social Butterflies (6)
    {'display_name': 'Taylor Brooks', 'slug': 'taylor.brooks', 'sub': 'pro', 'xp': 8500, 'level': 86, 'streak': 25, 'tz': 'America/New_York', 'vis': 'public', 'bio': 'Community builder. Connecting dreamers worldwide.', 'loc': 'Brooklyn, NY', 'arch': 'social', 'days_ago': 65},
    {'display_name': 'Maya Gupta', 'slug': 'maya.gupta', 'sub': 'premium', 'xp': 6800, 'level': 69, 'streak': 20, 'tz': 'Asia/Kolkata', 'vis': 'public', 'bio': 'Mindful living advocate and wellness coach.', 'loc': 'Bangalore, India', 'arch': 'social', 'days_ago': 60},
    {'display_name': 'Alex Rivera', 'slug': 'alex.rivera', 'sub': 'premium', 'xp': 5900, 'level': 60, 'streak': 18, 'tz': 'America/Chicago', 'vis': 'public', 'bio': 'Photographer. Every shot tells a story.', 'loc': 'Austin, TX', 'arch': 'social', 'days_ago': 55},
    {'display_name': 'Sam Wilson', 'slug': 'sam.wilson', 'sub': 'pro', 'xp': 9200, 'level': 93, 'streak': 30, 'tz': 'Europe/London', 'vis': 'public', 'bio': 'Startup mentor. Side hustle champion.', 'loc': 'Manchester, UK', 'arch': 'social', 'days_ago': 70},
    {'display_name': 'Jordan Lee', 'slug': 'jordan.lee', 'sub': 'premium', 'xp': 7100, 'level': 72, 'streak': 22, 'tz': 'Asia/Tokyo', 'vis': 'public', 'bio': 'Travel + fitness + learning = my life.', 'loc': 'Kyoto, Japan', 'arch': 'social', 'days_ago': 50},
    {'display_name': 'Riley Thompson', 'slug': 'riley.thompson', 'sub': 'premium', 'xp': 5500, 'level': 56, 'streak': 15, 'tz': 'Australia/Sydney', 'vis': 'public', 'bio': 'Down under dreamer. Coffee addict.', 'loc': 'Sydney, Australia', 'arch': 'social', 'days_ago': 48},
    # Archetype F: Inactive (4)
    {'display_name': 'Max Weber', 'slug': 'max.weber', 'sub': 'free', 'xp': 2100, 'level': 22, 'streak': 0, 'tz': 'Europe/Berlin', 'vis': 'public', 'bio': 'Taking a break.', 'loc': 'Munich, Germany', 'arch': 'inactive', 'days_ago': 80},
    {'display_name': 'Clara Rossi', 'slug': 'clara.rossi', 'sub': 'premium', 'xp': 3400, 'level': 35, 'streak': 0, 'tz': 'Europe/Rome', 'vis': 'friends', 'bio': 'Will be back soon.', 'loc': 'Rome, Italy', 'arch': 'inactive', 'days_ago': 75},
    {'display_name': 'Henry Chang', 'slug': 'henry.chang', 'sub': 'free', 'xp': 1800, 'level': 19, 'streak': 0, 'tz': 'America/Los_Angeles', 'vis': 'public', 'bio': 'On hiatus.', 'loc': 'San Francisco, CA', 'arch': 'inactive', 'days_ago': 85},
    {'display_name': 'Elena Popov', 'slug': 'elena.popov', 'sub': 'pro', 'xp': 8900, 'level': 90, 'streak': 0, 'tz': 'Europe/Moscow', 'vis': 'private', 'bio': 'Paused for now.', 'loc': 'Moscow, Russia', 'arch': 'inactive', 'days_ago': 90},
]

# ---------------------------------------------------------------------------
# Dream content library (5 per category)
# ---------------------------------------------------------------------------
DREAM_LIBRARY = {
    'health': [
        {'title': 'Run a Half Marathon', 'desc': 'Train for and complete a 21km half marathon by summer.', 'goals': [
            {'title': 'Build Base Fitness', 'tasks': ['Run 2 miles 3x/week', 'Do stretching routine daily', 'Track daily calories']},
            {'title': 'Increase Distance', 'tasks': ['Run 5 miles twice a week', 'Hill training once a week', 'Recovery yoga sessions']},
            {'title': 'Race Preparation', 'tasks': ['Complete 10-mile run', 'Register for race event', 'Buy proper running shoes']},
        ]},
        {'title': 'Master Yoga', 'desc': 'Build a consistent yoga practice and achieve advanced poses.', 'goals': [
            {'title': 'Daily Practice', 'tasks': ['Morning yoga 20 min', 'Learn 5 basic poses', 'Set up home space']},
            {'title': 'Intermediate Poses', 'tasks': ['Crow pose practice', 'Headstand progression', 'Flexibility routine']},
        ]},
        {'title': 'Sleep 8 Hours Nightly', 'desc': 'Fix sleep hygiene and establish a consistent schedule.', 'goals': [
            {'title': 'Sleep Hygiene', 'tasks': ['No screens after 9pm', 'Consistent bedtime alarm', 'Dark room setup']},
            {'title': 'Track Progress', 'tasks': ['Log sleep hours daily', 'Rate sleep quality', 'Weekly review']},
        ]},
        {'title': 'Complete 100 Push-ups', 'desc': 'Build up to 100 consecutive push-ups.', 'goals': [
            {'title': 'Foundation', 'tasks': ['Wall push-ups 3x20', 'Knee push-ups 3x15', 'Plank holds 60s']},
            {'title': 'Build Strength', 'tasks': ['Full push-ups 3x10', 'Diamond push-ups 3x8', 'Wide push-ups 3x10']},
            {'title': 'Endurance', 'tasks': ['Push-up pyramid sets', 'Timed max reps test', '100 push-up attempt']},
        ]},
        {'title': 'Lose 15 Pounds', 'desc': 'Reach target weight through nutrition and exercise.', 'goals': [
            {'title': 'Nutrition Plan', 'tasks': ['Meal prep Sundays', 'Track macros daily', 'Cut sugary drinks']},
            {'title': 'Exercise Routine', 'tasks': ['Cardio 4x/week', 'Strength training 3x/week', 'Daily 10k steps']},
        ]},
    ],
    'career': [
        {'title': 'Get Promoted to Senior Engineer', 'desc': 'Build skills and visibility for promotion within 6 months.', 'goals': [
            {'title': 'Technical Skills', 'tasks': ['Complete system design course', 'Lead a code review', 'Write technical RFC']},
            {'title': 'Visibility', 'tasks': ['Present at team meeting', 'Mentor a junior dev', 'Ship high-impact feature']},
            {'title': 'Feedback Loop', 'tasks': ['Schedule 1:1 with manager', 'Request 360 feedback', 'Update career doc']},
        ]},
        {'title': 'Launch My Side Business', 'desc': 'Start a freelance consulting practice.', 'goals': [
            {'title': 'Planning', 'tasks': ['Define service offering', 'Create business plan', 'Set up LLC']},
            {'title': 'Marketing', 'tasks': ['Build portfolio website', 'Create LinkedIn content', 'Reach out to 10 leads']},
        ]},
        {'title': 'Learn Public Speaking', 'desc': 'Overcome fear and deliver a conference talk.', 'goals': [
            {'title': 'Practice', 'tasks': ['Join Toastmasters', 'Record practice talks', 'Get feedback from peers']},
            {'title': 'Conference Talk', 'tasks': ['Submit CFP to 3 events', 'Prepare slide deck', 'Rehearse 10 times']},
        ]},
        {'title': 'Get AWS Certified', 'desc': 'Pass the AWS Solutions Architect exam.', 'goals': [
            {'title': 'Study', 'tasks': ['Complete AWS course', 'Take practice exams', 'Review weak areas']},
            {'title': 'Exam Prep', 'tasks': ['Schedule exam date', 'Final practice exam', 'Review notes']},
        ]},
        {'title': 'Negotiate a Raise', 'desc': 'Research, prepare, and negotiate a 20% salary increase.', 'goals': [
            {'title': 'Research', 'tasks': ['Check market salary data', 'Document achievements', 'Talk to mentors']},
            {'title': 'Negotiate', 'tasks': ['Schedule meeting', 'Present case', 'Follow up in writing']},
        ]},
    ],
    'education': [
        {'title': 'Learn Spanish', 'desc': 'Achieve B2 conversational fluency in Spanish.', 'goals': [
            {'title': 'Fundamentals', 'tasks': ['Duolingo 20 min daily', 'Learn 50 common verbs', 'Grammar workbook Ch1-5']},
            {'title': 'Practice', 'tasks': ['Language exchange weekly', 'Watch Spanish shows', 'Read a Spanish book']},
            {'title': 'Fluency', 'tasks': ['Take B2 practice test', 'Have 30-min conversation', 'Write an essay']},
        ]},
        {'title': 'Read 50 Books This Year', 'desc': 'Read across fiction and non-fiction genres.', 'goals': [
            {'title': 'Build Habit', 'tasks': ['Read 30 min before bed', 'Create reading list', 'Join a book club']},
            {'title': 'Track Progress', 'tasks': ['Log books completed', 'Write short reviews', 'Share recommendations']},
        ]},
        {'title': 'Master Data Science', 'desc': 'Complete online bootcamp and build a portfolio.', 'goals': [
            {'title': 'Foundations', 'tasks': ['Python for data science', 'Statistics refresher', 'SQL fundamentals']},
            {'title': 'Advanced Topics', 'tasks': ['Machine learning course', 'Deep learning basics', 'Kaggle competition']},
            {'title': 'Portfolio', 'tasks': ['Build 3 projects', 'Create GitHub portfolio', 'Write blog posts']},
        ]},
        {'title': 'Learn Piano', 'desc': 'Play 5 songs from memory within 6 months.', 'goals': [
            {'title': 'Basics', 'tasks': ['Learn music notation', 'Practice scales daily', 'Simple melody #1']},
            {'title': 'Songs', 'tasks': ['Learn first song', 'Learn second song', 'Practice hands together']},
        ]},
        {'title': 'Complete Online MBA', 'desc': 'Finish all coursework for online MBA program.', 'goals': [
            {'title': 'Core Courses', 'tasks': ['Finance module', 'Marketing module', 'Operations module']},
            {'title': 'Electives', 'tasks': ['Entrepreneurship course', 'Data analytics course', 'Capstone project']},
        ]},
    ],
    'finance': [
        {'title': 'Save $10,000 Emergency Fund', 'desc': 'Build a financial safety net over 10 months.', 'goals': [
            {'title': 'Budget Setup', 'tasks': ['Track all expenses for 1 month', 'Create zero-based budget', 'Set up auto-transfer']},
            {'title': 'Reduce Spending', 'tasks': ['Cancel unused subscriptions', 'Meal prep to save $200/mo', 'No-spend weekend challenge']},
            {'title': 'Milestones', 'tasks': ['Reach $3,000 saved', 'Reach $6,000 saved', 'Reach $10,000 goal']},
        ]},
        {'title': 'Start Investing', 'desc': 'Open brokerage account and build a diversified portfolio.', 'goals': [
            {'title': 'Education', 'tasks': ['Read investing basics book', 'Understand index funds', 'Learn about asset allocation']},
            {'title': 'Action', 'tasks': ['Open brokerage account', 'Set up monthly investment', 'Rebalance portfolio quarterly']},
        ]},
        {'title': 'Pay Off Student Loans', 'desc': 'Aggressive repayment strategy for $30k in loans.', 'goals': [
            {'title': 'Strategy', 'tasks': ['List all loans and rates', 'Choose avalanche method', 'Refinance if possible']},
            {'title': 'Execute', 'tasks': ['Extra $500/mo payment', 'Side income toward debt', 'Track payoff date']},
        ]},
        {'title': 'Create a Budget System', 'desc': 'Track every dollar with zero-based budgeting.', 'goals': [
            {'title': 'Setup', 'tasks': ['Choose budgeting app', 'Categorize expenses', 'Set spending limits']},
            {'title': 'Maintain', 'tasks': ['Daily expense logging', 'Weekly budget review', 'Monthly adjustment']},
        ]},
        {'title': 'Buy a Home', 'desc': 'Save for down payment and get mortgage-ready.', 'goals': [
            {'title': 'Prepare', 'tasks': ['Check credit score', 'Save for down payment', 'Get pre-approved']},
            {'title': 'Search', 'tasks': ['Define must-haves', 'Tour 10 properties', 'Make an offer']},
        ]},
    ],
    'creative': [
        {'title': 'Write a Novel', 'desc': 'Complete a 60,000-word first draft.', 'goals': [
            {'title': 'Planning', 'tasks': ['Outline plot structure', 'Develop characters', 'Research setting']},
            {'title': 'First Draft', 'tasks': ['Write 1,000 words daily', 'Complete Act 1', 'Complete Act 2']},
            {'title': 'Finish', 'tasks': ['Complete Act 3', 'Let it rest 2 weeks', 'First read-through']},
        ]},
        {'title': 'Learn Digital Art', 'desc': 'Master Procreate and build an online portfolio.', 'goals': [
            {'title': 'Basics', 'tasks': ['Complete Procreate tutorial', 'Practice gesture drawing', 'Color theory study']},
            {'title': 'Portfolio', 'tasks': ['Create 10 finished pieces', 'Set up art Instagram', 'Take commissions']},
        ]},
        {'title': 'Start a YouTube Channel', 'desc': 'Publish 50 videos and reach 1,000 subscribers.', 'goals': [
            {'title': 'Setup', 'tasks': ['Buy basic equipment', 'Learn video editing', 'Create channel branding']},
            {'title': 'Content', 'tasks': ['Script first 5 videos', 'Publish weekly', 'Engage with comments']},
            {'title': 'Growth', 'tasks': ['Collaborate with creators', 'SEO optimization', 'Analyze analytics weekly']},
        ]},
        {'title': 'Record an Album', 'desc': 'Write, record, and release 10 original songs.', 'goals': [
            {'title': 'Songwriting', 'tasks': ['Write 2 songs per month', 'Jam sessions weekly', 'Collect lyrics ideas']},
            {'title': 'Recording', 'tasks': ['Set up home studio', 'Record demos', 'Professional mixing']},
        ]},
        {'title': 'Build Photography Portfolio', 'desc': 'Shoot 100 professional-quality photos.', 'goals': [
            {'title': 'Learn', 'tasks': ['Study composition rules', 'Master manual mode', 'Edit in Lightroom']},
            {'title': 'Shoot', 'tasks': ['Street photography walk', 'Portrait session', 'Landscape trip']},
        ]},
    ],
    'personal': [
        {'title': 'Build a Morning Routine', 'desc': 'Wake at 5:30am and follow a structured routine.', 'goals': [
            {'title': 'Setup', 'tasks': ['Set 5:30am alarm', 'Prep clothes night before', 'No phone first hour']},
            {'title': 'Routine', 'tasks': ['10 min meditation', 'Journal 3 pages', 'Exercise 20 min']},
        ]},
        {'title': 'Practice Mindfulness Daily', 'desc': 'Meditate 20 minutes every day for 90 days.', 'goals': [
            {'title': 'Start Small', 'tasks': ['5-min guided meditation', 'Download meditation app', 'Set daily reminder']},
            {'title': 'Build Up', 'tasks': ['Increase to 15 min', 'Try body scan meditation', 'Walking meditation']},
            {'title': 'Mastery', 'tasks': ['20-min unguided sits', 'Mindful eating practice', 'Teach a friend']},
        ]},
        {'title': 'Declutter My Life', 'desc': 'KonMari the entire house room by room.', 'goals': [
            {'title': 'Clothes', 'tasks': ['Sort all clothing', 'Donate 3 bags', 'Organize closet']},
            {'title': 'Living Space', 'tasks': ['Kitchen declutter', 'Office reorganization', 'Digital declutter']},
        ]},
        {'title': 'Journal Every Day', 'desc': 'Write 500 words daily reflecting on the day.', 'goals': [
            {'title': 'Habit', 'tasks': ['Buy a journal', 'Write before bed', 'Review weekly']},
        ]},
        {'title': 'Digital Detox Challenge', 'desc': 'Reduce screen time and reclaim attention.', 'goals': [
            {'title': 'Awareness', 'tasks': ['Track screen time 1 week', 'Identify worst apps', 'Set daily limits']},
            {'title': 'Action', 'tasks': ['Delete social media apps', 'Phone-free mornings', 'Read instead of scroll']},
        ]},
    ],
    'social': [
        {'title': 'Make 5 New Close Friends', 'desc': 'Expand social circle meaningfully.', 'goals': [
            {'title': 'Meet People', 'tasks': ['Join a club or class', 'Attend networking events', 'Say yes to invitations']},
            {'title': 'Deepen Connections', 'tasks': ['Schedule 1-on-1 coffee dates', 'Remember birthdays', 'Be vulnerable in conversations']},
        ]},
        {'title': 'Plan a Family Reunion', 'desc': 'Organize a gathering for 30+ family members.', 'goals': [
            {'title': 'Planning', 'tasks': ['Choose date and venue', 'Create guest list', 'Send invitations']},
            {'title': 'Execution', 'tasks': ['Plan activities', 'Coordinate food', 'Create photo album']},
        ]},
        {'title': 'Be a Better Listener', 'desc': 'Practice active listening techniques daily.', 'goals': [
            {'title': 'Learn', 'tasks': ['Read active listening book', 'Practice mirroring', 'Ask open questions']},
        ]},
        {'title': 'Host Monthly Dinners', 'desc': 'Cook and host 6 dinner parties.', 'goals': [
            {'title': 'Plan', 'tasks': ['Choose monthly theme', 'Create guest rotation', 'Build recipe collection']},
            {'title': 'Host', 'tasks': ['First dinner party', 'Second dinner party', 'Third dinner party']},
        ]},
        {'title': 'Join a Community Group', 'desc': 'Find and actively participate in a local group.', 'goals': [
            {'title': 'Find', 'tasks': ['Research local groups', 'Attend 3 trial meetings', 'Choose one to commit to']},
        ]},
    ],
    'travel': [
        {'title': 'Backpack Through Southeast Asia', 'desc': '3-week trip through Thailand, Vietnam, Cambodia.', 'goals': [
            {'title': 'Plan', 'tasks': ['Research itinerary', 'Book flights', 'Get travel insurance']},
            {'title': 'Prepare', 'tasks': ['Pack efficiently', 'Learn basic phrases', 'Save travel budget']},
            {'title': 'Go', 'tasks': ['Thailand week', 'Vietnam week', 'Cambodia week']},
        ]},
        {'title': 'Visit All National Parks', 'desc': 'Road trip to visit 10 national parks this year.', 'goals': [
            {'title': 'Plan Route', 'tasks': ['Map out parks', 'Book campsites', 'Prep camping gear']},
            {'title': 'Trip 1', 'tasks': ['Visit park 1-3', 'Document with photos', 'Write trip journal']},
        ]},
        {'title': 'Learn to Scuba Dive', 'desc': 'Get PADI certified and dive at 3 locations.', 'goals': [
            {'title': 'Certification', 'tasks': ['Sign up for PADI course', 'Pool sessions', 'Open water dives']},
            {'title': 'Dive Trips', 'tasks': ['First ocean dive trip', 'Second dive location', 'Night dive experience']},
        ]},
        {'title': 'Solo Trip to Japan', 'desc': 'Plan and execute a 2-week Japan adventure.', 'goals': [
            {'title': 'Plan', 'tasks': ['Get JR Pass', 'Book accommodations', 'Create daily itinerary']},
            {'title': 'Explore', 'tasks': ['Tokyo exploration', 'Kyoto temples', 'Mount Fuji hike']},
        ]},
        {'title': 'Road Trip Across Europe', 'desc': 'Drive from Lisbon to Istanbul over 3 weeks.', 'goals': [
            {'title': 'Logistics', 'tasks': ['Rent a car', 'Plan route and stops', 'Book key accommodations']},
            {'title': 'Journey', 'tasks': ['Western Europe leg', 'Central Europe leg', 'Eastern Europe leg']},
        ]},
    ],
}

# Dream tag names
DREAM_TAGS = [
    'fitness', 'health', 'career', 'money', 'education', 'creative',
    'mindfulness', 'social', 'travel', 'productivity', 'habits',
    'reading', 'writing', 'music', 'photography', 'cooking',
    'technology', 'leadership', 'wellness', 'adventure',
]

# Circle post templates
CIRCLE_POST_TEMPLATES = [
    "Just completed my morning routine! Feeling energized.",
    "Hit a new milestone today - {progress}% done with my main goal!",
    "Struggling a bit this week but pushing through. Who else is with me?",
    "Sharing my weekly progress: completed {count} tasks this week!",
    "Found a great resource that helped me. Highly recommend checking it out.",
    "Day {day} of my streak! Consistency is key.",
    "Any tips for staying motivated when things get tough?",
    "Celebrating a small win today. Every step counts!",
    "Accountability check: did everyone do their daily task?",
    "This community keeps me going. Thanks for the support!",
    "New week, new goals. Let's crush it together!",
    "Reflecting on my progress this month. So grateful for this journey.",
    "Just started a new challenge within this circle. Who's joining?",
    "Morning check-in: what's everyone working on today?",
    "Reached a personal best today! Hard work pays off.",
]

# Encouragement messages
ENCOURAGEMENT_MESSAGES = [
    "You're doing amazing! Keep going!",
    "Proud of your consistency this week!",
    "Don't give up - you're closer than you think!",
    "Your progress is inspiring me to push harder too.",
    "Hey! Just checking in. How are you doing today?",
    "Remember why you started. You've got this!",
    "Incredible streak! Let's keep it going!",
    "Sending positive vibes your way today.",
    "You've made so much progress since we started!",
    "Let's both crush our goals this week!",
]

# Conversation message templates
CONV_MESSAGES = {
    'dream_creation': [
        ("user", "I want to start working towards running a half marathon. I've never run more than 3 miles."),
        ("assistant", "That's an exciting goal! Running a half marathon is a fantastic challenge. Let me help you create a structured plan. First, what's your timeline? Are you thinking 3 months, 6 months, or longer?"),
        ("user", "I'd like to do it in about 4 months if possible."),
        ("assistant", "Four months is doable with consistent training! I'll create a progressive plan that builds your endurance gradually. We'll start with 3 runs per week and increase distance by no more than 10% each week to avoid injury."),
    ],
    'check_in': [
        ("assistant", "Hey! Time for your daily check-in. How did things go today?"),
        ("user", "Pretty good! I completed 3 out of 4 tasks. Got busy in the afternoon."),
        ("assistant", "That's a solid day! 75% completion is great. Which task didn't you get to? Maybe we can find a better time slot for it."),
        ("user", "The stretching routine. I keep putting it off."),
        ("assistant", "That's really common! Try anchoring it to something you already do - like right after your morning coffee. Habit stacking makes it much easier to build consistency."),
    ],
    'motivation': [
        ("user", "I'm feeling really unmotivated this week. I've been skipping my tasks."),
        ("assistant", "I hear you. It's completely normal to hit rough patches. Let's not beat ourselves up about it. Can you tell me what's been going on?"),
        ("user", "Work has been stressful and by the time I get home I just want to do nothing."),
        ("assistant", "That makes total sense. When we're depleted, willpower drops. Here's what I suggest: let's scale back to just ONE tiny task per day this week. Something so small it feels almost silly. This keeps the habit alive without adding stress."),
        ("user", "That actually sounds manageable. Maybe just 5 minutes of stretching?"),
        ("assistant", "Perfect! Five minutes is ideal. You'll likely do more once you start, but even if you don't, you'll maintain your streak and momentum. Small wins compound into big results."),
    ],
    'planning': [
        ("user", "I need help breaking down my savings goal into weekly actions."),
        ("assistant", "Let's do it! To save $10,000 in 10 months, you need about $250 per week. Let me suggest some concrete weekly actions to hit that target."),
        ("user", "That seems like a lot. I'm not sure I can save that much."),
        ("assistant", "Let's look at it from both sides - reducing expenses and potentially increasing income. I'll create goals for tracking spending, cutting unnecessary costs, and exploring side income. Every dollar saved counts!"),
    ],
    'general': [
        ("user", "What features does the app have that I might not be using?"),
        ("assistant", "Great question! Here are some features you might find helpful: Vision Boards for visual goal-setting, the Buddy System for accountability partnerships, and Dream Circles for group motivation. Would you like to explore any of these?"),
        ("user", "Tell me more about Dream Circles."),
        ("assistant", "Dream Circles are small groups (up to 20 people) focused on shared interests. You can post progress updates, react to others' posts, and participate in time-bounded challenges. They're great for accountability and community support!"),
    ],
}

# Circle chat message templates
CIRCLE_CHAT_MESSAGES = [
    "Good morning everyone! Ready to crush it today?",
    "Just finished my daily task. Who else is on track?",
    "Has anyone tried that new technique we talked about?",
    "I'm struggling with consistency this week. Any tips?",
    "Quick update: hit my weekly goal early!",
    "Can we schedule a group call this weekend?",
    "Love the energy in this circle lately!",
    "Sharing a win: I finally completed that milestone!",
    "Anyone want to do an accountability check-in?",
    "Just read something great about habit formation. Should I share?",
    "Checking in - how's everyone doing today?",
    "Made some progress on my goal. Small steps!",
    "Thanks for the encouragement yesterday, it really helped.",
    "Who's up for a challenge this week?",
    "Feeling motivated after seeing everyone's updates!",
    "Need some advice - how do you handle setbacks?",
    "Proud of this group. We're all making progress!",
    "Reminder: don't compare your chapter 1 to someone's chapter 20.",
    "Just had a great idea for our next challenge.",
    "Happy to be part of this circle. You all inspire me!",
]

# Dream post content templates
DREAM_POST_TEMPLATES = [
    "Just took the first step toward my dream of {dream}. The journey begins! #DreamPlanner #Goals",
    "Week {week} update on my {dream} journey. Progress feels slow but I'm staying consistent.",
    "Milestone reached! I'm {progress}% closer to {dream}. Every small win counts!",
    "Reflecting on why I started chasing {dream}. The 'why' keeps me going on tough days.",
    "Sharing my morning routine that's been helping me work toward {dream}. Structure = freedom!",
    "Today was hard but I showed up anyway. {dream} won't achieve itself. #Discipline",
    "3 lessons I've learned so far while pursuing {dream}: patience, consistency, and self-compassion.",
    "Celebrating a small win today! One step closer to {dream}.",
    "Started my day at 5:30am to work on {dream}. Early mornings hit different when you have purpose.",
    "The power of community: this app helped me find people on the same journey toward {dream}.",
    "Accountability update: completed all my tasks this week for {dream}! Streak going strong.",
    "Visualization board for {dream} is complete. Seeing it every day keeps me focused.",
    "Big announcement: I just crossed the halfway mark on {dream}! Let's go!",
    "Grateful for my buddy who keeps me accountable on {dream}. Find your accountability partner!",
    "Plot twist: a setback on {dream} taught me more than a month of smooth sailing.",
    "One year ago I wouldn't have believed I'd be this close to {dream}. Trust the process.",
    "Dream update: {dream} is becoming real. Here's what I did differently this month.",
    "Needed this reminder today: progress isn't always linear. Still committed to {dream}.",
    "Just shared my {dream} goal with my circle. Making it public = making it real.",
    "End of month review: {dream} progress at {progress}%. Adjusting my approach for next month.",
]

# Dream post comment templates
DREAM_POST_COMMENT_TEMPLATES = [
    "This is so inspiring! Keep going!",
    "Love this update! You're doing amazing.",
    "I'm on a similar journey. We got this!",
    "Needed to see this today. Thank you for sharing!",
    "Your consistency is incredible. Goals!",
    "How do you stay so motivated?",
    "This made my day. Proud of you!",
    "Can you share more about your routine?",
    "Amazing progress! You should be so proud.",
    "Following your journey closely. So motivating!",
    "What a great milestone to hit!",
    "Your dedication is showing. Keep it up!",
    "This is exactly the energy I needed today.",
    "You're proof that consistency pays off!",
    "Love the positive vibes! Sharing with my circle.",
]

# Dream post comment reply templates
DREAM_POST_REPLY_TEMPLATES = [
    "Thank you so much! Means a lot.",
    "We definitely got this together!",
    "Happy to share! Ask me anything.",
    "It's all about showing up every day.",
    "Your support means everything!",
    "We're all in this together!",
    "Thanks for following along!",
    "That's so kind of you to say!",
]

# Encouragement types for DreamEncouragement
ENCOURAGEMENT_TYPES = ['you_got_this', 'keep_going', 'inspired', 'proud', 'fire']

# Encouragement messages for DreamEncouragement
DREAM_ENCOURAGEMENT_MESSAGES = [
    "Believe in yourself - you've come so far!",
    "Your journey inspires me every single day.",
    "Keep pushing! The best is yet to come.",
    "You're a testament to what consistency looks like.",
    "So proud of how far you've come!",
    "Never stop dreaming. You're making it happen!",
    "Your progress speaks volumes. Keep going!",
    "Sending all the positive energy your way!",
    "",  # Some encouragements have no message, just the type
    "",
    "",
]

# GoFundMe-style URLs for demo posts
GOFUNDME_URLS = [
    'https://www.gofundme.com/f/marathon-training-gear',
    'https://www.gofundme.com/f/music-studio-equipment',
    'https://www.gofundme.com/f/coding-bootcamp-tuition',
    'https://www.gofundme.com/f/art-supplies-for-portfolio',
    'https://www.gofundme.com/f/travel-dream-southeast-asia',
]

# Notification templates
NOTIF_TEMPLATES = [
    {'type': 'reminder', 'title': 'Task Reminder', 'body': "Don't forget: {task}"},
    {'type': 'motivation', 'title': 'Daily Motivation', 'body': 'Every small step counts. Keep pushing toward your dreams!'},
    {'type': 'progress', 'title': 'Weekly Progress', 'body': 'You completed {count} tasks this week. Great job!'},
    {'type': 'achievement', 'title': 'Achievement Unlocked!', 'body': 'You earned a new badge! Check your profile.'},
    {'type': 'check_in', 'title': 'Check-in Time', 'body': "How's your day going? Log your progress now."},
    {'type': 'streak_milestone', 'title': 'Streak Milestone!', 'body': "You're on a {days}-day streak! Keep it alive!"},
    {'type': 'system', 'title': 'Welcome to DreamPlanner!', 'body': "Start by creating your first dream. We'll guide you every step of the way."},
    {'type': 'buddy', 'title': 'Buddy Message', 'body': 'Your buddy sent you encouragement. Check it out!'},
]


class Command(BaseCommand):
    help = 'Seed database with comprehensive demo data (~12,000 records)'

    def add_arguments(self, parser):
        parser.add_argument('--flush', action='store_true', help='Clear all demo data before recreating.')
        parser.add_argument('--skip-prerequisites', action='store_true', help='Skip running prerequisite seed commands.')

    def handle(self, *args, **options):
        global NOW
        NOW = timezone.now()
        random.seed(42)

        if options['flush']:
            self._flush()

        # Check idempotency
        if User.objects.filter(email__endswith=f'@{DEMO_EMAIL_DOMAIN}').exists():
            self.stdout.write(self.style.NOTICE('Demo data already exists. Use --flush to recreate.'))
            return

        if not options.get('skip_prerequisites'):
            self._run_prerequisites()

        with transaction.atomic():
            users = self._create_users()
            user_map = {u.display_name: u for u in users}
            arch_map = self._build_archetype_map(users)

            self._create_gamification_profiles(users)
            self._create_subscriptions(users)

            dreams = self._create_dreams(users, arch_map)
            all_goals, all_tasks = self._create_goals_and_tasks(dreams)
            self._create_calibrations_and_obstacles(dreams)
            self._create_tags_and_taggings(dreams)
            self._create_progress_snapshots(dreams)
            self._create_vision_boards(dreams)
            self._create_collaborators_and_shares(dreams, users, arch_map)

            self._create_conversations_and_messages(users, dreams, arch_map)
            self._create_circles(users, user_map, arch_map)
            self._create_buddy_pairings(users, arch_map)
            self._create_social_graph(users, arch_map)
            self._create_activity_feed(users, arch_map)
            self._create_league_standings(users)
            self._create_store_purchases(users, arch_map)
            self._create_notifications(users, arch_map)
            self._create_calendar_events(users, all_tasks, arch_map)
            self._create_daily_activities(users, arch_map)
            self._create_achievements_and_searches(users, arch_map)
            self._create_calls(users, arch_map)
            self._create_message_read_statuses(users)
            self._create_circle_chat_messages(users, arch_map)
            self._create_circle_calls(users, arch_map)
            self._create_dream_posts(users, dreams, arch_map)

        self.stdout.write(self.style.SUCCESS('Demo data seeded successfully! (~15,000 records)'))

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _flush(self):
        from django.db.models.signals import post_delete
        from apps.dreams.signals import recalculate_goal_progress_on_task_delete
        from apps.dreams.models import Task as DreamTask

        # Disconnect signal that creates snapshots during cascade delete
        post_delete.disconnect(recalculate_goal_progress_on_task_delete, sender=DreamTask)

        try:
            # Delete users (cascades most other models)
            count, _ = User.objects.filter(email__endswith=f'@{DEMO_EMAIL_DOMAIN}').delete()
            # Clean up orphaned circles
            Circle.objects.filter(creator__isnull=True).delete()
            self.stdout.write(self.style.WARNING(f'Flushed {count} demo records.'))
        finally:
            # Reconnect signal
            post_delete.connect(recalculate_goal_progress_on_task_delete, sender=DreamTask)

    def _run_prerequisites(self):
        self.stdout.write('Running prerequisite seed commands...')
        for cmd in ['seed_leagues', 'seed_subscription_plans', 'seed_store',
                     'seed_achievements', 'seed_dream_templates',
                     'seed_conversation_templates', 'seed_notification_templates']:
            try:
                call_command(cmd, verbosity=0)
            except Exception as e:
                self.stdout.write(self.style.WARNING(f'  {cmd} skipped: {e}'))
        self.stdout.write('  Prerequisites done.')

    def _build_archetype_map(self, users):
        m = {}
        for p, u in zip(USER_PERSONAS, users):
            arch = p['arch']
            m.setdefault(arch, []).append(u)
        return m

    def _rand_dt(self, max_days_ago, min_days_ago=0):
        return NOW - timedelta(
            days=random.randint(min_days_ago, max_days_ago),
            hours=random.randint(0, 23),
            minutes=random.randint(0, 59),
        )

    def _users_by_arch(self, arch_map, *archetypes):
        result = []
        for a in archetypes:
            result.extend(arch_map.get(a, []))
        return result

    # ------------------------------------------------------------------
    # Phase 1: Users
    # ------------------------------------------------------------------
    def _create_users(self):
        self.stdout.write('Creating 40 demo users...')
        users = []
        for p in USER_PERSONAS:
            is_inactive = p['arch'] == 'inactive'
            last_activity = self._rand_dt(60, 30) if is_inactive else self._rand_dt(2, 0)

            u = User.objects.create_user(
                email=f"{p['slug']}@{DEMO_EMAIL_DOMAIN}",
                password=DEMO_PASSWORD,
                display_name=p['display_name'],
                bio=p['bio'],
                location=p['loc'],
                profile_visibility=p['vis'],
                subscription=p['sub'],
                subscription_ends=(NOW + timedelta(days=30)) if p['sub'] != 'free' else None,
                timezone=p['tz'],
                xp=p['xp'],
                level=p['level'],
                streak_days=p['streak'],
                last_activity=last_activity,
                is_online=p['arch'] in ('power', 'social') and random.random() > 0.5,
                last_seen=last_activity,
                social_links={'twitter': f"@{p['slug'].replace('.', '_')}"} if p['arch'] in ('power', 'social') else None,
                work_schedule={'workDays': [0, 1, 2, 3, 4], 'startTime': '09:00', 'endTime': '17:00'},
                notification_prefs={'pushEnabled': True, 'emailEnabled': True, 'dndEnabled': True, 'dndStart': 22, 'dndEnd': 7},
                app_prefs={'theme': random.choice(['dark', 'light']), 'language': 'en'},
            )
            # Backdate created_at
            User.objects.filter(pk=u.pk).update(created_at=NOW - timedelta(days=p['days_ago']))
            # Force demo accounts online with recent last_seen
            if p['slug'] in ('sophia.chen', 'emma.laurent'):
                User.objects.filter(pk=u.pk).update(is_online=True, last_seen=NOW)
                u.is_online = True
                u.last_seen = NOW
            users.append(u)

        # Verify all emails so demo users can log in
        from allauth.account.models import EmailAddress
        email_records = [
            EmailAddress(user=u, email=u.email, verified=True, primary=True)
            for u in users
        ]
        EmailAddress.objects.bulk_create(email_records, batch_size=50, ignore_conflicts=True)

        self.stdout.write(f'  Created {len(users)} users (emails verified).')
        return users

    # ------------------------------------------------------------------
    # Phase 2: Gamification Profiles
    # ------------------------------------------------------------------
    def _create_gamification_profiles(self, users):
        profiles = []
        for p, u in zip(USER_PERSONAS, users):
            xp = p['xp']
            profiles.append(GamificationProfile(
                user=u,
                health_xp=int(xp * random.uniform(0.1, 0.3)),
                career_xp=int(xp * random.uniform(0.1, 0.25)),
                relationships_xp=int(xp * random.uniform(0.05, 0.15)),
                personal_growth_xp=int(xp * random.uniform(0.1, 0.2)),
                finance_xp=int(xp * random.uniform(0.05, 0.15)),
                hobbies_xp=int(xp * random.uniform(0.05, 0.15)),
                streak_jokers=3 + (2 if p['sub'] == 'pro' else 0),
            ))
        GamificationProfile.objects.bulk_create(profiles, batch_size=50)
        self.stdout.write('  Created gamification profiles.')

    # ------------------------------------------------------------------
    # Phase 3: Subscriptions
    # ------------------------------------------------------------------
    def _create_subscriptions(self, users):
        plans = {p.slug: p for p in SubscriptionPlan.objects.all()}
        if not plans:
            self.stdout.write(self.style.WARNING('  No subscription plans found. Skipping.'))
            return

        customers = []
        subs = []
        for p, u in zip(USER_PERSONAS, users):
            if p['sub'] == 'free':
                continue
            plan = plans.get(p['sub'])
            if not plan:
                continue
            customers.append(StripeCustomer(
                user=u,
                stripe_customer_id=f'cus_demo_{u.pk.hex[:16]}',
            ))
            subs.append(Subscription(
                user=u,
                plan=plan,
                stripe_subscription_id=f'sub_demo_{u.pk.hex[:16]}',
                status='active',
                current_period_start=NOW - timedelta(days=15),
                current_period_end=NOW + timedelta(days=15),
            ))
        StripeCustomer.objects.bulk_create(customers, batch_size=50, ignore_conflicts=True)
        Subscription.objects.bulk_create(subs, batch_size=50, ignore_conflicts=True)
        self.stdout.write(f'  Created {len(subs)} subscriptions.')

    # ------------------------------------------------------------------
    # Phase 4: Dreams
    # ------------------------------------------------------------------
    def _create_dreams(self, users, arch_map):
        dream_counts = {'power': (5, 8), 'premium': (3, 5), 'casual': (1, 3),
                        'new': (0, 1), 'social': (2, 4), 'inactive': (2, 3)}
        categories = list(DREAM_LIBRARY.keys())
        all_dreams = []

        for p, u in zip(USER_PERSONAS, users):
            lo, hi = dream_counts.get(p['arch'], (1, 2))
            count = random.randint(lo, hi)
            if count == 0:
                continue

            chosen_cats = random.sample(categories, min(count, len(categories)))
            for i, cat in enumerate(chosen_cats):
                tmpl = random.choice(DREAM_LIBRARY[cat])
                status_pool = ['active'] * 3 + ['completed'] + ['paused']
                if p['arch'] == 'inactive':
                    status_pool = ['paused', 'archived']
                dream_status = random.choice(status_pool)
                progress = random.uniform(10, 90) if dream_status == 'active' else (100.0 if dream_status == 'completed' else random.uniform(5, 40))

                d = Dream(
                    user=u,
                    title=tmpl['title'],
                    description=tmpl['desc'],
                    category=cat,
                    priority=random.randint(1, 5),
                    status=dream_status,
                    target_date=NOW + timedelta(days=random.randint(30, 180)),
                    progress_percentage=round(progress, 1),
                    calibration_status=random.choice(['completed', 'skipped']),
                    has_two_minute_start=random.random() > 0.7,
                    completed_at=self._rand_dt(30, 5) if dream_status == 'completed' else None,
                )
                d._template = tmpl  # stash for goals/tasks
                d._user_arch = p['arch']
                all_dreams.append(d)

        Dream.objects.bulk_create(all_dreams, batch_size=100)
        self.stdout.write(f'  Created {len(all_dreams)} dreams.')
        return all_dreams

    # ------------------------------------------------------------------
    # Phase 5: Goals & Tasks
    # ------------------------------------------------------------------
    def _create_goals_and_tasks(self, dreams):
        all_goals = []
        all_tasks = []

        for dream in dreams:
            tmpl = dream._template
            for g_idx, g_tmpl in enumerate(tmpl['goals']):
                goal_status = 'completed' if dream.status == 'completed' else random.choice(['pending', 'in_progress', 'completed'] if g_idx == 0 else ['pending', 'in_progress'])
                g = Goal(
                    dream=dream,
                    title=g_tmpl['title'],
                    description=f"Goal for: {g_tmpl['title']}",
                    order=g_idx,
                    estimated_minutes=random.randint(60, 300),
                    status=goal_status,
                    progress_percentage=100.0 if goal_status == 'completed' else random.uniform(0, 80),
                    completed_at=self._rand_dt(20, 3) if goal_status == 'completed' else None,
                )
                g._tasks_tmpl = g_tmpl['tasks']
                g._dream_ref = dream
                all_goals.append(g)

        Goal.objects.bulk_create(all_goals, batch_size=200)

        for goal in all_goals:
            for t_idx, t_title in enumerate(goal._tasks_tmpl):
                task_status = 'completed' if goal.status == 'completed' else random.choice(['pending', 'completed', 'pending'])
                sched_date = self._rand_dt(60, 0) if task_status == 'completed' else NOW + timedelta(days=random.randint(1, 30))
                all_tasks.append(Task(
                    goal=goal,
                    title=t_title,
                    description='',
                    order=t_idx,
                    scheduled_date=sched_date,
                    scheduled_time=f'{random.randint(6, 20):02d}:00',
                    duration_mins=random.choice([15, 20, 30, 45, 60]),
                    status=task_status,
                    completed_at=sched_date if task_status == 'completed' else None,
                ))

        Task.objects.bulk_create(all_tasks, batch_size=500)
        self.stdout.write(f'  Created {len(all_goals)} goals, {len(all_tasks)} tasks.')
        return all_goals, all_tasks

    # ------------------------------------------------------------------
    # Phase 6: Calibrations & Obstacles
    # ------------------------------------------------------------------
    def _create_calibrations_and_obstacles(self, dreams):
        calibrations = []
        obstacles = []
        cal_categories = ['experience', 'timeline', 'resources', 'motivation', 'constraints']

        for dream in dreams:
            if dream.calibration_status == 'completed':
                for q_num in range(1, random.randint(3, 6)):
                    calibrations.append(CalibrationResponse(
                        dream=dream,
                        question=f"Calibration question {q_num} for {dream.title}?",
                        answer=f"User response to question {q_num}.",
                        question_number=q_num,
                        category=random.choice(cal_categories),
                    ))

            obstacles.append(Obstacle(
                dream=dream,
                title=f'Time management for {dream.title}',
                description='Finding enough time in the schedule.',
                obstacle_type='predicted',
                solution='Block specific time slots and protect them.',
                status=random.choice(['active', 'resolved']),
            ))

        CalibrationResponse.objects.bulk_create(calibrations, batch_size=500)
        Obstacle.objects.bulk_create(obstacles, batch_size=200)
        self.stdout.write(f'  Created {len(calibrations)} calibrations, {len(obstacles)} obstacles.')

    # ------------------------------------------------------------------
    # Phase 7: Tags & Taggings
    # ------------------------------------------------------------------
    def _create_tags_and_taggings(self, dreams):
        tags = []
        for name in DREAM_TAGS:
            tags.append(DreamTag(name=name))
        DreamTag.objects.bulk_create(tags, batch_size=50, ignore_conflicts=True)
        tag_objs = list(DreamTag.objects.filter(name__in=DREAM_TAGS))

        taggings = []
        for dream in dreams:
            chosen = random.sample(tag_objs, min(random.randint(1, 3), len(tag_objs)))
            for tag in chosen:
                taggings.append(DreamTagging(dream=dream, tag=tag))

        DreamTagging.objects.bulk_create(taggings, batch_size=500, ignore_conflicts=True)
        self.stdout.write(f'  Created {len(tag_objs)} tags, {len(taggings)} taggings.')

    # ------------------------------------------------------------------
    # Phase 8: Progress Snapshots
    # ------------------------------------------------------------------
    def _create_progress_snapshots(self, dreams):
        snapshots = []
        for dream in dreams:
            arch = getattr(dream, '_user_arch', 'casual')
            days_active = 5 if arch == 'new' else max(15, 60)
            num_points = random.randint(3, max(3, min(20, days_active // 3)))
            final_val = dream.progress_percentage

            for i in range(num_points):
                day_offset = int((i / max(num_points - 1, 1)) * days_active)
                progress = (i / max(num_points - 1, 1)) * final_val
                snap_date = (NOW - timedelta(days=days_active - day_offset)).date()
                snapshots.append(DreamProgressSnapshot(
                    dream=dream,
                    date=snap_date,
                    progress_percentage=round(progress, 1),
                ))

        DreamProgressSnapshot.objects.bulk_create(snapshots, batch_size=500, ignore_conflicts=True)
        self.stdout.write(f'  Created {len(snapshots)} progress snapshots.')

    # ------------------------------------------------------------------
    # Phase 9: Vision Boards
    # ------------------------------------------------------------------
    def _create_vision_boards(self, dreams):
        images = []
        for dream in dreams:
            if random.random() > 0.7:
                for i in range(random.randint(1, 3)):
                    images.append(VisionBoardImage(
                        dream=dream,
                        image_url=f'https://picsum.photos/seed/{dream.pk.hex[:8]}_{i}/800/600',
                        caption=f'Vision for {dream.title}',
                        is_ai_generated=random.random() > 0.5,
                        order=i,
                    ))
        VisionBoardImage.objects.bulk_create(images, batch_size=100)
        self.stdout.write(f'  Created {len(images)} vision board images.')

    # ------------------------------------------------------------------
    # Phase 10: Collaborators & Shares
    # ------------------------------------------------------------------
    def _create_collaborators_and_shares(self, dreams, users, arch_map):
        collabs = []
        shares = []
        power_social = self._users_by_arch(arch_map, 'power', 'social')

        for dream in dreams:
            if dream.user in power_social and random.random() > 0.7:
                viewer = random.choice([u for u in users if u != dream.user])
                collabs.append(DreamCollaborator(dream=dream, user=viewer, role='viewer'))
                shares.append(SharedDream(
                    dream=dream, shared_by=dream.user, shared_with=viewer, permission='view',
                ))

        DreamCollaborator.objects.bulk_create(collabs, batch_size=100, ignore_conflicts=True)
        SharedDream.objects.bulk_create(shares, batch_size=100, ignore_conflicts=True)
        self.stdout.write(f'  Created {len(collabs)} collaborators, {len(shares)} shared dreams.')

    # ------------------------------------------------------------------
    # Phase 11: Conversations & Messages
    # ------------------------------------------------------------------
    def _create_conversations_and_messages(self, users, dreams, arch_map):
        conv_counts = {'power': (6, 10), 'premium': (3, 5), 'casual': (1, 2),
                       'new': (0, 1), 'social': (3, 5), 'inactive': (1, 2)}
        conv_types = list(CONV_MESSAGES.keys())
        all_convs = []
        all_msgs = []

        user_dreams = {}
        for d in dreams:
            user_dreams.setdefault(d.user_id, []).append(d)

        for p, u in zip(USER_PERSONAS, users):
            lo, hi = conv_counts.get(p['arch'], (1, 2))
            count = random.randint(lo, hi)

            for _ in range(count):
                c_type = random.choice(conv_types)
                dream_link = None
                u_dreams = user_dreams.get(u.pk, [])
                if u_dreams and c_type in ('dream_creation', 'planning', 'check_in'):
                    dream_link = random.choice(u_dreams)

                conv = Conversation(
                    user=u,
                    dream=dream_link,
                    conversation_type=c_type,
                    title=f'{c_type.replace("_", " ").title()} Session',
                    total_messages=0,
                    total_tokens_used=0,
                )
                all_convs.append(conv)

        Conversation.objects.bulk_create(all_convs, batch_size=200)

        for conv in all_convs:
            msg_templates = CONV_MESSAGES.get(conv.conversation_type, CONV_MESSAGES['general'])
            for role, content in msg_templates:
                all_msgs.append(Message(
                    conversation=conv,
                    role=role,
                    content=content,
                    metadata={'tokens_used': random.randint(50, 200)},
                ))
            # Update message count
            Conversation.objects.filter(pk=conv.pk).update(
                total_messages=len(msg_templates),
                total_tokens_used=sum(random.randint(50, 200) for _ in msg_templates),
            )

        Message.objects.bulk_create(all_msgs, batch_size=500)
        self.stdout.write(f'  Created {len(all_convs)} conversations, {len(all_msgs)} messages.')

    # ------------------------------------------------------------------
    # Phase 12: Circles
    # ------------------------------------------------------------------
    def _create_circles(self, users, user_map, arch_map):
        circle_defs = [
            ('Morning Runners', 'fitness', 'Sophia Chen', True, 20),
            ('Career Climbers', 'career', 'Marcus Williams', True, 20),
            ('Budget Warriors', 'finance', 'Emma Laurent', True, 15),
            ('Creative Writers Guild', 'creativity', 'Isabella Costa', False, 10),
            ('Meditation Circle', 'personal_growth', 'Aisha Patel', True, 20),
            ('Language Learners', 'education', 'Yuki Nakamura', True, 20),
            ('Travel Dreamers', 'hobbies', 'Taylor Brooks', True, 15),
            ('Fitness First', 'health', 'Kenji Tanaka', True, 20),
            ('Side Hustle Club', 'career', 'Sam Wilson', False, 10),
            ('Book Club', 'education', 'Priya Sharma', True, 15),
            ('Photography Crew', 'creativity', 'Alex Rivera', True, 15),
            ('Mindful Living', 'personal_growth', 'Maya Gupta', True, 20),
        ]

        circles = []
        for name, cat, creator_name, is_public, max_mem in circle_defs:
            creator = user_map.get(creator_name)
            if not creator:
                continue
            circles.append(Circle(
                name=name, description=f'A circle for {name.lower()} enthusiasts.',
                category=cat, is_public=is_public, creator=creator, max_members=max_mem,
            ))
        Circle.objects.bulk_create(circles, batch_size=20)

        # Memberships
        eligible = self._users_by_arch(arch_map, 'power', 'premium', 'social')
        memberships = []
        all_posts = []
        all_reactions = []

        for circle in circles:
            # Creator is admin
            memberships.append(CircleMembership(circle=circle, user=circle.creator, role='admin'))
            # Add random members
            members = random.sample([u for u in eligible if u != circle.creator], min(random.randint(5, 12), len(eligible) - 1))
            for i, member in enumerate(members):
                role = 'moderator' if i == 0 else 'member'
                memberships.append(CircleMembership(circle=circle, user=member, role=role))

            # Posts
            all_members = [circle.creator] + members
            for _ in range(random.randint(5, 12)):
                author = random.choice(all_members)
                post = CirclePost(
                    circle=circle,
                    author=author,
                    content=random.choice(CIRCLE_POST_TEMPLATES).format(
                        progress=random.randint(20, 90), count=random.randint(3, 12), day=random.randint(5, 60),
                    ),
                )
                all_posts.append(post)

        CircleMembership.objects.bulk_create(memberships, batch_size=200, ignore_conflicts=True)
        CirclePost.objects.bulk_create(all_posts, batch_size=200)

        # Reactions on posts
        for post in all_posts:
            if random.random() > 0.4:
                reactor = random.choice(eligible)
                all_reactions.append(PostReaction(
                    post=post, user=reactor,
                    reaction_type=random.choice(['thumbs_up', 'fire', 'clap', 'heart']),
                ))
        PostReaction.objects.bulk_create(all_reactions, batch_size=500, ignore_conflicts=True)

        # Challenges
        challenges_created = 0
        for circle in circles:
            if random.random() > 0.4:
                ch = CircleChallenge.objects.create(
                    circle=circle,
                    title=f'{circle.name} Weekly Challenge',
                    description=f'Complete daily tasks for one week in {circle.name}!',
                    start_date=NOW - timedelta(days=7),
                    end_date=NOW + timedelta(days=7),
                    status='active',
                )
                participants = CircleMembership.objects.filter(circle=circle).values_list('user', flat=True)[:8]
                ch.participants.add(*participants)
                challenges_created += 1

        # Invitations for private circles
        invitations = []
        for circle in circles:
            if not circle.is_public:
                invitations.append(CircleInvitation(
                    circle=circle,
                    inviter=circle.creator,
                    invite_code=get_random_string(12),
                    status='pending',
                    expires_at=NOW + timedelta(days=7),
                ))
        CircleInvitation.objects.bulk_create(invitations, batch_size=20)

        self.stdout.write(f'  Created {len(circles)} circles, {len(memberships)} memberships, '
                          f'{len(all_posts)} posts, {len(all_reactions)} reactions, '
                          f'{challenges_created} challenges.')

    # ------------------------------------------------------------------
    # Phase 13: Buddy Pairings
    # ------------------------------------------------------------------
    def _create_buddy_pairings(self, users, arch_map):
        power = arch_map.get('power', [])
        social = arch_map.get('social', [])
        premium = arch_map.get('premium', [])
        inactive = arch_map.get('inactive', [])

        pairings = []
        encouragements = []

        # Guarantee Sophia Chen <-> Emma Laurent pairing (demo accounts)
        sophia = next((u for u in users if u.display_name == 'Sophia Chen'), None)
        emma = next((u for u in users if u.display_name == 'Emma Laurent'), None)
        paired = set()
        if sophia and emma:
            bp = BuddyPairing(
                user1=sophia, user2=emma, status='active',
                compatibility_score=0.92,
                encouragement_streak=18,
                best_encouragement_streak=22,
                last_encouragement_at=self._rand_dt(1, 0),
            )
            pairings.append(bp)
            paired.add(sophia.pk)
            paired.add(emma.pk)

        # Active pairings between power/social/premium
        pair_pool = power + social + premium
        for _ in range(min(10, len(pair_pool) // 2)):
            available = [u for u in pair_pool if u.pk not in paired]
            if len(available) < 2:
                break
            u1, u2 = random.sample(available, 2)
            paired.add(u1.pk)
            paired.add(u2.pk)
            bp = BuddyPairing(
                user1=u1, user2=u2, status='active',
                compatibility_score=round(random.uniform(0.65, 0.95), 2),
                encouragement_streak=random.randint(5, 25),
                best_encouragement_streak=random.randint(10, 30),
                last_encouragement_at=self._rand_dt(3, 0),
            )
            pairings.append(bp)

        # Completed pairings for inactive
        if len(inactive) >= 2:
            bp = BuddyPairing(
                user1=inactive[0], user2=inactive[1], status='completed',
                compatibility_score=0.72, encouragement_streak=0,
                best_encouragement_streak=15,
                ended_at=self._rand_dt(40, 30),
            )
            pairings.append(bp)

        BuddyPairing.objects.bulk_create(pairings, batch_size=50)

        for bp in pairings:
            if bp.status == 'active':
                for _ in range(random.randint(5, 15)):
                    sender = random.choice([bp.user1, bp.user2])
                    encouragements.append(BuddyEncouragement(
                        pairing=bp,
                        sender=sender,
                        message=random.choice(ENCOURAGEMENT_MESSAGES),
                    ))

        BuddyEncouragement.objects.bulk_create(encouragements, batch_size=200)
        self.stdout.write(f'  Created {len(pairings)} buddy pairings, {len(encouragements)} encouragements.')

    # ------------------------------------------------------------------
    # Phase 14: Social Graph
    # ------------------------------------------------------------------
    def _create_social_graph(self, users, arch_map):
        friendships = []
        follows = []
        existing_pairs = set()

        social = arch_map.get('social', [])
        power = arch_map.get('power', [])
        premium = arch_map.get('premium', [])
        casual = arch_map.get('casual', [])
        new_users = arch_map.get('new', [])

        # Guarantee Sophia <-> Emma friendship (demo accounts)
        sophia = next((u for u in users if u.display_name == 'Sophia Chen'), None)
        emma = next((u for u in users if u.display_name == 'Emma Laurent'), None)
        if sophia and emma:
            pair = tuple(sorted([sophia.pk, emma.pk], key=str))
            existing_pairs.add(pair)
            friendships.append(Friendship(user1=sophia, user2=emma, status='accepted'))

        # Social butterflies: lots of friendships
        for u in social:
            targets = random.sample([x for x in users if x != u], min(18, len(users) - 1))
            for t in targets:
                pair = tuple(sorted([u.pk, t.pk], key=str))
                if pair not in existing_pairs:
                    existing_pairs.add(pair)
                    friendships.append(Friendship(
                        user1=u, user2=t,
                        status=random.choice(['accepted'] * 9 + ['pending']),
                    ))

        # Power users: friends with each other + some premium
        for u in power:
            targets = random.sample([x for x in (power + premium) if x != u], min(8, len(power + premium) - 1))
            for t in targets:
                pair = tuple(sorted([u.pk, t.pk], key=str))
                if pair not in existing_pairs:
                    existing_pairs.add(pair)
                    friendships.append(Friendship(user1=u, user2=t, status='accepted'))

        # Casual: a few friends
        for u in casual:
            targets = random.sample([x for x in users if x != u], min(3, len(users) - 1))
            for t in targets:
                pair = tuple(sorted([u.pk, t.pk], key=str))
                if pair not in existing_pairs:
                    existing_pairs.add(pair)
                    friendships.append(Friendship(user1=u, user2=t, status='accepted'))

        # A few rejected
        if len(new_users) >= 2:
            pair = tuple(sorted([new_users[0].pk, new_users[1].pk], key=str))
            if pair not in existing_pairs:
                existing_pairs.add(pair)
                friendships.append(Friendship(user1=new_users[0], user2=new_users[1], status='rejected'))

        Friendship.objects.bulk_create(friendships, batch_size=500, ignore_conflicts=True)

        # Follows: asymmetric
        existing_follows = set()
        for u in social + power:
            # Many people follow power/social users
            followers_pool = [x for x in users if x != u]
            for follower in random.sample(followers_pool, min(random.randint(10, 25), len(followers_pool))):
                fk = (follower.pk, u.pk)
                if fk not in existing_follows:
                    existing_follows.add(fk)
                    follows.append(UserFollow(follower=follower, following=u))

        # Everyone follows Sophia Chen (top user)
        sophia = next((u for u in users if u.display_name == 'Sophia Chen'), None)
        if sophia:
            for u in users:
                if u != sophia:
                    fk = (u.pk, sophia.pk)
                    if fk not in existing_follows:
                        existing_follows.add(fk)
                        follows.append(UserFollow(follower=u, following=sophia))

        UserFollow.objects.bulk_create(follows, batch_size=500, ignore_conflicts=True)

        # Blocks & Reports (minimal)
        inactive = arch_map.get('inactive', [])
        if len(inactive) >= 2:
            BlockedUser.objects.create(blocker=inactive[0], blocked=inactive[1], reason='Personal reasons.')
        if len(casual) >= 2:
            BlockedUser.objects.create(blocker=casual[0], blocked=casual[1], reason='Spam messages.')
        if len(casual) >= 3:
            ReportedUser.objects.create(
                reporter=casual[2], reported=casual[1],
                reason='Sending spam content.', category='spam', status='dismissed',
            )
        if len(new_users) >= 2:
            ReportedUser.objects.create(
                reporter=new_users[0], reported=new_users[1],
                reason='Inappropriate behavior.', category='harassment', status='pending',
            )

        self.stdout.write(f'  Created {len(friendships)} friendships, {len(follows)} follows, blocks & reports.')

    # ------------------------------------------------------------------
    # Phase 15: Activity Feed
    # ------------------------------------------------------------------
    def _create_activity_feed(self, users, arch_map):
        feed_counts = {'power': (20, 35), 'premium': (10, 18), 'casual': (3, 8),
                       'new': (0, 2), 'social': (15, 25), 'inactive': (5, 10)}
        activity_types = ['task_completed', 'dream_completed', 'milestone_reached',
                          'level_up', 'streak_milestone', 'circle_joined', 'badge_earned']
        items = []

        for p, u in zip(USER_PERSONAS, users):
            lo, hi = feed_counts.get(p['arch'], (1, 5))
            count = random.randint(lo, hi)
            for _ in range(count):
                a_type = random.choice(activity_types)
                items.append(ActivityFeedItem(
                    user=u,
                    activity_type=a_type,
                    content={'title': f'{a_type.replace("_", " ").title()}', 'description': f'{u.display_name} activity'},
                    data={'xp_earned': random.randint(10, 100)},
                ))

        ActivityFeedItem.objects.bulk_create(items, batch_size=500)
        self.stdout.write(f'  Created {len(items)} activity feed items.')

    # ------------------------------------------------------------------
    # Phase 16: League Standings
    # ------------------------------------------------------------------
    def _create_league_standings(self, users):
        leagues = list(League.objects.all().order_by('min_xp'))
        season = Season.get_active_season()
        if not leagues or not season:
            self.stdout.write(self.style.WARNING('  No leagues/season found. Skipping.'))
            return

        standings = []
        snapshots = []

        for p, u in zip(USER_PERSONAS, users):
            xp = p['xp']
            league = leagues[0]
            for lg in leagues:
                if lg.contains_xp(xp):
                    league = lg
                    break

            season_xp = int(xp * random.uniform(0.5, 0.8))
            standings.append(LeagueStanding(
                user=u, league=league, season=season,
                xp_earned_this_season=season_xp,
                tasks_completed=random.randint(5, 200) if p['arch'] != 'new' else random.randint(0, 5),
                dreams_completed=random.randint(0, 3),
                streak_best=p['streak'],
            ))

        LeagueStanding.objects.bulk_create(standings, batch_size=50, ignore_conflicts=True)

        # Assign ranks
        all_standings = LeagueStanding.objects.filter(season=season).order_by('-xp_earned_this_season')
        for rank, st in enumerate(all_standings, 1):
            LeagueStanding.objects.filter(pk=st.pk).update(rank=rank)

        # Rank snapshots (last 30 days)
        for standing in standings:
            league = standing.league
            for day_offset in range(0, 30, 3):
                snap_date = (NOW - timedelta(days=day_offset)).date()
                snapshots.append(RankSnapshot(
                    user=standing.user, season=season, league=league,
                    rank=standing.rank + random.randint(-2, 2) if standing.rank > 2 else standing.rank,
                    xp=int(standing.xp_earned_this_season * (1 - day_offset / 90)),
                    snapshot_date=snap_date,
                ))

        RankSnapshot.objects.bulk_create(snapshots, batch_size=500, ignore_conflicts=True)
        self.stdout.write(f'  Created {len(standings)} standings, {len(snapshots)} rank snapshots.')

    # ------------------------------------------------------------------
    # Phase 17: Store Purchases
    # ------------------------------------------------------------------
    def _create_store_purchases(self, users, arch_map):
        items = list(StoreItem.objects.filter(is_active=True))
        if not items:
            self.stdout.write(self.style.WARNING('  No store items found. Skipping.'))
            return

        inventory = []
        wishlists = []
        gifts = []

        power = arch_map.get('power', [])
        social = arch_map.get('social', [])
        premium = arch_map.get('premium', [])
        casual = arch_map.get('casual', [])

        # Power users buy many items
        for u in power:
            bought = random.sample(items, min(random.randint(4, 8), len(items)))
            for i, item in enumerate(bought):
                inventory.append(UserInventory(
                    user=u, item=item,
                    stripe_payment_intent_id=f'pi_demo_{u.pk.hex[:8]}_{item.pk.hex[:8]}',
                    is_equipped=(i == 0),
                ))

        # Social/Premium buy a few
        for u in social + premium[:4]:
            bought = random.sample(items, min(random.randint(1, 3), len(items)))
            for item in bought:
                inventory.append(UserInventory(
                    user=u, item=item,
                    stripe_payment_intent_id=f'pi_demo_{u.pk.hex[:8]}_{item.pk.hex[:8]}',
                ))

        UserInventory.objects.bulk_create(inventory, batch_size=100, ignore_conflicts=True)

        # Wishlists for casual users
        for u in casual[:5]:
            wished = random.sample(items, min(2, len(items)))
            for item in wished:
                wishlists.append(Wishlist(user=u, item=item))
        Wishlist.objects.bulk_create(wishlists, batch_size=50, ignore_conflicts=True)

        # Gifts
        if len(power) >= 2 and len(premium) >= 1:
            gifts.append(Gift(
                sender=power[0], recipient=premium[0], item=random.choice(items),
                message='Keep up the great work!',
                stripe_payment_intent_id=f'pi_gift_{uuid.uuid4().hex[:16]}',
                is_claimed=True, claimed_at=self._rand_dt(10, 2),
            ))
            gifts.append(Gift(
                sender=power[1], recipient=social[0] if social else premium[1], item=random.choice(items),
                message='A gift for my accountability buddy!',
                stripe_payment_intent_id=f'pi_gift_{uuid.uuid4().hex[:16]}',
                is_claimed=False,
            ))
        Gift.objects.bulk_create(gifts, batch_size=10)

        self.stdout.write(f'  Created {len(inventory)} inventory, {len(wishlists)} wishlists, {len(gifts)} gifts.')

    # ------------------------------------------------------------------
    # Phase 18: Notifications
    # ------------------------------------------------------------------
    def _create_notifications(self, users, arch_map):
        notif_counts = {'power': (15, 25), 'premium': (8, 15), 'casual': (3, 8),
                        'new': (1, 3), 'social': (10, 15), 'inactive': (5, 8)}
        notifications = []

        for p, u in zip(USER_PERSONAS, users):
            lo, hi = notif_counts.get(p['arch'], (3, 8))
            count = random.randint(lo, hi)
            for _ in range(count):
                tmpl = random.choice(NOTIF_TEMPLATES)
                sched = self._rand_dt(60, 0) if random.random() > 0.15 else NOW + timedelta(hours=random.randint(1, 48))
                is_past = sched < NOW

                if is_past:
                    roll = random.random()
                    if roll < 0.2:
                        n_status, sent, read, opened = 'sent', sched + timedelta(minutes=1), sched + timedelta(hours=random.randint(1, 12)), sched + timedelta(hours=random.randint(1, 24))
                    elif roll < 0.5:
                        n_status, sent, read, opened = 'sent', sched + timedelta(minutes=1), sched + timedelta(hours=random.randint(1, 12)), None
                    else:
                        n_status, sent, read, opened = 'sent', sched + timedelta(minutes=1), None, None
                else:
                    n_status, sent, read, opened = 'pending', None, None, None

                notifications.append(Notification(
                    user=u,
                    notification_type=tmpl['type'],
                    title=tmpl['title'],
                    body=tmpl['body'].format(task='Complete daily tasks', count=random.randint(3, 12), days=random.randint(7, 60)),
                    scheduled_for=sched,
                    status=n_status,
                    sent_at=sent,
                    read_at=read,
                    opened_at=opened,
                ))

        Notification.objects.bulk_create(notifications, batch_size=500)
        self.stdout.write(f'  Created {len(notifications)} notifications.')

    # ------------------------------------------------------------------
    # Phase 19: Calendar Events & Time Blocks
    # ------------------------------------------------------------------
    def _create_calendar_events(self, users, all_tasks, arch_map):
        events = []
        time_blocks = []

        # Task-linked events
        for task in all_tasks:
            if task.scheduled_date and random.random() > 0.5:
                dur = task.duration_mins or 30
                events.append(CalendarEvent(
                    user=task.goal.dream.user,
                    task=task,
                    title=task.title,
                    start_time=task.scheduled_date,
                    end_time=task.scheduled_date + timedelta(minutes=dur),
                    status='completed' if task.status == 'completed' else 'scheduled',
                ))

        CalendarEvent.objects.bulk_create(events, batch_size=500)

        # Time blocks for active users
        block_defs = [
            ('work', 0, 4, time(9, 0), time(17, 0)),
            ('exercise', 0, 4, time(6, 0), time(7, 0)),
            ('personal', 0, 6, time(19, 0), time(21, 0)),
            ('family', 5, 6, time(10, 0), time(12, 0)),
        ]
        active_users = self._users_by_arch(arch_map, 'power', 'premium', 'social')
        for u in active_users:
            chosen = random.sample(block_defs, min(random.randint(2, 4), len(block_defs)))
            for btype, day_start, day_end, st, et in chosen:
                for day in range(day_start, day_end + 1):
                    time_blocks.append(TimeBlock(
                        user=u, block_type=btype, day_of_week=day,
                        start_time=st, end_time=et,
                    ))

        TimeBlock.objects.bulk_create(time_blocks, batch_size=500)
        self.stdout.write(f'  Created {len(events)} calendar events, {len(time_blocks)} time blocks.')

    # ------------------------------------------------------------------
    # Phase 20: Daily Activities
    # ------------------------------------------------------------------
    def _create_daily_activities(self, users, arch_map):
        activity_ranges = {'power': (60, 87, 0.9), 'premium': (30, 55, 0.7),
                           'casual': (10, 28, 0.45), 'new': (1, 6, 1.0),
                           'social': (25, 48, 0.65), 'inactive': (20, 40, 0.0)}
        activities = []

        for p, u in zip(USER_PERSONAS, users):
            days_range, max_days, active_rate = activity_ranges.get(p['arch'], (10, 30, 0.5))
            days_ago_start = min(p['days_ago'], max_days)

            for day_offset in range(days_ago_start):
                if p['arch'] == 'inactive' and day_offset < 30:
                    continue  # No recent activity
                if random.random() > active_rate:
                    continue

                d = (NOW - timedelta(days=day_offset)).date()
                tasks_done = random.randint(1, 8) if p['arch'] == 'power' else random.randint(0, 4)
                activities.append(DailyActivity(
                    user=u, date=d,
                    tasks_completed=tasks_done,
                    xp_earned=tasks_done * random.randint(10, 30),
                    minutes_active=tasks_done * random.randint(15, 45),
                ))

        DailyActivity.objects.bulk_create(activities, batch_size=500, ignore_conflicts=True)
        self.stdout.write(f'  Created {len(activities)} daily activities.')

    # ------------------------------------------------------------------
    # Phase 21: Achievements & Recent Searches
    # ------------------------------------------------------------------
    def _create_achievements_and_searches(self, users, arch_map):
        achievements = list(Achievement.objects.filter(is_active=True))
        if not achievements:
            self.stdout.write(self.style.WARNING('  No achievements found. Skipping.'))
            return

        unlock_counts = {'power': (8, 12), 'premium': (4, 7), 'casual': (1, 3),
                         'new': (0, 1), 'social': (5, 8), 'inactive': (2, 4)}
        user_achievements = []
        searches = []

        for p, u in zip(USER_PERSONAS, users):
            lo, hi = unlock_counts.get(p['arch'], (1, 3))
            count = min(random.randint(lo, hi), len(achievements))
            chosen = random.sample(achievements, count)
            for ach in chosen:
                user_achievements.append(UserAchievement(user=u, achievement=ach))

            # Recent searches
            if p['arch'] not in ('new', 'inactive'):
                for _ in range(random.randint(1, 4)):
                    search_terms = ['marathon', 'budget', 'learn spanish', 'yoga', 'career', 'travel',
                                    'reading', 'meditation', 'fitness', 'investing']
                    searches.append(RecentSearch(
                        user=u,
                        query=random.choice(search_terms),
                        search_type=random.choice(['users', 'dreams', 'all']),
                    ))

        UserAchievement.objects.bulk_create(user_achievements, batch_size=200, ignore_conflicts=True)
        RecentSearch.objects.bulk_create(searches, batch_size=200)
        self.stdout.write(f'  Created {len(user_achievements)} user achievements, {len(searches)} recent searches.')

    # ------------------------------------------------------------------
    # Phase 22: Calls (voice/video between buddy pairs)
    # ------------------------------------------------------------------
    def _create_calls(self, users, arch_map):
        pairings = list(BuddyPairing.objects.filter(
            user1__email__endswith=f'@{DEMO_EMAIL_DOMAIN}',
        ))
        if not pairings:
            self.stdout.write(self.style.WARNING('  No buddy pairings found. Skipping calls.'))
            return

        calls = []
        missed_notifs = []

        for bp in pairings:
            if bp.status != 'active':
                continue

            # Each active pair has 3-8 call records
            for _ in range(random.randint(3, 8)):
                caller = random.choice([bp.user1, bp.user2])
                callee = bp.user2 if caller == bp.user1 else bp.user1
                call_type = random.choice(['voice', 'voice', 'voice', 'video'])
                status = random.choices(
                    ['completed', 'missed', 'rejected', 'cancelled'],
                    weights=[5, 2, 1, 1],
                    k=1,
                )[0]

                created = self._rand_dt(30, 1)
                started = None
                ended = None
                duration = 0

                if status == 'completed':
                    started = created + timedelta(seconds=random.randint(5, 15))
                    duration = random.randint(60, 1800)  # 1-30 min
                    ended = started + timedelta(seconds=duration)

                calls.append(Call(
                    caller=caller,
                    callee=callee,
                    buddy_pairing=bp,
                    call_type=call_type,
                    status=status,
                    started_at=started,
                    ended_at=ended,
                    duration_seconds=duration,
                ))

                # Missed call notifications
                if status == 'missed':
                    missed_notifs.append(Notification(
                        user=callee,
                        notification_type='buddy',
                        title=f'Missed call from {caller.display_name}',
                        body=f'You missed a {call_type} call.',
                        status='sent',
                        sent_at=created + timedelta(seconds=30),
                        scheduled_for=created + timedelta(seconds=30),
                    ))

        Call.objects.bulk_create(calls, batch_size=200)
        if missed_notifs:
            Notification.objects.bulk_create(missed_notifs, batch_size=100)
        self.stdout.write(f'  Created {len(calls)} calls, {len(missed_notifs)} missed call notifications.')

    # ------------------------------------------------------------------
    # Phase 23: Message Read Statuses
    # ------------------------------------------------------------------
    def _create_message_read_statuses(self, users):
        conversations = list(Conversation.objects.filter(
            user__email__endswith=f'@{DEMO_EMAIL_DOMAIN}',
        ))
        if not conversations:
            self.stdout.write(self.style.WARNING('  No conversations found. Skipping read statuses.'))
            return

        statuses = []
        for conv in conversations:
            last_msg = Message.objects.filter(conversation=conv).order_by('-created_at').first()
            if not last_msg:
                continue

            # 70% chance user has read all messages, 30% some unread
            if random.random() < 0.7:
                read_msg = last_msg
            else:
                # Pick an earlier message
                earlier = Message.objects.filter(conversation=conv).order_by('created_at')
                count = earlier.count()
                if count > 1:
                    read_msg = earlier[random.randint(0, count - 2)]
                else:
                    read_msg = last_msg

            statuses.append(MessageReadStatus(
                user=conv.user,
                conversation=conv,
                last_read_message=read_msg,
            ))

        MessageReadStatus.objects.bulk_create(statuses, batch_size=200, ignore_conflicts=True)
        self.stdout.write(f'  Created {len(statuses)} message read statuses.')

    # ------------------------------------------------------------------
    # Phase 24: Circle Chat Messages
    # ------------------------------------------------------------------
    def _create_circle_chat_messages(self, users, arch_map):
        circles = list(Circle.objects.filter(
            creator__email__endswith=f'@{DEMO_EMAIL_DOMAIN}',
        ))
        if not circles:
            self.stdout.write(self.style.WARNING('  No circles found. Skipping circle chat messages.'))
            return

        messages = []
        for circle in circles:
            member_ids = list(
                CircleMembership.objects.filter(circle=circle).values_list('user_id', flat=True)
            )
            member_users = list(User.objects.filter(pk__in=member_ids))
            if not member_users:
                continue

            # Each circle gets 15-40 chat messages spread over the last 14 days
            num_messages = random.randint(15, 40)
            for i in range(num_messages):
                sender = random.choice(member_users)
                created = self._rand_dt(14, 0)
                messages.append(CircleMessage(
                    circle=circle,
                    sender=sender,
                    content=random.choice(CIRCLE_CHAT_MESSAGES),
                    metadata={'sender_id': str(sender.id)},
                    created_at=created,
                ))

        CircleMessage.objects.bulk_create(messages, batch_size=500)
        self.stdout.write(f'  Created {len(messages)} circle chat messages.')

    # ------------------------------------------------------------------
    # Phase 25: Circle Calls (Agora voice/video)
    # ------------------------------------------------------------------
    def _create_circle_calls(self, users, arch_map):
        circles = list(Circle.objects.filter(
            creator__email__endswith=f'@{DEMO_EMAIL_DOMAIN}',
        ))
        if not circles:
            self.stdout.write(self.style.WARNING('  No circles found. Skipping circle calls.'))
            return

        calls = []
        participants = []
        call_notifs = []

        for circle in circles:
            member_ids = list(
                CircleMembership.objects.filter(circle=circle).values_list('user_id', flat=True)
            )
            member_users = list(User.objects.filter(pk__in=member_ids))
            if len(member_users) < 2:
                continue

            # Each circle gets 2-5 past calls
            num_calls = random.randint(2, 5)
            for _ in range(num_calls):
                initiator = random.choice(member_users)
                call_type = random.choice(['voice', 'voice', 'video'])
                status = random.choices(
                    ['completed', 'cancelled'],
                    weights=[4, 1],
                    k=1,
                )[0]

                call_id = uuid.uuid4()
                started = self._rand_dt(21, 1)
                ended = None
                duration = 0

                if status == 'completed':
                    duration = random.randint(120, 3600)  # 2-60 min
                    ended = started + timedelta(seconds=duration)
                elif status == 'cancelled':
                    ended = started + timedelta(seconds=random.randint(5, 30))

                call = CircleCall(
                    id=call_id,
                    circle=circle,
                    initiator=initiator,
                    call_type=call_type,
                    status=status,
                    agora_channel=str(call_id),
                    started_at=started,
                    ended_at=ended,
                    duration_seconds=duration,
                )
                calls.append(call)

                # Participants: initiator + 1-5 random members
                call_members = [initiator]
                others = [u for u in member_users if u != initiator]
                num_joining = min(random.randint(1, 5), len(others))
                call_members.extend(random.sample(others, num_joining))

                for member in call_members:
                    join_offset = random.randint(0, 30)
                    left_at = ended if ended else started + timedelta(seconds=random.randint(60, 600))
                    participants.append(CircleCallParticipant(
                        call=call,
                        user=member,
                        joined_at=started + timedelta(seconds=join_offset),
                        left_at=left_at,
                    ))

                # Notification for call
                for member in member_users:
                    if member != initiator:
                        call_notifs.append(Notification(
                            user=member,
                            notification_type='social',
                            title=f'{initiator.display_name} started a {call_type} call',
                            body=f'Join the {call_type} call in {circle.name}!',
                            status='sent',
                            sent_at=started,
                            scheduled_for=started,
                        ))

        CircleCall.objects.bulk_create(calls, batch_size=200)
        CircleCallParticipant.objects.bulk_create(participants, batch_size=500, ignore_conflicts=True)
        if call_notifs:
            Notification.objects.bulk_create(call_notifs, batch_size=500)
        self.stdout.write(
            f'  Created {len(calls)} circle calls, {len(participants)} participants, '
            f'{len(call_notifs)} call notifications.'
        )

    # ------------------------------------------------------------------
    # Phase 26: Dream Posts, Likes, Comments, Encouragements
    # ------------------------------------------------------------------
    def _create_dream_posts(self, users, dreams, arch_map):
        power = arch_map.get('power', [])
        social = arch_map.get('social', [])
        premium = arch_map.get('premium', [])
        casual = arch_map.get('casual', [])

        active_users = power + social + premium + casual
        if not active_users:
            self.stdout.write(self.style.WARNING('  No active users. Skipping dream posts.'))
            return

        # Build user -> dreams map
        user_dreams = {}
        for dream in dreams:
            user_dreams.setdefault(dream.user_id, []).append(dream)

        posts = []
        post_user_dream = []  # Track (user, dream) for each post

        # Power users: 5-10 posts, social: 8-15, premium: 3-6, casual: 1-3
        counts = {
            'power': (5, 10), 'social': (8, 15),
            'premium': (3, 6), 'casual': (1, 3),
        }

        for user in active_users:
            persona = next((p for p in USER_PERSONAS if p['display_name'] == user.display_name), None)
            if not persona:
                continue
            arch = persona['arch']
            lo, hi = counts.get(arch, (1, 3))
            num_posts = random.randint(lo, hi)
            my_dreams = user_dreams.get(user.pk, [])

            for i in range(num_posts):
                dream = random.choice(my_dreams) if my_dreams else None
                dream_title = dream.title if dream else 'my goals'
                content = random.choice(DREAM_POST_TEMPLATES).format(
                    dream=dream_title,
                    week=random.randint(1, 12),
                    progress=random.randint(10, 95),
                )

                # 10% of posts have a GoFundMe link
                gofundme = random.choice(GOFUNDME_URLS) if random.random() < 0.10 else ''

                # Visibility: power/social mostly public, others mixed
                if arch in ('power', 'social'):
                    visibility = 'public' if random.random() < 0.85 else 'followers'
                elif arch == 'premium':
                    visibility = random.choice(['public', 'public', 'followers'])
                else:
                    visibility = random.choice(['public', 'followers', 'private'])

                post = DreamPost(
                    user=user,
                    dream=dream,
                    content=content,
                    gofundme_url=gofundme,
                    visibility=visibility,
                    created_at=self._rand_dt(30, 0),
                )
                posts.append(post)
                post_user_dream.append((user, dream))

        DreamPost.objects.bulk_create(posts, batch_size=500)
        # Refresh to get IDs
        posts = list(DreamPost.objects.filter(
            user__email__endswith=f'@{DEMO_EMAIL_DOMAIN}',
        ).select_related('user'))
        self.stdout.write(f'  Created {len(posts)} dream posts.')

        if not posts:
            return

        # --- Likes ---
        likes = []
        liked_pairs = set()
        for post in posts:
            # Each post gets 0-12 likes from random active users
            num_likes = random.randint(0, 12)
            likers = random.sample(active_users, min(num_likes, len(active_users)))
            for liker in likers:
                pair = (post.pk, liker.pk)
                if pair in liked_pairs:
                    continue
                liked_pairs.add(pair)
                likes.append(DreamPostLike(post=post, user=liker))

        DreamPostLike.objects.bulk_create(likes, batch_size=1000, ignore_conflicts=True)
        # Update denormalized counts
        for post in posts:
            post.likes_count = sum(1 for l in likes if l.post_id == post.pk)
        DreamPost.objects.bulk_update(posts, ['likes_count'], batch_size=500)
        self.stdout.write(f'  Created {len(likes)} dream post likes.')

        # --- Comments (with threaded replies) ---
        comments = []
        for post in posts:
            num_comments = random.randint(0, 6)
            commenters = random.sample(active_users, min(num_comments, len(active_users)))
            for commenter in commenters:
                comment = DreamPostComment(
                    post=post,
                    user=commenter,
                    content=random.choice(DREAM_POST_COMMENT_TEMPLATES),
                    created_at=post.created_at + timedelta(
                        hours=random.randint(1, 48),
                    ),
                )
                comments.append(comment)

        DreamPostComment.objects.bulk_create(comments, batch_size=1000)
        # Refresh to get IDs for replies
        comments = list(DreamPostComment.objects.filter(
            user__email__endswith=f'@{DEMO_EMAIL_DOMAIN}',
        ))

        # Threaded replies: 20% of comments get 1-2 replies
        replies = []
        for comment in comments:
            if random.random() < 0.20:
                num_replies = random.randint(1, 2)
                for _ in range(num_replies):
                    replier = random.choice(active_users)
                    replies.append(DreamPostComment(
                        post=comment.post,
                        user=replier,
                        content=random.choice(DREAM_POST_REPLY_TEMPLATES),
                        parent=comment,
                        created_at=comment.created_at + timedelta(
                            hours=random.randint(1, 24),
                        ),
                    ))
        DreamPostComment.objects.bulk_create(replies, batch_size=500)
        total_comments = len(comments) + len(replies)

        # Update denormalized comment counts
        for post in posts:
            post.comments_count = (
                sum(1 for c in comments if c.post_id == post.pk)
                + sum(1 for r in replies if r.post_id == post.pk)
            )
        DreamPost.objects.bulk_update(posts, ['comments_count'], batch_size=500)
        self.stdout.write(f'  Created {total_comments} comments ({len(replies)} threaded replies).')

        # --- Encouragements ---
        encouragements = []
        encouraged_pairs = set()
        for post in posts:
            # Each post gets 0-5 encouragements
            num_enc = random.randint(0, 5)
            encouragers = random.sample(active_users, min(num_enc, len(active_users)))
            for encourager in encouragers:
                pair = (post.pk, encourager.pk)
                if pair in encouraged_pairs:
                    continue
                encouraged_pairs.add(pair)
                encouragements.append(DreamEncouragement(
                    post=post,
                    user=encourager,
                    encouragement_type=random.choice(ENCOURAGEMENT_TYPES),
                    message=random.choice(DREAM_ENCOURAGEMENT_MESSAGES),
                    created_at=post.created_at + timedelta(
                        hours=random.randint(1, 72),
                    ),
                ))

        DreamEncouragement.objects.bulk_create(encouragements, batch_size=1000, ignore_conflicts=True)
        self.stdout.write(f'  Created {len(encouragements)} dream encouragements.')

        # --- Notifications for social interactions ---
        social_notifs = []
        # Sample some likes for notifications
        for like in random.sample(likes, min(50, len(likes))):
            if like.user != like.post.user:
                social_notifs.append(Notification(
                    user=like.post.user,
                    notification_type='social',
                    title=f'{like.user.display_name} liked your post',
                    body='Check out who liked your dream post!',
                    status=random.choice(['sent', 'sent', 'read']),
                    sent_at=self._rand_dt(7, 0),
                    scheduled_for=self._rand_dt(7, 0),
                ))
        # Sample some comments for notifications
        for comment in random.sample(comments, min(30, len(comments))):
            if comment.user != comment.post.user:
                social_notifs.append(Notification(
                    user=comment.post.user,
                    notification_type='social',
                    title=f'{comment.user.display_name} commented on your post',
                    body=comment.content[:80],
                    status=random.choice(['sent', 'sent', 'read']),
                    sent_at=self._rand_dt(7, 0),
                    scheduled_for=self._rand_dt(7, 0),
                ))
        # Sample some encouragements for notifications
        for enc in random.sample(encouragements, min(30, len(encouragements))):
            if enc.user != enc.post.user:
                social_notifs.append(Notification(
                    user=enc.post.user,
                    notification_type='social',
                    title=f'{enc.user.display_name} encouraged your dream!',
                    body=f'Sent you a "{enc.encouragement_type.replace("_", " ")}" reaction.',
                    status=random.choice(['sent', 'sent', 'read']),
                    sent_at=self._rand_dt(7, 0),
                    scheduled_for=self._rand_dt(7, 0),
                ))
        if social_notifs:
            Notification.objects.bulk_create(social_notifs, batch_size=500)
        self.stdout.write(f'  Created {len(social_notifs)} social notifications.')
