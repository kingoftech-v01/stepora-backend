import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../core/theme/app_theme.dart';
import '../../providers/auth_provider.dart';
import '../../providers/chat_provider.dart';
import '../../widgets/gradient_background.dart';
import '../../widgets/glass_container.dart';
import '../../widgets/glass_app_bar.dart';
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
  ChatNotifier? _chatNotifier;

  @override
  void initState() {
    super.initState();
    _initChat();
  }

  Future<void> _initChat() async {
    _chatNotifier = ref.read(chatProvider.notifier);
    final token = ref.read(authProvider).token;

    if (widget.conversationId == 'new') {
      final convo = await _chatNotifier!.createConversation();
      _activeConversationId = convo.id;
    } else {
      _activeConversationId = widget.conversationId;
      await _chatNotifier!.loadMessages(widget.conversationId);
    }

    if (_activeConversationId != null && token != null) {
      _chatNotifier!.connectWebSocket(_activeConversationId!, token);
    }
  }

  @override
  void dispose() {
    _chatNotifier?.disconnectWebSocket();
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

  void _copyMessage(String content) {
    Clipboard.setData(ClipboardData(text: content));
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('Message copied'), duration: Duration(seconds: 1)),
    );
  }

  @override
  Widget build(BuildContext context) {
    final chatState = ref.watch(chatProvider);
    final isDark = Theme.of(context).brightness == Brightness.dark;

    WidgetsBinding.instance.addPostFrameCallback((_) => _scrollToBottom());

    return GradientBackground(
      colors: isDark ? AppTheme.gradientChat : AppTheme.gradientChatLight,
      child: Scaffold(
        backgroundColor: Colors.transparent,
        extendBodyBehindAppBar: true,
        appBar: GlassAppBar(
          title: 'AI Coach',
          actions: [
            _ConnectionIndicator(status: chatState.connectionStatus, isDark: isDark),
            IconButton(
              icon: Icon(Icons.refresh, color: isDark ? Colors.white70 : const Color(0xFF1E1B4B)),
              onPressed: () {
                if (_activeConversationId != null) {
                  ref.read(chatProvider.notifier).loadMessages(_activeConversationId!);
                }
              },
            ),
          ],
        ),
        body: SafeArea(
          child: Column(
            children: [
              // Connection status banners
              if (chatState.connectionStatus == ConnectionStatus.reconnecting)
                GlassContainer(
                  margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
                  padding: const EdgeInsets.symmetric(vertical: 6, horizontal: 12),
                  opacity: 0.2,
                  child: Row(mainAxisAlignment: MainAxisAlignment.center, children: [
                    SizedBox(width: 12, height: 12, child: CircularProgressIndicator(strokeWidth: 1.5, color: Colors.orange.shade400)),
                    const SizedBox(width: 8),
                    Text('Reconnecting...', style: TextStyle(fontSize: 12, color: Colors.orange.shade400)),
                  ]),
                ).animate().fadeIn(duration: 200.ms),

              if (chatState.connectionStatus == ConnectionStatus.disconnected && _activeConversationId != null)
                GlassContainer(
                  margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
                  padding: const EdgeInsets.symmetric(vertical: 6, horizontal: 12),
                  opacity: 0.2,
                  child: Row(mainAxisAlignment: MainAxisAlignment.center, children: [
                    Icon(Icons.cloud_off, size: 14, color: Colors.red.shade400),
                    const SizedBox(width: 8),
                    Text('Disconnected', style: TextStyle(fontSize: 12, color: Colors.red.shade400)),
                  ]),
                ).animate().fadeIn(duration: 200.ms),

              // Messages
              Expanded(
                child: chatState.messages.isEmpty && !chatState.isLoading
                    ? _buildEmptyChat(isDark)
                    : ListView.builder(
                        controller: _scrollController,
                        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                        itemCount: chatState.messages.length + (chatState.streamingContent.isNotEmpty ? 1 : 0),
                        itemBuilder: (context, index) {
                          if (index < chatState.messages.length) {
                            final message = chatState.messages[index];
                            return GestureDetector(
                              onLongPress: () => _copyMessage(message.content),
                              child: ChatBubble(
                                content: message.content,
                                isUser: message.isUser,
                                timestamp: message.createdAt,
                              ),
                            ).animate().fadeIn(duration: 250.ms).slideX(begin: message.isUser ? 0.05 : -0.05, end: 0);
                          } else {
                            return ChatBubble(
                              content: chatState.streamingContent,
                              isUser: false,
                              isStreaming: true,
                            ).animate().fadeIn(duration: 200.ms);
                          }
                        },
                      ),
              ),

              // Suggestion chips
              if (chatState.messages.isEmpty)
                Padding(
                  padding: const EdgeInsets.only(bottom: 4),
                  child: SuggestionChips(
                    suggestions: const [
                      'Help me plan my goals',
                      'What should I focus on today?',
                      'I need motivation',
                      'Review my progress',
                    ],
                    onSelected: _sendMessage,
                  ),
                ),

              ChatInput(onSend: _sendMessage),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildEmptyChat(bool isDark) {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Container(
            padding: const EdgeInsets.all(20),
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              color: AppTheme.primaryPurple.withValues(alpha: 0.1),
            ),
            child: Icon(Icons.chat_bubble_outline, size: 48, color: AppTheme.primaryPurple.withValues(alpha: 0.5)),
          ).animate().fadeIn(duration: 500.ms).scale(begin: const Offset(0.8, 0.8), end: const Offset(1, 1)),
          const SizedBox(height: 20),
          Text('Start a conversation', style: TextStyle(fontSize: 18, fontWeight: FontWeight.w600, color: isDark ? Colors.white70 : Colors.grey[600]))
            .animate().fadeIn(duration: 500.ms, delay: 100.ms),
          const SizedBox(height: 8),
          Text('Your AI coach is ready to help!', style: TextStyle(color: isDark ? Colors.white38 : Colors.grey[600]))
            .animate().fadeIn(duration: 500.ms, delay: 200.ms),
        ],
      ),
    );
  }
}

class _ConnectionIndicator extends StatelessWidget {
  final ConnectionStatus status;
  final bool isDark;
  const _ConnectionIndicator({required this.status, required this.isDark});

  @override
  Widget build(BuildContext context) {
    final Color color;
    final String tooltip;
    switch (status) {
      case ConnectionStatus.connected:
        color = Colors.green;
        tooltip = 'Connected';
      case ConnectionStatus.connecting:
        color = Colors.orange;
        tooltip = 'Connecting';
      case ConnectionStatus.reconnecting:
        color = Colors.orange;
        tooltip = 'Reconnecting';
      case ConnectionStatus.disconnected:
        color = Colors.red;
        tooltip = 'Disconnected';
    }
    return Tooltip(
      message: tooltip,
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 8),
        child: Container(
          width: 10,
          height: 10,
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            color: color,
            boxShadow: [BoxShadow(color: color.withValues(alpha: 0.5), blurRadius: 6)],
          ),
        ),
      ),
    );
  }
}
