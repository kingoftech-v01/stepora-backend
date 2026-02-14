import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../core/theme/app_theme.dart';
import '../../providers/social_provider.dart';
import '../../services/api_service.dart';
import '../../widgets/gradient_background.dart';
import '../../widgets/glass_container.dart';
import '../../widgets/glass_app_bar.dart';
import '../../widgets/glass_button.dart';
import '../../widgets/animated_list_item.dart';
import '../../widgets/loading_shimmer.dart';

class SocialScreen extends ConsumerStatefulWidget {
  const SocialScreen({super.key});

  @override
  ConsumerState<SocialScreen> createState() => _SocialScreenState();
}

class _SocialScreenState extends ConsumerState<SocialScreen> {
  List<Map<String, dynamic>> _feed = [];
  bool _isLoading = true;

  @override
  void initState() {
    super.initState();
    _loadFeed();
    Future.microtask(() => ref.read(socialProvider.notifier).fetchPendingRequests());
  }

  Future<void> _loadFeed() async {
    setState(() => _isLoading = true);
    try {
      final api = ref.read(apiServiceProvider);
      final response = await api.get('/social/feed/');
      final results = response.data['results'] as List? ?? response.data as List? ?? [];
      setState(() { _feed = List<Map<String, dynamic>>.from(results); _isLoading = false; });
    } catch (_) { setState(() => _isLoading = false); }
  }

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;

    return GradientBackground(
      colors: isDark ? AppTheme.gradientSocial : AppTheme.gradientSocialLight,
      child: Scaffold(
        backgroundColor: Colors.transparent,
        extendBodyBehindAppBar: true,
        appBar: GlassAppBar(
          title: 'Social',
          actions: [
            Builder(builder: (context) {
              final pendingCount = ref.watch(socialProvider).pendingCount;
              if (pendingCount > 0) {
                return Badge(
                  label: Text('$pendingCount'),
                  child: IconButton(icon: Icon(Icons.person_add, color: isDark ? Colors.white70 : const Color(0xFF1E1B4B)), onPressed: () => context.push('/social/requests')),
                );
              }
              return IconButton(icon: Icon(Icons.person_add, color: isDark ? Colors.white70 : const Color(0xFF1E1B4B)), onPressed: () => context.push('/social/requests'));
            }),
            IconButton(icon: Icon(Icons.people, color: isDark ? Colors.white70 : const Color(0xFF1E1B4B)), tooltip: 'Friends', onPressed: () => context.push('/friends')),
            IconButton(icon: Icon(Icons.search, color: isDark ? Colors.white70 : const Color(0xFF1E1B4B)), tooltip: 'Search', onPressed: () => context.push('/social/search')),
            IconButton(icon: Icon(Icons.group_outlined, color: isDark ? Colors.white70 : const Color(0xFF1E1B4B)), onPressed: () => context.push('/circles')),
          ],
        ),
        body: RefreshIndicator(
          onRefresh: _loadFeed,
          child: _isLoading
              ? const Center(child: LoadingShimmer())
              : _feed.isEmpty
                  ? _buildEmptyFeed(context, isDark)
                  : ListView.builder(
                      padding: EdgeInsets.fromLTRB(16, MediaQuery.of(context).padding.top + kToolbarHeight + 8, 16, 32),
                      itemCount: _feed.length,
                      itemBuilder: (context, index) => AnimatedListItem(
                        index: index,
                        child: _buildFeedItem(_feed[index], isDark),
                      ),
                    ),
        ),
        floatingActionButton: Container(
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            boxShadow: [BoxShadow(color: AppTheme.primaryPurple.withValues(alpha: 0.4), blurRadius: 16, spreadRadius: 2)],
          ),
          child: FloatingActionButton(
            onPressed: () => context.push('/circles'),
            backgroundColor: AppTheme.primaryPurple,
            foregroundColor: Colors.white,
            child: const Icon(Icons.group_add),
          ),
        ).animate().fadeIn(duration: 500.ms, delay: 300.ms).scale(begin: const Offset(0.8, 0.8), end: const Offset(1, 1)),
      ),
    );
  }

  Widget _buildEmptyFeed(BuildContext context, bool isDark) {
    return ListView(children: [
      const SizedBox(height: 100),
      Center(child: Column(children: [
        Container(
          padding: const EdgeInsets.all(24),
          decoration: BoxDecoration(shape: BoxShape.circle, color: AppTheme.primaryPurple.withValues(alpha: 0.1)),
          child: Icon(Icons.people_outline, size: 48, color: isDark ? Colors.white24 : Colors.grey[600]),
        ).animate().fadeIn(duration: 500.ms).scale(begin: const Offset(0.8, 0.8), end: const Offset(1, 1)),
        const SizedBox(height: 16),
        Text('No activity yet', style: TextStyle(fontSize: 18, fontWeight: FontWeight.w600, color: isDark ? Colors.white70 : Colors.grey[700]))
          .animate().fadeIn(duration: 500.ms, delay: 100.ms),
        const SizedBox(height: 8),
        Text('Join circles and find a buddy!', style: TextStyle(color: isDark ? Colors.white38 : Colors.grey[600]))
          .animate().fadeIn(duration: 500.ms, delay: 200.ms),
        const SizedBox(height: 24),
        Row(mainAxisAlignment: MainAxisAlignment.center, children: [
          GlassButton(label: 'Circles', icon: Icons.group, onPressed: () => context.push('/circles')),
          const SizedBox(width: 12),
          GlassButton(label: 'Find Buddy', icon: Icons.people, onPressed: () => context.push('/buddy'), style: GlassButtonStyle.secondary),
        ]).animate().fadeIn(duration: 500.ms, delay: 300.ms),
      ])),
    ]);
  }

  Widget _buildFeedItem(Map<String, dynamic> item, bool isDark) {
    final type = item['type'] ?? '';
    final user = item['user'] ?? {};
    final data = item['data'] ?? {};

    return GlassContainer(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(16),
      opacity: isDark ? 0.12 : 0.25,
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          CircleAvatar(
            radius: 20,
            backgroundColor: AppTheme.primaryPurple.withValues(alpha: 0.15),
            child: Text((user['display_name'] ?? 'U')[0].toUpperCase(), style: TextStyle(color: AppTheme.primaryPurple, fontWeight: FontWeight.bold)),
          ),
          const SizedBox(width: 12),
          Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(user['display_name'] ?? 'User', style: TextStyle(fontWeight: FontWeight.w600, color: isDark ? Colors.white : const Color(0xFF1E1B4B))),
            Text(_getFeedText(type, data), style: TextStyle(color: isDark ? Colors.white54 : Colors.grey[600], fontSize: 13)),
          ])),
          Container(
            padding: const EdgeInsets.all(6),
            decoration: BoxDecoration(color: AppTheme.accent.withValues(alpha: 0.12), borderRadius: BorderRadius.circular(8)),
            child: Icon(_getFeedIcon(type), color: AppTheme.accent, size: 18),
          ),
        ]),
        if (data['content'] != null) ...[
          const SizedBox(height: 10),
          Text(data['content'], style: TextStyle(color: isDark ? Colors.white70 : const Color(0xFF1E1B4B))),
        ],
      ]),
    );
  }

  String _getFeedText(String type, Map<String, dynamic> data) {
    switch (type) {
      case 'dream_created': return 'created a new dream';
      case 'task_completed': return 'completed a task';
      case 'level_up': return 'reached level ${data['level']}';
      case 'streak': return '${data['days']} day streak!';
      default: return 'was active';
    }
  }

  IconData _getFeedIcon(String type) {
    switch (type) {
      case 'dream_created': return Icons.auto_awesome;
      case 'task_completed': return Icons.check_circle;
      case 'level_up': return Icons.arrow_upward;
      case 'streak': return Icons.local_fire_department;
      default: return Icons.star;
    }
  }
}
