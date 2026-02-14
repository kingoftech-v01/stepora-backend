import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../core/theme/app_theme.dart';
import '../../providers/auth_provider.dart';
import '../../services/api_service.dart';
import '../../models/user.dart';
import '../../widgets/gradient_background.dart';
import '../../widgets/glass_container.dart';
import '../../widgets/glass_app_bar.dart';
import '../../widgets/glass_button.dart';
import '../../widgets/animated_list_item.dart';
import '../../widgets/animated_counter.dart';
import '../../widgets/loading_shimmer.dart';

class ProfileScreen extends ConsumerStatefulWidget {
  const ProfileScreen({super.key});

  @override
  ConsumerState<ProfileScreen> createState() => _ProfileScreenState();
}

class _ProfileScreenState extends ConsumerState<ProfileScreen> {
  GamificationProfile? _gamification;

  @override
  void initState() {
    super.initState();
    _loadGamification();
  }

  Future<void> _loadGamification() async {
    try {
      final api = ref.read(apiServiceProvider);
      final response = await api.get('/users/me/gamification/');
      setState(() => _gamification = GamificationProfile.fromJson(response.data));
    } catch (_) {}
  }

  @override
  Widget build(BuildContext context) {
    final user = ref.watch(authProvider).user;
    final isDark = Theme.of(context).brightness == Brightness.dark;

    return GradientBackground(
      colors: isDark ? AppTheme.gradientProfile : AppTheme.gradientProfileLight,
      child: Scaffold(
        backgroundColor: Colors.transparent,
        extendBodyBehindAppBar: true,
        appBar: GlassAppBar(
          title: 'Profile',
          actions: [
            IconButton(
              icon: Icon(Icons.settings_outlined, color: isDark ? Colors.white70 : const Color(0xFF1E1B4B)),
              onPressed: () => context.push('/settings'),
            ),
          ],
        ),
        body: user == null
            ? const Center(child: LoadingShimmer())
            : RefreshIndicator(
                onRefresh: () async {
                  await ref.read(authProvider.notifier).refreshUser();
                  await _loadGamification();
                },
                child: ListView(
                  padding: EdgeInsets.fromLTRB(16, MediaQuery.of(context).padding.top + kToolbarHeight + 8, 16, 32),
                  children: [
                    // Profile Header
                    GlassContainer(
                      padding: const EdgeInsets.all(24),
                      opacity: isDark ? 0.15 : 0.3,
                      child: Column(
                        children: [
                          // Avatar with glow ring
                          Container(
                            padding: const EdgeInsets.all(4),
                            decoration: BoxDecoration(
                              shape: BoxShape.circle,
                              gradient: const LinearGradient(
                                colors: [AppTheme.primaryPurple, Color(0xFF8B5CF6), AppTheme.accent],
                              ),
                              boxShadow: [
                                BoxShadow(
                                  color: AppTheme.primaryPurple.withValues(alpha: 0.4),
                                  blurRadius: 20,
                                  spreadRadius: 2,
                                ),
                              ],
                            ),
                            child: CircleAvatar(
                              radius: 44,
                              backgroundColor: isDark ? const Color(0xFF1E1B4B) : Colors.white,
                              backgroundImage: user.avatarUrl != null ? NetworkImage(user.avatarUrl!) : null,
                              child: user.avatarUrl == null
                                  ? Text(
                                      (user.displayName.isNotEmpty ? user.displayName[0] : user.email[0]).toUpperCase(),
                                      style: TextStyle(fontSize: 32, fontWeight: FontWeight.bold, color: AppTheme.primaryPurple),
                                    )
                                  : null,
                            ),
                          ).animate().fadeIn(duration: 500.ms).scale(begin: const Offset(0.8, 0.8), end: const Offset(1, 1)),
                          const SizedBox(height: 16),
                          Row(
                            mainAxisAlignment: MainAxisAlignment.center,
                            children: [
                              Text(
                                user.displayName.isNotEmpty ? user.displayName : user.email,
                                style: TextStyle(
                                  fontSize: 20,
                                  fontWeight: FontWeight.bold,
                                  color: isDark ? Colors.white : const Color(0xFF1E1B4B),
                                ),
                              ),
                              if (user.isPremium) ...[
                                const SizedBox(width: 8),
                                Container(
                                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                                  decoration: BoxDecoration(
                                    gradient: LinearGradient(colors: [AppTheme.accent.withValues(alpha: 0.2), AppTheme.accent.withValues(alpha: 0.1)]),
                                    borderRadius: BorderRadius.circular(12),
                                    border: Border.all(color: AppTheme.accent.withValues(alpha: 0.3)),
                                  ),
                                  child: Row(
                                    mainAxisSize: MainAxisSize.min,
                                    children: [
                                      Icon(Icons.star, color: AppTheme.accent, size: 14),
                                      const SizedBox(width: 2),
                                      Text(
                                        user.subscription.toUpperCase(),
                                        style: TextStyle(color: AppTheme.accent, fontWeight: FontWeight.bold, fontSize: 11),
                                      ),
                                    ],
                                  ),
                                ).animate(onPlay: (c) => c.repeat(reverse: true)).shimmer(duration: 2000.ms, color: AppTheme.accent.withValues(alpha: 0.3)),
                              ],
                            ],
                          ).animate().fadeIn(duration: 500.ms, delay: 100.ms),
                          const SizedBox(height: 4),
                          Text(user.email, style: TextStyle(color: isDark ? Colors.white54 : Colors.grey[600]))
                            .animate().fadeIn(duration: 500.ms, delay: 150.ms),
                          if (user.isPremium && user.subscriptionEnds != null) ...[
                            const SizedBox(height: 4),
                            Text(
                              'Renews ${_formatDate(user.subscriptionEnds!)}',
                              style: TextStyle(color: isDark ? Colors.white38 : Colors.grey[700], fontSize: 12),
                            ).animate().fadeIn(duration: 500.ms, delay: 200.ms),
                          ],
                        ],
                      ),
                    ).animate().fadeIn(duration: 400.ms),
                    const SizedBox(height: 16),

                    // Stats Row
                    Row(
                      children: [
                        Expanded(
                          child: _GlassStatCard(
                            label: 'Level',
                            value: user.level,
                            icon: Icons.star,
                            color: AppTheme.primaryPurple,
                            isDark: isDark,
                            index: 0,
                          ),
                        ),
                        const SizedBox(width: 8),
                        Expanded(
                          child: _GlassStatCard(
                            label: 'XP',
                            value: user.xp,
                            icon: Icons.bolt,
                            color: AppTheme.accent,
                            isDark: isDark,
                            index: 1,
                          ),
                        ),
                        const SizedBox(width: 8),
                        Expanded(
                          child: _GlassStatCard(
                            label: 'Streak',
                            value: user.streakDays,
                            icon: Icons.local_fire_department,
                            color: AppTheme.error,
                            isDark: isDark,
                            index: 2,
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 16),

                    // Gamification / Skill Levels
                    if (_gamification != null) ...[
                      Text('Skill Levels', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16, color: isDark ? Colors.white : const Color(0xFF1E1B4B)))
                        .animate().fadeIn(duration: 400.ms),
                      const SizedBox(height: 10),
                      GlassContainer(
                        padding: const EdgeInsets.all(16),
                        opacity: isDark ? 0.12 : 0.25,
                        child: Column(
                          children: [
                            _GlassSkillBar(label: 'Health', level: _gamification!.healthLevel, xp: _gamification!.healthXp, color: Colors.green, isDark: isDark),
                            _GlassSkillBar(label: 'Career', level: _gamification!.careerLevel, xp: _gamification!.careerXp, color: Colors.blue, isDark: isDark),
                            _GlassSkillBar(label: 'Relations', level: _gamification!.relationshipsLevel, xp: _gamification!.relationshipsXp, color: Colors.pink, isDark: isDark),
                            _GlassSkillBar(label: 'Growth', level: _gamification!.personalGrowthLevel, xp: _gamification!.personalGrowthXp, color: AppTheme.primaryPurple, isDark: isDark),
                          ],
                        ),
                      ).animate().fadeIn(duration: 500.ms, delay: 200.ms),
                      const SizedBox(height: 16),
                    ],

                    // Menu Items
                    ...[
                      _GlassMenuTile(icon: Icons.chat_outlined, label: 'Conversations', isDark: isDark, onTap: () => context.push('/conversations')),
                      _GlassMenuTile(icon: Icons.workspace_premium, label: 'Subscription', isDark: isDark, onTap: () => context.push('/subscription')),
                      _GlassMenuTile(icon: Icons.store, label: 'Store', isDark: isDark, onTap: () => context.push('/store')),
                      _GlassMenuTile(icon: Icons.emoji_events, label: 'Leaderboard', isDark: isDark, onTap: () => context.push('/leaderboard')),
                      _GlassMenuTile(icon: Icons.notifications_outlined, label: 'Notifications', isDark: isDark, onTap: () => context.push('/notifications')),
                    ].asMap().entries.map((entry) => AnimatedListItem(
                      index: entry.key + 4,
                      child: entry.value,
                    )).toList(),

                    const SizedBox(height: 16),
                    GlassButton(
                      label: 'Sign Out',
                      icon: Icons.logout,
                      style: GlassButtonStyle.danger,
                      onPressed: () => ref.read(authProvider.notifier).logout(),
                    ).animate().fadeIn(duration: 500.ms, delay: 400.ms),
                  ],
                ),
              ),
      ),
    );
  }

  String _formatDate(DateTime date) {
    return '${date.day}/${date.month}/${date.year}';
  }
}

class _GlassStatCard extends StatelessWidget {
  final String label;
  final int value;
  final IconData icon;
  final Color color;
  final bool isDark;
  final int index;
  const _GlassStatCard({required this.label, required this.value, required this.icon, required this.color, required this.isDark, required this.index});

  @override
  Widget build(BuildContext context) {
    return GlassContainer(
      padding: const EdgeInsets.all(14),
      opacity: isDark ? 0.12 : 0.25,
      child: Column(
        children: [
          Container(
            padding: const EdgeInsets.all(8),
            decoration: BoxDecoration(
              color: color.withValues(alpha: 0.15),
              borderRadius: BorderRadius.circular(10),
            ),
            child: Icon(icon, color: color, size: 22),
          ),
          const SizedBox(height: 8),
          AnimatedCounter(value: value, style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold, color: color)),
          const SizedBox(height: 2),
          Text(label, style: TextStyle(fontSize: 12, color: isDark ? Colors.white54 : Colors.grey[600])),
        ],
      ),
    ).animate().fadeIn(duration: 400.ms, delay: Duration(milliseconds: 100 + index * 80)).slideY(begin: 0.1, end: 0);
  }
}

class _GlassSkillBar extends StatelessWidget {
  final String label;
  final int level;
  final int xp;
  final Color color;
  final bool isDark;
  const _GlassSkillBar({required this.label, required this.level, required this.xp, required this.color, required this.isDark});

  @override
  Widget build(BuildContext context) {
    final progress = (xp % 1000) / 1000;
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Text(label, style: TextStyle(fontWeight: FontWeight.w600, fontSize: 13, color: isDark ? Colors.white : const Color(0xFF1E1B4B))),
              const Spacer(),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                decoration: BoxDecoration(color: color.withValues(alpha: 0.15), borderRadius: BorderRadius.circular(6)),
                child: Text('Lv.$level', style: TextStyle(fontWeight: FontWeight.bold, color: color, fontSize: 11)),
              ),
              const SizedBox(width: 8),
              Text('${xp % 1000}/1000', style: TextStyle(fontSize: 11, color: isDark ? Colors.white38 : Colors.grey[700])),
            ],
          ),
          const SizedBox(height: 6),
          ClipRRect(
            borderRadius: BorderRadius.circular(4),
            child: TweenAnimationBuilder<double>(
              tween: Tween(begin: 0, end: progress),
              duration: const Duration(milliseconds: 800),
              curve: Curves.easeOutCubic,
              builder: (context, value, _) => Stack(
                children: [
                  Container(
                    height: 6,
                    decoration: BoxDecoration(
                      color: color.withValues(alpha: 0.1),
                      borderRadius: BorderRadius.circular(4),
                    ),
                  ),
                  FractionallySizedBox(
                    widthFactor: value,
                    child: Container(
                      height: 6,
                      decoration: BoxDecoration(
                        gradient: LinearGradient(colors: [color.withValues(alpha: 0.7), color]),
                        borderRadius: BorderRadius.circular(4),
                        boxShadow: [BoxShadow(color: color.withValues(alpha: 0.3), blurRadius: 4)],
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _GlassMenuTile extends StatelessWidget {
  final IconData icon;
  final String label;
  final bool isDark;
  final VoidCallback onTap;
  const _GlassMenuTile({required this.icon, required this.label, required this.isDark, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: GlassContainer(
        opacity: isDark ? 0.1 : 0.2,
        child: Material(
          color: Colors.transparent,
          child: InkWell(
            borderRadius: BorderRadius.circular(16),
            onTap: onTap,
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
              child: Row(
                children: [
                  Container(
                    padding: const EdgeInsets.all(8),
                    decoration: BoxDecoration(
                      color: AppTheme.primaryPurple.withValues(alpha: isDark ? 0.2 : 0.1),
                      borderRadius: BorderRadius.circular(10),
                    ),
                    child: Icon(icon, color: AppTheme.primaryPurple, size: 20),
                  ),
                  const SizedBox(width: 14),
                  Expanded(child: Text(label, style: TextStyle(fontWeight: FontWeight.w500, color: isDark ? Colors.white : const Color(0xFF1E1B4B)))),
                  Icon(Icons.chevron_right, color: isDark ? Colors.white24 : Colors.grey[600], size: 20),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}
