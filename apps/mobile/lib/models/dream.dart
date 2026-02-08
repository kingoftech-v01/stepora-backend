import 'package:equatable/equatable.dart';

class Dream extends Equatable {
  final String id;
  final String title;
  final String description;
  final String category;
  final String status;
  final String timeframe;
  final DateTime? targetDate;
  final double progress;
  final String? visionBoardUrl;
  final Map<String, dynamic>? aiAnalysis;
  final int goalCount;
  final int completedGoalCount;
  final DateTime createdAt;
  final DateTime updatedAt;

  const Dream({
    required this.id,
    required this.title,
    this.description = '',
    this.category = 'personal_growth',
    this.status = 'active',
    this.timeframe = '6_months',
    this.targetDate,
    this.progress = 0,
    this.visionBoardUrl,
    this.aiAnalysis,
    this.goalCount = 0,
    this.completedGoalCount = 0,
    required this.createdAt,
    required this.updatedAt,
  });

  factory Dream.fromJson(Map<String, dynamic> json) {
    return Dream(
      id: json['id'],
      title: json['title'],
      description: json['description'] ?? '',
      category: json['category'] ?? 'personal_growth',
      status: json['status'] ?? 'active',
      timeframe: json['timeframe'] ?? '6_months',
      targetDate: json['target_date'] != null
          ? DateTime.parse(json['target_date'])
          : null,
      progress: (json['progress'] ?? 0).toDouble(),
      visionBoardUrl: json['vision_board_url'],
      aiAnalysis: json['ai_analysis'],
      goalCount: json['goal_count'] ?? 0,
      completedGoalCount: json['completed_goal_count'] ?? 0,
      createdAt: DateTime.parse(json['created_at']),
      updatedAt: DateTime.parse(json['updated_at']),
    );
  }

  Map<String, dynamic> toJson() => {
    'title': title,
    'description': description,
    'category': category,
    'timeframe': timeframe,
    'target_date': targetDate?.toIso8601String(),
  };

  String get categoryLabel {
    const labels = {
      'health': 'Health & Fitness',
      'career': 'Career',
      'relationships': 'Relationships',
      'personal_growth': 'Personal Growth',
      'finance': 'Finance',
      'hobbies': 'Hobbies & Fun',
    };
    return labels[category] ?? category;
  }

  @override
  List<Object?> get props => [id];
}
