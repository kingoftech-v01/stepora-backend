import 'package:flutter/material.dart';
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
  void initState() { super.initState(); _loadData(); }

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
    } catch (_) { setState(() => _isLoading = false); }
  }

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;

    return GradientBackground(
      colors: isDark ? AppTheme.gradientSocial : AppTheme.gradientSocialLight,
      child: Scaffold(
        backgroundColor: Colors.transparent,
        extendBodyBehindAppBar: true,
        appBar: const GlassAppBar(title: 'Dream Buddy'),
        body: _isLoading
            ? const Center(child: LoadingShimmer())
            : RefreshIndicator(
                onRefresh: _loadData,
                child: ListView(
                  padding: EdgeInsets.fromLTRB(16, MediaQuery.of(context).padding.top + kToolbarHeight + 8, 16, 32),
                  children: [
                    if (_currentBuddy != null) ...[
                      Text('Your Buddy', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16, color: isDark ? Colors.white : const Color(0xFF1E1B4B)))
                        .animate().fadeIn(duration: 400.ms),
                      const SizedBox(height: 10),
                      GlassContainer(
                        padding: const EdgeInsets.all(20),
                        opacity: isDark ? 0.15 : 0.3,
                        border: Border.all(color: AppTheme.primaryPurple.withValues(alpha: 0.3)),
                        child: Row(children: [
                          Container(
                            width: 60, height: 60,
                            decoration: BoxDecoration(
                              gradient: const LinearGradient(colors: [AppTheme.primaryPurple, Color(0xFF8B5CF6)]),
                              borderRadius: BorderRadius.circular(18),
                              boxShadow: [BoxShadow(color: AppTheme.primaryPurple.withValues(alpha: 0.3), blurRadius: 10)],
                            ),
                            child: const Icon(Icons.person, color: Colors.white, size: 30),
                          ),
                          const SizedBox(width: 16),
                          Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                            Text(_currentBuddy!['user2_name'] ?? _currentBuddy!['user1_name'] ?? 'Buddy',
                              style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16, color: isDark ? Colors.white : const Color(0xFF1E1B4B))),
                            const SizedBox(height: 4),
                            Row(children: [
                              Icon(Icons.favorite, size: 14, color: AppTheme.accent),
                              const SizedBox(width: 4),
                              Text('Compatibility: ${_currentBuddy!['compatibility_score'] ?? 0}%',
                                style: TextStyle(color: AppTheme.accent, fontSize: 13, fontWeight: FontWeight.w600)),
                            ]),
                          ])),
                          Column(children: [
                            _glassIconButton(Icons.chat_outlined, 'Chat', () {
                              final convId = _currentBuddy!['conversation_id']?.toString();
                              if (convId != null) {
                                context.push('/buddy-chat/$convId');
                              } else {
                                ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('No chat available yet')));
                              }
                            }),
                            const SizedBox(height: 8),
                            _glassIconButton(Icons.favorite_outline, 'Encourage', () => _showEncourageDialog()),
                          ]),
                        ]),
                      ).animate().fadeIn(duration: 500.ms).slideY(begin: 0.05, end: 0),
                      const SizedBox(height: 24),
                    ] else ...[
                      GlassContainer(
                        padding: const EdgeInsets.all(32),
                        opacity: isDark ? 0.12 : 0.25,
                        child: Column(children: [
                          Container(
                            padding: const EdgeInsets.all(20),
                            decoration: BoxDecoration(shape: BoxShape.circle, color: AppTheme.primaryPurple.withValues(alpha: 0.1)),
                            child: Icon(Icons.people_outline, size: 48, color: AppTheme.primaryPurple.withValues(alpha: 0.5)),
                          ).animate().fadeIn(duration: 500.ms).scale(begin: const Offset(0.8, 0.8), end: const Offset(1, 1)),
                          const SizedBox(height: 16),
                          Text('Find Your Dream Buddy', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 18, color: isDark ? Colors.white : const Color(0xFF1E1B4B)))
                            .animate().fadeIn(duration: 500.ms, delay: 100.ms),
                          const SizedBox(height: 8),
                          Text('Get matched with someone who shares your goals!', style: TextStyle(color: isDark ? Colors.white54 : Colors.grey[600]), textAlign: TextAlign.center)
                            .animate().fadeIn(duration: 500.ms, delay: 200.ms),
                          const SizedBox(height: 20),
                          GlassButton(
                            label: 'Find Match',
                            icon: Icons.search,
                            onPressed: () async {
                              final api = ref.read(apiServiceProvider);
                              try { await api.post('/buddies/find_match/'); _loadData(); } catch (_) {}
                            },
                          ).animate().fadeIn(duration: 500.ms, delay: 300.ms),
                        ]),
                      ).animate().fadeIn(duration: 400.ms),
                      const SizedBox(height: 24),
                    ],

                    if (_suggestions.isNotEmpty) ...[
                      Text('Suggested Buddies', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16, color: isDark ? Colors.white : const Color(0xFF1E1B4B)))
                        .animate().fadeIn(duration: 400.ms),
                      const SizedBox(height: 10),
                      ..._suggestions.asMap().entries.map((entry) {
                        final index = entry.key;
                        final s = entry.value;
                        return AnimatedListItem(
                          index: index,
                          child: GlassContainer(
                            margin: const EdgeInsets.only(bottom: 10),
                            padding: const EdgeInsets.all(14),
                            opacity: isDark ? 0.12 : 0.25,
                            child: Row(children: [
                              CircleAvatar(
                                radius: 22,
                                backgroundColor: AppTheme.primaryPurple.withValues(alpha: 0.15),
                                child: Text((s['display_name'] ?? 'U')[0].toUpperCase(), style: TextStyle(color: AppTheme.primaryPurple, fontWeight: FontWeight.bold)),
                              ),
                              const SizedBox(width: 12),
                              Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                                Text(s['display_name'] ?? '', style: TextStyle(fontWeight: FontWeight.w600, color: isDark ? Colors.white : const Color(0xFF1E1B4B))),
                                Text('${s['shared_categories']?.join(', ') ?? 'Common interests'}', style: TextStyle(fontSize: 13, color: isDark ? Colors.white54 : Colors.grey[600])),
                              ])),
                              GlassButton(
                                label: 'Request',
                                onPressed: () async {
                                  try {
                                    final api = ref.read(apiServiceProvider);
                                    await api.post('/buddies/pair/', data: {'partner_id': s['id']});
                                    if (mounted) { ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Buddy request sent!'))); _loadData(); }
                                  } catch (e) {
                                    if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Error: $e')));
                                  }
                                },
                              ),
                            ]),
                          ),
                        );
                      }),
                    ],
                  ],
                ),
              ),
      ),
    );
  }

  Widget _glassIconButton(IconData icon, String tooltip, VoidCallback onTap) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    return Tooltip(
      message: tooltip,
      child: GestureDetector(
        onTap: onTap,
        child: Container(
          padding: const EdgeInsets.all(8),
          decoration: BoxDecoration(
            color: isDark ? Colors.white.withValues(alpha: 0.08) : Colors.white.withValues(alpha: 0.3),
            borderRadius: BorderRadius.circular(10),
          ),
          child: Icon(icon, color: AppTheme.primaryPurple, size: 20),
        ),
      ),
    );
  }

  void _showEncourageDialog() {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final msgController = TextEditingController(text: 'Keep going, you got this!');
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: isDark ? const Color(0xFF1E1B4B) : Colors.white,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
        title: Text('Send Encouragement', style: TextStyle(color: isDark ? Colors.white : const Color(0xFF1E1B4B))),
        content: GlassTextField(controller: msgController, label: 'Message', maxLines: 3),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx), child: Text('Cancel', style: TextStyle(color: isDark ? Colors.white54 : Colors.grey))),
          GlassButton(
            label: 'Send',
            icon: Icons.favorite,
            onPressed: () async {
              Navigator.pop(ctx);
              try {
                final api = ref.read(apiServiceProvider);
                await api.post('/buddies/${_currentBuddy!['id']}/encourage/', data: {'message': msgController.text.trim()});
                if (mounted) ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Encouragement sent!')));
              } catch (e) {
                if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Error: $e')));
              }
            },
          ),
        ],
      ),
    );
  }
}
