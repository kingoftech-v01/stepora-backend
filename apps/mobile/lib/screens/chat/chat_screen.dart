import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../core/theme/app_theme.dart';
import '../../providers/auth_provider.dart';
import '../../providers/chat_provider.dart';
import '../../widgets/chat_bubble.dart';
import '../../widgets/chat_input.dart';
import '../../widgets/suggestion_chips.dart';

class ChatScreen extends ConsumerStatefulWidget {
  final String conversationId;
  const ChatScreen({super.key, required this.conversationId});

  @override
  ConsumerState<ChatScreen> createState() => _ChatScreenState();
}

class _ChatScreenState extends ConsumerState<ChatScreen> {
  final _scrollController = ScrollController();
  String? _activeConversationId;

  @override
  void initState() {
    super.initState();
    _initChat();
  }

  Future<void> _initChat() async {
    final chatNotifier = ref.read(chatProvider.notifier);
    final token = ref.read(authProvider).token;

    if (widget.conversationId == 'new') {
      final convo = await chatNotifier.createConversation();
      _activeConversationId = convo.id;
    } else {
      _activeConversationId = widget.conversationId;
      await chatNotifier.loadMessages(widget.conversationId);
    }

    if (_activeConversationId != null && token != null) {
      chatNotifier.connectWebSocket(_activeConversationId!, token);
    }
  }

  @override
  void dispose() {
    ref.read(chatProvider.notifier).disconnectWebSocket();
    _scrollController.dispose();
    super.dispose();
  }

  void _scrollToBottom() {
    if (_scrollController.hasClients) {
      Future.delayed(const Duration(milliseconds: 100), () {
        _scrollController.animateTo(
          _scrollController.position.maxScrollExtent,
          duration: const Duration(milliseconds: 300),
          curve: Curves.easeOut,
        );
      });
    }
  }

  void _sendMessage(String content) {
    ref.read(chatProvider.notifier).sendMessage(content);
    _scrollToBottom();
  }

  @override
  Widget build(BuildContext context) {
    final chatState = ref.watch(chatProvider);

    // Auto-scroll on new messages
    WidgetsBinding.instance.addPostFrameCallback((_) => _scrollToBottom());

    return Scaffold(
      appBar: AppBar(
        title: const Text('AI Coach'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: () {
              if (_activeConversationId != null) {
                ref.read(chatProvider.notifier).loadMessages(_activeConversationId!);
              }
            },
          ),
        ],
      ),
      body: Column(
        children: [
          Expanded(
            child: chatState.messages.isEmpty && !chatState.isLoading
                ? _buildEmptyChat(context)
                : ListView.builder(
                    controller: _scrollController,
                    padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                    itemCount: chatState.messages.length +
                        (chatState.streamingContent.isNotEmpty ? 1 : 0),
                    itemBuilder: (context, index) {
                      if (index < chatState.messages.length) {
                        final message = chatState.messages[index];
                        return ChatBubble(
                          content: message.content,
                          isUser: message.isUser,
                          timestamp: message.createdAt,
                        );
                      } else {
                        // Streaming message
                        return ChatBubble(
                          content: chatState.streamingContent,
                          isUser: false,
                          isStreaming: true,
                        );
                      }
                    },
                  ),
          ),
          if (chatState.messages.isEmpty)
            SuggestionChips(
              suggestions: const [
                'Help me plan my goals',
                'What should I focus on today?',
                'I need motivation',
                'Review my progress',
              ],
              onSelected: _sendMessage,
            ),
          ChatInput(onSend: _sendMessage),
        ],
      ),
    );
  }

  Widget _buildEmptyChat(BuildContext context) {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(Icons.chat_bubble_outline, size: 64, color: AppTheme.primaryPurple.withValues(alpha: 0.3)),
          const SizedBox(height: 16),
          Text(
            'Start a conversation',
            style: Theme.of(context).textTheme.titleMedium?.copyWith(color: Colors.grey[500]),
          ),
          const SizedBox(height: 8),
          Text(
            'Your AI coach is ready to help!',
            style: Theme.of(context).textTheme.bodyMedium?.copyWith(color: Colors.grey[400]),
          ),
        ],
      ),
    );
  }
}
