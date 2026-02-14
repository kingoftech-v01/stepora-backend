import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../core/theme/app_theme.dart';
import '../../providers/auth_provider.dart';
import '../../providers/dreams_provider.dart';
import '../../widgets/dream_card.dart';
import '../../widgets/glass_container.dart';
import '../../widgets/glass_app_bar.dart';
import '../../widgets/animated_counter.dart';
import '../../widgets/animated_list_item.dart';
import '../../widgets/loading_shimmer.dart';

class HomeScreen extends ConsumerStatefulWidget {
  const HomeScreen({super.key});

  @override
  ConsumerState<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends ConsumerState<HomeScreen> {
  double _scrollOffset = 0;

  @override
  void initState() {
    super.initState();
    Future.microtask(() {
      ref.read(dreamsProvider.notifier).fetchDreams();
    });
  }

  @override
  Widget build(BuildContext context) {
    final authState = ref.watch(authProvider);
    final dreamsState = ref.watch(dreamsProvider);
    final user = authState.user;
    final isDark = Theme.of(context).brightness == Brightness.dark;

    return Scaffold(
      backgroundColor: Colors.transparent,
      extendBodyBehindAppBar: true,
      appBar: GlassAppBar(
        title: 'DreamPlanner',
        automaticallyImplyLeading: false,
        actions: [
          IconButton(
            icon: Icon(Icons.notifications_outlined,
                color: isDark ? Colors.white : const Color(0xFF1E1B4B)),
            onPressed: () => context.push('/notifications'),
          ),
        ],
      ),
      body: NotificationListener<ScrollNotification>(
        onNotification: (notification) {
          setState(() => _scrollOffset = notification.metrics.pixels);
          return false;
        },
        child: RefreshIndicator(
          onRefresh: () async {
            await ref.read(dreamsProvider.notifier).fetchDreams();
            await ref.read(authProvider.notifier).refreshUser();
          },
          child: ListView(
            padding: EdgeInsets.fromLTRB(16, MediaQuery.of(context).padding.top + kToolbarHeight + 8, 16, 120),
            children: [
              // Welcome card with parallax
              if (user != null)
                Transform.translate(
                  offset: Offset(0, -_scrollOffset * 0.3),
                  child: _buildWelcomeCard(context, user, isDark),
                ),
              const SizedBox(height: 24),

              // Quick Actions
              _buildQuickActions(context, isDark),
              const SizedBox(height: 28),

              // Dreams header
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Text(
                    'Your Dreams',
                    style: TextStyle(
                      fontSize: 20,
                      fontWeight: FontWeight.bold,
                      color: isDark ? Colors.white : const Color(0xFF1E1B4B),
                    ),
                  ),
                  GestureDetector(
                    onTap: () => context.push('/dreams/create'),
                    child: Container(
                      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                      decoration: BoxDecoration(
                        color: AppTheme.primaryPurple.withValues(alpha: 0.15),
                        borderRadius: BorderRadius.circular(20),
                        border: Border.all(
                          color: AppTheme.primaryPurple.withValues(alpha: 0.3),
                        ),
                      ),
                      child: Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Icon(Icons.add, size: 16, color: AppTheme.primaryPurple),
                          const SizedBox(width: 4),
                          Text(
                            'New Dream',
                            style: TextStyle(
                              color: AppTheme.primaryPurple,
                              fontWeight: FontWeight.w600,
                              fontSize: 13,
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                ],
              ).animate().fadeIn(duration: 400.ms, delay: 400.ms),
              const SizedBox(height: 12),

              // Dreams list
              if (dreamsState.isLoading)
                const LoadingShimmer()
              else if (dreamsState.dreams.isEmpty)
                _buildEmptyState(context, isDark)
              else
                ...dreamsState.dreams.asMap().entries.map((entry) =>
                    AnimatedListItem(
                      index: entry.key,
                      child: DreamCard(
                        dream: entry.value,
                        onTap: () => context.push('/dreams/${entry.value.id}'),
                      ),
                    )),
            ],
          ),
        ),
      ),
      floatingActionButton: Container(
        decoration: BoxDecoration(
          gradient: const LinearGradient(
            colors: [AppTheme.primaryPurple, AppTheme.primaryDark],
          ),
          borderRadius: BorderRadius.circular(16),
          boxShadow: [
            BoxShadow(
              color: AppTheme.primaryPurple.withValues(alpha: 0.4),
              blurRadius: 12,
              offset: const Offset(0, 4),
            ),
          ],
        ),
        child: FloatingActionButton.extended(
          onPressed: () => context.push('/dreams/create'),
          backgroundColor: Colors.transparent,
          foregroundColor: Colors.white,
          elevation: 0,
          icon: const Icon(Icons.add),
          label: const Text('New Dream'),
        ),
      ),
    );
  }

  Widget _buildWelcomeCard(BuildContext context, dynamic user, bool isDark) {
    return GlassContainer(
      padding: const EdgeInsets.all(20),
      opacity: isDark ? 0.12 : 0.25,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                width: 48,
                height: 48,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  gradient: LinearGradient(
                    colors: [
                      AppTheme.primaryPurple.withValues(alpha: 0.3),
                      AppTheme.primaryDark.withValues(alpha: 0.3),
                    ],
                  ),
                  border: Border.all(
                    color: AppTheme.primaryPurple.withValues(alpha: 0.5),
                    width: 2,
                  ),
                ),
                child: Center(
                  child: Text(
                    (user.displayName.isNotEmpty
                            ? user.displayName[0]
                            : user.email[0])
                        .toUpperCase(),
                    style: TextStyle(
                      fontSize: 20,
                      fontWeight: FontWeight.bold,
                      color: isDark ? Colors.white : AppTheme.primaryPurple,
                    ),
                  ),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Welcome back!',
                      style: TextStyle(
                        fontSize: 13,
                        color: isDark ? Colors.white54 : Colors.grey[600],
                      ),
                    ),
                    Text(
                      user.displayName.isNotEmpty ? user.displayName : user.email,
                      style: TextStyle(
                        fontSize: 18,
                        fontWeight: FontWeight.bold,
                        color: isDark ? Colors.white : const Color(0xFF1E1B4B),
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 20),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceAround,
            children: [
              _buildStat(Icons.star, user.level, 'Level', isDark),
              _buildStatDivider(isDark),
              _buildStat(Icons.bolt, user.xp, 'XP', isDark),
              _buildStatDivider(isDark),
              _buildStat(Icons.local_fire_department, user.streakDays, 'Streak', isDark),
            ],
          ),
        ],
      ),
    ).animate().fadeIn(duration: 500.ms).slideY(begin: 0.1, end: 0);
  }

  Widget _buildStat(IconData icon, int value, String label, bool isDark) {
    return Column(
      children: [
        Icon(icon, color: AppTheme.accent, size: 26),
        const SizedBox(height: 6),
        AnimatedCounter(
          value: value,
          style: TextStyle(
            fontSize: 18,
            fontWeight: FontWeight.bold,
            color: isDark ? Colors.white : const Color(0xFF1E1B4B),
          ),
        ),
        Text(
          label,
          style: TextStyle(
            fontSize: 11,
            color: isDark ? Colors.white38 : Colors.grey[700],
          ),
        ),
      ],
    );
  }

  Widget _buildStatDivider(bool isDark) {
    return Container(
      width: 1,
      height: 40,
      color: isDark ? Colors.white12 : Colors.grey[600],
    );
  }

  Widget _buildQuickActions(BuildContext context, bool isDark) {
    final actions = [
      _QuickAction(Icons.chat_bubble_outline, 'AI Coach', AppTheme.primaryPurple, () => context.push('/chat/new')),
      _QuickAction(Icons.forum_outlined, 'Conversations', Colors.teal, () => context.push('/conversations')),
      _QuickAction(Icons.emoji_events_outlined, 'Leaderboard', AppTheme.accent, () => context.push('/leaderboard')),
      _QuickAction(Icons.store_outlined, 'Store', AppTheme.success, () => context.push('/store')),
    ];

    return Column(
      children: [
        Row(
          children: [
            Expanded(child: _buildQuickActionCard(actions[0], isDark, 0)),
            const SizedBox(width: 12),
            Expanded(child: _buildQuickActionCard(actions[1], isDark, 1)),
          ],
        ),
        const SizedBox(height: 12),
        Row(
          children: [
            Expanded(child: _buildQuickActionCard(actions[2], isDark, 2)),
            const SizedBox(width: 12),
            Expanded(child: _buildQuickActionCard(actions[3], isDark, 3)),
          ],
        ),
      ],
    );
  }

  Widget _buildQuickActionCard(_QuickAction action, bool isDark, int index) {
    return AnimatedListItem(
      index: index,
      delay: const Duration(milliseconds: 80),
      child: GestureDetector(
        onTap: action.onTap,
        child: GlassContainer(
          padding: const EdgeInsets.symmetric(vertical: 18, horizontal: 8),
          opacity: isDark ? 0.1 : 0.2,
          child: Column(
            children: [
              Container(
                padding: const EdgeInsets.all(10),
                decoration: BoxDecoration(
                  color: action.color.withValues(alpha: 0.15),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Icon(action.icon, color: action.color, size: 26),
              ),
              const SizedBox(height: 10),
              Text(
                action.label,
                style: TextStyle(
                  fontWeight: FontWeight.w600,
                  fontSize: 13,
                  color: isDark ? Colors.white : const Color(0xFF1E1B4B),
                ),
                textAlign: TextAlign.center,
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildEmptyState(BuildContext context, bool isDark) {
    return GlassContainer(
      padding: const EdgeInsets.symmetric(vertical: 48, horizontal: 24),
      opacity: isDark ? 0.08 : 0.15,
      child: Column(
        children: [
          Icon(
            Icons.auto_awesome,
            size: 64,
            color: isDark ? Colors.white24 : Colors.grey[600],
          ),
          const SizedBox(height: 16),
          Text(
            'No dreams yet',
            style: TextStyle(
              fontSize: 18,
              fontWeight: FontWeight.w600,
              color: isDark ? Colors.white54 : Colors.grey[700],
            ),
          ),
          const SizedBox(height: 8),
          Text(
            'Create your first dream and start planning!',
            style: TextStyle(
              fontSize: 14,
              color: isDark ? Colors.white30 : Colors.grey[600],
            ),
          ),
        ],
      ),
    ).animate().fadeIn(duration: 500.ms);
  }
}

class _QuickAction {
  final IconData icon;
  final String label;
  final Color color;
  final VoidCallback onTap;
  const _QuickAction(this.icon, this.label, this.color, this.onTap);
}
