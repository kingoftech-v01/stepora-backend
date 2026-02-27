# Scaling Projections - DreamPlanner

Cost projections at different user scales, with monthly recurring and one-time costs broken out.

## Assumptions

| Parameter | Value | Reasoning |
|-----------|-------|-----------|
| Avg dreams per user | 3 | 50% casual (1-2), 35% active (3-4), 15% power (5-8) |
| Avg dream duration | 5 months | Most dreams are 3-6 months; some 12+ |
| Avg plan generation cost | $0.30 | Weighted avg across durations |
| Monthly active rate | 60% | % of users with at least 1 active dream |
| Recurring AI cost/active user/mo | $0.03 | Motivation + adjustments + rescue |
| Vision board images per user | 2 | On-demand feature |
| DALL-E cost per image | $0.04 | Standard 1024x1024 |

---

## One-Time Costs (Per User, At Registration + Dream Creation)

These costs are incurred once when users create dreams and generate plans.

| Feature | Per Dream | Per User (3 dreams) |
|---------|-----------|-------------------|
| Calibration | $0.12 | $0.36 |
| Plan generation | $0.18 avg | $0.54 |
| Dream analysis | $0.004 | $0.012 |
| Obstacle prediction | $0.009 | $0.027 |
| Vision board (2 images) | $0.08 | $0.08 |
| **Total one-time** | **~$0.39** | **~$1.02** |

---

## Monthly Recurring Costs (Per Active User)

These costs are incurred continuously while users have active dreams.

| Feature | Frequency | Cost/Call | Monthly Cost |
|---------|-----------|----------|-------------|
| Motivation messages | Daily | $0.0002 | $0.006 |
| Task adjustments | Weekly | $0.007 | $0.028 |
| Rescue messages | ~0.5/mo | $0.0003 | $0.0002 |
| Two-minute starts | ~2/mo | $0.0001 | $0.0002 |
| **Total recurring** | | | **~$0.035/mo** |

---

## Scaling Table: One-Time Costs

Cost of onboarding all users (all dreams created and plans generated).

| Total Users | Dreams Created | One-Time AI Cost | Notes |
|-------------|---------------|-----------------|-------|
| 100 | 300 | **$102** | Beta / early launch |
| 500 | 1,500 | **$510** | Early traction |
| 1,000 | 3,000 | **$1,020** | Growing user base |
| 5,000 | 15,000 | **$5,100** | |
| 10,000 | 30,000 | **$10,200** | |
| 25,000 | 75,000 | **$25,500** | |
| 50,000 | 150,000 | **$51,000** | |
| 100,000 | 300,000 | **$102,000** | |
| 500,000 | 1,500,000 | **$510,000** | |

**Note:** One-time costs are spread over the user's lifetime (they don't all happen on day 1).

---

## Scaling Table: Monthly Recurring Costs

Monthly AI spend for active users (motivation, adjustments, rescue).

| Total Users | Active Users (60%) | Monthly Recurring Cost | Annual Recurring Cost |
|-------------|-------------------|----------------------|---------------------|
| 100 | 60 | **$2.10** | **$25** |
| 500 | 300 | **$10.50** | **$126** |
| 1,000 | 600 | **$21** | **$252** |
| 5,000 | 3,000 | **$105** | **$1,260** |
| 10,000 | 6,000 | **$210** | **$2,520** |
| 25,000 | 15,000 | **$525** | **$6,300** |
| 50,000 | 30,000 | **$1,050** | **$12,600** |
| 100,000 | 60,000 | **$2,100** | **$25,200** |
| 500,000 | 300,000 | **$10,500** | **$126,000** |

---

## Scaling Table: Total Monthly Cost (New Users + Recurring)

Assuming 10% of total users are new each month (creating dreams for the first time).

| Total Users | New Users/Mo (10%) | One-Time Cost/Mo | Recurring Cost/Mo | **Total AI Cost/Mo** |
|-------------|-------------------|-----------------|-------------------|---------------------|
| 100 | 10 | $10 | $2 | **$12** |
| 500 | 50 | $51 | $11 | **$62** |
| 1,000 | 100 | $102 | $21 | **$123** |
| 5,000 | 500 | $510 | $105 | **$615** |
| 10,000 | 1,000 | $1,020 | $210 | **$1,230** |
| 25,000 | 2,500 | $2,550 | $525 | **$3,075** |
| 50,000 | 5,000 | $5,100 | $1,050 | **$6,150** |
| 100,000 | 10,000 | $10,200 | $2,100 | **$12,300** |
| 500,000 | 50,000 | $51,000 | $10,500 | **$61,500** |

---

## Revenue vs Cost (Break-Even Analysis)

Assuming tiered subscription model:

| Tier | Price/Mo | % of Users | Avg Revenue/User/Mo |
|------|---------|-----------|-------------------|
| Free | $0 | 40% | $0.00 |
| Basic | $4.99 | 35% | $1.75 |
| Pro | $9.99 | 20% | $2.00 |
| Premium | $19.99 | 5% | $1.00 |
| **Blended ARPU** | | | **$4.75** |

### Revenue vs AI Cost at Scale

| Users | Monthly Revenue | Monthly AI Cost | **AI as % of Revenue** | **Net After AI** |
|-------|----------------|----------------|----------------------|-----------------|
| 1,000 | $4,750 | $123 | 2.6% | $4,627 |
| 5,000 | $23,750 | $615 | 2.6% | $23,135 |
| 10,000 | $47,500 | $1,230 | 2.6% | $46,270 |
| 50,000 | $237,500 | $6,150 | 2.6% | $231,350 |
| 100,000 | $475,000 | $12,300 | 2.6% | $462,700 |
| 500,000 | $2,375,000 | $61,500 | 2.6% | $2,313,500 |

**AI costs stay at ~2.6% of revenue regardless of scale.** This is an excellent margin.

---

## Worst-Case Scenario

All users are power users (8 dreams, 12-month avg, daily image generation):

| Users | Monthly AI Cost | Monthly Revenue | AI as % of Revenue |
|-------|----------------|----------------|-------------------|
| 10,000 | ~$8,500 | $47,500 | 17.9% |
| 100,000 | ~$85,000 | $475,000 | 17.9% |

Even in the worst case, AI costs remain under 20% of revenue.

---

## Cost Reduction Roadmap

### Phase 1 (Current)
- GPT-3.5 Turbo for simple messages (motivation, rescue, micro-actions)
- Chunked generation to prevent token waste
- AIUsageTracker for per-user limits

### Phase 2 (10K+ users)
- Response caching for repeated motivation patterns
- Batch calibration questions (reduce round trips from 4 to 2-3)
- GPT-4o-mini for analysis and obstacle prediction (~50% cheaper)

### Phase 3 (50K+ users)
- Fine-tuned model for plan generation (reduce prompt size, improve quality)
- Semantic caching for similar dreams (share partial plans)
- Pre-generated template plans for common dreams (bypass AI entirely)

### Phase 4 (100K+ users)
- Self-hosted open-source model for simple tasks (motivation, rescue)
- Negotiated enterprise pricing with OpenAI (volume discounts)
- Hybrid approach: templates for common dreams, AI for unique ones

### Estimated Cost Reduction Per Phase

| Phase | Est. Reduction | AI as % of Revenue |
|-------|---------------|-------------------|
| Phase 1 (current) | baseline | ~2.6% |
| Phase 2 | -30% | ~1.8% |
| Phase 3 | -50% | ~1.3% |
| Phase 4 | -70% | ~0.8% |
