# Custom Email Display Names per Email Type

## Overview

Each outgoing email from Stepora uses a category-specific display name in the
From header so recipients can identify the purpose of the message at a glance.

## Display Name Mapping

| Category       | Display Name            | Email Types                                              |
|----------------|-------------------------|----------------------------------------------------------|
| Account        | Stepora Account         | Email verification, email change verification, data export |
| Security       | Stepora Security        | Password reset, password changed, login notification      |
| Billing        | Stepora Billing         | Payment receipt, upgrade, downgrade, cancel, reactivation |
| Notifications  | Stepora Notifications   | Social/dream notifications delivered by email             |
| Welcome        | Stepora                 | Welcome email after registration                          |

## From Header Format

```
Display Name <info@stepora.net>
```

Example: `Stepora Security <info@stepora.net>`

## Implementation

### `core/email.py` — `send_templated_email()`

Accepts an optional `from_name` parameter (default: `"Stepora"`).  The
function builds the full From header as `f"{from_name} <{DEFAULT_FROM_EMAIL}>"`.

### Callers

Every call site passes the appropriate `from_name`:

- `core/auth/tasks.py`
  - `send_verification_email` -> `"Stepora Account"`
  - `send_password_reset_email` -> `"Stepora Security"`
  - `send_welcome_email` -> `"Stepora"`
  - `send_password_changed_email` -> `"Stepora Security"`
  - `send_login_notification_email` -> `"Stepora Security"`
- `apps/users/tasks.py`
  - `send_email_change_verification` -> `"Stepora Account"`
  - `export_user_data` -> `"Stepora Account"`
- `apps/subscriptions/tasks.py`
  - All subscription emails -> `"Stepora Billing"`
- `apps/notifications/services.py`
  - `_send_email` -> `"Stepora Notifications"`

## Backward Compatibility

When `from_name` is omitted or `None`, the default display name `"Stepora"` is
used.  This ensures any new call sites that forget to pass `from_name` still
produce a valid From header.

## Testing

Tests in `core/tests/test_email.py` verify:

1. `send_templated_email` accepts and uses `from_name`.
2. Default behavior when `from_name` is omitted.
3. Correct From header format: `"Display Name <email>"`.
4. Each email task passes the expected `from_name` value.
