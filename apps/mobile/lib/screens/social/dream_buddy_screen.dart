import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../core/theme/app_theme.dart';
import '../../services/api_service.dart';

class DreamBuddyScreen extends ConsumerStatefulWidget {
  const DreamBuddyScreen({super.key});

  @override
  ConsumerState<DreamBuddyScreen> createState() => _DreamBuddyScreenState();
}

class _DreamBuddyScreenState extends ConsumerState<DreamBuddyScreen> {
  Map<String, dynamic>? _currentBuddy;
  List<Map<String, dynamic>> _suggestions = [];
  bool _isLoading = true;

  @override
  void initState() {
    super.initState();
    _loadData();
  }

  Future<void> _loadData() async {
    setState(() => _isLoading = true);
    try {
      final api = ref.read(apiServiceProvider);
      final response = await api.get('/buddies/');
      final results = response.data['results'] as List? ?? response.data as List? ?? [];
      if (results.isNotEmpty) {
        final active = results.where((b) => b['status'] == 'active').toList();
        if (active.isNotEmpty) _currentBuddy = active.first;
      }
      try {
        final sugResponse = await api.get('/buddies/find_match/');
        _suggestions = List<Map<String, dynamic>>.from(sugResponse.data['suggestions'] ?? []);
      } catch (_) {}
      setState(() => _isLoading = false);
    } catch (_) {
      setState(() => _isLoading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_isLoading) {
      return Scaffold(
        appBar: AppBar(title: const Text('Dream Buddy')),
        body: const Center(child: CircularProgressIndicator()),
      );
    }

    return Scaffold(
      appBar: AppBar(title: const Text('Dream Buddy')),
      body: RefreshIndicator(
        onRefresh: _loadData,
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            if (_currentBuddy != null) ...[
              Text(
                'Your Buddy',
                style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.bold),
              ),
              const SizedBox(height: 8),
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Row(
                    children: [
                      CircleAvatar(
                        radius: 30,
                        backgroundColor: AppTheme.primaryPurple,
                        child: const Icon(Icons.person, color: Colors.white, size: 30),
                      ),
                      const SizedBox(width: 16),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              _currentBuddy!['user2_name'] ?? _currentBuddy!['user1_name'] ?? 'Buddy',
                              style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 16),
                            ),
                            const SizedBox(height: 4),
                            Text(
                              'Compatibility: ${(_currentBuddy!['compatibility_score'] ?? 0)}%',
                              style: TextStyle(color: AppTheme.accent),
                            ),
                          ],
                        ),
                      ),
                      Column(
                        children: [
                          IconButton(
                            icon: const Icon(Icons.chat_outlined),
                            tooltip: 'Chat with buddy',
                            onPressed: () {
                              final convId = _currentBuddy!['conversation_id']?.toString();
                              if (convId != null) {
                                context.push('/buddy-chat/$convId');
                              } else {
                                ScaffoldMessenger.of(context).showSnackBar(
                                  const SnackBar(content: Text('No chat available yet')),
                                );
                              }
                            },
                          ),
                          IconButton(
                            icon: const Icon(Icons.favorite_outline),
                            tooltip: 'Send encouragement',
                            onPressed: () {
                              final msgController = TextEditingController(text: 'Keep going, you got this!');
                              showDialog(
                                context: context,
                                builder: (ctx) => AlertDialog(
                                  title: const Text('Send Encouragement'),
                                  content: TextField(
                                    controller: msgController,
                                    maxLines: 3,
                                    decoration: const InputDecoration(
                                      labelText: 'Message',
                                      border: OutlineInputBorder(),
                                    ),
                                  ),
                                  actions: [
                                    TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Cancel')),
                                    FilledButton(
                                      onPressed: () async {
                                        Navigator.pop(ctx);
                                        try {
                                          final api = ref.read(apiServiceProvider);
                                          await api.post(
                                            '/buddies/${_currentBuddy!['id']}/encourage/',
                                            data: {'message': msgController.text.trim()},
                                          );
                                          if (mounted) {
                                            ScaffoldMessenger.of(context).showSnackBar(
                                              const SnackBar(content: Text('Encouragement sent!')),
                                            );
                                          }
                                        } catch (e) {
                                          if (mounted) {
                                            ScaffoldMessenger.of(context).showSnackBar(
                                              SnackBar(content: Text('Error: $e')),
                                            );
                                          }
                                        }
                                      },
                                      child: const Text('Send'),
                                    ),
                                  ],
                                ),
                              );
                            },
                          ),
                        ],
                      ),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 24),
            ] else ...[
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(24),
                  child: Column(
                    children: [
                      Icon(Icons.people_outline, size: 64, color: AppTheme.primaryPurple.withValues(alpha: 0.3)),
                      const SizedBox(height: 16),
                      Text(
                        'Find Your Dream Buddy',
                        style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.bold),
                      ),
                      const SizedBox(height: 8),
                      Text(
                        'Get matched with someone who shares your goals!',
                        style: TextStyle(color: Colors.grey[600]),
                        textAlign: TextAlign.center,
                      ),
                      const SizedBox(height: 16),
                      FilledButton.icon(
                        onPressed: () async {
                          final api = ref.read(apiServiceProvider);
                          try {
                            await api.post('/buddies/find_match/');
                            _loadData();
                          } catch (_) {}
                        },
                        icon: const Icon(Icons.search),
                        label: const Text('Find Match'),
                        style: FilledButton.styleFrom(backgroundColor: AppTheme.primaryPurple),
                      ),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 24),
            ],
            if (_suggestions.isNotEmpty) ...[
              Text(
                'Suggested Buddies',
                style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.bold),
              ),
              const SizedBox(height: 8),
              ..._suggestions.map((s) => Card(
                margin: const EdgeInsets.only(bottom: 8),
                child: ListTile(
                  leading: CircleAvatar(
                    backgroundColor: AppTheme.primaryPurple.withValues(alpha: 0.1),
                    child: Text(
                      (s['display_name'] ?? 'U')[0].toUpperCase(),
                      style: TextStyle(color: AppTheme.primaryPurple),
                    ),
                  ),
                  title: Text(s['display_name'] ?? ''),
                  subtitle: Text('${s['shared_categories']?.join(', ') ?? 'Common interests'}'),
                  trailing: FilledButton(
                    onPressed: () async {
                      try {
                        final api = ref.read(apiServiceProvider);
                        await api.post('/buddies/pair/', data: {'partner_id': s['id']});
                        if (mounted) {
                          ScaffoldMessenger.of(context).showSnackBar(
                            const SnackBar(content: Text('Buddy request sent!')),
                          );
                          _loadData();
                        }
                      } catch (e) {
                        if (mounted) {
                          ScaffoldMessenger.of(context).showSnackBar(
                            SnackBar(content: Text('Error: $e')),
                          );
                        }
                      }
                    },
                    style: FilledButton.styleFrom(backgroundColor: AppTheme.primaryPurple),
                    child: const Text('Request'),
                  ),
                ),
              )),
            ],
          ],
        ),
      ),
    );
  }
}
