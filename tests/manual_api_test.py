"""
Manual API test script - tests all endpoints by making real API calls.
Run: python tests/manual_api_test.py
"""
import os, sys, warnings
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings.testing'
warnings.filterwarnings('ignore')

import django
django.setup()

from unittest.mock import patch, Mock
from django.test.utils import setup_test_environment
setup_test_environment()

from rest_framework.test import APIClient
from apps.users.models import User
from apps.dreams.models import Dream, Goal, Task, Obstacle
from apps.conversations.models import Conversation, Message
from apps.notifications.models import Notification
from django.utils import timezone
from datetime import timedelta
from django.core.management import call_command
import logging
logging.disable(logging.CRITICAL)

call_command('migrate', '--run-syncdb', verbosity=0)

# Create users with Stripe mocked
with patch('apps.subscriptions.services.StripeService.create_customer'):
    free_user = User.objects.create_user(
        email='free@manual.com', password='TestPass123!', display_name='Free User')
    premium_user = User.objects.create_user(
        email='premium@manual.com', password='TestPass123!', display_name='Premium User',
        subscription='premium', subscription_ends=timezone.now() + timedelta(days=30))
    pro_user = User.objects.create_user(
        email='pro@manual.com', password='TestPass123!', display_name='Pro User',
        subscription='pro', subscription_ends=timezone.now() + timedelta(days=30))
    second_user = User.objects.create_user(
        email='second@manual.com', password='TestPass123!', display_name='Second User')

passed = 0
failed = 0
total = 0

def check(name, condition, detail=''):
    global passed, failed, total
    total += 1
    if condition:
        passed += 1
        print(f'  PASS  {name}')
    else:
        failed += 1
        print(f'  FAIL  {name} {detail}')

client = APIClient()

# ===== AUTHENTICATION =====
print('=== AUTHENTICATION ===')
resp = client.get('/api/users/me/')
check('Unauth GET /api/users/me/ -> 401', resp.status_code == 401, f'got {resp.status_code}')

resp = client.post('/api/auth/login/', {'email': 'free@manual.com', 'password': 'TestPass123!'})
check('Login valid creds -> 200', resp.status_code == 200, f'got {resp.status_code}')
token = resp.data.get('key') or resp.data.get('token')
check('Login returns token', token is not None)

resp = client.post('/api/auth/login/', {'email': 'free@manual.com', 'password': 'wrong'})
check('Login wrong password -> 400/401', resp.status_code in (400, 401), f'got {resp.status_code}')

resp = client.post('/api/auth/login/', {'email': 'nonexistent@x.com', 'password': 'x'})
check('Login nonexistent user -> 400/401', resp.status_code in (400, 401), f'got {resp.status_code}')

# Use token auth
from rest_framework.authtoken.models import Token
tok, _ = Token.objects.get_or_create(user=free_user)
token_client = APIClient()
token_client.credentials(HTTP_AUTHORIZATION=f'Bearer {tok.key}')
resp = token_client.get('/api/users/me/')
check('Bearer token auth -> 200', resp.status_code == 200, f'got {resp.status_code}')

token_client2 = APIClient()
token_client2.credentials(HTTP_AUTHORIZATION=f'Token {tok.key}')
resp = token_client2.get('/api/users/me/')
check('Token prefix auth -> 200', resp.status_code == 200, f'got {resp.status_code}')

bad_client = APIClient()
bad_client.credentials(HTTP_AUTHORIZATION='Token invalidgarbage')
resp = bad_client.get('/api/users/me/')
check('Invalid token -> 401', resp.status_code == 401, f'got {resp.status_code}')

# Expired token
Token.objects.filter(pk=tok.pk).update(created=timezone.now() - timedelta(hours=25))
expired_client = APIClient()
expired_client.credentials(HTTP_AUTHORIZATION=f'Token {tok.key}')
resp = expired_client.get('/api/users/me/')
check('Expired token -> 401', resp.status_code == 401, f'got {resp.status_code}')

# ===== USER PROFILE =====
print()
print('=== USER PROFILE ===')
client.force_authenticate(user=free_user)

resp = client.get('/api/users/me/')
check('GET /api/users/me/ -> 200', resp.status_code == 200, f'got {resp.status_code}')
check('Profile email correct', resp.data.get('email') == 'free@manual.com')

resp = client.patch('/api/users/update_profile/', {'display_name': 'Updated Name', 'bio': 'Hello world'})
check('PATCH update_profile -> 200', resp.status_code == 200, f'got {resp.status_code}')

resp = client.get('/api/users/stats/')
check('GET /api/users/stats/ -> 200', resp.status_code == 200, f'got {resp.status_code}')

resp = client.get('/api/users/dashboard/')
check('GET /api/users/dashboard/ -> 200', resp.status_code == 200, f'got {resp.status_code}')

resp = client.get('/api/users/achievements/')
check('GET /api/users/achievements/ -> 200', resp.status_code == 200, f'got {resp.status_code}')

resp = client.get('/api/users/export-data/')
check('GET /api/users/export-data/ -> 200', resp.status_code == 200, f'got {resp.status_code}')

resp = client.get('/api/users/2fa/status/')
check('GET /api/users/2fa/status/ -> 200', resp.status_code == 200, f'got {resp.status_code}')

resp = client.put('/api/users/notification-preferences/', {'push_enabled': True, 'email_enabled': False}, format='json')
check('PUT notification-preferences -> 200', resp.status_code == 200, f'got {resp.status_code}')

# ===== SUBSCRIPTION GATING =====
print()
print('=== SUBSCRIPTION GATING (Free blocked) ===')
resp = client.get('/api/conversations/')
check('Free GET /conversations/ -> 403', resp.status_code == 403, f'got {resp.status_code}')

resp = client.get('/api/buddies/current/')
check('Free GET /buddies/current/ -> 403', resp.status_code == 403, f'got {resp.status_code}')

resp = client.get('/api/leagues/leagues/')
check('Free GET /leagues/ -> 403', resp.status_code == 403, f'got {resp.status_code}')

resp = client.post('/api/store/purchase/', {'item_id': 'fake'})
check('Free POST /store/purchase/ -> 403', resp.status_code == 403, f'got {resp.status_code}')

resp = client.get('/api/circles/')
check('Free GET /circles/ -> 403', resp.status_code == 403, f'got {resp.status_code}')

resp = client.get('/api/social/follow-suggestions/')
check('Free GET follow-suggestions -> 403', resp.status_code == 403, f'got {resp.status_code}')

# Free user allowed
resp = client.get('/api/dreams/dreams/')
check('Free GET /dreams/ -> 200 (allowed)', resp.status_code == 200, f'got {resp.status_code}')

resp = client.get('/api/notifications/')
check('Free GET /notifications/ -> 200 (allowed)', resp.status_code == 200, f'got {resp.status_code}')

resp = client.get('/api/social/friends/')
check('Free GET /social/friends/ -> 200 (allowed)', resp.status_code == 200, f'got {resp.status_code}')

# ===== DREAMS CRUD =====
print()
print('=== DREAMS CRUD ===')
resp = client.post('/api/dreams/dreams/', {
    'title': 'Learn Python', 'description': 'Master it', 'category': 'education', 'priority': 1})
check('POST create dream -> 201', resp.status_code in (200, 201), f'got {resp.status_code}')
dream = Dream.objects.filter(user=free_user, title='Learn Python').first()
check('Dream exists in DB', dream is not None)

resp = client.get(f'/api/dreams/dreams/{dream.id}/')
check('GET dream detail -> 200', resp.status_code == 200, f'got {resp.status_code}')
check('Title matches', resp.data.get('title') == 'Learn Python')

resp = client.patch(f'/api/dreams/dreams/{dream.id}/', {'title': 'Learn Advanced Python'})
check('PATCH update dream -> 200', resp.status_code == 200, f'got {resp.status_code}')

resp = client.get('/api/dreams/dreams/', {'status': 'active'})
check('Filter by status -> 200', resp.status_code == 200, f'got {resp.status_code}')

resp = client.get('/api/dreams/dreams/', {'search': 'Python'})
check('Search dreams -> 200', resp.status_code == 200, f'got {resp.status_code}')

resp = client.post(f'/api/dreams/dreams/{dream.id}/complete/')
check('POST complete dream -> 200', resp.status_code == 200, f'got {resp.status_code}')

resp = client.post(f'/api/dreams/dreams/{dream.id}/duplicate/')
check('POST duplicate dream -> 200/201', resp.status_code in (200, 201), f'got {resp.status_code}')

resp = client.post(f'/api/dreams/dreams/{dream.id}/share/', {'shared_with_id': str(second_user.id)})
check('POST share dream -> 200/201', resp.status_code in (200, 201), f'got {resp.status_code}')

resp = client.post(f'/api/dreams/dreams/{dream.id}/tags/', {'tag_name': 'important'})
check('POST add tag -> 200', resp.status_code == 200, f'got {resp.status_code}')

# Dream limit (free=3)
Dream.objects.create(user=free_user, title='D2', status='active')
Dream.objects.create(user=free_user, title='D3', status='active')
resp = client.post('/api/dreams/dreams/', {
    'title': 'Over Limit', 'description': 'x', 'category': 'education', 'priority': 1})
check('Free 4th dream -> 403 (limit)', resp.status_code == 403, f'got {resp.status_code}')

# ===== GOALS / TASKS / OBSTACLES =====
print()
print('=== GOALS / TASKS / OBSTACLES ===')
active_dream = Dream.objects.create(user=free_user, title='Active', status='active')
goal = Goal.objects.create(dream=active_dream, title='Goal 1', order=0)
task = Task.objects.create(goal=goal, title='Task 1', order=0)
obstacle = Obstacle.objects.create(dream=active_dream, title='Obs', description='Desc')

resp = client.get('/api/dreams/goals/')
check('GET goals list -> 200', resp.status_code == 200, f'got {resp.status_code}')

resp = client.get(f'/api/dreams/goals/{goal.id}/')
check('GET goal detail -> 200', resp.status_code == 200, f'got {resp.status_code}')

resp = client.patch(f'/api/dreams/goals/{goal.id}/', {'title': 'Updated Goal'})
check('PATCH update goal -> 200', resp.status_code == 200, f'got {resp.status_code}')

resp = client.get('/api/dreams/tasks/')
check('GET tasks list -> 200', resp.status_code == 200, f'got {resp.status_code}')

resp = client.get(f'/api/dreams/tasks/{task.id}/')
check('GET task detail -> 200', resp.status_code == 200, f'got {resp.status_code}')

resp = client.post(f'/api/dreams/tasks/{task.id}/complete/')
check('POST complete task -> 200', resp.status_code == 200, f'got {resp.status_code}')

task2 = Task.objects.create(goal=goal, title='Task 2', order=1)
resp = client.post(f'/api/dreams/tasks/{task2.id}/skip/')
check('POST skip task -> 200', resp.status_code == 200, f'got {resp.status_code}')

resp = client.get('/api/dreams/obstacles/')
check('GET obstacles list -> 200', resp.status_code == 200, f'got {resp.status_code}')

resp = client.post(f'/api/dreams/obstacles/{obstacle.id}/resolve/')
check('POST resolve obstacle -> 200', resp.status_code == 200, f'got {resp.status_code}')

resp = client.post(f'/api/dreams/goals/{goal.id}/complete/')
check('POST complete goal -> 200', resp.status_code == 200, f'got {resp.status_code}')

# Delete
del_dream = Dream.objects.create(user=free_user, title='ToDelete', status='active')
resp = client.delete(f'/api/dreams/dreams/{del_dream.id}/')
check('DELETE dream -> 204', resp.status_code in (200, 204), f'got {resp.status_code}')

# ===== IDOR / OWNERSHIP =====
print()
print('=== IDOR / OWNERSHIP ===')
other_client = APIClient()
other_client.force_authenticate(user=second_user)

resp = other_client.get(f'/api/dreams/dreams/{active_dream.id}/')
check('Other user GET dream -> 404', resp.status_code == 404, f'got {resp.status_code}')

resp = other_client.patch(f'/api/dreams/dreams/{active_dream.id}/', {'title': 'Hacked'})
check('Other user PATCH dream -> 404', resp.status_code == 404, f'got {resp.status_code}')

resp = other_client.delete(f'/api/dreams/dreams/{active_dream.id}/')
check('Other user DELETE dream -> 404', resp.status_code == 404, f'got {resp.status_code}')

resp = other_client.get(f'/api/dreams/goals/{goal.id}/')
check('Other user GET goal -> 404', resp.status_code == 404, f'got {resp.status_code}')

resp = other_client.get(f'/api/dreams/tasks/{task.id}/')
check('Other user GET task -> 404', resp.status_code == 404, f'got {resp.status_code}')

# ===== PREMIUM FEATURES =====
print()
print('=== PREMIUM USER FEATURES ===')
pclient = APIClient()
pclient.force_authenticate(user=premium_user)

resp = pclient.get('/api/conversations/')
check('Premium GET /conversations/ -> 200', resp.status_code == 200, f'got {resp.status_code}')

resp = pclient.get('/api/buddies/current/')
check('Premium GET /buddies/current/ -> 200', resp.status_code == 200, f'got {resp.status_code}')

resp = pclient.get('/api/leagues/leagues/')
check('Premium GET /leagues/ -> 200', resp.status_code == 200, f'got {resp.status_code}')

resp = pclient.get('/api/circles/')
check('Premium GET /circles/ -> 200', resp.status_code == 200, f'got {resp.status_code}')

resp = pclient.post('/api/circles/', {'name': 'Test', 'description': 'x'})
check('Premium POST /circles/ -> 403', resp.status_code == 403, f'got {resp.status_code}')

# ===== CONVERSATIONS (with AI mock) =====
print()
print('=== CONVERSATIONS ===')
conv = Conversation.objects.create(user=premium_user, conversation_type='general')

with patch('integrations.openai_service._client') as mock_oa:
    mock_chat = Mock()
    mock_chat.return_value = Mock(
        choices=[Mock(message=Mock(content='I can help plan your goals!', function_call=None))],
        usage=Mock(total_tokens=50), model='gpt-4',
    )
    mock_oa.chat.completions.create = mock_chat

    resp = pclient.post(f'/api/conversations/{conv.id}/send_message/', {'content': 'Help me plan my dream'})
    check('Send message -> 200', resp.status_code == 200, f'got {resp.status_code}')
    if resp.status_code == 200:
        check('Has assistant_message', 'assistant_message' in resp.data)
        check('Has user_message', 'user_message' in resp.data)

resp = pclient.post(f'/api/conversations/{conv.id}/send_message/', {'content': ''})
check('Empty message -> 400', resp.status_code == 400, f'got {resp.status_code}')

resp = pclient.get(f'/api/conversations/{conv.id}/messages/')
check('GET messages -> 200', resp.status_code == 200, f'got {resp.status_code}')

resp = pclient.post(f'/api/conversations/{conv.id}/pin/')
check('Pin conversation -> 200', resp.status_code == 200, f'got {resp.status_code}')

msg = Message.objects.filter(conversation=conv, role='assistant').first()
if msg:
    resp = pclient.post(f'/api/conversations/{conv.id}/like-message/{msg.id}/')
    check('Like message -> 200', resp.status_code == 200, f'got {resp.status_code}')

    resp = pclient.post(f'/api/conversations/{conv.id}/react-message/{msg.id}/', {'emoji': '👍'})
    check('React to message -> 200', resp.status_code == 200, f'got {resp.status_code}')

resp = pclient.get(f'/api/conversations/{conv.id}/search/', {'q': 'dream'})
check('Search messages -> 200', resp.status_code == 200, f'got {resp.status_code}')

resp = pclient.get(f'/api/conversations/{conv.id}/export/')
check('Export conversation -> 200', resp.status_code == 200, f'got {resp.status_code}')

# IDOR: other user cant see this conversation
resp = other_client.get(f'/api/conversations/{conv.id}/')
check('Other user GET conversation -> 404 (IDOR)', resp.status_code in (403, 404), f'got {resp.status_code}')

# ===== SOCIAL =====
print()
print('=== SOCIAL ===')
resp = client.get('/api/social/friends/')
check('GET friends -> 200', resp.status_code == 200, f'got {resp.status_code}')

# Unblock second_user first (was blocked earlier)
client.delete(f'/api/social/unblock/{second_user.id}/')

resp = client.post('/api/social/friends/request/', {'targetUserId': str(premium_user.id)})
check('Send friend request -> 200/201', resp.status_code in (200, 201), f'got {resp.status_code}')

resp = client.get('/api/social/friends/requests/sent/')
check('GET sent requests -> 200', resp.status_code == 200, f'got {resp.status_code}')

# Accept from premium side
resp = pclient.get('/api/social/friends/requests/pending/')
check('GET pending requests -> 200', resp.status_code == 200, f'got {resp.status_code}')
results = resp.data.get('results', resp.data)
if isinstance(results, list) and len(results) > 0:
    req_id = results[0].get('id')
    if req_id:
        resp = pclient.post(f'/api/social/friends/accept/{req_id}/')
        check('Accept friend request -> 200', resp.status_code == 200, f'got {resp.status_code}')

resp = client.post('/api/social/follow/', {'targetUserId': str(premium_user.id)})
check('Follow user -> 200/201', resp.status_code in (200, 201), f'got {resp.status_code}')

resp = client.get(f'/api/social/counts/{premium_user.id}/')
check('GET social counts -> 200', resp.status_code == 200, f'got {resp.status_code}')

resp = client.get('/api/social/users/search', {'q': 'Premium'})
check('Search users -> 200', resp.status_code == 200, f'got {resp.status_code}')

resp = client.get('/api/social/friends/online/')
check('GET online friends -> 200', resp.status_code == 200, f'got {resp.status_code}')

resp = client.post('/api/social/recent-searches/add/', {'query': 'test search'})
check('Add recent search -> 200/201', resp.status_code in (200, 201), f'got {resp.status_code}')

resp = client.get('/api/social/recent-searches/list/')
check('GET recent searches -> 200', resp.status_code == 200, f'got {resp.status_code}')

resp = client.post('/api/social/report/', {
    'targetUserId': str(second_user.id), 'reason': 'Spam', 'category': 'spam'})
check('Report user -> 200/201', resp.status_code in (200, 201), f'got {resp.status_code}')

resp = client.post('/api/social/block/', {'targetUserId': str(second_user.id)})
check('Block user -> 200/201', resp.status_code in (200, 201), f'got {resp.status_code}')

resp = client.get('/api/social/blocked/')
check('GET blocked -> 200', resp.status_code == 200, f'got {resp.status_code}')

# ===== NOTIFICATIONS =====
print()
print('=== NOTIFICATIONS ===')
notif = Notification.objects.create(
    user=free_user, notification_type='reminder', title='Test Notif',
    body='Reminder body', scheduled_for=timezone.now())

resp = client.get('/api/notifications/')
check('GET notifications -> 200', resp.status_code == 200, f'got {resp.status_code}')

resp = client.get(f'/api/notifications/{notif.id}/')
check('GET notification detail -> 200', resp.status_code == 200, f'got {resp.status_code}')

resp = client.post(f'/api/notifications/{notif.id}/mark_read/')
check('POST mark_read -> 200', resp.status_code == 200, f'got {resp.status_code}')

resp = client.get('/api/notifications/unread_count/')
check('GET unread_count -> 200', resp.status_code == 200, f'got {resp.status_code}')

resp = client.post('/api/notifications/mark_all_read/')
check('POST mark_all_read -> 200', resp.status_code == 200, f'got {resp.status_code}')

resp = client.get('/api/notifications/grouped/')
check('GET grouped -> 200', resp.status_code == 200, f'got {resp.status_code}')

# ===== STORE =====
print()
print('=== STORE ===')
anon = APIClient()
resp = anon.get('/api/store/categories/')
check('GET /store/categories/ (public) -> 200', resp.status_code == 200, f'got {resp.status_code}')

resp = anon.get('/api/store/items/')
check('GET /store/items/ (public) -> 200', resp.status_code == 200, f'got {resp.status_code}')

resp = anon.get('/api/store/items/featured/')
check('GET /store/items/featured/ -> 200', resp.status_code == 200, f'got {resp.status_code}')

resp = anon.get('/api/store/inventory/')
check('GET inventory unauth -> 401', resp.status_code == 401, f'got {resp.status_code}')

resp = client.get('/api/store/inventory/')
check('GET inventory auth -> 200', resp.status_code == 200, f'got {resp.status_code}')

resp = client.get('/api/store/wishlist/')
check('GET wishlist -> 200', resp.status_code == 200, f'got {resp.status_code}')

resp = client.get('/api/store/gifts/')
check('GET gifts -> 200', resp.status_code == 200, f'got {resp.status_code}')

# ===== SUBSCRIPTIONS =====
print()
print('=== SUBSCRIPTIONS ===')
resp = anon.get('/api/subscriptions/plans/')
check('GET plans (public) -> 200', resp.status_code == 200, f'got {resp.status_code}')

resp = client.get('/api/subscriptions/subscription/current/')
check('GET current sub -> 200/404', resp.status_code in (200, 404), f'got {resp.status_code}')

resp = anon.post('/api/subscriptions/webhook/stripe/', {}, format='json')
check('Stripe webhook no sig -> 400', resp.status_code == 400, f'got {resp.status_code}')

# ===== PRO USER =====
print()
print('=== PRO USER ===')
pro_c = APIClient()
pro_c.force_authenticate(user=pro_user)

resp = pro_c.post('/api/circles/', {'name': 'Pro Circle', 'description': 'Pro only'})
check('Pro POST /circles/ -> not 403', resp.status_code != 403, f'got {resp.status_code}')

# Pro unlimited dreams
for i in range(12):
    Dream.objects.create(user=pro_user, title=f'ProDream{i}', status='active')
resp = pro_c.post('/api/dreams/dreams/', {
    'title': 'Dream 13', 'description': 'Unlimited', 'category': 'education', 'priority': 1})
check('Pro unlimited dreams -> 201', resp.status_code in (200, 201), f'got {resp.status_code}')

# ===== XSS INJECTION =====
print()
print('=== XSS INJECTION ===')
xss_payloads = [
    '<script>alert(1)</script>',
    '<img src=x onerror=alert(1)>',
    '"><svg onload=alert(1)>',
]
for payload in xss_payloads:
    resp = client.post('/api/dreams/dreams/', {
        'title': payload, 'description': 'Normal', 'category': 'education', 'priority': 1})
    if resp.status_code in (200, 201):
        title = str(resp.data.get('title', ''))
        check(f'XSS "{payload[:30]}" sanitized in title',
              '<script' not in title.lower() and 'onerror=' not in title.lower() and 'onload=' not in title.lower())

resp = client.patch('/api/users/update_profile/', {'bio': '<img src=x onerror=alert(1)>'})
if resp.status_code == 200:
    bio = str(resp.data.get('bio', ''))
    check('XSS in bio sanitized', 'onerror=' not in bio.lower())

# ===== SQL INJECTION =====
print()
print('=== SQL INJECTION ===')
sqli_payloads = [
    "'; DROP TABLE users; --",
    "1 OR 1=1",
    "' UNION SELECT * FROM users --",
]
for payload in sqli_payloads:
    resp = client.get('/api/dreams/dreams/', {'search': payload})
    check(f'SQLi "{payload[:30]}" in search -> not 500', resp.status_code != 500, f'got {resp.status_code}')

resp = client.get('/api/social/users/search', {'q': "'; DROP TABLE users; --"})
check('SQLi in user search -> not 500', resp.status_code != 500, f'got {resp.status_code}')

# ===== EDGE CASES =====
print()
print('=== EDGE CASES ===')
# Use a fresh user to avoid dream limit issues
with patch('apps.subscriptions.services.StripeService.create_customer'):
    edge_user = User.objects.create_user(email='edge@manual.com', password='TestPass123!', display_name='Edge User')
edge_client = APIClient()
edge_client.force_authenticate(user=edge_user)

resp = edge_client.post('/api/dreams/dreams/', {'title': '', 'description': 'x', 'category': 'education', 'priority': 1})
check('Empty title -> 400', resp.status_code == 400, f'got {resp.status_code}')

resp = edge_client.post('/api/dreams/dreams/', {})
check('Empty body -> 400', resp.status_code == 400, f'got {resp.status_code}')

resp = edge_client.post('/api/dreams/dreams/', {
    'title': 'Apprendre le japonais 日本語', 'description': 'Unicode', 'category': 'education', 'priority': 1})
check('Unicode in title -> 201', resp.status_code in (200, 201), f'got {resp.status_code}')

import uuid
resp = client.get(f'/api/dreams/dreams/{uuid.uuid4()}/')
check('Random UUID -> 404', resp.status_code == 404, f'got {resp.status_code}')

resp = client.get('/api/dreams/dreams/', {'page': '-1'})
check('Negative page -> 400/404', resp.status_code in (400, 404), f'got {resp.status_code}')

# ===== HEALTH CHECK =====
print()
print('=== HEALTH CHECK ===')
resp = anon.get('/health/')
check('GET /health/ -> 200', resp.status_code == 200, f'got {resp.status_code}')

# ===== SUMMARY =====
print()
print('=' * 60)
print(f'MANUAL API TEST RESULTS: {passed}/{total} passed, {failed} failed')
print('=' * 60)

sys.exit(0 if failed == 0 else 1)
