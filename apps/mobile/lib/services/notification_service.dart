import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../config/api_constants.dart';
import '../models/notification_model.dart';
import 'api_service.dart';

final notificationServiceProvider = Provider<NotificationService>((ref) {
  return NotificationService(ref.read(apiServiceProvider));
});

class NotificationService {
  final ApiService _api;

  NotificationService(this._api);

  Future<List<NotificationModel>> getNotifications({int page = 1}) async {
    final response = await _api.get(
      ApiConstants.notifications,
      queryParams: {'page': page},
    );
    final results = response.data['results'] as List;
    return results.map((n) => NotificationModel.fromJson(n)).toList();
  }

  Future<void> markAsRead(String id) async {
    await _api.patch('${ApiConstants.notifications}$id/', data: {
      'is_read': true,
    });
  }

  Future<void> markAllAsRead() async {
    await _api.post('${ApiConstants.notifications}mark_all_read/');
  }

  Future<int> getUnreadCount() async {
    final response = await _api.get('${ApiConstants.notifications}unread_count/');
    return response.data['count'] ?? 0;
  }

  Future<void> registerFcmToken(String token, String platform) async {
    await _api.post(ApiConstants.fcmToken, data: {
      'token': token,
      'platform': platform,
    });
  }
}
