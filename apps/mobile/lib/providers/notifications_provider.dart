import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../models/notification_model.dart';
import '../services/notification_service.dart';

class NotificationsState {
  final List<NotificationModel> notifications;
  final int unreadCount;
  final bool isLoading;

  const NotificationsState({
    this.notifications = const [],
    this.unreadCount = 0,
    this.isLoading = false,
  });

  NotificationsState copyWith({
    List<NotificationModel>? notifications,
    int? unreadCount,
    bool? isLoading,
  }) {
    return NotificationsState(
      notifications: notifications ?? this.notifications,
      unreadCount: unreadCount ?? this.unreadCount,
      isLoading: isLoading ?? this.isLoading,
    );
  }
}

class NotificationsNotifier extends StateNotifier<NotificationsState> {
  final NotificationService _service;

  NotificationsNotifier(this._service) : super(const NotificationsState());

  Future<void> fetchNotifications() async {
    state = state.copyWith(isLoading: true);
    try {
      final notifications = await _service.getNotifications();
      final unread = await _service.getUnreadCount();
      state = state.copyWith(
        notifications: notifications,
        unreadCount: unread,
        isLoading: false,
      );
    } catch (_) {
      state = state.copyWith(isLoading: false);
    }
  }

  Future<void> markAsRead(String id) async {
    await _service.markAsRead(id);
    state = state.copyWith(
      notifications: state.notifications.map((n) {
        if (n.id == id) {
          return NotificationModel(
            id: n.id,
            notificationType: n.notificationType,
            title: n.title,
            body: n.body,
            data: n.data,
            status: n.status,
            isRead: true,
            createdAt: n.createdAt,
          );
        }
        return n;
      }).toList(),
      unreadCount: (state.unreadCount - 1).clamp(0, 999),
    );
  }

  Future<void> markAllAsRead() async {
    await _service.markAllAsRead();
    state = state.copyWith(
      notifications: state.notifications.map((n) {
        return NotificationModel(
          id: n.id,
          notificationType: n.notificationType,
          title: n.title,
          body: n.body,
          data: n.data,
          status: n.status,
          isRead: true,
          createdAt: n.createdAt,
        );
      }).toList(),
      unreadCount: 0,
    );
  }
}

final notificationsProvider =
    StateNotifierProvider<NotificationsNotifier, NotificationsState>((ref) {
  return NotificationsNotifier(ref.read(notificationServiceProvider));
});
