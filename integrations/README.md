# Integrations

External service integrations for DreamPlanner.

## OpenAI Service (`openai_service.py`)

Central service class for all OpenAI API interactions. All AI features go through `OpenAIService`.

### Models Used

| Model | Features | Why |
|-------|----------|-----|
| **GPT-4o** (`settings.OPENAI_MODEL`) | Plan generation, calibration, analysis, obstacles, task adjustments | Best quality for structured JSON output |
| **GPT-3.5 Turbo** | Motivation messages, rescue messages, two-minute starts | 5x cheaper, sufficient for short text |
| **GPT-4 Vision** | Image analysis | Multimodal capability needed |
| **Whisper-1** | Audio transcription | Only speech-to-text model |
| **DALL-E 3** | Vision board images | Best image generation quality |

### Feature Cost Summary

| Feature | Model | max_tokens | Input Tokens | Output Tokens | Cost/Call |
|---------|-------|-----------|-------------|---------------|----------|
| `generate_plan` (single) | GPT-4o | 16,384 | ~3,500 | ~2,500-14,000 | $0.03-0.15 |
| `generate_plan` (chunked, per chunk) | GPT-4o | 16,384 | ~3,200-5,200 | ~14,000 | ~$0.15 |
| `generate_calibration_questions` | GPT-4o | 2,500 | ~3,000-5,500 | ~1,500-2,000 | $0.02-0.03 |
| `generate_calibration_summary` | GPT-4o | 1,500 | ~5,500 | ~1,500 | ~$0.03 |
| `analyze_dream` | GPT-4o | 500 | ~300 | ~300 | ~$0.004 |
| `predict_obstacles` | GPT-4o | 1,500 | ~400 | ~800 | ~$0.009 |
| `generate_task_adjustments` | GPT-4o | 1,000 | ~600 | ~500 | ~$0.007 |
| `generate_motivational_message` | GPT-3.5 | 60 | ~200 | ~40 | ~$0.0002 |
| `generate_two_minute_start` | GPT-3.5 | 50 | ~150 | ~30 | ~$0.0001 |
| `generate_rescue_message` | GPT-3.5 | 150 | ~250 | ~100 | ~$0.0003 |
| `analyze_image` | GPT-4V | 500 | ~500 | ~300 | ~$0.004 |
| `transcribe_audio` | Whisper-1 | - | - | - | $0.006/min |
| `generate_vision_image` | DALL-E 3 | - | - | - | $0.04/image |

### Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| `OPENAI_API_KEY` | required | OpenAI API key |
| `OPENAI_MODEL` | `gpt-4o-mini` | Default model for GPT-4o features |
| `OPENAI_ORGANIZATION_ID` | optional | OpenAI organization ID |
| `OPENAI_TIMEOUT` | 30 | Default timeout in seconds (plan generation uses 180s) |

### Retry Policy

All methods decorated with `@openai_retry` automatically retry on:
- `APIError` - Server-side errors
- `APIConnectionError` - Network issues
- `RateLimitError` - Rate limit exceeded
- `APITimeoutError` - Request timeout

Retry config: 3 attempts, exponential backoff (2s min, 30s max).

### Safety

All system prompts include `ETHICAL_PREAMBLE` which enforces:
- Identity lock (cannot be jailbroken or role-played)
- Content restrictions (violence, sexual, illegal, self-harm)
- Anti-manipulation (hypothetical/fictional bypass attempts)
- Task quality (realistic durations, no hallucinated resources)

### Plan Generation Architecture

```
Dream Duration <= 6 months:
  1 API call -> Full plan (up to 16,384 output tokens)

Dream Duration > 6 months:
  Split into 6-month chunks:
  Chunk 1 (months 1-6)  -> 16,384 tokens -> includes analysis + tips
  Chunk 2 (months 7-12) -> 16,384 tokens -> uses chunk 1 summary for continuity
  Chunk 3 (months 13-18)-> 16,384 tokens -> uses chunks 1-2 summary
  ...
  Last chunk            -> 16,384 tokens -> includes potential_obstacles

  All chunks merged into single plan response
```

### Calibration Architecture

```
Round 1: Generate 7 questions across 8 areas (experience, timeline,
         resources, motivation, constraints, specifics, lifestyle, preferences)
         -> Confidence score 0.0-1.0

Round 2: Analyze answers, generate follow-up questions for weak areas
         -> Updated confidence score

Round 3+: Continue until confidence >= 0.95 or 25 questions reached

Final:   Generate calibration summary (profile + recommendations)
         -> Used as context for plan generation
```

### Cost Documentation

For detailed cost analysis and scaling projections, see:
- [`docs/AI_COST_ANALYSIS.md`](../docs/AI_COST_ANALYSIS.md) - Per-feature cost breakdown
- [`docs/SCALING_PROJECTIONS.md`](../docs/SCALING_PROJECTIONS.md) - Cost at scale with revenue analysis
