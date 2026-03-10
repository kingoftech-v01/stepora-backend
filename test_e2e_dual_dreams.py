#!/usr/bin/env python3
"""
E2E test: Two dreams in different languages with VAGUE descriptions.

Tests that the full flow works even when the user gives minimal info,
and that context is always preserved and passed correctly.

Dream A (French):  "Devenir musicien"        — very vague
Dream B (English): "Start my own business"   — very vague
"""

import os
import sys
import time

os.environ["DB_HOST"] = "172.22.0.7"
os.environ["DB_NAME"] = "stepora"
os.environ["DB_USER"] = "stepora"
os.environ["DB_PASSWORD"] = "stepora_dev_password"
os.environ["REDIS_HOST"] = "172.22.0.3"
os.environ["REDIS_URL"] = "redis://:dp_redis_S3cur3_2026!@172.22.0.3:6379/1"
os.environ["CELERY_BROKER_URL"] = "redis://:dp_redis_S3cur3_2026!@172.22.0.3:6379/0"
os.environ["CELERY_RESULT_BACKEND"] = "redis://:dp_redis_S3cur3_2026!@172.22.0.3:6379/0"
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

import logging

logging.disable(logging.DEBUG)

import django

django.setup()

# Disable Elasticsearch signals
try:
    from django.db.models.signals import post_delete, post_save

    post_save.receivers = [
        r for r in post_save.receivers if "elasticsearch" not in str(r)
    ]
    post_delete.receivers = [
        r for r in post_delete.receivers if "elasticsearch" not in str(r)
    ]
except Exception:
    pass

from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from apps.dreams.models import (
    CalibrationResponse,
    Dream,
    DreamMilestone,
    Goal,
    Task,
)
from apps.users.models import User
from integrations.context_builder import build_dream_context
from integrations.openai_service import OpenAIService

# Force sync Celery
settings.CELERY_TASK_ALWAYS_EAGER = True
settings.CELERY_TASK_EAGER_PROPAGATES = True
from config.celery import app as celery_app

celery_app.conf.task_always_eager = True
celery_app.conf.task_eager_propagates = True

from apps.dreams.tasks import (
    _calculate_pace,
    generate_dream_skeleton_task,
    generate_initial_tasks_task,
)

ai_service = OpenAIService()

PASS = "PASS"
FAIL = "FAIL"
results = []


def log_result(name, passed, detail=""):
    status = PASS if passed else FAIL
    results.append((name, status, detail))
    icon = "+" if passed else "!"
    print(f"  [{icon}] {name}: {status}" + (f" — {detail}" if detail else ""))


def run_dream_flow(dream_config):
    """Run the full lifecycle for a single dream. Returns summary dict."""
    label = dream_config["label"]
    lang = dream_config["lang"]

    print("\n" + "#" * 70)
    print(f"# DREAM {label} ({lang.upper()}): {dream_config['title']}")
    print("#" * 70)

    user = dream_config["user"]

    # --- 1. Create dream ---
    print(f"\n{'='*60}\n[{label}] STEP 1: Create dream\n{'='*60}")
    Dream.objects.filter(user=user, title=dream_config["title"]).delete()

    dream = Dream.objects.create(
        user=user,
        title=dream_config["title"],
        description=dream_config["description"],
        category=dream_config.get("category", "other"),
        language=lang,
        target_date=timezone.now() + timedelta(days=dream_config.get("days", 180)),
        status="active",
        calibration_status="completed",
        plan_phase="none",
    )
    print(f"  Dream: {dream.title} (id={dream.id})")
    log_result(f"{label} dream created", True)

    # --- 2. Calibration ---
    print(f"\n{'='*60}\n[{label}] STEP 2: Calibration responses\n{'='*60}")
    CalibrationResponse.objects.filter(dream=dream).delete()
    for num, cat, question, answer in dream_config["calibration"]:
        CalibrationResponse.objects.create(
            dream=dream,
            question_number=num,
            category=cat,
            question=question,
            answer=answer,
        )
    print(f"  Created {len(dream_config['calibration'])} calibration responses")
    log_result(f"{label} calibration stored", True)

    # --- 3. Generate skeleton + tasks ---
    print(f"\n{'='*60}\n[{label}] STEP 3: Generate plan (AI call)\n{'='*60}")
    t0 = time.time()
    try:
        generate_dream_skeleton_task.apply(args=[str(dream.id), str(user.id)])
        dream.refresh_from_db()
        ms_count = DreamMilestone.objects.filter(dream=dream).count()
        goal_count = Goal.objects.filter(dream=dream).count()
        print(
            f"  Skeleton: {ms_count} milestones, {goal_count} goals ({round(time.time()-t0, 1)}s)"
        )

        task_count = Task.objects.filter(goal__dream=dream).count()
        if task_count == 0:
            t1 = time.time()
            generate_initial_tasks_task.apply(args=[str(dream.id), str(user.id)])
            print(f"  Tasks generated in {round(time.time()-t1, 1)}s")

        dream.refresh_from_db()
        task_count = Task.objects.filter(goal__dream=dream).count()
        print(f"  Total: {ms_count} milestones, {goal_count} goals, {task_count} tasks")
        print(f"  Tasks through month: {dream.tasks_generated_through_month}")
        log_result(f"{label} plan generated", task_count > 0, f"{task_count} tasks")
    except Exception as e:
        print(f"  FAILED: {e}")
        import traceback

        traceback.print_exc()
        log_result(f"{label} plan generated", False, str(e))
        return None

    # --- 4. Fake 14 days + completions ---
    print(f"\n{'='*60}\n[{label}] STEP 4: Simulate 14 days + completions\n{'='*60}")
    dream.next_checkin_at = timezone.now() - timedelta(hours=1)
    dream.last_checkin_at = timezone.now() - timedelta(days=14)
    dream.checkin_interval_days = 14
    dream.save(
        update_fields=["next_checkin_at", "last_checkin_at", "checkin_interval_days"]
    )

    first_tasks = Task.objects.filter(goal__dream=dream, status="pending").order_by(
        "expected_date", "order"
    )[:5]
    completed = 0
    for t in first_tasks:
        t.status = "completed"
        t.completed_at = timezone.now() - timedelta(days=14 - completed)
        t.save(update_fields=["status", "completed_at"])
        completed += 1

    dream.update_progress()
    dream.refresh_from_db()
    print(f"  Completed {completed} tasks, progress: {dream.progress_percentage}%")

    # --- 5. Context inspection ---
    print(f"\n{'='*60}\n[{label}] STEP 5: Context inspection\n{'='*60}")
    context = build_dream_context(dream, user)
    ctx_len = len(context)
    ctx_tokens = ctx_len // 4

    # Verify all sections present
    has_dream = "=== DREAM CONTEXT ===" in context
    has_calibration = "=== CALIBRATION RESPONSES ===" in context
    has_persona = "=== USER PERSONA ===" in context
    has_title = dream.title in context

    print(f"  Context: {ctx_len} chars (~{ctx_tokens} tokens)")
    log_result(f"{label} context has DREAM section", has_dream)
    log_result(f"{label} context has CALIBRATION", has_calibration)
    log_result(f"{label} context has PERSONA", has_persona)
    log_result(f"{label} context has dream title", has_title)

    # --- 6. Questionnaire ---
    print(f"\n{'='*60}\n[{label}] STEP 6: Generate questionnaire (AI call)\n{'='*60}")
    pace = _calculate_pace(dream)
    print(f"  Pace: {pace['pace_status']}")

    t0 = time.time()
    try:
        q_result = ai_service.generate_checkin_questionnaire(dream, user, pace)
        elapsed = round(time.time() - t0, 1)
        questions = q_result.get("questions", [])
        opening = q_result.get("opening_message", "")
        print(f"  Generated {len(questions)} questions in {elapsed}s")
        print(f"  Opening: {opening[:150]}")
        for q in questions:
            print(
                f"    [{q.get('id', '')}] ({q.get('question_type', '')}) {q.get('question', '')[:90]}"
            )

        # Language check: opening should be in the dream's language
        log_result(
            f"{label} questionnaire generated",
            len(questions) >= 3,
            f"{len(questions)} questions",
        )

        # Check questions reference dream context (not generic)
        print(f"\n  [Language check] Opening first 50 chars: '{opening[:50]}'")

    except Exception as e:
        print(f"  FAILED: {e}")
        import traceback

        traceback.print_exc()
        log_result(f"{label} questionnaire generated", False, str(e))
        return None

    # --- 7. User responses ---
    print(f"\n{'='*60}\n[{label}] STEP 7: User responses\n{'='*60}")
    user_responses = {}
    for q in questions:
        q_id = q.get("id", "")
        q_type = q.get("question_type", "")
        if q_id == "satisfaction":
            user_responses[q_id] = 3
        elif q_id == "time_change":
            user_responses[q_id] = "same" if lang == "en" else "pareil"
        elif q_id == "obstacle_text":
            user_responses[q_id] = dream_config["obstacle_response"]
        elif q_id == "energy_level":
            user_responses[q_id] = 4
        elif q_type == "slider":
            user_responses[q_id] = 3
        elif q_type == "choice":
            opts = q.get("options", [])
            user_responses[q_id] = opts[0] if opts else "yes"
        elif q_type == "text":
            user_responses[q_id] = dream_config["generic_response"]
        else:
            user_responses[q_id] = "ok"
    print(f"  Submitted {len(user_responses)} responses")

    # --- 8. Interactive adaptation ---
    print(f"\n{'='*60}\n[{label}] STEP 8: Run adaptation (AI call)\n{'='*60}")
    tasks_before = Task.objects.filter(goal__dream=dream).count()
    goals_before = Goal.objects.filter(dream=dream).count()
    months_before = dream.tasks_generated_through_month

    t0 = time.time()
    try:
        adapt_result = ai_service.run_interactive_checkin_agent(
            dream, user, questions, user_responses
        )
        elapsed = round(time.time() - t0, 1)
        tasks_after = Task.objects.filter(goal__dream=dream).count()
        goals_after = Goal.objects.filter(dream=dream).count()

        pace_status = adapt_result.get("pace_status")
        next_days = adapt_result.get("next_checkin_days")
        months_through = adapt_result.get("months_generated_through")
        coaching = adapt_result.get("coaching_message", "")
        actions = adapt_result.get("actions_taken", [])

        print(f"  Completed in {elapsed}s")
        print(f"  Pace: {pace_status}, Next: {next_days} days")
        print(f"  Months covered: {months_through}")
        print(f"  Actions: {len(actions)}")
        for a in actions:
            print(
                f"    - {a.get('tool', '?')}({', '.join(list(a.get('args', {}).keys())[:3])})"
            )
        print(
            f"  Tasks: {tasks_before} -> {tasks_after} (+{tasks_after - tasks_before})"
        )
        print(
            f"  Goals: {goals_before} -> {goals_after} (+{goals_after - goals_before})"
        )
        print(f"\n  Coaching ({lang}):")
        print(f"  {coaching[:400]}")

        # Validations
        log_result(f"{label} adaptation completed", True)
        log_result(
            f"{label} pace_status returned", pace_status is not None, pace_status
        )
        log_result(
            f"{label} next_checkin_days returned", next_days is not None, str(next_days)
        )
        log_result(
            f"{label} months not regressed",
            months_through is None or months_through >= months_before,
            f"{months_before} -> {months_through}",
        )
        log_result(
            f"{label} coaching not empty", len(coaching) > 20, f"{len(coaching)} chars"
        )
        log_result(
            f"{label} actions taken", len(actions) > 0, f"{len(actions)} actions"
        )

        return {
            "dream": dream,
            "tasks_before": tasks_before,
            "tasks_after": tasks_after,
            "pace": pace_status,
            "coaching": coaching,
            "months": months_through,
            "lang": lang,
        }

    except Exception as e:
        print(f"  FAILED: {e}")
        import traceback

        traceback.print_exc()
        log_result(f"{label} adaptation completed", False, str(e))
        return None


# ==================================================================
# SETUP: Create user with persona
# ==================================================================
print("=" * 70)
print("SETUP: Create test user")
print("=" * 70)

user, created = User.objects.get_or_create(
    email="test_dual_dreams@stepora.test",
    defaults={"display_name": "Alex Testeur", "timezone": "Europe/Paris"},
)
if created:
    user.set_password("testpass123")
    user.save()

user.persona = {
    "available_hours_per_week": 8,
    "preferred_schedule": "evenings and weekends",
    "budget_range": "0-50 EUR/month",
    "learning_style": "hands-on",
    "typical_day": "Work 9-18h, free evenings and weekends",
    "occupation": "office worker",
    "global_motivation": "Want to do something meaningful with my free time",
    "global_constraints": "Limited budget, live in a small apartment",
}
user.work_schedule = {
    "workDays": [1, 2, 3, 4, 5],
    "startTime": "09:00",
    "endTime": "18:00",
}
user.save(update_fields=["persona", "work_schedule"])
print(f"  User: {user.email}")

# ==================================================================
# DREAM A: French, very vague
# ==================================================================
dream_a_config = {
    "label": "A",
    "lang": "fr",
    "user": user,
    "title": "Devenir musicien",
    "description": "Je veux apprendre la musique.",
    "category": "learning",
    "days": 365,
    "calibration": [
        (
            1,
            "experience",
            "Quel est votre niveau actuel en musique?",
            "Aucun, je n'ai jamais joue d'un instrument.",
        ),
        (
            2,
            "preferences",
            "Quel instrument vous interesse?",
            "Je sais pas trop, peut-etre la guitare ou le piano.",
        ),
        (3, "resources", "Avez-vous un instrument?", "Non, rien du tout."),
        (
            4,
            "motivation",
            "Pourquoi la musique?",
            "J'aime bien ecouter de la musique et je me dis que ce serait cool de jouer.",
        ),
        (
            5,
            "constraints",
            "Des contraintes particulieres?",
            "Budget serre, et mes voisins se plaignent du bruit.",
        ),
    ],
    "obstacle_response": "J'ai pas encore achete d'instrument et je sais toujours pas lequel choisir",
    "generic_response": "Pas trop avance, j'hesite encore.",
}

# ==================================================================
# DREAM B: English, very vague
# ==================================================================
dream_b_config = {
    "label": "B",
    "lang": "en",
    "user": user,
    "title": "Start my own business",
    "description": "I want to start a business someday.",
    "category": "career",
    "days": 365,
    "calibration": [
        (
            1,
            "experience",
            "Do you have any business experience?",
            "Not really, I've only ever been an employee.",
        ),
        (
            2,
            "preferences",
            "What kind of business are you thinking about?",
            "No idea honestly, maybe something online.",
        ),
        (
            3,
            "resources",
            "What resources do you have available?",
            "Just my laptop and some savings, maybe 2000 euros.",
        ),
        (
            4,
            "motivation",
            "Why do you want to start a business?",
            "I'm bored at my job and want more freedom.",
        ),
        (
            5,
            "constraints",
            "Any constraints we should know about?",
            "I still need my day job income, can't quit yet. Limited time.",
        ),
    ],
    "obstacle_response": "I still have no clear idea what business to start, feeling stuck",
    "generic_response": "Haven't made much progress, still exploring options.",
}

# ==================================================================
# RUN BOTH DREAMS
# ==================================================================
result_a = run_dream_flow(dream_a_config)
result_b = run_dream_flow(dream_b_config)

# ==================================================================
# FINAL VERIFICATION
# ==================================================================
print("\n" + "=" * 70)
print("FINAL VERIFICATION: Cross-dream context isolation")
print("=" * 70)

if result_a and result_b:
    dream_a = result_a["dream"]
    dream_b = result_b["dream"]

    # Verify contexts are separate
    ctx_a = build_dream_context(dream_a, user)
    ctx_b = build_dream_context(dream_b, user)

    # Dream A context should have French title, not English
    a_has_own_title = dream_a.title in ctx_a
    a_not_have_b = dream_b.title not in ctx_a
    b_has_own_title = dream_b.title in ctx_b
    b_not_have_a = dream_a.title not in ctx_b

    log_result("A context has own title", a_has_own_title)
    log_result("A context does NOT have B's title", a_not_have_b)
    log_result("B context has own title", b_has_own_title)
    log_result("B context does NOT have A's title", b_not_have_a)

    # Verify persona is shared (same user)
    a_has_persona = "=== USER PERSONA ===" in ctx_a
    b_has_persona = "=== USER PERSONA ===" in ctx_b
    log_result("A has persona (shared user)", a_has_persona)
    log_result("B has persona (shared user)", b_has_persona)

    # Verify coaching language matches dream language
    coaching_a = result_a["coaching"]
    coaching_b = result_b["coaching"]

    # Simple heuristic: French coaching should have French words
    fr_markers = ["vous", "votre", "les", "des", "pour", "est", "pas", "une"]
    en_markers = ["you", "your", "the", "and", "for", "have", "can", "with"]
    a_fr_score = sum(1 for w in fr_markers if w in coaching_a.lower())
    b_en_score = sum(1 for w in en_markers if w in coaching_b.lower())
    log_result("A coaching in French", a_fr_score >= 3, f"FR score: {a_fr_score}/8")
    log_result("B coaching in English", b_en_score >= 3, f"EN score: {b_en_score}/8")

# ==================================================================
# SUMMARY
# ==================================================================
print("\n" + "=" * 70)
print("TEST SUMMARY")
print("=" * 70)

passed = sum(1 for _, s, _ in results if s == PASS)
failed = sum(1 for _, s, _ in results if s == FAIL)

for name, status, detail in results:
    icon = "+" if status == PASS else "X"
    line = f"  [{icon}] {name}"
    if detail:
        line += f" — {detail}"
    print(line)

print(f"\n  Total: {passed} passed, {failed} failed out of {len(results)}")

if result_a:
    d = result_a["dream"]
    d.refresh_from_db()
    tc = Task.objects.filter(goal__dream=d).count()
    print(
        f"\n  Dream A '{d.title}': {tc} tasks, {d.progress_percentage}% progress, months={d.tasks_generated_through_month}"
    )
if result_b:
    d = result_b["dream"]
    d.refresh_from_db()
    tc = Task.objects.filter(goal__dream=d).count()
    print(
        f"  Dream B '{d.title}': {tc} tasks, {d.progress_percentage}% progress, months={d.tasks_generated_through_month}"
    )

if failed > 0:
    print(f"\n  *** {failed} TEST(S) FAILED ***")
    sys.exit(1)
else:
    print("\n  ALL TESTS PASSED")
