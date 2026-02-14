import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../core/theme/app_theme.dart';
import '../../config/api_constants.dart';
import '../../services/api_service.dart';
import '../../services/websocket_service.dart';
import '../../widgets/gradient_background.dart';
import '../../widgets/glass_container.dart';
import '../../widgets/glass_app_bar.dart';
import '../../widgets/loading_shimmer.dart';

class BuddyChatScreen extends ConsumerStatefulWidget {
  final String conversationId;
  const BuddyChatScreen({super.key, required this.conversationId});

  @override
  ConsumerState<BuddyChatScreen> createState() => _BuddyChatScreenState();
}

class _BuddyChatScreenState extends ConsumerState<BuddyChatScreen> {
  final _controller = TextEditingController();
  final _scrollController = ScrollController();
  List<Map<String, dynamic>> _messages = [];
  bool _isLoading = true;
  WebSocketService? _ws;
  StreamSubscription? _wsSubscription;

  @override
  void initState() {
    super.initState();
    _loadMessages();
    _connectWebSocket();
  }

  @override
  void dispose() {
    _controller.dispose();
    _scrollController.dispose();
    _wsSubscription?.cancel();
    _ws?.disconnect();
    super.dispose();
  }

  Future<void> _loadMessages() async {
    try {
      final api = ref.read(apiServiceProvider);
      final response = await api.get(ApiConstants.conversationMessages(widget.conversationId));
      final results = response.data['results'] as List? ?? response.data as List? ?? [];
      setState(() {
        _messages = List<Map<String, dynamic>>.from(results.reversed);
        _isLoading = false;
      });
      _scrollToBottom();
    } catch (_) {
      setState(() => _isLoading = false);
    }
  }

  Future<void> _connectWebSocket() async {
    final api = ref.read(apiServiceProvider);
    final token = await api.getToken();
    if (token == null) return;
    _ws = WebSocketService();
    _ws!.connect(widget.conversationId, token);
    _wsSubscription = _ws!.messageStream.listen((data) {
      if (data['type'] == 'chat_message' || data['type'] == 'message') {
        setState(() { _messages.add(data['message'] ?? data); });
        _scrollToBottom();
      }
    });
  }

  void _scrollToBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scrollController.hasClients) {
        _scrollController.animateTo(
          _scrollController.position.maxScrollExtent,
          duration: const Duration(milliseconds: 300),
          curve: Curves.easeOut,
        );
      }
    });
  }

  void _sendMessage() {
    final text = _controller.text.trim();
    if (text.isEmpty) return;
    _ws?.sendMessage(text);
    _controller.clear();
  }

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;

    return GradientBackground(
      colors: isDark ? AppTheme.gradientChat : AppTheme.gradientChatLight,
      child: Scaffold(
        backgroundColor: Colors.transparent,
        extendBodyBehindAppBar: true,
        appBar: const GlassAppBar(title: 'Buddy Chat'),
        body: SafeArea(
          child: Column(
            children: [
              Expanded(
                child: _isLoading
                    ? const Center(child: LoadingShimmer())
                    : _messages.isEmpty
                        ? Center(
                            child: Column(
                              mainAxisAlignment: MainAxisAlignment.center,
                              children: [
                                Container(
                                  padding: const EdgeInsets.all(20),
                                  decoration: BoxDecoration(
                                    shape: BoxShape.circle,
                                    color: AppTheme.primaryPurple.withValues(alpha: 0.1),
                                  ),
                                  child: Icon(Icons.people_outline, size: 48, color: isDark ? Colors.white38 : Colors.grey[600]),
                                ).animate().fadeIn(duration: 500.ms).scale(begin: const Offset(0.8, 0.8), end: const Offset(1, 1)),
                                const SizedBox(height: 16),
                                Text('Start chatting with your buddy!', style: TextStyle(color: isDark ? Colors.white54 : Colors.grey[700]))
                                  .animate().fadeIn(duration: 500.ms, delay: 100.ms),
                              ],
                            ),
                          )
                        : ListView.builder(
                            controller: _scrollController,
                            padding: const EdgeInsets.all(16),
                            itemCount: _messages.length,
                            itemBuilder: (context, index) {
                              final msg = _messages[index];
                              final isMe = msg['is_mine'] == true || msg['is_self'] == true;
                              return Align(
                                alignment: isMe ? Alignment.centerRight : Alignment.centerLeft,
                                child: Container(
                                  margin: const EdgeInsets.only(bottom: 8),
                                  constraints: BoxConstraints(maxWidth: MediaQuery.of(context).size.width * 0.75),
                                  child: ClipRRect(
                                    borderRadius: BorderRadius.only(
                                      topLeft: const Radius.circular(16),
                                      topRight: const Radius.circular(16),
                                      bottomLeft: Radius.circular(isMe ? 16 : 4),
                                      bottomRight: Radius.circular(isMe ? 4 : 16),
                                    ),
                                    child: GlassContainer(
                                      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
                                      opacity: isMe ? 0.25 : (isDark ? 0.12 : 0.2),
                                      borderRadius: 0,
                                      child: Text(
                                        msg['content'] ?? msg['text'] ?? '',
                                        style: TextStyle(color: isDark ? Colors.white : const Color(0xFF1E1B4B)),
                                      ),
                                    ),
                                  ),
                                ),
                              ).animate().fadeIn(duration: 250.ms).slideX(begin: isMe ? 0.05 : -0.05, end: 0);
                            },
                          ),
              ),
              // Glass input bar
              GlassContainer(
                margin: const EdgeInsets.fromLTRB(12, 0, 12, 8),
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 6),
                opacity: isDark ? 0.15 : 0.3,
                child: Row(
                  children: [
                    Expanded(
                      child: TextField(
                        controller: _controller,
                        style: TextStyle(color: isDark ? Colors.white : const Color(0xFF1E1B4B)),
                        decoration: InputDecoration(
                          hintText: 'Type a message...',
                          hintStyle: TextStyle(color: isDark ? Colors.white30 : Colors.grey),
                          border: InputBorder.none,
                          contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                        ),
                        textInputAction: TextInputAction.send,
                        onSubmitted: (_) => _sendMessage(),
                      ),
                    ),
                    GestureDetector(
                      onTap: _sendMessage,
                      child: Container(
                        padding: const EdgeInsets.all(10),
                        decoration: BoxDecoration(
                          gradient: const LinearGradient(colors: [AppTheme.primaryPurple, Color(0xFF8B5CF6)]),
                          borderRadius: BorderRadius.circular(12),
                          boxShadow: [BoxShadow(color: AppTheme.primaryPurple.withValues(alpha: 0.3), blurRadius: 8)],
                        ),
                        child: const Icon(Icons.send, color: Colors.white, size: 20),
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
