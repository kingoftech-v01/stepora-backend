import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../core/theme/app_theme.dart';
import '../../services/api_service.dart';

class CircleDetailScreen extends ConsumerStatefulWidget {
  final String circleId;
  const CircleDetailScreen({super.key, required this.circleId});

  @override
  ConsumerState<CircleDetailScreen> createState() => _CircleDetailScreenState();
}

class _CircleDetailScreenState extends ConsumerState<CircleDetailScreen> with SingleTickerProviderStateMixin {
  Map<String, dynamic>? _circle;
  List<Map<String, dynamic>> _members = [];
  List<Map<String, dynamic>> _posts = [];
  List<Map<String, dynamic>> _challenges = [];
  bool _isLoading = true;
  bool _isMember = false;
  late TabController _tabController;
  final _postController = TextEditingController();

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 3, vsync: this);
    _loadCircle();
  }

  @override
  void dispose() {
    _tabController.dispose();
    _postController.dispose();
    super.dispose();
  }

  Future<void> _loadCircle() async {
    try {
      final api = ref.read(apiServiceProvider);
      final response = await api.get('/circles/${widget.circleId}/');
      setState(() {
        _circle = response.data;
        _members = List<Map<String, dynamic>>.from(response.data['members'] ?? []);
        _challenges = List<Map<String, dynamic>>.from(response.data['challenges'] ?? []);
        _isMember = response.data['is_member'] == true || response.data['isMember'] == true;
        _isLoading = false;
      });
      if (_isMember) _loadPosts();
    } catch (_) {
      setState(() => _isLoading = false);
    }
  }

  Future<void> _loadPosts() async {
    try {
      final api = ref.read(apiServiceProvider);
      final response = await api.get('/circles/${widget.circleId}/feed/');
      final results = response.data['results'] as List? ?? response.data as List? ?? [];
      setState(() {
        _posts = List<Map<String, dynamic>>.from(results);
      });
    } catch (_) {}
  }

  Future<void> _leaveCircle() async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Leave Circle?'),
        content: const Text('You will no longer see posts or participate in challenges.'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancel')),
          TextButton(onPressed: () => Navigator.pop(ctx, true), child: const Text('Leave')),
        ],
      ),
    );
    if (confirmed != true) return;
    try {
      final api = ref.read(apiServiceProvider);
      await api.post('/circles/${widget.circleId}/leave/');
      if (mounted) context.pop();
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Error: $e')));
      }
    }
  }

  Future<void> _joinCircle() async {
    try {
      final api = ref.read(apiServiceProvider);
      await api.post('/circles/${widget.circleId}/join/');
      _loadCircle();
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Error: $e')));
      }
    }
  }

  Future<void> _showInviteDialog() async {
    showModalBottomSheet(
      context: context,
      builder: (ctx) => SafeArea(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Padding(
              padding: EdgeInsets.all(16),
              child: Text(
                'Invite to Circle',
                style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
              ),
            ),
            ListTile(
              leading: const Icon(Icons.link),
              title: const Text('Generate Invite Link'),
              subtitle: const Text('Share a link anyone can use to join'),
              onTap: () async {
                Navigator.pop(ctx);
                try {
                  final api = ref.read(apiServiceProvider);
                  final response = await api.post('/circles/${widget.circleId}/invite-link/');
                  final link = response.data['invite_link'] ?? response.data['invite_url'] ?? '';
                  if (mounted && link.toString().isNotEmpty) {
                    showDialog(
                      context: context,
                      builder: (dlgCtx) => AlertDialog(
                        title: const Text('Invite Link'),
                        content: SelectableText(link.toString()),
                        actions: [
                          TextButton(
                            onPressed: () {
                              Clipboard.setData(ClipboardData(text: link.toString()));
                              Navigator.pop(dlgCtx);
                              ScaffoldMessenger.of(context).showSnackBar(
                                const SnackBar(content: Text('Link copied to clipboard!')),
                              );
                            },
                            child: const Text('Copy'),
                          ),
                          TextButton(
                            onPressed: () => Navigator.pop(dlgCtx),
                            child: const Text('Close'),
                          ),
                        ],
                      ),
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
            ),
            ListTile(
              leading: const Icon(Icons.person_add),
              title: const Text('Invite by Username'),
              subtitle: const Text('Send a direct invitation'),
              onTap: () {
                Navigator.pop(ctx);
                final controller = TextEditingController();
                showDialog(
                  context: context,
                  builder: (dlgCtx) => AlertDialog(
                    title: const Text('Invite User'),
                    content: TextField(
                      controller: controller,
                      decoration: const InputDecoration(
                        labelText: 'Username or Email',
                        border: OutlineInputBorder(),
                      ),
                    ),
                    actions: [
                      TextButton(
                        onPressed: () => Navigator.pop(dlgCtx),
                        child: const Text('Cancel'),
                      ),
                      FilledButton(
                        onPressed: () async {
                          final value = controller.text.trim();
                          if (value.isEmpty) return;
                          Navigator.pop(dlgCtx);
                          try {
                            final api = ref.read(apiServiceProvider);
                            await api.post('/circles/${widget.circleId}/invite/', data: {
                              'username': value,
                            });
                            if (mounted) {
                              ScaffoldMessenger.of(context).showSnackBar(
                                const SnackBar(content: Text('Invitation sent!')),
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
                        child: const Text('Invite'),
                      ),
                    ],
                  ),
                );
              },
            ),
            const SizedBox(height: 16),
          ],
        ),
      ),
    );
  }

  Future<void> _submitPost() async {
    if (_postController.text.trim().isEmpty) return;
    try {
      final api = ref.read(apiServiceProvider);
      await api.post('/circles/${widget.circleId}/posts/', data: {
        'content': _postController.text.trim(),
      });
      _postController.clear();
      _loadPosts();
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Error: $e')));
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_isLoading) {
      return Scaffold(appBar: AppBar(), body: const Center(child: CircularProgressIndicator()));
    }

    return Scaffold(
      appBar: AppBar(
        title: Text(_circle?['name'] ?? 'Circle'),
        actions: [
          if (_isMember) ...[
            IconButton(
              icon: const Icon(Icons.person_add),
              tooltip: 'Invite',
              onPressed: _showInviteDialog,
            ),
            IconButton(
              icon: const Icon(Icons.exit_to_app),
              tooltip: 'Leave Circle',
              onPressed: _leaveCircle,
            ),
          ] else
            TextButton(
              onPressed: _joinCircle,
              child: const Text('Join'),
            ),
        ],
        bottom: TabBar(
          controller: _tabController,
          tabs: const [
            Tab(text: 'Members'),
            Tab(text: 'Feed'),
            Tab(text: 'Challenges'),
          ],
        ),
      ),
      body: Column(
        children: [
          Card(
            margin: const EdgeInsets.all(16),
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    _circle?['name'] ?? '',
                    style: Theme.of(context).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.bold),
                  ),
                  if (_circle?['description'] != null) ...[
                    const SizedBox(height: 8),
                    Text(_circle!['description'], style: TextStyle(color: Colors.grey[600])),
                  ],
                  const SizedBox(height: 12),
                  Row(
                    children: [
                      Chip(
                        label: Text('${_circle?['category'] ?? 'General'}'),
                        backgroundColor: AppTheme.primaryPurple.withValues(alpha: 0.1),
                      ),
                      const SizedBox(width: 8),
                      Text('${_members.length} members', style: TextStyle(color: Colors.grey[600])),
                    ],
                  ),
                ],
              ),
            ),
          ),
          Expanded(
            child: TabBarView(
              controller: _tabController,
              children: [
                _buildMembersTab(),
                _buildFeedTab(),
                _buildChallengesTab(),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildMembersTab() {
    if (_members.isEmpty) {
      return const Center(child: Text('No members yet'));
    }
    return ListView.builder(
      padding: const EdgeInsets.symmetric(horizontal: 16),
      itemCount: _members.length,
      itemBuilder: (context, index) {
        final member = _members[index];
        return Card(
          margin: const EdgeInsets.only(bottom: 8),
          child: ListTile(
            leading: CircleAvatar(
              backgroundColor: AppTheme.primaryPurple.withValues(alpha: 0.1),
              child: Text(
                (member['display_name'] ?? member['username'] ?? 'U')[0].toUpperCase(),
                style: TextStyle(color: AppTheme.primaryPurple),
              ),
            ),
            title: Text(member['display_name'] ?? member['username'] ?? member['email'] ?? ''),
            subtitle: Text(member['role'] ?? 'member'),
            trailing: Text(
              '${member['xp'] ?? 0} XP',
              style: TextStyle(color: AppTheme.accent, fontWeight: FontWeight.bold),
            ),
          ),
        );
      },
    );
  }

  Widget _buildFeedTab() {
    if (!_isMember) {
      return const Center(child: Text('Join the circle to see the feed'));
    }
    return Column(
      children: [
        Padding(
          padding: const EdgeInsets.all(16),
          child: Row(
            children: [
              Expanded(
                child: TextField(
                  controller: _postController,
                  decoration: const InputDecoration(
                    hintText: 'Share an update...',
                    border: OutlineInputBorder(),
                    contentPadding: EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                  ),
                ),
              ),
              const SizedBox(width: 8),
              IconButton(
                onPressed: _submitPost,
                icon: const Icon(Icons.send),
                color: AppTheme.primaryPurple,
              ),
            ],
          ),
        ),
        Expanded(
          child: _posts.isEmpty
              ? Center(
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Icon(Icons.forum_outlined, size: 48, color: Colors.grey[300]),
                      const SizedBox(height: 8),
                      Text('No posts yet. Be the first!', style: TextStyle(color: Colors.grey[500])),
                    ],
                  ),
                )
              : RefreshIndicator(
                  onRefresh: _loadPosts,
                  child: ListView.builder(
                    padding: const EdgeInsets.symmetric(horizontal: 16),
                    itemCount: _posts.length,
                    itemBuilder: (context, index) {
                      final post = _posts[index];
                      final user = post['user'] as Map<String, dynamic>?;
                      return Card(
                        margin: const EdgeInsets.only(bottom: 8),
                        child: Padding(
                          padding: const EdgeInsets.all(12),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Row(
                                children: [
                                  CircleAvatar(
                                    radius: 16,
                                    backgroundColor: AppTheme.primaryPurple.withValues(alpha: 0.1),
                                    child: Text(
                                      (user?['username'] ?? user?['display_name'] ?? 'U')[0].toUpperCase(),
                                      style: TextStyle(color: AppTheme.primaryPurple, fontSize: 12),
                                    ),
                                  ),
                                  const SizedBox(width: 8),
                                  Text(
                                    user?['username'] ?? user?['display_name'] ?? 'User',
                                    style: const TextStyle(fontWeight: FontWeight.bold),
                                  ),
                                  const Spacer(),
                                  Text(
                                    post['created_at']?.toString().substring(0, 10) ?? '',
                                    style: Theme.of(context).textTheme.bodySmall,
                                  ),
                                ],
                              ),
                              const SizedBox(height: 8),
                              Text(post['content'] ?? ''),
                            ],
                          ),
                        ),
                      );
                    },
                  ),
                ),
        ),
      ],
    );
  }

  Widget _buildChallengesTab() {
    if (_challenges.isEmpty) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.emoji_events_outlined, size: 48, color: Colors.grey[300]),
            const SizedBox(height: 8),
            Text('No challenges yet', style: TextStyle(color: Colors.grey[500])),
          ],
        ),
      );
    }
    return ListView.builder(
      padding: const EdgeInsets.all(16),
      itemCount: _challenges.length,
      itemBuilder: (context, index) {
        final challenge = _challenges[index];
        return Card(
          margin: const EdgeInsets.only(bottom: 12),
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Expanded(
                      child: Text(
                        challenge['title'] ?? '',
                        style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 16),
                      ),
                    ),
                    Chip(
                      label: Text(challenge['status'] ?? 'upcoming'),
                      backgroundColor: challenge['status'] == 'active'
                          ? AppTheme.success.withValues(alpha: 0.1)
                          : Colors.grey.withValues(alpha: 0.1),
                      labelStyle: TextStyle(
                        color: challenge['status'] == 'active' ? AppTheme.success : Colors.grey,
                        fontSize: 12,
                      ),
                    ),
                  ],
                ),
                if (challenge['description'] != null) ...[
                  const SizedBox(height: 8),
                  Text(challenge['description'], style: TextStyle(color: Colors.grey[600])),
                ],
                const SizedBox(height: 8),
                Row(
                  children: [
                    Icon(Icons.people, size: 16, color: Colors.grey[600]),
                    const SizedBox(width: 4),
                    Text(
                      '${challenge['participant_count'] ?? challenge['participantCount'] ?? 0} participants',
                      style: TextStyle(color: Colors.grey[600]),
                    ),
                    const Spacer(),
                    if (_isMember && challenge['status'] == 'active')
                      FilledButton(
                        onPressed: () async {
                          try {
                            final api = ref.read(apiServiceProvider);
                            await api.post('/circles/challenges/${challenge['id']}/join/');
                            _loadCircle();
                          } catch (e) {
                            if (mounted) {
                              ScaffoldMessenger.of(context).showSnackBar(
                                SnackBar(content: Text('Error: $e')),
                              );
                            }
                          }
                        },
                        style: FilledButton.styleFrom(backgroundColor: AppTheme.primaryPurple),
                        child: const Text('Join'),
                      ),
                  ],
                ),
              ],
            ),
          ),
        );
      },
    );
  }
}
