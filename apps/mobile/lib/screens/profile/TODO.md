# Profile Screens - TODO

## Current Status
- profile_screen.dart: Functional (read-only profile display with gamification)
- settings_screen.dart: Fully implemented with all handlers connected

## Placeholders to Fix

### settings_screen.dart
- [x] **Edit Profile** (onTap empty): Navigate to EditProfileScreen with avatar upload
- [x] **Email** (onTap empty): Show read-only email info or change dialog
- [x] **Change Password** (onTap empty): Navigate to ChangePasswordScreen
- [x] **Language picker** (onTap empty): Show language selection bottom sheet with 15 languages, persist via locale_provider
- [x] **Timezone picker** (onTap empty): Show timezone picker dialog, update via preferences API
- [x] **Terms of Service** (onTap empty): Open URL in browser via url_launcher
- [x] **Privacy Policy** (onTap empty): Open URL in browser via url_launcher
- [x] **App Version/About** (onTap empty): Show Flutter `showAboutDialog()` with version info

## Missing Screens
- [x] EditProfileScreen: Form with display_name, timezone, avatar upload; call `PUT /api/users/me/`
- [x] ChangePasswordScreen: Form with old_password, new_password, confirm; call `POST /api/auth/password/change/`

## Small Improvements
- [x] Add profile photo upload (avatar_url field exists in backend)
- [x] Add "Delete Account" option with multi-step confirmation dialog
- [x] Add "Dark Mode" toggle (theme_provider + settings)
- [x] Show subscription end date in profile header
