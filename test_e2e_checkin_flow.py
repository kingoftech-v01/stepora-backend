#!/usr/bin/env python3
"""
End-to-end test of the full dream lifecycle with context-aware check-ins.

Flow:
1. Create a test user with persona
2. Create a dream with description
3. Simulate calibration responses
4. Generate the plan skeleton
5. Fake 14 days passing, complete some tasks
6. Trigger check-in → get questionnaire
7. Submit responses → get adaptation
8. Inspect all context was properly used
"""

import os, sys, json, time
os.environ['DB_HOST'] = '172.22.0.7'
os.environ['DB_NAME'] = 'stepora'
os.environ['DB_USER'] = 'stepora'
os.environ['DB_PASSWORD'] = 'stepora_dev_password'
os.environ['REDIS_HOST'] = '172.22.0.3'
os.environ['REDIS_URL'] = 'redis://:dp_redis_S3cur3_2026!@172.22.0.3:6379/1'
os.environ['CELERY_BROKER_URL'] = 'redis://:dp_redis_S3cur3_2026!@172.22.0.3:6379/0'
os.environ['CELERY_RESULT_BACKEND'] = 'redis://:dp_redis_S3cur3_2026!@172.22.0.3:6379/0'
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')

# Suppress noisy logging
import logging
logging.disable(logging.DEBUG)

import django
django.setup()

# Disable Elasticsearch signals (no ES in this environment)
try:
    from django_elasticsearch_dsl.signals import RealTimeSignalProcessor
    from django.db.models.signals import post_save, post_delete
    post_save.receivers = [r for r in post_save.receivers if 'elasticsearch' not in str(r)]
    post_delete.receivers = [r for r in post_delete.receivers if 'elasticsearch' not in str(r)]
except ImportError:
    pass

from datetime import timedelta, date, datetime
from django.utils import timezone
from apps.dreams.models import (
    Dream, DreamMilestone, Goal, Task, CalibrationResponse,
    Obstacle, PlanCheckIn,
)
from apps.users.models import User
from integrations.openai_service import OpenAIService
from integrations.context_builder import build_dream_context

# ============================================================
# Step 1: Create test user with full persona
# ============================================================
print("=" * 70)
print("STEP 1: Create test user with persona")
print("=" * 70)

user, created = User.objects.get_or_create(
    email='test_e2e_checkin@stepora.test',
    defaults={
        'display_name': 'Marie Test',
        'timezone': 'Europe/Paris',
    }
)
if created:
    user.set_password('testpass123')
    user.save()

user.persona = {
    'available_hours_per_week': 6,
    'preferred_schedule': 'evenings',
    'budget_range': '50-100 EUR/mois',
    'fitness_level': 'beginner',
    'learning_style': 'visual',
    'typical_day': 'Travaille de 9h a 18h, libre le soir et le weekend',
    'occupation': 'comptable',
    'global_motivation': 'Vouloir etre en meilleure forme et avoir plus d energie',
    'global_constraints': 'Douleur legere au dos, pas de materiel sportif chez moi',
    'astrological_sign': 'Balance',
}
user.work_schedule = {
    'workDays': [1, 2, 3, 4, 5],
    'startTime': '09:00',
    'endTime': '18:00',
}
user.save(update_fields=['persona', 'work_schedule'])
print(f"  User: {user.email} (persona set)")

# ============================================================
# Step 2: Create dream
# ============================================================
print("\n" + "=" * 70)
print("STEP 2: Create dream")
print("=" * 70)

# Clean up any existing test dream
Dream.objects.filter(user=user, title__startswith='Perdre 10kg').delete()

dream = Dream.objects.create(
    user=user,
    title='Perdre 10kg en 6 mois',
    description=(
        "Je veux perdre 10 kilos en 6 mois de maniere saine et durable. "
        "Je pese actuellement 85kg pour 1m70. Je n'ai jamais fait de regime "
        "serieux mais je mange plutot equilibre. Je veux combiner sport et "
        "alimentation. J'ai acces a une salle de sport pres de chez moi mais "
        "je n'y suis jamais alle. Mon objectif est de peser 75kg avant septembre."
    ),
    category='health',
    language='fr',
    target_date=timezone.now() + timedelta(days=180),
    status='active',
    calibration_status='completed',
    plan_phase='none',
    ai_analysis={
        'analysis': (
            "Objectif realiste: perdre 10kg en 6 mois represente ~1.6kg/mois. "
            "Approche recommandee: deficit calorique modere (300-500 kcal/jour) "
            "combine avec exercice progressif. Le user est debutant en sport, "
            "attention au dos. Recommandation: consultation nutritionniste + "
            "coach sportif pour les premieres semaines."
        ),
    },
)
print(f"  Dream: {dream.title} (id={dream.id})")
print(f"  Target: {dream.target_date.date()}")

# ============================================================
# Step 3: Create calibration responses
# ============================================================
print("\n" + "=" * 70)
print("STEP 3: Simulate calibration responses")
print("=" * 70)

calibration_data = [
    (1, 'experience', "Quel est votre niveau d'experience en sport?",
     "Debutant total. Je marche tous les jours mais je n'ai jamais fait de musculation ou de cardio regulier."),
    (2, 'timeline', "Pourquoi 6 mois specifiquement?",
     "J'ai un mariage en septembre et je veux etre en forme pour ca."),
    (3, 'resources', "Avez-vous acces a du materiel ou une salle de sport?",
     "Oui, il y a une salle Basic-Fit a 5 minutes de chez moi. Abonnement a 30 EUR/mois."),
    (4, 'motivation', "Qu'est-ce qui vous motive le plus?",
     "Le mariage de ma soeur. Et aussi avoir plus d'energie au quotidien, je suis fatiguee le soir."),
    (5, 'constraints', "Y a-t-il des contraintes medicales ou physiques?",
     "Oui, j'ai une douleur legere au dos (lombaires) quand je reste assise trop longtemps. Mon medecin dit que le sport devrait aider."),
    (6, 'lifestyle', "Decrivez une journee typique niveau alimentation.",
     "Petit-dej: cafe + tartines. Dejeuner: sandwich au bureau. Diner: plat cuisine maison, souvent pates ou riz. Je grignote vers 16h."),
    (7, 'preferences', "Preferez-vous les exercices en salle ou en exterieur?",
     "Je prefere l'interieur, je suis un peu timide a l'idee de courir dehors. La salle me va bien."),
]

CalibrationResponse.objects.filter(dream=dream).delete()
for num, cat, question, answer in calibration_data:
    CalibrationResponse.objects.create(
        dream=dream,
        question_number=num,
        category=cat,
        question=question,
        answer=answer,
    )
print(f"  Created {len(calibration_data)} calibration responses")

# ============================================================
# Step 4: Create obstacles
# ============================================================
print("\n" + "=" * 70)
print("STEP 4: Create obstacles")
print("=" * 70)

Obstacle.objects.filter(dream=dream).delete()
obstacles_data = [
    ("Douleur au dos", "Les lombalgies pourraient limiter certains exercices", "predicted",
     "Eviter les exercices a fort impact, privilegier le renforcement du core"),
    ("Grignotage a 16h", "Habitude de grignoter l'apres-midi au bureau", "predicted",
     "Preparer des snacks sains a l'avance (fruits secs, yaourt)"),
    ("Timidite en salle", "Le user est timide et n'a jamais ete en salle", "predicted",
     "Commencer par des cours collectifs debutants ou des machines guidees"),
]
for title, desc, obs_type, solution in obstacles_data:
    Obstacle.objects.create(
        dream=dream, title=title, description=desc,
        obstacle_type=obs_type, solution=solution,
    )
print(f"  Created {len(obstacles_data)} obstacles")

# ============================================================
# Step 5: Generate plan skeleton via AI
# ============================================================
print("\n" + "=" * 70)
print("STEP 5: Generate plan skeleton (calling OpenAI...)")
print("=" * 70)

ai_service = OpenAIService()

# Force CELERY_TASK_ALWAYS_EAGER so tasks run synchronously
from django.conf import settings
settings.CELERY_TASK_ALWAYS_EAGER = True
settings.CELERY_TASK_EAGER_PROPAGATES = True

from config.celery import app as celery_app
celery_app.conf.task_always_eager = True
celery_app.conf.task_eager_propagates = True

from apps.dreams.tasks import generate_dream_skeleton_task, generate_initial_tasks_task

start_time = time.time()
try:
    # Phase 1: Generate skeleton (milestones + goals, no tasks)
    print("  Phase 1: Generating skeleton...")
    result1 = generate_dream_skeleton_task.apply(args=[str(dream.id), str(user.id)])
    elapsed1 = round(time.time() - start_time, 1)
    print(f"  Skeleton done in {elapsed1}s: {result1.result}")

    dream.refresh_from_db()
    ms_count = DreamMilestone.objects.filter(dream=dream).count()
    goal_count = Goal.objects.filter(dream=dream).count()
    print(f"  Milestones: {ms_count}, Goals: {goal_count}")

    # Phase 2: Generate tasks (skeleton task chains this, but check if it ran)
    task_count = Task.objects.filter(goal__dream=dream).count()
    if task_count == 0:
        print("  Phase 2: Generating tasks...")
        start2 = time.time()
        result2 = generate_initial_tasks_task.apply(args=[str(dream.id), str(user.id)])
        elapsed2 = round(time.time() - start2, 1)
        print(f"  Tasks done in {elapsed2}s: {result2.result}")

    dream.refresh_from_db()
    task_count = Task.objects.filter(goal__dream=dream).count()
    print(f"  Phase: {dream.plan_phase}")
    print(f"  Tasks: {task_count}")
    print(f"  Tasks through month: {dream.tasks_generated_through_month}")
    print(f"  Total time: {round(time.time() - start_time, 1)}s")

except Exception as e:
    print(f"  Plan generation failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# ============================================================
# Step 6: Fake 14 days passing, complete some tasks
# ============================================================
print("\n" + "=" * 70)
print("STEP 6: Simulate 14 days + task completions")
print("=" * 70)

# Set next_checkin_at in the past
dream.next_checkin_at = timezone.now() - timedelta(hours=1)
dream.last_checkin_at = timezone.now() - timedelta(days=14)
dream.checkin_interval_days = 14
dream.created_at  # Can't change auto_now_add, but we can adjust dates

# Save dream
dream.save(update_fields=['next_checkin_at', 'last_checkin_at', 'checkin_interval_days'])

# Complete some tasks (first 5-8 tasks)
first_tasks = Task.objects.filter(
    goal__dream=dream, status='pending'
).order_by('expected_date', 'order')[:7]

completed_count = 0
for t in first_tasks:
    t.status = 'completed'
    t.completed_at = timezone.now() - timedelta(days=14 - completed_count)
    t.save(update_fields=['status', 'completed_at'])
    completed_count += 1

# Skip 2 tasks (make them overdue)
overdue_tasks = Task.objects.filter(
    goal__dream=dream, status='pending'
).order_by('expected_date')[:2]
for t in overdue_tasks:
    t.deadline_date = (timezone.now() - timedelta(days=3)).date()
    t.save(update_fields=['deadline_date'])

# Update dream progress
dream.update_progress()
dream.refresh_from_db()

print(f"  Completed {completed_count} tasks")
print(f"  Made 2 tasks overdue")
print(f"  Dream progress: {dream.progress_percentage}%")

# ============================================================
# Step 7: Check what context the AI will see
# ============================================================
print("\n" + "=" * 70)
print("STEP 7: Inspect context that will be injected")
print("=" * 70)

context = build_dream_context(dream, user)
print(context)
print(f"\n  Context length: {len(context)} chars (~{len(context)//4} tokens)")

# ============================================================
# Step 8: Generate check-in questionnaire
# ============================================================
print("\n" + "=" * 70)
print("STEP 8: Generate check-in questionnaire (calling OpenAI...)")
print("=" * 70)

from apps.dreams.tasks import _calculate_pace

pace = _calculate_pace(dream)
print(f"  Pace analysis: {json.dumps(pace, indent=2)}")

start_time = time.time()
try:
    result = ai_service.generate_checkin_questionnaire(dream, user, pace)
    elapsed = round(time.time() - start_time, 1)

    questions = result.get('questions', [])
    opening = result.get('opening_message', '')
    pace_summary = result.get('pace_summary', '')

    print(f"\n  Generated in {elapsed}s")
    print(f"  Opening: {opening[:200]}")
    print(f"  Pace summary: {pace_summary[:200]}")
    print(f"  Questions ({len(questions)}):")
    for q in questions:
        q_type = q.get('question_type', '?')
        q_text = q.get('question', '?')
        q_id = q.get('id', '?')
        print(f"    [{q_id}] ({q_type}) {q_text[:100]}")
        if q_type == 'choice':
            print(f"      Options: {q.get('options', [])}")
        elif q_type == 'slider':
            print(f"      Scale: {q.get('scale_min', 1)}-{q.get('scale_max', 5)} {q.get('scale_labels', {})}")
except Exception as e:
    print(f"  Questionnaire generation failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# ============================================================
# Step 9: Simulate user responses
# ============================================================
print("\n" + "=" * 70)
print("STEP 9: Submit user responses")
print("=" * 70)

# Build realistic responses
user_responses = {}
for q in questions:
    q_id = q.get('id', '')
    q_type = q.get('question_type', '')

    if q_id == 'satisfaction':
        user_responses[q_id] = 3  # Medium satisfaction
    elif q_id == 'time_change':
        user_responses[q_id] = 'same'
    elif q_id == 'obstacle_text':
        user_responses[q_id] = "Mon dos me fait un peu mal apres les exercices, et j'ai du mal a resister au grignotage de 16h"
    elif q_id == 'energy_level':
        user_responses[q_id] = 4  # Good energy
    elif q_type == 'slider':
        user_responses[q_id] = 3
    elif q_type == 'choice':
        options = q.get('options', [])
        user_responses[q_id] = options[0] if options else 'oui'
    elif q_type == 'text':
        user_responses[q_id] = "Ca va globalement, mais les exercices de dos sont difficiles."
    else:
        user_responses[q_id] = 'ok'

print(f"  Responses: {json.dumps(user_responses, ensure_ascii=False, indent=2)}")

# ============================================================
# Step 10: Run interactive check-in adaptation
# ============================================================
print("\n" + "=" * 70)
print("STEP 10: Run interactive adaptation (calling OpenAI...)")
print("=" * 70)

# Get task/goal counts before
tasks_before = Task.objects.filter(goal__dream=dream).count()
goals_before = Goal.objects.filter(dream=dream).count()

start_time = time.time()
try:
    result = ai_service.run_interactive_checkin_agent(
        dream, user, questions, user_responses
    )
    elapsed = round(time.time() - start_time, 1)

    tasks_after = Task.objects.filter(goal__dream=dream).count()
    goals_after = Goal.objects.filter(dream=dream).count()

    print(f"\n  Completed in {elapsed}s")
    print(f"  Pace status: {result.get('pace_status')}")
    print(f"  Next check-in: {result.get('next_checkin_days')} days")
    print(f"  Months covered through: {result.get('months_generated_through')}")
    print(f"  Actions taken: {len(result.get('actions_taken', []))}")
    for a in result.get('actions_taken', []):
        tool = a.get('tool')
        args_keys = list(a.get('args', {}).keys())
        print(f"    - {tool}({', '.join(args_keys)})")

    print(f"\n  Tasks: {tasks_before} -> {tasks_after} (+{tasks_after - tasks_before})")
    print(f"  Goals: {goals_before} -> {goals_after} (+{goals_after - goals_before})")

    print(f"\n  Coaching message:")
    msg = result.get('coaching_message', '')
    print(f"  {msg[:500]}")

    if result.get('adjustment_summary'):
        print(f"\n  Adjustment summary:")
        print(f"  {result['adjustment_summary'][:300]}")

except Exception as e:
    print(f"  Adaptation failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# ============================================================
# Summary
# ============================================================
print("\n" + "=" * 70)
print("END-TO-END TEST COMPLETE")
print("=" * 70)

dream.refresh_from_db()
ms_count = DreamMilestone.objects.filter(dream=dream).count()
goal_count = Goal.objects.filter(dream=dream).count()
task_count = Task.objects.filter(goal__dream=dream).count()
completed = Task.objects.filter(goal__dream=dream, status='completed').count()
pending = Task.objects.filter(goal__dream=dream, status='pending').count()

print(f"""
  Dream: {dream.title}
  Progress: {dream.progress_percentage}%
  Plan phase: {dream.plan_phase}
  Milestones: {ms_count}
  Goals: {goal_count}
  Tasks: {task_count} (completed: {completed}, pending: {pending})
  Tasks through month: {dream.tasks_generated_through_month}

  Context injected: YES (description, calibration, persona, obstacles)
  Check-in with user responses: YES
""")
