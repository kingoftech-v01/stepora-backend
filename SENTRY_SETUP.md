# Sentry Error Monitoring Setup

## Overview

Sentry has been configured across all three Stepora repositories:

1. **Backend (Django)** - `/root/stepora`
2. **Frontend (React/Vite)** - `/root/stepora-frontend`
3. **Mobile (React Native)** - `/root/stepora-mobile`

All DSN values are **placeholders** (`https://placeholder@sentry.io/0`). Replace them with real Sentry project DSNs before deploying.

---

## 1. Backend (Django)

### What was configured

- **File**: `config/settings/production.py` - Full Sentry SDK init with integrations
- **File**: `.env` - Uncommented `SENTRY_DSN`, `SENTRY_ENVIRONMENT`, `SENTRY_TRACES_SAMPLE_RATE`
- **File**: `docker-compose.yml` - Added `SENTRY_DSN`, `SENTRY_ENVIRONMENT`, `SENTRY_TRACES_SAMPLE_RATE` to web, daphne, celery, and celery-beat services
- **Package**: `sentry-sdk==1.39.1` (already in `requirements/production.txt`)

### Integrations

| Integration | Purpose |
|---|---|
| `DjangoIntegration` | Captures Django request errors, middleware exceptions, template errors |
| `CeleryIntegration` | Tracks Celery task failures, retries, and performance |
| `RedisIntegration` | Monitors Redis operations (cache, channels, broker) |

### Configuration details

- `traces_sample_rate=0.1` - 10% of requests get performance tracing
- `profiles_sample_rate=0.1` - 10% profiling (requires Sentry Profiling plan)
- `send_default_pii=False` - No personal data (emails, IPs) sent to Sentry
- `environment` - Read from `SENTRY_ENVIRONMENT` env var (defaults to "production")
- `before_send` filter - Ignores HTTP 404 errors and `/health/` endpoint errors

### Where to set the real DSN

1. **Local/VPS**: Set `SENTRY_DSN` in `/root/stepora/.env`
2. **AWS ECS**: Add `SENTRY_DSN` and `SENTRY_ENVIRONMENT` to AWS Secrets Manager (`stepora/backend-env`)
3. **Docker**: The `docker-compose.yml` reads `${SENTRY_DSN}` from `.env`

---

## 2. Frontend (React/Vite)

### What was configured

- **File**: `src/main.jsx` - Sentry.init() at top + ErrorBoundary wrapping the app
- **File**: `.env` - Added `VITE_SENTRY_DSN` (empty for dev) and `VITE_SENTRY_ENV=development`
- **File**: `.env.production` - Added `VITE_SENTRY_DSN=https://placeholder@sentry.io/0` and `VITE_SENTRY_ENV=production`
- **File**: `vite.config.js` - Enabled `sourcemap: true` in build config, added comments for source map upload plugin
- **Package**: `@sentry/react` installed

### Integrations

| Integration | Purpose |
|---|---|
| `browserTracingIntegration` | Performance monitoring for page loads and navigation |
| `replayIntegration` | Session replay for debugging (records DOM, clicks, console) |
| `ErrorBoundary` | Catches React render errors and reports to Sentry |

### Configuration details

- `tracesSampleRate: 0.1` - 10% of page loads get performance tracing
- `replaysSessionSampleRate: 0.05` - 5% of sessions get replay recording
- `replaysOnErrorSampleRate: 1.0` - 100% of sessions with errors get replay
- `enabled: !!import.meta.env.VITE_SENTRY_DSN` - Disabled when no DSN is set (dev mode)

### Source maps upload (not yet active)

To enable source maps for readable stack traces in Sentry:

```bash
npm install @sentry/vite-plugin --save-dev
```

Then in `vite.config.js`, uncomment and configure the plugin:

```javascript
import { sentryVitePlugin } from '@sentry/vite-plugin';

// Add to plugins array:
sentryVitePlugin({
  org: "your-sentry-org",
  project: "stepora-frontend",
  authToken: process.env.SENTRY_AUTH_TOKEN,
})
```

Set `SENTRY_AUTH_TOKEN` in CI/CD (GitHub Secrets) for automated uploads.

### Where to set the real DSN

1. **Local dev**: Leave `VITE_SENTRY_DSN` empty in `.env` (Sentry disabled)
2. **Production build**: Set `VITE_SENTRY_DSN` in `.env.production`
3. **CI/CD**: Add `VITE_SENTRY_DSN` to the build step in `deploy-frontend.yml`

---

## 3. Mobile (React Native)

### What was configured

- **File**: `index.js` - `Sentry.init()` at the top level before app registration
- **File**: `src/App.jsx` - App component wrapped with `Sentry.wrap()` for automatic error boundary and performance
- **Package**: `@sentry/react-native` installed

### Configuration details

- `tracesSampleRate: 0.1` - 10% of app sessions get performance tracing
- `enabled: !__DEV__` - Only enabled in release builds (not during development)
- `environment` - Automatically set to "development" or "production"

### Native setup required

After replacing the placeholder DSN, you need to run the Sentry wizard for native crash reporting:

```bash
cd /root/stepora-mobile
npx @sentry/wizard@latest -i reactNative
```

This will:
- Add Sentry to `android/app/build.gradle` for native symbolication
- Add Sentry to `ios/Podfile` (if applicable)
- Create `sentry.properties` with org/project/auth token

### Where to set the real DSN

Replace the placeholder DSN directly in `index.js`, or use `react-native-config` to load from `.env`:

```bash
# .env
SENTRY_DSN=https://your-real-dsn@sentry.io/123
```

---

## Testing

### Verify backend Sentry works

```python
# In Django shell (manage.py shell)
import sentry_sdk
sentry_sdk.capture_message("Test from Stepora backend")
```

Or trigger a test error:

```python
# In any Django view temporarily:
raise Exception("Sentry test error from backend")
```

### Verify frontend Sentry works

Open browser console on the deployed app and run:

```javascript
// This will appear in your Sentry dashboard
throw new Error("Sentry test error from frontend");
```

### Verify mobile Sentry works

Add temporarily in any screen component:

```javascript
import * as Sentry from '@sentry/react-native';
Sentry.captureMessage("Test from Stepora mobile");
```

---

## Environment Variables Summary

### Backend (.env / AWS Secrets Manager)

| Variable | Default | Description |
|---|---|---|
| `SENTRY_DSN` | (none) | Sentry project DSN - Sentry is disabled if unset |
| `SENTRY_ENVIRONMENT` | `production` | Environment tag in Sentry (production/staging/development) |
| `SENTRY_TRACES_SAMPLE_RATE` | `0.1` | Performance tracing sample rate (0.0 to 1.0) |
| `SENTRY_PROFILES_SAMPLE_RATE` | `0.1` | Profiling sample rate (requires Sentry Profiling plan) |

### Frontend (.env.production / CI)

| Variable | Default | Description |
|---|---|---|
| `VITE_SENTRY_DSN` | (none) | Sentry project DSN - Sentry is disabled if unset |
| `VITE_SENTRY_ENV` | `production` | Environment tag in Sentry |

### Mobile (hardcoded in index.js / react-native-config)

| Variable | Default | Description |
|---|---|---|
| DSN in `index.js` | placeholder | Replace with real DSN |

---

## Sentry Projects to Create

Create three separate projects in Sentry:

1. **stepora-backend** (Platform: Django)
2. **stepora-frontend** (Platform: React / Browser JavaScript)
3. **stepora-mobile** (Platform: React Native)

Each project will have its own DSN. Use the DSN from each project to replace the placeholder values.
