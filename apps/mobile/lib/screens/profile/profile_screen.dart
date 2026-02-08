import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../core/theme/app_theme.dart';
import '../../providers/auth_provider.dart';
import '../../services/api_service.dart';
import '../../models/user.dart';

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

    return Scaffold(
      appBar: AppBar(
        title: const Text('Profile'),
        actions: [
          IconButton(
            icon: const Icon(Icons.settings_outlined),
            onPressed: () {},
          ),
        ],
      ),
      body: user == null
          ? const Center(child: CircularProgressIndicator())
          : RefreshIndicator(
              onRefresh: () async {
                await ref.read(authProvider.notifier).refreshUser();
                await _loadGamification();
              },
              child: ListView(
                padding: const EdgeInsets.all(16),
                children: [
                  // Profile Header
                  Card(
                    child: Padding(
                      padding: const EdgeInsets.all(20),
                      child: Column(
                        children: [
                          CircleAvatar(
                            radius: 40,
                            backgroundColor: AppTheme.primaryPurple.withValues(alpha: 0.1),
                            child: Text(
                              (user.displayName.isNotEmpty ? user.displayName[0] : user.email[0]).toUpperCase(),
                              style: TextStyle(fontSize: 32, fontWeight: FontWeight.bold, color: AppTheme.primaryPurple),
                            ),
                          ),
                          const SizedBox(height: 12),
                          Text(
                            user.displayName.isNotEmpty ? user.displayName : user.email,
                            style: Theme.of(context).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.bold),
                          ),
                          Text(user.email, style: TextStyle(color: Colors.grey[600])),
                          const SizedBox(height: 8),
                          if (user.isPremium)
                            Chip(
                              label: Text(user.subscription.toUpperCase()),
                              backgroundColor: AppTheme.accent.withValues(alpha: 0.1),
                              labelStyle: TextStyle(color: AppTheme.accent, fontWeight: FontWeight.bold),
                              avatar: Icon(Icons.star, color: AppTheme.accent, size: 16),
                            ),
                        ],
                      ),
                    ),
                  ),
                  const SizedBox(height: 16),
                  // Stats
                  Row(
                    children: [
                      Expanded(child: _StatCard(label: 'Level', value: '${user.level}', icon: Icons.star, color: AppTheme.primaryPurple)),
                      const SizedBox(width: 8),
                      Expanded(child: _StatCard(label: 'XP', value: '${user.xp}', icon: Icons.bolt, color: AppTheme.accent)),
                      const SizedBox(width: 8),
                      Expanded(child: _StatCard(label: 'Streak', value: '${user.streakDays}', icon: Icons.local_fire_department, color: AppTheme.error)),
                    ],
                  ),
                  const SizedBox(height: 16),
                  // Gamification
                  if (_gamification != null) ...[
                    Text('Skill Levels', style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.bold)),
                    const SizedBox(height: 8),
                    _SkillBar(label: 'Health', level: _gamification!.healthLevel, xp: _gamification!.healthXp, color: Colors.green),
                    _SkillBar(label: 'Career', level: _gamification!.careerLevel, xp: _gamification!.careerXp, color: Colors.blue),
                    _SkillBar(label: 'Relationships', level: _gamification!.relationshipsLevel, xp: _gamification!.relationshipsXp, color: Colors.pink),
                    _SkillBar(label: 'Growth', level: _gamification!.personalGrowthLevel, xp: _gamification!.personalGrowthXp, color: AppTheme.primaryPurple),
                    const SizedBox(height: 16),
                  ],
                  // Menu Items
                  Card(
                    child: Column(
                      children: [
                        _MenuTile(icon: Icons.workspace_premium, label: 'Subscription', onTap: () => context.push('/subscription')),
                        const Divider(height: 1),
                        _MenuTile(icon: Icons.store, label: 'Store', onTap: () => context.push('/store')),
                        const Divider(height: 1),
                        _MenuTile(icon: Icons.emoji_events, label: 'Leaderboard', onTap: () => context.push('/leaderboard')),
                        const Divider(height: 1),
                        _MenuTile(icon: Icons.notifications_outlined, label: 'Notifications', onTap: () => context.push('/notifications')),
                      ],
                    ),
                  ),
                  const SizedBox(height: 16),
                  OutlinedButton.icon(
                    onPressed: () => ref.read(authProvider.notifier).logout(),
                    icon: const Icon(Icons.logout, color: AppTheme.error),
                    label: const Text('Sign Out', style: TextStyle(color: AppTheme.error)),
                    style: OutlinedButton.styleFrom(
                      side: const BorderSide(color: AppTheme.error),
                      padding: const EdgeInsets.symmetric(vertical: 14),
                    ),
                  ),
                ],
              ),
            ),
    );
  }
}

class _StatCard extends StatelessWidget {
  final String label;
  final String value;
  final IconData icon;
  final Color color;
  const _StatCard({required this.label, required this.value, required this.icon, required this.color});

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          children: [
            Icon(icon, color: color, size: 28),
            const SizedBox(height: 8),
            Text(value, style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold, color: color)),
            Text(label, style: Theme.of(context).textTheme.bodySmall),
          ],
        ),
      ),
    );
  }
}

class _SkillBar extends StatelessWidget {
  final String label;
  final int level;
  final int xp;
  final Color color;
  const _SkillBar({required this.label, required this.level, required this.xp, required this.color});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Row(
        children: [
          SizedBox(width: 100, child: Text(label, style: const TextStyle(fontWeight: FontWeight.w500))),
          Text('Lv.$level', style: TextStyle(fontWeight: FontWeight.bold, color: color)),
          const SizedBox(width: 8),
          Expanded(
            child: ClipRRect(
              borderRadius: BorderRadius.circular(4),
              child: LinearProgressIndicator(
                value: (xp % 1000) / 1000,
                backgroundColor: color.withValues(alpha: 0.1),
                color: color,
                minHeight: 8,
              ),
            ),
          ),
          const SizedBox(width: 8),
          Text('${xp % 1000}/1000', style: Theme.of(context).textTheme.bodySmall),
        ],
      ),
    );
  }
}

class _MenuTile extends StatelessWidget {
  final IconData icon;
  final String label;
  final VoidCallback onTap;
  const _MenuTile({required this.icon, required this.label, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return ListTile(
      leading: Icon(icon, color: AppTheme.primaryPurple),
      title: Text(label),
      trailing: const Icon(Icons.chevron_right),
      onTap: onTap,
    );
  }
}
