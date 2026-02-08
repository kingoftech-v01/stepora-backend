import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:timeago/timeago.dart' as timeago;
import '../../core/theme/app_theme.dart';
import '../../providers/notifications_provider.dart';

class NotificationsScreen extends ConsumerStatefulWidget {
  const NotificationsScreen({super.key});

  @override
  ConsumerState<NotificationsScreen> createState() => _NotificationsScreenState();
}

class _NotificationsScreenState extends ConsumerState<NotificationsScreen> {
  @override
  void initState() {
    super.initState();
    Future.microtask(() => ref.read(notificationsProvider.notifier).fetchNotifications());
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(notificationsProvider);

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
      body: state.isLoading
          ? const Center(child: CircularProgressIndicator())
          : state.notifications.isEmpty
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
                    itemCount: state.notifications.length,
                    itemBuilder: (context, index) {
                      final notif = state.notifications[index];
                      return ListTile(
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
                        onTap: () {
                          if (!notif.isRead) {
                            ref.read(notificationsProvider.notifier).markAsRead(notif.id);
                          }
                        },
                      );
                    },
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
      default: return Icons.notifications;
    }
  }
}
