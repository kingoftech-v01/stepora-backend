import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../core/theme/app_theme.dart';
import '../../services/api_service.dart';
import '../../config/api_constants.dart';

class ConversationListScreen extends ConsumerStatefulWidget {
  const ConversationListScreen({super.key});

  @override
  ConsumerState<ConversationListScreen> createState() => _ConversationListScreenState();
}

class _ConversationListScreenState extends ConsumerState<ConversationListScreen> {
  List<Map<String, dynamic>> _conversations = [];
  bool _isLoading = true;

  @override
  void initState() {
    super.initState();
    _loadConversations();
  }

  Future<void> _loadConversations() async {
    setState(() => _isLoading = true);
    try {
      final api = ref.read(apiServiceProvider);
      final response = await api.get(ApiConstants.conversations);
      final results = response.data['results'] as List? ?? response.data as List? ?? [];
      setState(() {
        _conversations = List<Map<String, dynamic>>.from(results);
        _isLoading = false;
      });
    } catch (_) {
      setState(() => _isLoading = false);
    }
  }

  Future<void> _deleteConversation(String id, int index) async {
    final removed = _conversations[index];
    setState(() => _conversations.removeAt(index));

    try {
      final api = ref.read(apiServiceProvider);
      await api.delete(ApiConstants.conversationDetail(id));
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Conversation deleted')),
        );
      }
    } catch (e) {
      // Restore on failure
      setState(() => _conversations.insert(index, removed));
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Failed to delete: $e')),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Conversations')),
      body: RefreshIndicator(
        onRefresh: _loadConversations,
        child: _isLoading
            ? const Center(child: CircularProgressIndicator())
            : _conversations.isEmpty
                ? Center(
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Icon(Icons.chat_outlined, size: 64, color: Colors.grey[300]),
                        const SizedBox(height: 16),
                        Text(
                          'No conversations yet',
                          style: TextStyle(color: Colors.grey[500], fontSize: 16),
                        ),
                        const SizedBox(height: 8),
                        Text(
                          "Start a conversation from a dream's AI Coach",
                          style: TextStyle(color: Colors.grey[400]),
                        ),
                      ],
                    ),
                  )
                : ListView.builder(
                    padding: const EdgeInsets.all(16),
                    itemCount: _conversations.length,
                    itemBuilder: (context, index) {
                      final conv = _conversations[index];
                      final type = conv['conversation_type'] ?? conv['type'] ?? 'dream_coaching';
                      final id = conv['id'].toString();
                      return Dismissible(
                        key: Key(id),
                        direction: DismissDirection.endToStart,
                        background: Container(
                          alignment: Alignment.centerRight,
                          padding: const EdgeInsets.only(right: 20),
                          margin: const EdgeInsets.only(bottom: 8),
                          decoration: BoxDecoration(
                            color: Colors.red,
                            borderRadius: BorderRadius.circular(12),
                          ),
                          child: const Icon(Icons.delete, color: Colors.white),
                        ),
                        confirmDismiss: (_) async {
                          return await showDialog<bool>(
                            context: context,
                            builder: (ctx) => AlertDialog(
                              title: const Text('Delete Conversation?'),
                              content: const Text('This action cannot be undone.'),
                              actions: [
                                TextButton(
                                  onPressed: () => Navigator.pop(ctx, false),
                                  child: const Text('Cancel'),
                                ),
                                TextButton(
                                  onPressed: () => Navigator.pop(ctx, true),
                                  child: const Text('Delete', style: TextStyle(color: Colors.red)),
                                ),
                              ],
                            ),
                          ) ?? false;
                        },
                        onDismissed: (_) => _deleteConversation(id, index),
                        child: Card(
                          margin: const EdgeInsets.only(bottom: 8),
                          child: ListTile(
                            leading: CircleAvatar(
                              backgroundColor: AppTheme.primaryPurple.withValues(alpha: 0.1),
                              child: Icon(
                                _getTypeIcon(type),
                                color: AppTheme.primaryPurple,
                              ),
                            ),
                            title: Text(
                              conv['title'] ?? _getTypeLabel(type),
                              style: const TextStyle(fontWeight: FontWeight.w600),
                            ),
                            subtitle: Text('${conv['total_messages'] ?? conv['message_count'] ?? 0} messages'),
                            trailing: const Icon(Icons.chevron_right),
                            onTap: () => context.push('/chat/$id'),
                          ),
                        ),
                      );
                    },
                  ),
      ),
    );
  }

  IconData _getTypeIcon(String type) {
    switch (type) {
      case 'dream_creation': return Icons.auto_awesome;
      case 'planning': return Icons.flag;
      case 'motivation': return Icons.favorite;
      case 'check_in': return Icons.psychology;
      case 'buddy_chat': return Icons.people;
      default: return Icons.chat;
    }
  }

  String _getTypeLabel(String type) {
    switch (type) {
      case 'dream_creation': return 'Dream Creation';
      case 'planning': return 'Goal Planning';
      case 'motivation': return 'Motivation';
      case 'check_in': return 'Check In';
      case 'buddy_chat': return 'Buddy Chat';
      default: return 'Conversation';
    }
  }
}
