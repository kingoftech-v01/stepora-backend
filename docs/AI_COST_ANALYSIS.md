# AI Cost Analysis - DreamPlanner

Detailed breakdown of all OpenAI API costs per feature, per user, and at scale.

## Pricing Reference (GPT-4o, as of 2025)

| Model | Input | Output | Notes |
|-------|-------|--------|-------|
| **GPT-4o** | $2.50 / 1M tokens | $10.00 / 1M tokens | Plan generation, analysis, calibration, obstacles, adjustments |
| **GPT-3.5 Turbo** | $0.50 / 1M tokens | $1.50 / 1M tokens | Motivation, rescue messages, 2-min start |
| **GPT-4 Vision** | $2.50 / 1M tokens | $10.00 / 1M tokens | Image analysis |
| **Whisper-1** | $0.006 / minute | - | Audio transcription |
| **DALL-E 3** | $0.040 / image (standard 1024x1024) | - | Vision board images |

---

## 1. Dream Plan Generation (Core Feature)

The most token-intensive feature. Uses GPT-4o with JSON structured output.

### Architecture

- **Short dreams (1-6 months):** 1 API call, up to 16,384 output tokens
- **Long dreams (>6 months):** Chunked into 6-month segments, each chunk = 1 API call
- **Always 1 milestone per month, 4+ goals per milestone, 4+ tasks per goal**

### Per-Call Token Breakdown

| Component | Input Tokens | Notes |
|-----------|-------------|-------|
| System prompt (planning) | ~2,000 | ETHICAL_PREAMBLE + planning rules + JSON schema |
| User prompt (dream + context) | ~500 | Dream title, description, timeline info |
| Calibration section | ~500 | If calibration was completed (profile data) |
| Previous chunk summary | ~200 per chunk | Growing context for continuity (chunked only) |
| **Total input per call** | **~3,200** | +200 per additional chunk |

| Component | Output Tokens | Notes |
|-----------|-------------|-------|
| Per milestone | ~60 | Title, description, dates, reasoning |
| Per goal (x4 per milestone) | ~80 each = ~320 | Title, description, dates, estimated_minutes |
| Per task (x4 per goal = x16 per milestone) | ~130 each = ~2,080 | Title, detailed instructions, dates, duration |
| Per obstacle (~2 per milestone) | ~80 each = ~160 | Title, description, solution, evidence |
| Analysis + tips + metadata | ~500 | First chunk only |
| **Total output per month** | **~2,200** | Per month of dream duration |

### Cost by Dream Duration

| Duration | API Calls | Input Tokens | Output Tokens | Cost |
|----------|-----------|-------------|---------------|------|
| 1 month | 1 | ~3,500 | ~2,500 | **$0.034** |
| 2 months | 1 | ~3,500 | ~5,000 | **$0.059** |
| 3 months | 1 | ~3,500 | ~7,500 | **$0.084** |
| 6 months | 1 | ~3,500 | ~14,000 | **$0.149** |
| 12 months | 2 | ~7,000 | ~28,000 | **$0.298** |
| 18 months | 3 | ~11,000 | ~42,000 | **$0.448** |
| 24 months | 4 | ~15,500 | ~56,000 | **$0.599** |
| 36 months | 6 | ~25,500 | ~84,000 | **$0.904** |

### Objects Generated per Duration

| Duration | Milestones | Goals | Tasks | Obstacles | Total Objects |
|----------|------------|-------|-------|-----------|---------------|
| 1 month | 1 | 4 | 16 | ~2 | ~23 |
| 3 months | 3 | 12 | 48 | ~6 | ~69 |
| 6 months | 6 | 24 | 96 | ~10 | ~136 |
| 12 months | 12 | 48 | 192 | ~18 | ~270 |
| 24 months | 24 | 96 | 384 | ~30 | ~534 |
| 36 months | 36 | 144 | 576 | ~42 | ~798 |

---

## 2. Calibration (Pre-Plan Phase)

Progressive Q&A to build a user profile before plan generation. Uses GPT-4o.

| Phase | Input Tokens | Output Tokens | Cost | Notes |
|-------|-------------|---------------|------|-------|
| Initial questions (7 Qs) | ~3,000 | ~2,000 | $0.028 | System prompt + dream context |
| Follow-up round 1 | ~4,000 | ~2,000 | $0.030 | Previous Q&A context grows |
| Follow-up round 2 | ~5,000 | ~1,500 | $0.028 | More context, fewer questions |
| Profile generation | ~5,500 | ~2,000 | $0.034 | Final summary call |
| **Total** | **~17,500** | **~7,500** | **~$0.12** | 4 API calls, constant per dream |

**Notes:**
- Max 25 questions total across all rounds
- 8 mandatory areas: experience, timeline, resources, motivation, constraints, specifics, lifestyle, preferences
- AI must reach 0.95+ confidence before completing
- Calibration cost is constant regardless of dream duration

---

## 3. Dream Analysis

Quick AI analysis of dream feasibility. Uses GPT-4o.

| Component | Tokens | Cost |
|-----------|--------|------|
| Input | ~300 | $0.001 |
| Output (max 500) | ~300 | $0.003 |
| **Total per call** | **~600** | **~$0.004** |

Called once per dream (on demand).

---

## 4. Motivational Messages

Short personalized messages. Uses **GPT-3.5 Turbo** (cheaper model).

| Component | Tokens | Cost |
|-----------|--------|------|
| Input | ~200 | $0.0001 |
| Output (max 60) | ~40 | $0.0001 |
| **Total per call** | **~240** | **~$0.0002** |

Called daily per active dream (automated via Celery).

---

## 5. Two-Minute Start (Micro-Actions)

Quick micro-action generation. Uses **GPT-3.5 Turbo**.

| Component | Tokens | Cost |
|-----------|--------|------|
| Input | ~150 | $0.0001 |
| Output (max 50) | ~30 | $0.00005 |
| **Total per call** | **~180** | **~$0.0001** |

Called on demand by user.

---

## 6. Rescue Messages

Empathetic messages for inactive users. Uses **GPT-3.5 Turbo**.

| Component | Tokens | Cost |
|-----------|--------|------|
| Input | ~250 | $0.0001 |
| Output (max 150) | ~100 | $0.0002 |
| **Total per call** | **~350** | **~$0.0003** |

Called once when user becomes inactive (automated via Celery).

---

## 7. Obstacle Prediction

AI-predicted obstacles for dreams. Uses GPT-4o.

| Component | Tokens | Cost |
|-----------|--------|------|
| Input | ~400 | $0.001 |
| Output (max 1,500) | ~800 | $0.008 |
| **Total per call** | **~1,200** | **~$0.009** |

Called once per dream (automated via Celery after plan generation).

---

## 8. Task Adjustments

AI coaching when completion rate drops below 50%. Uses GPT-4o.

| Component | Tokens | Cost |
|-----------|--------|------|
| Input | ~600 | $0.002 |
| Output (max 1,000) | ~500 | $0.005 |
| **Total per call** | **~1,100** | **~$0.007** |

Called at most once per week per user (automated via Celery).

---

## 9. Vision Board Image (DALL-E 3)

| Component | Cost |
|-----------|------|
| 1 image (1024x1024, standard) | **$0.040** |

Called on demand by user. Users can generate multiple images per dream.

---

## 10. Audio Transcription (Whisper)

| Component | Cost |
|-----------|------|
| Per minute of audio | **$0.006** |
| Typical voice message (30s) | **$0.003** |

Called on demand when user records audio.

---

## 11. Image Analysis (GPT-4 Vision)

| Component | Tokens | Cost |
|-----------|--------|------|
| Input (text + image) | ~500 | $0.001 |
| Output (max 500) | ~300 | $0.003 |
| **Total per call** | **~800** | **~$0.004** |

Called on demand when user uploads an image.

---

## Total Cost Per Dream (Full Lifecycle)

Assuming a typical 6-month dream with all features used:

| Feature | Frequency | Cost | Subtotal |
|---------|-----------|------|----------|
| Calibration | 1x | $0.12 | $0.12 |
| Plan generation (6mo) | 1x | $0.15 | $0.15 |
| Dream analysis | 1x | $0.004 | $0.004 |
| Obstacle prediction | 1x | $0.009 | $0.009 |
| Motivation messages | ~150 (daily for 5mo) | $0.0002 | $0.03 |
| Rescue messages | ~2 (if inactive) | $0.0003 | $0.001 |
| Task adjustments | ~8 (weekly checks) | $0.007 | $0.056 |
| Two-minute starts | ~5 (on demand) | $0.0001 | $0.001 |
| Vision board | ~2 images | $0.040 | $0.08 |
| **TOTAL PER DREAM** | | | **~$0.45** |

---

## Total Cost Per User (Lifetime)

Assuming average 3 dreams per user with mixed durations:

| User Profile | Dreams | Duration Mix | One-Time Cost | Recurring/Month | Lifetime (1yr) |
|-------------|--------|-------------|---------------|-----------------|----------------|
| Casual | 1-2 | 3mo avg | $0.35 | $0.01 | **~$0.47** |
| Active | 3-4 | 6mo avg | $1.35 | $0.04 | **~$1.83** |
| Power | 5-8 | mixed | $3.00 | $0.08 | **~$3.96** |
| **Weighted Average** | **~3** | **~5mo avg** | **$0.89** | **$0.03** | **~$1.25** |

**One-time costs:** calibration + plan generation + analysis + obstacles (incurred once per dream)
**Recurring costs:** motivation messages + task adjustments (daily/weekly while dream is active)

---

## Cost vs Revenue

| Subscription | Monthly Revenue | AI Cost/User/Month | **Margin** |
|-------------|----------------|-------------------|-----------|
| Free tier (1 dream, no AI) | $0.00 | $0.00 | - |
| Basic ($4.99/mo) | $4.99 | ~$0.10 | **98%** |
| Premium ($19.99/mo) | $19.99 | ~$0.15 | **99.3%** |
| Pro ($29.99/mo) | $29.99 | ~$0.25 | **99.2%** |

AI costs are negligible relative to subscription revenue, even for power users.

---

## Cost Optimization Strategies

1. **GPT-3.5 Turbo for simple tasks** - Already implemented for motivation, rescue, and micro-actions (4x cheaper than GPT-4o)
2. **Chunked generation** - Prevents wasted tokens on truncated responses for long dreams
3. **Calibration capping** - Max 25 questions prevents runaway calibration costs
4. **DALL-E standard quality** - Using standard (not HD) saves 50% per image
5. **Celery scheduling** - Batch AI tasks during off-peak hours for lower latency costs
6. **Response caching** - Motivation messages and analyses can be cached to avoid duplicate calls
7. **Token budget monitoring** - `AIUsageTracker` tracks per-user usage for subscription enforcement
