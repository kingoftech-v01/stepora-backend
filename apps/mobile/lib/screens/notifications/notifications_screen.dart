import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:timeago/timeago.dart' as timeago;
import '../../core/theme/app_theme.dart';
import '../../providers/notifications_provider.dart';

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

    final filtered = _selectedFilter == 'all'
        ? state.notifications
        : state.notifications.where((n) => n.notificationType == _selectedFilter).toList();

    return Scaffold(
      appBar: AppBar(
        title: const Text('Notifications'),
        actions: [
          if (state.unreadCount > 0)
            TextButton(
              onPressed: () => ref.read(notificationsProvider.notifier).markAllAsRead(),
              child: const Text('Mark all read'),
            ),
        ],
      ),
      body: Column(
        children: [
          // Filter chips
          SizedBox(
            height: 48,
            child: ListView.builder(
              scrollDirection: Axis.horizontal,
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
              itemCount: _filters.length,
              itemBuilder: (context, index) {
                final filter = _filters[index];
                final isSelected = _selectedFilter == filter['key'];
                return Padding(
                  padding: const EdgeInsets.only(right: 8),
                  child: FilterChip(
                    label: Text(filter['label']!),
                    selected: isSelected,
                    onSelected: (_) => setState(() => _selectedFilter = filter['key']!),
                    selectedColor: AppTheme.primaryPurple.withValues(alpha: 0.15),
                    checkmarkColor: AppTheme.primaryPurple,
                  ),
                );
              },
            ),
          ),
          Expanded(
            child: state.isLoading
                ? const Center(child: CircularProgressIndicator())
                : filtered.isEmpty
                    ? Center(
                        child: Column(
                          mainAxisAlignment: MainAxisAlignment.center,
                          children: [
                            Icon(Icons.notifications_none, size: 64, color: Colors.grey[300]),
                            const SizedBox(height: 16),
                            Text('No notifications', style: TextStyle(color: Colors.grey[500], fontSize: 16)),
                          ],
                        ),
                      )
                    : RefreshIndicator(
                        onRefresh: () => ref.read(notificationsProvider.notifier).fetchNotifications(),
                        child: ListView.builder(
                          itemCount: filtered.length,
                          itemBuilder: (context, index) {
                            final notif = filtered[index];
                            return Dismissible(
                              key: Key(notif.id),
                              direction: DismissDirection.endToStart,
                              background: Container(
                                alignment: Alignment.centerRight,
                                padding: const EdgeInsets.only(right: 20),
                                color: Colors.grey.shade300,
                                child: const Icon(Icons.done_all, color: Colors.white),
                              ),
                              onDismissed: (_) {
                                ref.read(notificationsProvider.notifier).markAsRead(notif.id);
                              },
                              child: ListTile(
                                leading: CircleAvatar(
                                  backgroundColor: notif.isRead
                                      ? Colors.grey[200]
                                      : AppTheme.primaryPurple.withValues(alpha: 0.1),
                                  child: Icon(
                                    _getNotifIcon(notif.notificationType),
                                    color: notif.isRead ? Colors.grey : AppTheme.primaryPurple,
                                  ),
                                ),
                                title: Text(
                                  notif.title,
                                  style: TextStyle(fontWeight: notif.isRead ? FontWeight.normal : FontWeight.bold),
                                ),
                                subtitle: Column(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    Text(notif.body, maxLines: 2, overflow: TextOverflow.ellipsis),
                                    const SizedBox(height: 4),
                                    Text(
                                      timeago.format(notif.createdAt),
                                      style: Theme.of(context).textTheme.bodySmall?.copyWith(color: Colors.grey[500]),
                                    ),
                                  ],
                                ),
                                isThreeLine: true,
                                onTap: () => _handleNotificationTap(notif),
                              ),
                            );
                          },
                        ),
                      ),
          ),
        ],
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
