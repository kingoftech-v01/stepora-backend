import 'dart:async';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../config/api_constants.dart';
import '../models/conversation.dart';
import '../models/message.dart';
import '../services/api_service.dart';
import '../services/websocket_service.dart';

class ChatState {
  final List<Conversation> conversations;
  final List<Message> messages;
  final bool isLoading;
  final String streamingContent;

  const ChatState({
    this.conversations = const [],
    this.messages = const [],
    this.isLoading = false,
    this.streamingContent = '',
  });

  ChatState copyWith({
    List<Conversation>? conversations,
    List<Message>? messages,
    bool? isLoading,
    String? streamingContent,
  }) {
    return ChatState(
      conversations: conversations ?? this.conversations,
      messages: messages ?? this.messages,
      isLoading: isLoading ?? this.isLoading,
      streamingContent: streamingContent ?? this.streamingContent,
    );
  }
}

class ChatNotifier extends StateNotifier<ChatState> {
  final ApiService _api;
  final WebSocketService _ws = WebSocketService();
  StreamSubscription? _wsSubscription;

  ChatNotifier(this._api) : super(const ChatState());

  Future<void> fetchConversations() async {
    state = state.copyWith(isLoading: true);
    try {
      final response = await _api.get(ApiConstants.conversations);
      final results = response.data['results'] as List? ?? response.data as List;
      final convos = results.map((c) => Conversation.fromJson(c)).toList();
      state = state.copyWith(conversations: convos, isLoading: false);
    } catch (_) {
      state = state.copyWith(isLoading: false);
    }
  }

  Future<Conversation> createConversation({String type = 'general', String? dreamId}) async {
    final response = await _api.post(ApiConstants.conversations, data: {
      'conversation_type': type,
      if (dreamId != null) 'dream': dreamId,
    });
    return Conversation.fromJson(response.data);
  }

  Future<void> loadMessages(String conversationId) async {
    state = state.copyWith(isLoading: true);
    try {
      final response = await _api.get(ApiConstants.conversationMessages(conversationId));
      final results = response.data['results'] as List? ?? response.data as List;
      final messages = results.map((m) => Message.fromJson(m)).toList();
      state = state.copyWith(messages: messages, isLoading: false);
    } catch (_) {
      state = state.copyWith(isLoading: false);
    }
  }

  void connectWebSocket(String conversationId, String token) {
    _ws.connect(conversationId, token);
    _wsSubscription = _ws.messageStream.listen((data) {
      final type = data['type'];
      if (type == 'chat_message') {
        final message = Message.fromJson(data['message']);
        state = state.copyWith(
          messages: [...state.messages, message],
          streamingContent: '',
        );
      } else if (type == 'stream_chunk') {
        state = state.copyWith(
          streamingContent: state.streamingContent + (data['content'] ?? ''),
        );
      } else if (type == 'stream_end') {
        final message = Message.fromJson(data['message']);
        state = state.copyWith(
          messages: [...state.messages, message],
          streamingContent: '',
        );
      }
    });
  }

  void sendMessage(String content) {
    final userMessage = Message(
      id: DateTime.now().millisecondsSinceEpoch.toString(),
      conversationId: '',
      role: 'user',
      content: content,
      createdAt: DateTime.now(),
    );
    state = state.copyWith(messages: [...state.messages, userMessage]);
    _ws.sendMessage(content);
  }

  void disconnectWebSocket() {
    _wsSubscription?.cancel();
    _ws.disconnect();
  }

  @override
  void dispose() {
    disconnectWebSocket();
    _ws.dispose();
    super.dispose();
  }
}

final chatProvider = StateNotifierProvider<ChatNotifier, ChatState>((ref) {
  return ChatNotifier(ref.read(apiServiceProvider));
});
