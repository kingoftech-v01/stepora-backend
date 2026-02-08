import 'package:equatable/equatable.dart';

class Task extends Equatable {
  final String id;
  final String goalId;
  final String title;
  final String description;
  final String priority;
  final int estimatedMinutes;
  final bool isCompleted;
  final DateTime? completedAt;
  final DateTime? scheduledDate;
  final DateTime? scheduledTime;
  final String? twoMinuteAction;
  final int xpReward;
  final DateTime createdAt;

  const Task({
    required this.id,
    required this.goalId,
    required this.title,
    this.description = '',
    this.priority = 'medium',
    this.estimatedMinutes = 30,
    this.isCompleted = false,
    this.completedAt,
    this.scheduledDate,
    this.scheduledTime,
    this.twoMinuteAction,
    this.xpReward = 10,
    required this.createdAt,
  });

  factory Task.fromJson(Map<String, dynamic> json) {
    return Task(
      id: json['id'],
      goalId: json['goal'] ?? '',
      title: json['title'],
      description: json['description'] ?? '',
      priority: json['priority'] ?? 'medium',
      estimatedMinutes: json['estimated_minutes'] ?? 30,
      isCompleted: json['is_completed'] ?? false,
      completedAt: json['completed_at'] != null
          ? DateTime.parse(json['completed_at'])
          : null,
      scheduledDate: json['scheduled_date'] != null
          ? DateTime.parse(json['scheduled_date'])
          : null,
      scheduledTime: json['scheduled_time'] != null
          ? DateTime.parse('1970-01-01T${json['scheduled_time']}')
          : null,
      twoMinuteAction: json['two_minute_action'],
      xpReward: json['xp_reward'] ?? 10,
      createdAt: DateTime.parse(json['created_at']),
    );
  }

  Map<String, dynamic> toJson() => {
    'goal': goalId,
    'title': title,
    'description': description,
    'priority': priority,
    'estimated_minutes': estimatedMinutes,
    'scheduled_date': scheduledDate?.toIso8601String().split('T').first,
  };

  @override
  List<Object?> get props => [id];
}
