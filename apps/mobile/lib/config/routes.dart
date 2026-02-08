import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../providers/auth_provider.dart';
import '../screens/auth/login_screen.dart';
import '../screens/auth/register_screen.dart';
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
import '../screens/notifications/notifications_screen.dart';
import '../screens/store/store_screen.dart';
import '../screens/subscription/subscription_screen.dart';
import '../screens/vision_board/vision_board_screen.dart';
import '../screens/micro_start/micro_start_screen.dart';

final routerProvider = Provider<GoRouter>((ref) {
  final authState = ref.watch(authProvider);

  return GoRouter(
    initialLocation: '/login',
    redirect: (context, state) {
      final isLoggedIn = authState.token != null;
      final isAuthRoute = state.matchedLocation == '/login' ||
          state.matchedLocation == '/register';

      if (!isLoggedIn && !isAuthRoute) return '/login';
      if (isLoggedIn && isAuthRoute) return '/';
      return null;
    },
    routes: [
      GoRoute(
        path: '/login',
        builder: (context, state) => const LoginScreen(),
      ),
      GoRoute(
        path: '/register',
        builder: (context, state) => const RegisterScreen(),
      ),
      ShellRoute(
        builder: (context, state, child) => ScaffoldWithNav(child: child),
        routes: [
          GoRoute(
            path: '/',
            builder: (context, state) => const HomeScreen(),
          ),
          GoRoute(
            path: '/calendar',
            builder: (context, state) => const CalendarScreen(),
          ),
          GoRoute(
            path: '/social',
            builder: (context, state) => const SocialScreen(),
          ),
          GoRoute(
            path: '/profile',
            builder: (context, state) => const ProfileScreen(),
          ),
        ],
      ),
      GoRoute(
        path: '/dreams/create',
        builder: (context, state) => const CreateDreamScreen(),
      ),
      GoRoute(
        path: '/dreams/:id',
        builder: (context, state) =>
            DreamDetailScreen(dreamId: state.pathParameters['id']!),
      ),
      GoRoute(
        path: '/dreams/:id/calibration',
        builder: (context, state) =>
            CalibrationScreen(dreamId: state.pathParameters['id']!),
      ),
      GoRoute(
        path: '/chat/:id',
        builder: (context, state) =>
            ChatScreen(conversationId: state.pathParameters['id']!),
      ),
      GoRoute(
        path: '/circles',
        builder: (context, state) => const CirclesScreen(),
      ),
      GoRoute(
        path: '/circles/:id',
        builder: (context, state) =>
            CircleDetailScreen(circleId: state.pathParameters['id']!),
      ),
      GoRoute(
        path: '/buddy',
        builder: (context, state) => const DreamBuddyScreen(),
      ),
      GoRoute(
        path: '/leaderboard',
        builder: (context, state) => const LeaderboardScreen(),
      ),
      GoRoute(
        path: '/notifications',
        builder: (context, state) => const NotificationsScreen(),
      ),
      GoRoute(
        path: '/store',
        builder: (context, state) => const StoreScreen(),
      ),
      GoRoute(
        path: '/subscription',
        builder: (context, state) => const SubscriptionScreen(),
      ),
      GoRoute(
        path: '/vision-board/:id',
        builder: (context, state) =>
            VisionBoardScreen(dreamId: state.pathParameters['id']!),
      ),
      GoRoute(
        path: '/micro-start/:id',
        builder: (context, state) =>
            MicroStartScreen(taskId: state.pathParameters['id']!),
      ),
    ],
  );
});

class ScaffoldWithNav extends StatelessWidget {
  final Widget child;
  const ScaffoldWithNav({super.key, required this.child});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: child,
      bottomNavigationBar: NavigationBar(
        selectedIndex: _calculateSelectedIndex(context),
        onDestinationSelected: (index) => _onItemTapped(index, context),
        destinations: const [
          NavigationDestination(
            icon: Icon(Icons.home_outlined),
            selectedIcon: Icon(Icons.home),
            label: 'Home',
          ),
          NavigationDestination(
            icon: Icon(Icons.calendar_month_outlined),
            selectedIcon: Icon(Icons.calendar_month),
            label: 'Calendar',
          ),
          NavigationDestination(
            icon: Icon(Icons.people_outline),
            selectedIcon: Icon(Icons.people),
            label: 'Social',
          ),
          NavigationDestination(
            icon: Icon(Icons.person_outline),
            selectedIcon: Icon(Icons.person),
            label: 'Profile',
          ),
        ],
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
