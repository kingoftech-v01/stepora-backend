import 'dart:async';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../config/api_constants.dart';
import '../models/conversation.dart';
import '../models/message.dart';
import '../services/api_service.dart';
import '../services/websocket_service.dart';

enum ConnectionStatus { disconnected, connecting, connected, reconnecting }

class ChatState {
  final List<Conversation> conversations;
  final List<Message> messages;
  final bool isLoading;
  final String streamingContent;
  final ConnectionStatus connectionStatus;

  const ChatState({
    this.conversations = const [],
    this.messages = const [],
    this.isLoading = false,
    this.streamingContent = '',
    this.connectionStatus = ConnectionStatus.disconnected,
  });

  ChatState copyWith({
    List<Conversation>? conversations,
    List<Message>? messages,
    bool? isLoading,
    String? streamingContent,
    ConnectionStatus? connectionStatus,
  }) {
    return ChatState(
      conversations: conversations ?? this.conversations,
      messages: messages ?? this.messages,
      isLoading: isLoading ?? this.isLoading,
      streamingContent: streamingContent ?? this.streamingContent,
      connectionStatus: connectionStatus ?? this.connectionStatus,
    );
  }
}

class ChatNotifier extends Notifier<ChatState> {
  late ApiService _api;
  final WebSocketService _ws = WebSocketService();
  StreamSubscription? _wsSubscription;

  @override
  ChatState build() {
    _api = ref.read(apiServiceProvider);
    ref.onDispose(() {
      _wsSubscription?.cancel();
      _ws.disconnect();
      _ws.dispose();
    });
    return const ChatState();
  }

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

  Future<void> deleteConversation(String conversationId) async {
    await _api.delete(ApiConstants.conversationDetail(conversationId));
    state = state.copyWith(
      conversations: state.conversations.where((c) => c.id != conversationId).toList(),
    );
  }

  void connectWebSocket(String conversationId, String token) {
    state = state.copyWith(connectionStatus: ConnectionStatus.connecting);
    _ws.connect(conversationId, token);
    state = state.copyWith(connectionStatus: ConnectionStatus.connected);
    _wsSubscription = _ws.messageStream.listen((data) {
      final type = data['type'];
      if (type == 'chat_message') {
        final message = Message.fromJson(data['message']);
        state = state.copyWith(
          messages: [...state.messages, message],
          streamingContent: '',
          connectionStatus: ConnectionStatus.connected,
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
    }, onError: (_) {
      state = state.copyWith(connectionStatus: ConnectionStatus.reconnecting);
    }, onDone: () {
      state = state.copyWith(connectionStatus: ConnectionStatus.disconnected);
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
    state = state.copyWith(connectionStatus: ConnectionStatus.disconnected);
  }

  void retrySendMessage(String content) {
    if (state.connectionStatus == ConnectionStatus.connected) {
      sendMessage(content);
    }
  }
}

final chatProvider = NotifierProvider<ChatNotifier, ChatState>(ChatNotifier.new);
