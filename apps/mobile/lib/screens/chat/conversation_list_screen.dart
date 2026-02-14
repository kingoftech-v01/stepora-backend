import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../core/theme/app_theme.dart';
import '../../services/api_service.dart';
import '../../config/api_constants.dart';
import '../../widgets/gradient_background.dart';
import '../../widgets/glass_container.dart';
import '../../widgets/glass_app_bar.dart';
import '../../widgets/animated_list_item.dart';
import '../../widgets/loading_shimmer.dart';

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
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Conversation deleted')));
    } catch (e) {
      setState(() => _conversations.insert(index, removed));
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Failed to delete: $e')));
    }
  }

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;

    return GradientBackground(
      colors: isDark ? AppTheme.gradientChat : AppTheme.gradientChatLight,
      child: Scaffold(
        backgroundColor: Colors.transparent,
        extendBodyBehindAppBar: true,
        appBar: const GlassAppBar(title: 'Conversations'),
        body: RefreshIndicator(
          onRefresh: _loadConversations,
          child: _isLoading
              ? const Center(child: LoadingShimmer())
              : _conversations.isEmpty
                  ? ListView(children: [
                      const SizedBox(height: 120),
                      Center(
                        child: Column(
                          children: [
                            Container(
                              padding: const EdgeInsets.all(20),
                              decoration: BoxDecoration(
                                shape: BoxShape.circle,
                                color: AppTheme.primaryPurple.withValues(alpha: 0.1),
                              ),
                              child: Icon(Icons.chat_outlined, size: 48, color: isDark ? Colors.white24 : Colors.grey[600]),
                            ).animate().fadeIn(duration: 500.ms).scale(begin: const Offset(0.8, 0.8), end: const Offset(1, 1)),
                            const SizedBox(height: 16),
                            Text('No conversations yet', style: TextStyle(color: isDark ? Colors.white54 : Colors.grey[700], fontSize: 16))
                              .animate().fadeIn(duration: 500.ms, delay: 100.ms),
                            const SizedBox(height: 8),
                            Text("Start a conversation from a dream's AI Coach", style: TextStyle(color: isDark ? Colors.white38 : Colors.grey[600]))
                              .animate().fadeIn(duration: 500.ms, delay: 200.ms),
                          ],
                        ),
                      ),
                    ])
                  : ListView.builder(
                      padding: EdgeInsets.fromLTRB(16, MediaQuery.of(context).padding.top + kToolbarHeight + 8, 16, 32),
                      itemCount: _conversations.length,
                      itemBuilder: (context, index) {
                        final conv = _conversations[index];
                        final type = conv['conversation_type'] ?? conv['type'] ?? 'dream_coaching';
                        final id = conv['id'].toString();
                        return AnimatedListItem(
                          index: index,
                          child: Dismissible(
                            key: Key(id),
                            direction: DismissDirection.endToStart,
                            background: GlassContainer(
                              margin: const EdgeInsets.only(bottom: 10),
                              padding: const EdgeInsets.only(right: 20),
                              opacity: 0.2,
                              child: const Align(
                                alignment: Alignment.centerRight,
                                child: Icon(Icons.delete_outline, color: Colors.red),
                              ),
                            ),
                            confirmDismiss: (_) async {
                              return await showDialog<bool>(
                                context: context,
                                builder: (ctx) => AlertDialog(
                                  backgroundColor: isDark ? const Color(0xFF1E1B4B) : Colors.white,
                                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
                                  title: Text('Delete Conversation?', style: TextStyle(color: isDark ? Colors.white : const Color(0xFF1E1B4B))),
                                  content: Text('This action cannot be undone.', style: TextStyle(color: isDark ? Colors.white70 : Colors.grey[700])),
                                  actions: [
                                    TextButton(onPressed: () => Navigator.pop(ctx, false), child: Text('Cancel', style: TextStyle(color: isDark ? Colors.white54 : Colors.grey))),
                                    TextButton(onPressed: () => Navigator.pop(ctx, true), child: const Text('Delete', style: TextStyle(color: Colors.red))),
                                  ],
                                ),
                              ) ?? false;
                            },
                            onDismissed: (_) => _deleteConversation(id, index),
                            child: GestureDetector(
                              onTap: () => context.push('/chat/$id'),
                              child: GlassContainer(
                                margin: const EdgeInsets.only(bottom: 10),
                                padding: const EdgeInsets.all(16),
                                opacity: isDark ? 0.12 : 0.25,
                                child: Row(children: [
                                  Container(
                                    padding: const EdgeInsets.all(10),
                                    decoration: BoxDecoration(
                                      color: AppTheme.primaryPurple.withValues(alpha: 0.12),
                                      borderRadius: BorderRadius.circular(12),
                                    ),
                                    child: Icon(_getTypeIcon(type), color: AppTheme.primaryPurple, size: 22),
                                  ),
                                  const SizedBox(width: 14),
                                  Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                                    Text(conv['title'] ?? _getTypeLabel(type),
                                      style: TextStyle(fontWeight: FontWeight.w600, fontSize: 15, color: isDark ? Colors.white : const Color(0xFF1E1B4B)),
                                    ),
                                    const SizedBox(height: 3),
                                    Text('${conv['total_messages'] ?? conv['message_count'] ?? 0} messages',
                                      style: TextStyle(fontSize: 13, color: isDark ? Colors.white54 : Colors.grey[600]),
                                    ),
                                  ])),
                                  Icon(Icons.chevron_right, color: isDark ? Colors.white24 : Colors.grey[600]),
                                ]),
                              ),
                            ),
                          ),
                        );
                      },
                    ),
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
