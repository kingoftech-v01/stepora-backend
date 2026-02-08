# Auth Screens - TODO

## Current Status
- login_screen.dart: Fully functional (email/password login)
- register_screen.dart: Fully functional (email/password registration)
- forgot_password_screen.dart: Fully functional (email reset request)

## Missing Screens
- [x] **Change Password screen**: Form with old_password, new_password, confirm_password; call `POST /api/auth/password/change/`

## Small Improvements
- [x] Add "Remember me" checkbox on login (persist token longer)
- [x] Add social login buttons (Google Sign-In + Apple Sign-In fully implemented)
- [x] Add password strength indicator on register screen
- [x] Add email format validation feedback on typing
