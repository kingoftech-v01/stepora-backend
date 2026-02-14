import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:timeago/timeago.dart' as timeago;
import '../../core/theme/app_theme.dart';
import '../../providers/notifications_provider.dart';
import '../../widgets/gradient_background.dart';
import '../../widgets/glass_container.dart';
import '../../widgets/glass_app_bar.dart';
import '../../widgets/animated_list_item.dart';
import '../../widgets/loading_shimmer.dart';

class NotificationsScreen extends ConsumerStatefulWidget {
  const NotificationsScreen({super.key});

  @override
  ConsumerState<NotificationsScreen> createState() => _NotificationsScreenState();
}

class _NotificationsScreenState extends ConsumerState<NotificationsScreen> {
  String _selectedFilter = 'all';

  static const _filters = [
    {'key': 'all', 'label': 'All'},
    {'key': 'task_reminder', 'label': 'Tasks'},
    {'key': 'achievement', 'label': 'Achievements'},
    {'key': 'buddy_request', 'label': 'Buddy'},
    {'key': 'circle_invite', 'label': 'Circles'},
  ];

  @override
  void initState() {
    super.initState();
    Future.microtask(() => ref.read(notificationsProvider.notifier).fetchNotifications());
  }

  void _handleNotificationTap(dynamic notif) {
    if (!notif.isRead) {
      ref.read(notificationsProvider.notifier).markAsRead(notif.id);
    }

    final data = notif.data;
    if (data == null) return;

    final type = data['type'] as String? ?? '';
    final targetId = data['target_id'] as String? ?? '';

    if (targetId.isEmpty) return;

    switch (type) {
      case 'dream':
        context.push('/dreams/$targetId');
      case 'task':
        context.push('/dreams/$targetId');
      case 'buddy':
        context.push('/buddy');
      case 'circle':
        context.push('/circles/$targetId');
      case 'conversation':
        context.push('/chat/$targetId');
      case 'achievement':
        context.push('/profile');
    }
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(notificationsProvider);
    final isDark = Theme.of(context).brightness == Brightness.dark;

    final filtered = _selectedFilter == 'all'
        ? state.notifications
        : state.notifications.where((n) => n.notificationType == _selectedFilter).toList();

    return GradientBackground(
      colors: isDark ? AppTheme.gradientSocial : AppTheme.gradientSocialLight,
      child: Scaffold(
        backgroundColor: Colors.transparent,
        extendBodyBehindAppBar: true,
        appBar: GlassAppBar(
          title: 'Notifications',
          actions: [
            if (state.unreadCount > 0)
              TextButton(
                onPressed: () => ref.read(notificationsProvider.notifier).markAllAsRead(),
                child: Text('Mark all read', style: TextStyle(color: AppTheme.primaryPurple, fontSize: 13)),
              ),
          ],
        ),
        body: Column(
          children: [
            SizedBox(height: MediaQuery.of(context).padding.top + kToolbarHeight + 8),
            // Filter chips
            SizedBox(
              height: 44,
              child: ListView.builder(
                scrollDirection: Axis.horizontal,
                padding: const EdgeInsets.symmetric(horizontal: 16),
                itemCount: _filters.length,
                itemBuilder: (context, index) {
                  final filter = _filters[index];
                  final isSelected = _selectedFilter == filter['key'];
                  return Padding(
                    padding: const EdgeInsets.only(right: 8),
                    child: GestureDetector(
                      onTap: () => setState(() => _selectedFilter = filter['key']!),
                      child: Container(
                        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
                        decoration: BoxDecoration(
                          color: isSelected
                              ? AppTheme.primaryPurple.withValues(alpha: 0.25)
                              : (isDark ? Colors.white.withValues(alpha: 0.08) : Colors.white.withValues(alpha: 0.3)),
                          borderRadius: BorderRadius.circular(20),
                          border: Border.all(
                            color: isSelected
                                ? AppTheme.primaryPurple.withValues(alpha: 0.5)
                                : (isDark ? Colors.white.withValues(alpha: 0.15) : Colors.white.withValues(alpha: 0.5)),
                          ),
                        ),
                        child: Text(
                          filter['label']!,
                          style: TextStyle(
                            fontSize: 13,
                            fontWeight: isSelected ? FontWeight.w600 : FontWeight.w400,
                            color: isSelected ? AppTheme.primaryPurple : (isDark ? Colors.white70 : const Color(0xFF1E1B4B)),
                          ),
                        ),
                      ),
                    ),
                  ).animate().fadeIn(duration: 300.ms, delay: Duration(milliseconds: index * 50));
                },
              ),
            ),
            const SizedBox(height: 8),
            Expanded(
              child: state.isLoading
                  ? const Center(child: LoadingShimmer())
                  : filtered.isEmpty
                      ? Center(
                          child: Column(
                            mainAxisAlignment: MainAxisAlignment.center,
                            children: [
                              Container(
                                padding: const EdgeInsets.all(20),
                                decoration: BoxDecoration(shape: BoxShape.circle, color: AppTheme.primaryPurple.withValues(alpha: 0.1)),
                                child: Icon(Icons.notifications_none, size: 48, color: isDark ? Colors.white24 : Colors.grey[600]),
                              ).animate().fadeIn(duration: 500.ms),
                              const SizedBox(height: 16),
                              Text('No notifications', style: TextStyle(color: isDark ? Colors.white54 : Colors.grey[700], fontSize: 16))
                                .animate().fadeIn(duration: 500.ms, delay: 100.ms),
                            ],
                          ),
                        )
                      : RefreshIndicator(
                          onRefresh: () => ref.read(notificationsProvider.notifier).fetchNotifications(),
                          child: ListView.builder(
                            padding: const EdgeInsets.symmetric(horizontal: 16),
                            itemCount: filtered.length,
                            itemBuilder: (context, index) {
                              final notif = filtered[index];
                              return AnimatedListItem(
                                index: index,
                                child: Dismissible(
                                  key: Key(notif.id),
                                  direction: DismissDirection.endToStart,
                                  background: Container(
                                    alignment: Alignment.centerRight,
                                    padding: const EdgeInsets.only(right: 20),
                                    margin: const EdgeInsets.only(bottom: 8),
                                    decoration: BoxDecoration(
                                      color: AppTheme.primaryPurple.withValues(alpha: 0.15),
                                      borderRadius: BorderRadius.circular(16),
                                    ),
                                    child: Icon(Icons.done_all, color: AppTheme.primaryPurple),
                                  ),
                                  onDismissed: (_) {
                                    ref.read(notificationsProvider.notifier).markAsRead(notif.id);
                                  },
                                  child: Padding(
                                    padding: const EdgeInsets.only(bottom: 8),
                                    child: GlassContainer(
                                      padding: const EdgeInsets.all(14),
                                      opacity: notif.isRead
                                          ? (isDark ? 0.08 : 0.15)
                                          : (isDark ? 0.15 : 0.3),
                                      border: notif.isRead
                                          ? null
                                          : Border.all(color: AppTheme.primaryPurple.withValues(alpha: 0.2)),
                                      child: Material(
                                        color: Colors.transparent,
                                        child: InkWell(
                                          borderRadius: BorderRadius.circular(16),
                                          onTap: () => _handleNotificationTap(notif),
                                          child: Row(
                                            crossAxisAlignment: CrossAxisAlignment.start,
                                            children: [
                                              Container(
                                                padding: const EdgeInsets.all(10),
                                                decoration: BoxDecoration(
                                                  color: notif.isRead
                                                      ? (isDark ? Colors.white.withValues(alpha: 0.05) : Colors.grey.withValues(alpha: 0.1))
                                                      : AppTheme.primaryPurple.withValues(alpha: 0.15),
                                                  borderRadius: BorderRadius.circular(12),
                                                ),
                                                child: Icon(
                                                  _getNotifIcon(notif.notificationType),
                                                  color: notif.isRead
                                                      ? (isDark ? Colors.white38 : Colors.grey)
                                                      : AppTheme.primaryPurple,
                                                  size: 20,
                                                ),
                                              ),
                                              const SizedBox(width: 12),
                                              Expanded(
                                                child: Column(
                                                  crossAxisAlignment: CrossAxisAlignment.start,
                                                  children: [
                                                    Text(
                                                      notif.title,
                                                      style: TextStyle(
                                                        fontWeight: notif.isRead ? FontWeight.w400 : FontWeight.w600,
                                                        color: isDark ? Colors.white : const Color(0xFF1E1B4B),
                                                      ),
                                                    ),
                                                    const SizedBox(height: 2),
                                                    Text(
                                                      notif.body,
                                                      maxLines: 2,
                                                      overflow: TextOverflow.ellipsis,
                                                      style: TextStyle(fontSize: 13, color: isDark ? Colors.white54 : Colors.grey[600]),
                                                    ),
                                                    const SizedBox(height: 4),
                                                    Text(
                                                      timeago.format(notif.createdAt),
                                                      style: TextStyle(fontSize: 11, color: isDark ? Colors.white30 : Colors.grey[600]),
                                                    ),
                                                  ],
                                                ),
                                              ),
                                              if (!notif.isRead)
                                                Container(
                                                  margin: const EdgeInsets.only(top: 4),
                                                  width: 8, height: 8,
                                                  decoration: BoxDecoration(
                                                    color: AppTheme.primaryPurple,
                                                    shape: BoxShape.circle,
                                                    boxShadow: [BoxShadow(color: AppTheme.primaryPurple.withValues(alpha: 0.4), blurRadius: 6)],
                                                  ),
                                                ),
                                            ],
                                          ),
                                        ),
                                      ),
                                    ),
                                  ),
                                ),
                              );
                            },
                          ),
                        ),
            ),
          ],
        ),
      ),
    );
  }

  IconData _getNotifIcon(String type) {
    switch (type) {
      case 'task_reminder': return Icons.task_alt;
      case 'streak_warning': return Icons.local_fire_department;
      case 'achievement': return Icons.emoji_events;
      case 'buddy_request': return Icons.people;
      case 'circle_invite': return Icons.group;
      case 'dream_milestone': return Icons.flag;
      default: return Icons.notifications;
    }
  }
}
