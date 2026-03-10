# Stepora - Dream Planning Application

## Project Vision

**Stepora** is a backend web application (Django API) that uses ChatGPT artificial intelligence to help users transform their dreams into concrete and achievable goals.

## Problem Solved

Many people have dreams and goals but lack:
- Structure to break them down into actionable steps
- Realistic time planning
- Regular tracking and motivation
- Adaptation to their existing schedule

## Solution

A personal AI assistant that:
1. **Listens** - Understands your dreams and goals in detail
2. **Analyzes** - Evaluates feasibility and required resources
3. **Plans** - Creates a personalized schedule with clear milestones
4. **Supports** - Sends reminders and notifications at the right time
5. **Adapts** - Adjusts the plan according to your constraints (work, breaks, personal life)

## Main Features

### 1. Intelligent Conversation with ChatGPT
- Natural discussion to define dreams
- Automatic clarification questions
- Extraction of goals and desired deadlines

### 2. Smart Calendar
- Automatic schedule generation
- Integration of existing work hours
- Respect for break times
- Day/week/month views

### 3. Notification System
- Reminders for each step
- Motivational notifications
- Progress alerts
- Smart "Do Not Disturb" mode

### 4. Progress Tracking
- Progress visualization
- Statistics and metrics
- Achievement celebrations

### 5. Community & Social
- **Dream Posts** - Share dream progress publicly with images, GoFundMe links, and typed encouragements
- **Buddy Chat & Calls** - Real-time WebSocket messaging between accountability buddies with FCM push notifications
- **Circle Chat & Calls** - Real-time group chat within circles plus Agora-powered voice/video group calls
- **Social Feed** - Aggregated feed from followed users and public posts with block filtering

## Target Audience

- Professionals looking to develop new skills
- Students preparing for exams or projects
- Entrepreneurs launching their business
- Anyone with a personal goal (fitness, travel, learning)

## Business Model

- **Freemium**:
  - Free: 3 active goals, basic notifications
  - Premium ($19.99/month): Unlimited goals, advanced notifications, calendar export
  - Pro ($29.99/month): Advanced AI coaching, calendar integrations, detailed analytics

## Tech Stack

- **Framework**: Django 5.0.1 + Django REST Framework
- **Language**: Python 3.11
- **Database**: PostgreSQL + Redis
- **AI**: OpenAI ChatGPT API (GPT-4)
- **WebSocket**: Django Channels (Daphne)
- **Asynchronous Tasks**: Celery
- **Notifications**: Celery + WebSocket
- **Auth**: Custom `core.auth` package + SimpleJWT (JWT authentication)

## Estimated Timeline

| Phase | Duration | Deliverables |
|-------|----------|--------------|
| Phase 1 - MVP | 8 weeks | Basic API with conversation and calendar |
| Phase 2 - Notifications | 4 weeks | Complete notification system |
| Phase 3 - Polish | 4 weeks | Finalized API, tests, optimizations |
| Phase 4 - Launch | 2 weeks | Production deployment, marketing |

**Total: ~18 weeks for v1.0**
