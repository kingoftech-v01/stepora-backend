import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../core/theme/app_theme.dart';
import '../../services/api_service.dart';
import '../../widgets/gradient_background.dart';
import '../../widgets/glass_container.dart';
import '../../widgets/glass_app_bar.dart';
import '../../widgets/glass_button.dart';
import '../../widgets/glass_text_field.dart';
import '../../widgets/animated_list_item.dart';
import '../../widgets/loading_shimmer.dart';

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
  void dispose() { _tabController.dispose(); _postController.dispose(); super.dispose(); }

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
    } catch (_) { setState(() => _isLoading = false); }
  }

  Future<void> _loadPosts() async {
    try {
      final api = ref.read(apiServiceProvider);
      final response = await api.get('/circles/${widget.circleId}/feed/');
      final results = response.data['results'] as List? ?? response.data as List? ?? [];
      setState(() { _posts = List<Map<String, dynamic>>.from(results); });
    } catch (_) {}
  }

  Future<void> _leaveCircle() async {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: isDark ? const Color(0xFF1E1B4B) : Colors.white,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
        title: Text('Leave Circle?', style: TextStyle(color: isDark ? Colors.white : const Color(0xFF1E1B4B))),
        content: Text('You will no longer see posts or participate in challenges.', style: TextStyle(color: isDark ? Colors.white70 : Colors.grey[700])),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: Text('Cancel', style: TextStyle(color: isDark ? Colors.white54 : Colors.grey))),
          TextButton(onPressed: () => Navigator.pop(ctx, true), child: const Text('Leave', style: TextStyle(color: Colors.red))),
        ],
      ),
    );
    if (confirmed != true) return;
    try {
      final api = ref.read(apiServiceProvider);
      await api.post('/circles/${widget.circleId}/leave/');
      if (mounted) context.pop();
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Error: $e')));
    }
  }

  Future<void> _joinCircle() async {
    try {
      final api = ref.read(apiServiceProvider);
      await api.post('/circles/${widget.circleId}/join/');
      _loadCircle();
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Error: $e')));
    }
  }

  Future<void> _showInviteDialog() async {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    showModalBottomSheet(
      context: context,
      backgroundColor: Colors.transparent,
      builder: (ctx) => Container(
        decoration: BoxDecoration(
          color: isDark ? const Color(0xFF1E1B4B).withValues(alpha: 0.95) : Colors.white.withValues(alpha: 0.97),
          borderRadius: const BorderRadius.vertical(top: Radius.circular(24)),
        ),
        child: SafeArea(child: Column(mainAxisSize: MainAxisSize.min, children: [
          Container(margin: const EdgeInsets.only(top: 12), width: 40, height: 4, decoration: BoxDecoration(color: isDark ? Colors.white24 : Colors.grey[600], borderRadius: BorderRadius.circular(2))),
          Padding(
            padding: const EdgeInsets.all(16),
            child: Text('Invite to Circle', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: isDark ? Colors.white : const Color(0xFF1E1B4B))),
          ),
          GlassContainer(
            margin: const EdgeInsets.symmetric(horizontal: 16),
            padding: const EdgeInsets.all(4),
            opacity: isDark ? 0.1 : 0.15,
            child: ListTile(
              leading: Icon(Icons.link, color: AppTheme.primaryPurple),
              title: Text('Generate Invite Link', style: TextStyle(color: isDark ? Colors.white : const Color(0xFF1E1B4B))),
              subtitle: Text('Share a link anyone can use', style: TextStyle(fontSize: 13, color: isDark ? Colors.white54 : Colors.grey)),
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
                        backgroundColor: isDark ? const Color(0xFF1E1B4B) : Colors.white,
                        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
                        title: Text('Invite Link', style: TextStyle(color: isDark ? Colors.white : const Color(0xFF1E1B4B))),
                        content: SelectableText(link.toString(), style: TextStyle(color: isDark ? Colors.white70 : const Color(0xFF1E1B4B))),
                        actions: [
                          TextButton(
                            onPressed: () { Clipboard.setData(ClipboardData(text: link.toString())); Navigator.pop(dlgCtx); ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Link copied!'))); },
                            child: const Text('Copy'),
                          ),
                          TextButton(onPressed: () => Navigator.pop(dlgCtx), child: Text('Close', style: TextStyle(color: isDark ? Colors.white54 : Colors.grey))),
                        ],
                      ),
                    );
                  }
                } catch (e) {
                  if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Error: $e')));
                }
              },
            ),
          ),
          GlassContainer(
            margin: const EdgeInsets.fromLTRB(16, 8, 16, 16),
            padding: const EdgeInsets.all(4),
            opacity: isDark ? 0.1 : 0.15,
            child: ListTile(
              leading: Icon(Icons.person_add, color: AppTheme.primaryPurple),
              title: Text('Invite by Username', style: TextStyle(color: isDark ? Colors.white : const Color(0xFF1E1B4B))),
              subtitle: Text('Send a direct invitation', style: TextStyle(fontSize: 13, color: isDark ? Colors.white54 : Colors.grey)),
              onTap: () {
                Navigator.pop(ctx);
                final controller = TextEditingController();
                showDialog(
                  context: context,
                  builder: (dlgCtx) => AlertDialog(
                    backgroundColor: isDark ? const Color(0xFF1E1B4B) : Colors.white,
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
                    title: Text('Invite User', style: TextStyle(color: isDark ? Colors.white : const Color(0xFF1E1B4B))),
                    content: GlassTextField(controller: controller, label: 'Username or Email'),
                    actions: [
                      TextButton(onPressed: () => Navigator.pop(dlgCtx), child: Text('Cancel', style: TextStyle(color: isDark ? Colors.white54 : Colors.grey))),
                      GlassButton(
                        label: 'Invite',
                        onPressed: () async {
                          if (controller.text.trim().isEmpty) return;
                          Navigator.pop(dlgCtx);
                          try {
                            final api = ref.read(apiServiceProvider);
                            await api.post('/circles/${widget.circleId}/invite/', data: {'username': controller.text.trim()});
                            if (mounted) ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Invitation sent!')));
                          } catch (e) {
                            if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Error: $e')));
                          }
                        },
                      ),
                    ],
                  ),
                );
              },
            ),
          ),
        ])),
      ),
    );
  }

  Future<void> _submitPost() async {
    if (_postController.text.trim().isEmpty) return;
    try {
      final api = ref.read(apiServiceProvider);
      await api.post('/circles/${widget.circleId}/posts/', data: {'content': _postController.text.trim()});
      _postController.clear();
      _loadPosts();
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Error: $e')));
    }
  }

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;

    if (_isLoading) {
      return GradientBackground(
        colors: isDark ? AppTheme.gradientSocial : AppTheme.gradientSocialLight,
        child: Scaffold(backgroundColor: Colors.transparent, appBar: const GlassAppBar(title: ''), body: const Center(child: LoadingShimmer())),
      );
    }

    return GradientBackground(
      colors: isDark ? AppTheme.gradientSocial : AppTheme.gradientSocialLight,
      child: Scaffold(
        backgroundColor: Colors.transparent,
        extendBodyBehindAppBar: true,
        appBar: GlassAppBar(
          title: _circle?['name'] ?? 'Circle',
          actions: [
            if (_isMember) ...[
              IconButton(icon: Icon(Icons.person_add, color: isDark ? Colors.white70 : const Color(0xFF1E1B4B)), tooltip: 'Invite', onPressed: _showInviteDialog),
              IconButton(icon: Icon(Icons.exit_to_app, color: isDark ? Colors.white70 : const Color(0xFF1E1B4B)), tooltip: 'Leave', onPressed: _leaveCircle),
            ] else
              Padding(padding: const EdgeInsets.only(right: 8), child: GlassButton(label: 'Join', onPressed: _joinCircle)),
          ],
        ),
        body: SafeArea(
          child: Column(children: [
            GlassContainer(
              margin: const EdgeInsets.fromLTRB(16, 8, 16, 0),
              padding: const EdgeInsets.all(16),
              opacity: isDark ? 0.12 : 0.25,
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text(_circle?['name'] ?? '', style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold, color: isDark ? Colors.white : const Color(0xFF1E1B4B))),
                if (_circle?['description'] != null) ...[
                  const SizedBox(height: 8),
                  Text(_circle!['description'], style: TextStyle(color: isDark ? Colors.white60 : Colors.grey[600])),
                ],
                const SizedBox(height: 12),
                Row(children: [
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                    decoration: BoxDecoration(color: AppTheme.primaryPurple.withValues(alpha: 0.12), borderRadius: BorderRadius.circular(8)),
                    child: Text('${_circle?['category'] ?? 'General'}', style: TextStyle(color: AppTheme.primaryPurple, fontSize: 12, fontWeight: FontWeight.w600)),
                  ),
                  const SizedBox(width: 10),
                  Text('${_members.length} members', style: TextStyle(color: isDark ? Colors.white54 : Colors.grey[600])),
                ]),
              ]),
            ).animate().fadeIn(duration: 400.ms).slideY(begin: -0.05, end: 0),

            GlassContainer(
              margin: const EdgeInsets.fromLTRB(16, 10, 16, 0),
              padding: const EdgeInsets.all(4),
              opacity: isDark ? 0.1 : 0.2,
              borderRadius: 12,
              child: TabBar(
                controller: _tabController,
                indicatorSize: TabBarIndicatorSize.tab,
                indicator: BoxDecoration(color: AppTheme.primaryPurple.withValues(alpha: 0.3), borderRadius: BorderRadius.circular(10)),
                labelColor: isDark ? Colors.white : const Color(0xFF1E1B4B),
                unselectedLabelColor: isDark ? Colors.white54 : Colors.grey,
                labelStyle: const TextStyle(fontWeight: FontWeight.w600, fontSize: 13),
                dividerHeight: 0,
                tabs: const [Tab(text: 'Members'), Tab(text: 'Feed'), Tab(text: 'Challenges')],
              ),
            ),

            Expanded(
              child: TabBarView(controller: _tabController, children: [
                _buildMembersTab(isDark),
                _buildFeedTab(isDark),
                _buildChallengesTab(isDark),
              ]),
            ),
          ]),
        ),
      ),
    );
  }

  Widget _buildMembersTab(bool isDark) {
    if (_members.isEmpty) return Center(child: Text('No members yet', style: TextStyle(color: isDark ? Colors.white54 : Colors.grey)));
    return ListView.builder(
      padding: const EdgeInsets.all(16),
      itemCount: _members.length,
      itemBuilder: (context, index) {
        final member = _members[index];
        return AnimatedListItem(
          index: index,
          child: GlassContainer(
            margin: const EdgeInsets.only(bottom: 8),
            padding: const EdgeInsets.all(12),
            opacity: isDark ? 0.1 : 0.2,
            child: Row(children: [
              CircleAvatar(
                radius: 20,
                backgroundColor: AppTheme.primaryPurple.withValues(alpha: 0.15),
                child: Text((member['display_name'] ?? member['username'] ?? 'U')[0].toUpperCase(), style: TextStyle(color: AppTheme.primaryPurple, fontWeight: FontWeight.bold)),
              ),
              const SizedBox(width: 12),
              Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text(member['display_name'] ?? member['username'] ?? member['email'] ?? '', style: TextStyle(fontWeight: FontWeight.w600, color: isDark ? Colors.white : const Color(0xFF1E1B4B))),
                Text(member['role'] ?? 'member', style: TextStyle(fontSize: 13, color: isDark ? Colors.white54 : Colors.grey)),
              ])),
              Text('${member['xp'] ?? 0} XP', style: TextStyle(color: AppTheme.accent, fontWeight: FontWeight.bold)),
            ]),
          ),
        );
      },
    );
  }

  Widget _buildFeedTab(bool isDark) {
    if (!_isMember) return Center(child: Text('Join the circle to see the feed', style: TextStyle(color: isDark ? Colors.white54 : Colors.grey)));
    return Column(children: [
      Padding(
        padding: const EdgeInsets.all(16),
        child: GlassContainer(
          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
          opacity: isDark ? 0.12 : 0.25,
          child: Row(children: [
            Expanded(child: TextField(
              controller: _postController,
              style: TextStyle(color: isDark ? Colors.white : const Color(0xFF1E1B4B)),
              decoration: InputDecoration(hintText: 'Share an update...', hintStyle: TextStyle(color: isDark ? Colors.white30 : Colors.grey), border: InputBorder.none, contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8)),
            )),
            GestureDetector(
              onTap: _submitPost,
              child: Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(gradient: const LinearGradient(colors: [AppTheme.primaryPurple, Color(0xFF8B5CF6)]), borderRadius: BorderRadius.circular(10)),
                child: const Icon(Icons.send, color: Colors.white, size: 18),
              ),
            ),
          ]),
        ),
      ),
      Expanded(
        child: _posts.isEmpty
            ? Center(child: Column(mainAxisAlignment: MainAxisAlignment.center, children: [
                Icon(Icons.forum_outlined, size: 48, color: isDark ? Colors.white24 : Colors.grey[600]),
                const SizedBox(height: 8),
                Text('No posts yet. Be the first!', style: TextStyle(color: isDark ? Colors.white54 : Colors.grey[700])),
              ]))
            : RefreshIndicator(
                onRefresh: _loadPosts,
                child: ListView.builder(
                  padding: const EdgeInsets.symmetric(horizontal: 16),
                  itemCount: _posts.length,
                  itemBuilder: (context, index) {
                    final post = _posts[index];
                    final user = post['user'] as Map<String, dynamic>?;
                    return AnimatedListItem(
                      index: index,
                      child: GlassContainer(
                        margin: const EdgeInsets.only(bottom: 10),
                        padding: const EdgeInsets.all(14),
                        opacity: isDark ? 0.1 : 0.2,
                        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                          Row(children: [
                            CircleAvatar(radius: 16, backgroundColor: AppTheme.primaryPurple.withValues(alpha: 0.15),
                              child: Text((user?['username'] ?? user?['display_name'] ?? 'U')[0].toUpperCase(), style: TextStyle(color: AppTheme.primaryPurple, fontSize: 12))),
                            const SizedBox(width: 8),
                            Text(user?['username'] ?? user?['display_name'] ?? 'User', style: TextStyle(fontWeight: FontWeight.bold, color: isDark ? Colors.white : const Color(0xFF1E1B4B))),
                            const Spacer(),
                            Text(post['created_at']?.toString().substring(0, 10) ?? '', style: TextStyle(fontSize: 12, color: isDark ? Colors.white38 : Colors.grey)),
                          ]),
                          const SizedBox(height: 8),
                          Text(post['content'] ?? '', style: TextStyle(color: isDark ? Colors.white70 : const Color(0xFF1E1B4B))),
                        ]),
                      ),
                    );
                  },
                ),
              ),
      ),
    ]);
  }

  Widget _buildChallengesTab(bool isDark) {
    if (_challenges.isEmpty) {
      return Center(child: Column(mainAxisAlignment: MainAxisAlignment.center, children: [
        Icon(Icons.emoji_events_outlined, size: 48, color: isDark ? Colors.white24 : Colors.grey[600]),
        const SizedBox(height: 8),
        Text('No challenges yet', style: TextStyle(color: isDark ? Colors.white54 : Colors.grey[700])),
      ]));
    }
    return ListView.builder(
      padding: const EdgeInsets.all(16),
      itemCount: _challenges.length,
      itemBuilder: (context, index) {
        final challenge = _challenges[index];
        final isActive = challenge['status'] == 'active';
        return AnimatedListItem(
          index: index,
          child: GlassContainer(
            margin: const EdgeInsets.only(bottom: 12),
            padding: const EdgeInsets.all(16),
            opacity: isDark ? 0.12 : 0.25,
            border: isActive ? Border.all(color: AppTheme.success.withValues(alpha: 0.4)) : null,
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Row(children: [
                Expanded(child: Text(challenge['title'] ?? '', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16, color: isDark ? Colors.white : const Color(0xFF1E1B4B)))),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                  decoration: BoxDecoration(
                    color: isActive ? AppTheme.success.withValues(alpha: 0.12) : Colors.grey.withValues(alpha: 0.12),
                    borderRadius: BorderRadius.circular(6),
                  ),
                  child: Text(challenge['status'] ?? 'upcoming', style: TextStyle(color: isActive ? AppTheme.success : Colors.grey, fontSize: 12, fontWeight: FontWeight.w600)),
                ),
              ]),
              if (challenge['description'] != null) ...[
                const SizedBox(height: 8),
                Text(challenge['description'], style: TextStyle(color: isDark ? Colors.white60 : Colors.grey[600])),
              ],
              const SizedBox(height: 10),
              Row(children: [
                Icon(Icons.people, size: 16, color: isDark ? Colors.white54 : Colors.grey[600]),
                const SizedBox(width: 4),
                Text('${challenge['participant_count'] ?? challenge['participantCount'] ?? 0} participants', style: TextStyle(color: isDark ? Colors.white54 : Colors.grey[600], fontSize: 13)),
                const Spacer(),
                if (_isMember && isActive)
                  GlassButton(label: 'Join', onPressed: () async {
                    try {
                      final api = ref.read(apiServiceProvider);
                      await api.post('/circles/challenges/${challenge['id']}/join/');
                      _loadCircle();
                    } catch (e) {
                      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Error: $e')));
                    }
                  }),
              ]),
            ]),
          ),
        );
      },
    );
  }
}
