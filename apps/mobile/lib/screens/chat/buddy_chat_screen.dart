import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../core/theme/app_theme.dart';
import '../../config/api_constants.dart';
import '../../services/api_service.dart';
import '../../services/websocket_service.dart';

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
        setState(() {
          _messages.add(data['message'] ?? data);
        });
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
    return Scaffold(
      appBar: AppBar(
        title: const Text('Buddy Chat'),
      ),
      body: Column(
        children: [
          Expanded(
            child: _isLoading
                ? const Center(child: CircularProgressIndicator())
                : _messages.isEmpty
                    ? Center(
                        child: Column(
                          mainAxisAlignment: MainAxisAlignment.center,
                          children: [
                            Icon(Icons.chat_outlined, size: 64, color: Colors.grey[300]),
                            const SizedBox(height: 16),
                            Text(
                              'Start chatting with your buddy!',
                              style: TextStyle(color: Colors.grey[500]),
                            ),
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
                              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
                              constraints: BoxConstraints(
                                maxWidth: MediaQuery.of(context).size.width * 0.75,
                              ),
                              decoration: BoxDecoration(
                                color: isMe
                                    ? AppTheme.primaryPurple
                                    : Theme.of(context).colorScheme.surfaceContainerHighest,
                                borderRadius: BorderRadius.circular(16),
                              ),
                              child: Text(
                                msg['content'] ?? msg['text'] ?? '',
                                style: TextStyle(
                                  color: isMe ? Colors.white : null,
                                ),
                              ),
                            ),
                          );
                        },
                      ),
          ),
          Container(
            padding: const EdgeInsets.all(8),
            decoration: BoxDecoration(
              color: Theme.of(context).colorScheme.surface,
              border: Border(
                top: BorderSide(color: Colors.grey.withValues(alpha: 0.2)),
              ),
            ),
            child: SafeArea(
              child: Row(
                children: [
                  Expanded(
                    child: TextField(
                      controller: _controller,
                      decoration: const InputDecoration(
                        hintText: 'Type a message...',
                        border: OutlineInputBorder(),
                        contentPadding: EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                      ),
                      textInputAction: TextInputAction.send,
                      onSubmitted: (_) => _sendMessage(),
                    ),
                  ),
                  const SizedBox(width: 8),
                  IconButton(
                    onPressed: _sendMessage,
                    icon: const Icon(Icons.send),
                    color: AppTheme.primaryPurple,
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}
