class NotificationModel {
  final String id;
  final String notificationType;
  final String title;
  final String body;
  final Map<String, dynamic>? data;
  final String status;
  final bool isRead;
  final DateTime createdAt;

  const NotificationModel({
    required this.id,
    required this.notificationType,
    required this.title,
    required this.body,
    this.data,
    this.status = 'sent',
    this.isRead = false,
    required this.createdAt,
  });

  factory NotificationModel.fromJson(Map<String, dynamic> json) {
    return NotificationModel(
      id: json['id'],
      notificationType: json['notification_type'] ?? '',
      title: json['title'] ?? '',
      body: json['body'] ?? '',
      data: json['data'],
      status: json['status'] ?? 'sent',
      isRead: json['is_read'] ?? false,
      createdAt: DateTime.parse(json['created_at']),
    );
  }
}
