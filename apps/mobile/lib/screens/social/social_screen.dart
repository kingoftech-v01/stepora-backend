import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../core/theme/app_theme.dart';
import '../../services/api_service.dart';

class SocialScreen extends ConsumerStatefulWidget {
  const SocialScreen({super.key});

  @override
  ConsumerState<SocialScreen> createState() => _SocialScreenState();
}

class _SocialScreenState extends ConsumerState<SocialScreen> {
  List<Map<String, dynamic>> _feed = [];
  bool _isLoading = true;

  @override
  void initState() {
    super.initState();
    _loadFeed();
  }

  Future<void> _loadFeed() async {
    setState(() => _isLoading = true);
    try {
      final api = ref.read(apiServiceProvider);
      final response = await api.get('/social/feed/');
      final results = response.data['results'] as List? ?? response.data as List? ?? [];
      setState(() {
        _feed = List<Map<String, dynamic>>.from(results);
        _isLoading = false;
      });
    } catch (_) {
      setState(() => _isLoading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Social'),
        actions: [
          IconButton(
            icon: const Icon(Icons.group_outlined),
            onPressed: () => context.push('/circles'),
          ),
          IconButton(
            icon: const Icon(Icons.people_alt_outlined),
            onPressed: () => context.push('/buddy'),
          ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: _loadFeed,
        child: _isLoading
            ? const Center(child: CircularProgressIndicator())
            : _feed.isEmpty
                ? _buildEmptyFeed(context)
                : ListView.builder(
                    padding: const EdgeInsets.all(16),
                    itemCount: _feed.length,
                    itemBuilder: (context, index) => _buildFeedItem(_feed[index]),
                  ),
      ),
      floatingActionButton: FloatingActionButton(
        onPressed: () => context.push('/circles'),
        backgroundColor: AppTheme.primaryPurple,
        foregroundColor: Colors.white,
        child: const Icon(Icons.group_add),
      ),
    );
  }

  Widget _buildEmptyFeed(BuildContext context) {
    return ListView(
      children: [
        const SizedBox(height: 100),
        Center(
          child: Column(
            children: [
              Icon(Icons.people_outline, size: 64, color: Colors.grey[300]),
              const SizedBox(height: 16),
              Text('No activity yet', style: Theme.of(context).textTheme.titleMedium?.copyWith(color: Colors.grey[500])),
              const SizedBox(height: 8),
              Text('Join circles and find a buddy!', style: TextStyle(color: Colors.grey[400])),
              const SizedBox(height: 24),
              Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  FilledButton.icon(
                    onPressed: () => context.push('/circles'),
                    icon: const Icon(Icons.group),
                    label: const Text('Circles'),
                  ),
                  const SizedBox(width: 12),
                  OutlinedButton.icon(
                    onPressed: () => context.push('/buddy'),
                    icon: const Icon(Icons.people),
                    label: const Text('Find Buddy'),
                  ),
                ],
              ),
            ],
          ),
        ),
      ],
    );
  }

  Widget _buildFeedItem(Map<String, dynamic> item) {
    final type = item['type'] ?? '';
    final user = item['user'] ?? {};
    final data = item['data'] ?? {};

    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                CircleAvatar(
                  radius: 20,
                  backgroundColor: AppTheme.primaryPurple.withValues(alpha: 0.1),
                  child: Text(
                    (user['display_name'] ?? 'U')[0].toUpperCase(),
                    style: TextStyle(color: AppTheme.primaryPurple, fontWeight: FontWeight.bold),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(user['display_name'] ?? 'User', style: const TextStyle(fontWeight: FontWeight.w600)),
                      Text(_getFeedText(type, data), style: TextStyle(color: Colors.grey[600], fontSize: 13)),
                    ],
                  ),
                ),
                Icon(_getFeedIcon(type), color: AppTheme.accent),
              ],
            ),
            if (data['content'] != null) ...[
              const SizedBox(height: 8),
              Text(data['content']),
            ],
          ],
        ),
      ),
    );
  }

  String _getFeedText(String type, Map<String, dynamic> data) {
    switch (type) {
      case 'dream_created': return 'created a new dream';
      case 'task_completed': return 'completed a task';
      case 'level_up': return 'reached level ${data['level']}';
      case 'streak': return '${data['days']} day streak!';
      default: return 'was active';
    }
  }

  IconData _getFeedIcon(String type) {
    switch (type) {
      case 'dream_created': return Icons.auto_awesome;
      case 'task_completed': return Icons.check_circle;
      case 'level_up': return Icons.arrow_upward;
      case 'streak': return Icons.local_fire_department;
      default: return Icons.star;
    }
  }
}
