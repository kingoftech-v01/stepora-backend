# Profile Screens - TODO

## Current Status
- profile_screen.dart: Functional (read-only profile display with gamification)
- settings_screen.dart: Mostly placeholder -- 8 empty onTap handlers

## Placeholders to Fix

### settings_screen.dart
- [ ] **Edit Profile** (onTap empty): Navigate to EditProfileScreen -- needs new screen
- [ ] **Email** (onTap empty): Show read-only email info or change dialog
- [ ] **Change Password** (onTap empty): Navigate to ChangePasswordScreen -- needs new screen
- [ ] **Language picker** (onTap empty): Show language selection bottom sheet with 15 languages, persist via `POST /api/users/me/update-preferences/`
- [ ] **Timezone picker** (onTap empty): Show timezone picker dialog, update via preferences API
- [ ] **Terms of Service** (onTap empty): Open URL in browser via url_launcher
- [ ] **Privacy Policy** (onTap empty): Open URL in browser via url_launcher
- [ ] **App Version/About** (onTap empty): Show Flutter `showAboutDialog()` with version info

## Missing Screens
- [ ] EditProfileScreen: Form with display_name, timezone; call `PUT /api/users/me/`
- [ ] ChangePasswordScreen: Form with old_password, new_password, confirm; call `POST /api/auth/password/change/`

## Small Improvements
- [ ] Add profile photo upload (avatar_url field exists in backend)
- [ ] Add "Delete Account" option with confirmation dialog
- [ ] Add "Dark Mode" toggle (app supports dark theme, just no switch in settings)
- [ ] Show subscription end date in profile header
