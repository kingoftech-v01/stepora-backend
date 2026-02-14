import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../providers/auth_provider.dart';
import '../widgets/glass_bottom_nav.dart';
import '../widgets/gradient_background.dart';
import '../core/theme/app_theme.dart';
import '../core/theme/page_transitions.dart';
import '../screens/auth/login_screen.dart';
import '../screens/auth/register_screen.dart';
import '../screens/auth/forgot_password_screen.dart';
import '../screens/home/home_screen.dart';
import '../screens/dreams/dream_detail_screen.dart';
import '../screens/dreams/create_dream_screen.dart';
import '../screens/dreams/calibration_screen.dart';
import '../screens/chat/chat_screen.dart';
import '../screens/calendar/calendar_screen.dart';
import '../screens/social/social_screen.dart';
import '../screens/social/circles_screen.dart';
import '../screens/social/circle_detail_screen.dart';
import '../screens/social/dream_buddy_screen.dart';
import '../screens/social/leaderboard_screen.dart';
import '../screens/profile/profile_screen.dart';
import '../screens/profile/settings_screen.dart';
import '../screens/notifications/notifications_screen.dart';
import '../screens/store/store_screen.dart';
import '../screens/subscription/subscription_screen.dart';
import '../screens/vision_board/vision_board_screen.dart';
import '../screens/micro_start/micro_start_screen.dart';
import '../screens/profile/edit_profile_screen.dart';
import '../screens/auth/change_password_screen.dart';
import '../screens/dreams/edit_dream_screen.dart';
import '../screens/chat/conversation_list_screen.dart';
import '../screens/social/friends_screen.dart';
import '../screens/social/user_search_screen.dart';
import '../screens/social/friend_requests_screen.dart';
import '../screens/chat/buddy_chat_screen.dart';
import '../screens/dreams/dream_templates_screen.dart';
import '../screens/profile/google_calendar_screen.dart';

final routerProvider = Provider<GoRouter>((ref) {
  final authState = ref.watch(authProvider);

  return GoRouter(
    initialLocation: '/login',
    redirect: (context, state) {
      final isLoggedIn = authState.token != null;
      final isAuthRoute = state.matchedLocation == '/login' ||
          state.matchedLocation == '/register' ||
          state.matchedLocation == '/forgot-password';

      if (!isLoggedIn && !isAuthRoute) return '/login';
      if (isLoggedIn && isAuthRoute) return '/';
      return null;
    },
    routes: [
      // Auth routes (no glass nav)
      GoRoute(
        path: '/login',
        pageBuilder: (context, state) =>
            glassPageBuilder(context, state, const LoginScreen()),
      ),
      GoRoute(
        path: '/register',
        pageBuilder: (context, state) =>
            glassPageBuilder(context, state, const RegisterScreen()),
      ),
      GoRoute(
        path: '/forgot-password',
        pageBuilder: (context, state) =>
            glassPageBuilder(context, state, const ForgotPasswordScreen()),
      ),
      // Main shell with glass bottom nav
      ShellRoute(
        builder: (context, state, child) => ScaffoldWithNav(child: child),
        routes: [
          GoRoute(
            path: '/',
            pageBuilder: (context, state) =>
                glassPageBuilder(context, state, const HomeScreen()),
          ),
          GoRoute(
            path: '/calendar',
            pageBuilder: (context, state) =>
                glassPageBuilder(context, state, const CalendarScreen()),
          ),
          GoRoute(
            path: '/social',
            pageBuilder: (context, state) =>
                glassPageBuilder(context, state, const SocialScreen()),
          ),
          GoRoute(
            path: '/profile',
            pageBuilder: (context, state) =>
                glassPageBuilder(context, state, const ProfileScreen()),
          ),
        ],
      ),
      // Dream routes
      GoRoute(
        path: '/dreams/create',
        pageBuilder: (context, state) =>
            glassPageBuilder(context, state, const CreateDreamScreen()),
      ),
      GoRoute(
        path: '/dreams/:id',
        pageBuilder: (context, state) => glassPageBuilder(
            context, state, DreamDetailScreen(dreamId: state.pathParameters['id']!)),
      ),
      GoRoute(
        path: '/dreams/:id/calibration',
        pageBuilder: (context, state) => glassPageBuilder(
            context, state, CalibrationScreen(dreamId: state.pathParameters['id']!)),
      ),
      GoRoute(
        path: '/dreams/:id/edit',
        pageBuilder: (context, state) => glassPageBuilder(
            context, state, EditDreamScreen(dreamId: state.pathParameters['id']!)),
      ),
      GoRoute(
        path: '/dream-templates',
        pageBuilder: (context, state) =>
            glassPageBuilder(context, state, const DreamTemplatesScreen()),
      ),
      // Chat routes
      GoRoute(
        path: '/chat/:id',
        pageBuilder: (context, state) => glassPageBuilder(
            context, state, ChatScreen(conversationId: state.pathParameters['id']!)),
      ),
      GoRoute(
        path: '/conversations',
        pageBuilder: (context, state) =>
            glassPageBuilder(context, state, const ConversationListScreen()),
      ),
      GoRoute(
        path: '/buddy-chat/:id',
        pageBuilder: (context, state) => glassPageBuilder(
            context, state, BuddyChatScreen(conversationId: state.pathParameters['id']!)),
      ),
      // Social routes
      GoRoute(
        path: '/circles',
        pageBuilder: (context, state) =>
            glassPageBuilder(context, state, const CirclesScreen()),
      ),
      GoRoute(
        path: '/circles/:id',
        pageBuilder: (context, state) => glassPageBuilder(
            context, state, CircleDetailScreen(circleId: state.pathParameters['id']!)),
      ),
      GoRoute(
        path: '/buddy',
        pageBuilder: (context, state) =>
            glassPageBuilder(context, state, const DreamBuddyScreen()),
      ),
      GoRoute(
        path: '/leaderboard',
        pageBuilder: (context, state) =>
            glassPageBuilder(context, state, const LeaderboardScreen()),
      ),
      GoRoute(
        path: '/friends',
        pageBuilder: (context, state) =>
            glassPageBuilder(context, state, const FriendsScreen()),
      ),
      GoRoute(
        path: '/social/search',
        pageBuilder: (context, state) =>
            glassPageBuilder(context, state, const UserSearchScreen()),
      ),
      GoRoute(
        path: '/social/requests',
        pageBuilder: (context, state) =>
            glassPageBuilder(context, state, const FriendRequestsScreen()),
      ),
      // Profile routes
      GoRoute(
        path: '/settings',
        pageBuilder: (context, state) =>
            glassPageBuilder(context, state, const SettingsScreen()),
      ),
      GoRoute(
        path: '/profile/edit',
        pageBuilder: (context, state) =>
            glassPageBuilder(context, state, const EditProfileScreen()),
      ),
      GoRoute(
        path: '/change-password',
        pageBuilder: (context, state) =>
            glassPageBuilder(context, state, const ChangePasswordScreen()),
      ),
      GoRoute(
        path: '/google-calendar',
        pageBuilder: (context, state) =>
            glassPageBuilder(context, state, const GoogleCalendarScreen()),
      ),
      // Other routes
      GoRoute(
        path: '/notifications',
        pageBuilder: (context, state) =>
            glassPageBuilder(context, state, const NotificationsScreen()),
      ),
      GoRoute(
        path: '/store',
        pageBuilder: (context, state) =>
            glassPageBuilder(context, state, const StoreScreen()),
      ),
      GoRoute(
        path: '/subscription',
        pageBuilder: (context, state) =>
            glassPageBuilder(context, state, const SubscriptionScreen()),
      ),
      GoRoute(
        path: '/vision-board/:id',
        pageBuilder: (context, state) => glassPageBuilder(
            context, state, VisionBoardScreen(dreamId: state.pathParameters['id']!)),
      ),
      GoRoute(
        path: '/micro-start/:id',
        pageBuilder: (context, state) => glassPageBuilder(
            context, state, MicroStartScreen(taskId: state.pathParameters['id']!)),
      ),
    ],
  );
});

class ScaffoldWithNav extends StatelessWidget {
  final Widget child;
  const ScaffoldWithNav({super.key, required this.child});

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final gradients = isDark ? AppTheme.gradientHome : AppTheme.gradientHomeLight;

    return GradientBackground(
      colors: gradients,
      child: Scaffold(
        backgroundColor: Colors.transparent,
        extendBodyBehindAppBar: true,
        body: child,
        bottomNavigationBar: GlassBottomNav(
          selectedIndex: _calculateSelectedIndex(context),
          onDestinationSelected: (index) => _onItemTapped(index, context),
        ),
      ),
    );
  }

  int _calculateSelectedIndex(BuildContext context) {
    final location = GoRouterState.of(context).matchedLocation;
    if (location == '/') return 0;
    if (location.startsWith('/calendar')) return 1;
    if (location.startsWith('/social')) return 2;
    if (location.startsWith('/profile')) return 3;
    return 0;
  }

  void _onItemTapped(int index, BuildContext context) {
    switch (index) {
      case 0:
        context.go('/');
      case 1:
        context.go('/calendar');
      case 2:
        context.go('/social');
      case 3:
        context.go('/profile');
    }
  }
}
