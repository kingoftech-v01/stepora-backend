import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../core/theme/app_theme.dart';
import '../../providers/auth_provider.dart';
import '../../providers/dreams_provider.dart';
import '../../widgets/dream_card.dart';

class HomeScreen extends ConsumerStatefulWidget {
  const HomeScreen({super.key});

  @override
  ConsumerState<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends ConsumerState<HomeScreen> {
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

    return Scaffold(
      appBar: AppBar(
        title: const Text('DreamPlanner'),
        actions: [
          IconButton(
            icon: const Icon(Icons.notifications_outlined),
            onPressed: () => context.push('/notifications'),
          ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: () async {
          await ref.read(dreamsProvider.notifier).fetchDreams();
          await ref.read(authProvider.notifier).refreshUser();
        },
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            // Welcome & Stats Card
            if (user != null) _buildWelcomeCard(context, user),
            const SizedBox(height: 24),
            // Quick Actions
            _buildQuickActions(context),
            const SizedBox(height: 24),
            // Active Dreams
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text(
                  'Your Dreams',
                  style: Theme.of(context).textTheme.titleLarge?.copyWith(
                    fontWeight: FontWeight.bold,
                  ),
                ),
                TextButton.icon(
                  onPressed: () => context.push('/dreams/create'),
                  icon: const Icon(Icons.add),
                  label: const Text('New Dream'),
                ),
              ],
            ),
            const SizedBox(height: 12),
            if (dreamsState.isLoading)
              const Center(child: CircularProgressIndicator())
            else if (dreamsState.dreams.isEmpty)
              _buildEmptyState(context)
            else
              ...dreamsState.dreams.map((dream) => Padding(
                padding: const EdgeInsets.only(bottom: 12),
                child: DreamCard(
                  dream: dream,
                  onTap: () => context.push('/dreams/${dream.id}'),
                ),
              )),
          ],
        ),
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () => context.push('/dreams/create'),
        backgroundColor: AppTheme.primaryPurple,
        foregroundColor: Colors.white,
        icon: const Icon(Icons.add),
        label: const Text('New Dream'),
      ),
    );
  }

  Widget _buildWelcomeCard(BuildContext context, dynamic user) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                CircleAvatar(
                  radius: 24,
                  backgroundColor: AppTheme.primaryPurple.withValues(alpha: 0.1),
                  child: Text(
                    (user.displayName.isNotEmpty
                        ? user.displayName[0]
                        : user.email[0]).toUpperCase(),
                    style: TextStyle(
                      fontSize: 20,
                      fontWeight: FontWeight.bold,
                      color: AppTheme.primaryPurple,
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
                        style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                          color: Colors.grey[600],
                        ),
                      ),
                      Text(
                        user.displayName.isNotEmpty ? user.displayName : user.email,
                        style: Theme.of(context).textTheme.titleMedium?.copyWith(
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
            const SizedBox(height: 16),
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceAround,
              children: [
                _buildStat(context, Icons.star, 'Level ${user.level}', 'Level'),
                _buildStat(context, Icons.bolt, '${user.xp} XP', 'Experience'),
                _buildStat(context, Icons.local_fire_department, '${user.streakDays}', 'Streak'),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildStat(BuildContext context, IconData icon, String value, String label) {
    return Column(
      children: [
        Icon(icon, color: AppTheme.accent, size: 28),
        const SizedBox(height: 4),
        Text(value, style: Theme.of(context).textTheme.titleSmall?.copyWith(
          fontWeight: FontWeight.bold,
        )),
        Text(label, style: Theme.of(context).textTheme.bodySmall?.copyWith(
          color: Colors.grey[500],
        )),
      ],
    );
  }

  Widget _buildQuickActions(BuildContext context) {
    return Column(
      children: [
        Row(
          children: [
            Expanded(
              child: _QuickActionCard(
                icon: Icons.chat_bubble_outline,
                label: 'AI Coach',
                color: AppTheme.primaryPurple,
                onTap: () => context.push('/chat/new'),
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: _QuickActionCard(
                icon: Icons.forum_outlined,
                label: 'Conversations',
                color: Colors.teal,
                onTap: () => context.push('/conversations'),
              ),
            ),
          ],
        ),
        const SizedBox(height: 12),
        Row(
          children: [
            Expanded(
              child: _QuickActionCard(
                icon: Icons.emoji_events_outlined,
                label: 'Leaderboard',
                color: AppTheme.accent,
                onTap: () => context.push('/leaderboard'),
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: _QuickActionCard(
                icon: Icons.store_outlined,
                label: 'Store',
                color: AppTheme.success,
                onTap: () => context.push('/store'),
              ),
            ),
          ],
        ),
      ],
    );
  }

  Widget _buildEmptyState(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 48),
        child: Column(
          children: [
            Icon(Icons.auto_awesome, size: 64, color: Colors.grey[300]),
            const SizedBox(height: 16),
            Text(
              'No dreams yet',
              style: Theme.of(context).textTheme.titleMedium?.copyWith(
                color: Colors.grey[500],
              ),
            ),
            const SizedBox(height: 8),
            Text(
              'Create your first dream and start planning!',
              style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                color: Colors.grey[400],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _QuickActionCard extends StatelessWidget {
  final IconData icon;
  final String label;
  final Color color;
  final VoidCallback onTap;

  const _QuickActionCard({
    required this.icon,
    required this.label,
    required this.color,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return Card(
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(16),
        child: Padding(
          padding: const EdgeInsets.symmetric(vertical: 16, horizontal: 8),
          child: Column(
            children: [
              Icon(icon, color: color, size: 32),
              const SizedBox(height: 8),
              Text(
                label,
                style: Theme.of(context).textTheme.bodySmall?.copyWith(
                  fontWeight: FontWeight.w600,
                ),
                textAlign: TextAlign.center,
              ),
            ],
          ),
        ),
      ),
    );
  }
}
