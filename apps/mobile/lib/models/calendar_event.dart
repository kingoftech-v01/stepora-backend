class CalendarEvent {
  final String id;
  final String title;
  final String? description;
  final String eventType;
  final DateTime startTime;
  final DateTime endTime;
  final bool isAllDay;
  final String? taskId;
  final String? location;
  final String? color;
  final DateTime createdAt;

  const CalendarEvent({
    required this.id,
    required this.title,
    this.description,
    this.eventType = 'task',
    required this.startTime,
    required this.endTime,
    this.isAllDay = false,
    this.taskId,
    this.location,
    this.color,
    required this.createdAt,
  });

  factory CalendarEvent.fromJson(Map<String, dynamic> json) {
    return CalendarEvent(
      id: json['id'],
      title: json['title'],
      description: json['description'],
      eventType: json['event_type'] ?? 'task',
      startTime: DateTime.parse(json['start_time']),
      endTime: DateTime.parse(json['end_time']),
      isAllDay: json['is_all_day'] ?? false,
      taskId: json['task'],
      location: json['location'],
      color: json['color'],
      createdAt: DateTime.parse(json['created_at']),
    );
  }

  Map<String, dynamic> toJson() => {
    'title': title,
    'description': description,
    'event_type': eventType,
    'start_time': startTime.toIso8601String(),
    'end_time': endTime.toIso8601String(),
    'is_all_day': isAllDay,
    'task': taskId,
    'location': location,
    'color': color,
  };
}
