"""
Centralized OpenAPI examples for DreamPlanner API documentation.
"""

from drf_spectacular.utils import OpenApiExample


# --- Auth Examples ---
AUTH_LOGIN_REQUEST = OpenApiExample(
    'Login Request',
    value={'email': 'user@example.com', 'password': 'securePassword123'},
    request_only=True,
)

AUTH_LOGIN_RESPONSE = OpenApiExample(
    'Login Response',
    value={'key': 'a1b2c3d4e5f6g7h8i9j0...'},
    response_only=True,
    status_codes=['200'],
)

# --- Dream Examples ---
DREAM_CREATE_REQUEST = OpenApiExample(
    'Create Dream',
    value={
        'title': 'Run a Marathon',
        'description': 'Complete a full 42km marathon within the next 12 months',
        'category': 'health',
        'target_date': '2027-03-15',
        'priority': 'high',
    },
    request_only=True,
)

DREAM_LIST_RESPONSE = OpenApiExample(
    'Dream List',
    value=[{
        'id': '550e8400-e29b-41d4-a716-446655440000',
        'title': 'Run a Marathon',
        'category': 'health',
        'status': 'active',
        'progress_percentage': 35.0,
        'goals_count': 48,
        'tasks_count': 192,
        'tags': ['fitness', 'endurance'],
        'sparkline_data': [
            {'date': '2026-02-16', 'progress': 20.0},
            {'date': '2026-02-17', 'progress': 25.0},
            {'date': '2026-02-18', 'progress': 30.0},
            {'date': '2026-02-19', 'progress': 35.0},
        ],
    }],
    response_only=True,
    status_codes=['200'],
)

MILESTONE_DETAIL_RESPONSE = OpenApiExample(
    'Milestone Detail',
    value={
        'id': '660e8400-e29b-41d4-a716-446655440001',
        'dream': '550e8400-e29b-41d4-a716-446655440000',
        'title': 'Month 1: Build Running Foundation',
        'description': 'Establish a consistent running routine with proper form',
        'order': 1,
        'target_date': '2026-04-01T00:00:00Z',
        'expected_date': '2026-03-28',
        'deadline_date': '2026-04-05',
        'status': 'in_progress',
        'progress_percentage': 50.0,
        'goals_count': 4,
        'completed_goals_count': 2,
    },
    response_only=True,
    status_codes=['200'],
)

DREAM_ANALYZE_RESPONSE = OpenApiExample(
    'AI Analysis Response',
    value={
        'analysis': {
            'feasibility': 'high',
            'strengths': ['Clear deadline', 'Measurable goal'],
            'challenges': ['Requires consistent training schedule'],
            'recommendations': ['Start with a 5K training plan', 'Join a running group'],
        },
    },
    response_only=True,
    status_codes=['200'],
)

# --- Goal Examples ---
GOAL_CREATE_REQUEST = OpenApiExample(
    'Create Goal',
    value={
        'dream': '550e8400-e29b-41d4-a716-446655440000',
        'milestone': '660e8400-e29b-41d4-a716-446655440001',
        'title': 'Complete 5K training',
        'description': 'Build up to running 5K without stopping',
        'order': 1,
        'estimated_minutes': 1800,
        'expected_date': '2026-03-20',
        'deadline_date': '2026-03-25',
    },
    request_only=True,
)

# --- Conversation Examples ---
AI_SEND_MESSAGE_REQUEST = OpenApiExample(
    'Send Message',
    value={'content': 'Help me break down my marathon goal into weekly milestones'},
    request_only=True,
)

AI_SEND_MESSAGE_RESPONSE = OpenApiExample(
    'AI Response',
    value={
        'user_message': {
            'role': 'user',
            'content': 'Help me break down my marathon goal into weekly milestones',
        },
        'assistant_message': {
            'id': '550e8400-e29b-41d4-a716-446655440001',
            'role': 'assistant',
            'content': 'Here is a 16-week marathon training plan...',
            'created_at': '2026-02-22T14:30:00Z',
        },
    },
    response_only=True,
    status_codes=['200'],
)

# --- Subscription Examples ---
SUBSCRIPTION_CHECKOUT_REQUEST = OpenApiExample(
    'Checkout Request',
    value={
        'plan_slug': 'premium',
        'success_url': 'https://app.dreamplanner.app/subscription/success',
        'cancel_url': 'https://app.dreamplanner.app/subscription/cancel',
    },
    request_only=True,
)

SUBSCRIPTION_CHECKOUT_RESPONSE = OpenApiExample(
    'Checkout Response',
    value={
        'checkout_url': 'https://checkout.stripe.com/c/pay/cs_test_...',
        'session_id': 'cs_test_...',
    },
    response_only=True,
    status_codes=['200'],
)

# --- Store Examples ---
STORE_PURCHASE_REQUEST = OpenApiExample(
    'Purchase Request',
    value={'item_id': '550e8400-e29b-41d4-a716-446655440002'},
    request_only=True,
)

# --- Error Examples ---
ERROR_VALIDATION = OpenApiExample(
    'Validation Error',
    value={'title': ['This field is required.']},
    response_only=True,
    status_codes=['400'],
)

ERROR_SUBSCRIPTION_REQUIRED = OpenApiExample(
    'Subscription Required',
    value={'detail': 'This feature requires a Premium or Pro subscription.'},
    response_only=True,
    status_codes=['403'],
)

ERROR_RATE_LIMITED = OpenApiExample(
    'Rate Limited',
    value={'detail': 'Request was throttled. Expected available in 42 seconds.'},
    response_only=True,
    status_codes=['429'],
)

ERROR_AI_SERVICE = OpenApiExample(
    'AI Service Error',
    value={'error': 'AI service returned an invalid response.'},
    response_only=True,
    status_codes=['502'],
)

ERROR_NOT_FOUND = OpenApiExample(
    'Not Found',
    value={'detail': 'Not found.'},
    response_only=True,
    status_codes=['404'],
)
