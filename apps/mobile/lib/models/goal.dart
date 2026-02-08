import 'package:equatable/equatable.dart';

class Goal extends Equatable {
  final String id;
  final String dreamId;
  final String title;
  final String description;
  final int orderIndex;
  final double progress;
  final bool isCompleted;
  final int taskCount;
  final int completedTaskCount;
  final DateTime createdAt;

  const Goal({
    required this.id,
    required this.dreamId,
    required this.title,
    this.description = '',
    this.orderIndex = 0,
    this.progress = 0,
    this.isCompleted = false,
    this.taskCount = 0,
    this.completedTaskCount = 0,
    required this.createdAt,
  });

  factory Goal.fromJson(Map<String, dynamic> json) {
    return Goal(
      id: json['id'],
      dreamId: json['dream'] ?? '',
      title: json['title'],
      description: json['description'] ?? '',
      orderIndex: json['order_index'] ?? 0,
      progress: (json['progress'] ?? 0).toDouble(),
      isCompleted: json['is_completed'] ?? false,
      taskCount: json['task_count'] ?? 0,
      completedTaskCount: json['completed_task_count'] ?? 0,
      createdAt: DateTime.parse(json['created_at']),
    );
  }

  Map<String, dynamic> toJson() => {
    'dream': dreamId,
    'title': title,
    'description': description,
    'order_index': orderIndex,
  };

  @override
  List<Object?> get props => [id];
}
