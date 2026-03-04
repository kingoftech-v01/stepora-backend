# Integrations — TODO

Feature ideas and improvements for external service integrations (OpenAI, Google Calendar, Agora).

---

## OpenAI

- [ ] **GPT-4o migration** — Upgrade from GPT-4 to GPT-4o for faster responses and lower cost (same quality)
- [ ] **Streaming responses via SSE** — Add Server-Sent Events endpoint as alternative to WebSocket for AI chat (simpler, works through CDNs)
- [ ] **Function calling** — Use GPT-4 function calling to let AI directly create tasks, update goals, schedule events, and set reminders
- [ ] **Structured outputs** — Use JSON mode / structured outputs for all AI-generated content (plans, calibration questions, micro-starts) to eliminate parsing failures
- [ ] **Embedding-based memory** — Store conversation embeddings in pgvector for semantic search across past conversations
- [ ] **Fine-tuned model** — Fine-tune a GPT-3.5 model on DreamPlanner conversations for faster, cheaper, more consistent coaching
- [ ] **Cost tracking dashboard** — Per-user and per-conversation OpenAI cost tracking with monthly budget alerts
- [ ] **Fallback model** — Automatic fallback to GPT-3.5 when GPT-4 rate limits are hit or latency exceeds threshold
- [ ] **DALL-E 3 style presets** — Predefined art styles for vision board generation (watercolor, minimalist, photorealistic, etc.)
- [ ] **Whisper language detection** — Auto-detect voice message language and set transcription accordingly

## Google Calendar

- [ ] **Real-time sync** — Use Google Calendar push notifications (webhook) instead of polling for instant bidirectional sync
- [ ] **Multi-calendar support** — Let users choose which Google calendars to sync (work, personal, etc.)
- [ ] **Calendar conflict resolution** — Smart conflict detection and resolution when DreamPlanner events overlap with Google Calendar events
- [ ] **Outlook/Office 365 integration** — Add Microsoft Graph API integration for Outlook calendar sync
- [ ] **Apple Calendar integration** — CalDAV-based sync for Apple Calendar users

## Agora

- [ ] **RTM v2 migration** — Upgrade from legacy RTM v1.x to RTM v2 for better performance and features
- [ ] **Screen sharing** — Add screen sharing support for circle video calls
- [ ] **Recording** — Enable cloud recording for calls (useful for coaching sessions)
- [ ] **Call quality monitoring** — Track call quality metrics (latency, packet loss, jitter) and surface to users
- [ ] **Breakout rooms** — Split circle calls into smaller groups for focused discussions

## New Integrations

- [ ] **Spotify integration** — Focus music/ambient playlists linked to task sessions
- [ ] **Notion/Todoist import** — Import existing goals and tasks from popular productivity tools
- [ ] **Slack notifications** — Send dream milestones and buddy messages to Slack channels
- [ ] **Fitbit/Apple Health** — Sync health-related dream progress with fitness trackers
- [ ] **GitHub integration** — Track coding goals via GitHub commit activity
