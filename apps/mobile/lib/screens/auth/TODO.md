# Auth Screens - TODO

## Current Status
- login_screen.dart: Fully functional (email/password login)
- register_screen.dart: Fully functional (email/password registration)
- forgot_password_screen.dart: Fully functional (email reset request)

## Missing Screens
- [ ] **Change Password screen**: Form with old_password, new_password, confirm_password; call `POST /api/auth/password/change/`

## Small Improvements
- [ ] Add "Remember me" checkbox on login (persist token longer)
- [ ] Add social login buttons placeholder (Google, Apple) for future OAuth
- [ ] Add password strength indicator on register screen
- [ ] Add email format validation feedback on typing
