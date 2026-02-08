import 'package:equatable/equatable.dart';

class Conversation extends Equatable {
  final String id;
  final String conversationType;
  final String? dreamId;
  final String? title;
  final int messageCount;
  final DateTime createdAt;
  final DateTime updatedAt;

  const Conversation({
    required this.id,
    this.conversationType = 'general',
    this.dreamId,
    this.title,
    this.messageCount = 0,
    required this.createdAt,
    required this.updatedAt,
  });

  factory Conversation.fromJson(Map<String, dynamic> json) {
    return Conversation(
      id: json['id'],
      conversationType: json['conversation_type'] ?? 'general',
      dreamId: json['dream'],
      title: json['title'],
      messageCount: json['message_count'] ?? 0,
      createdAt: DateTime.parse(json['created_at']),
      updatedAt: DateTime.parse(json['updated_at']),
    );
  }

  @override
  List<Object?> get props => [id];
}
