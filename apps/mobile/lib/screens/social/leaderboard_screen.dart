import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../core/theme/app_theme.dart';
import '../../services/api_service.dart';
import '../../widgets/gradient_background.dart';
import '../../widgets/glass_container.dart';
import '../../widgets/glass_app_bar.dart';
import '../../widgets/animated_list_item.dart';
import '../../widgets/animated_counter.dart';
import '../../widgets/loading_shimmer.dart';

class LeaderboardScreen extends ConsumerStatefulWidget {
  const LeaderboardScreen({super.key});

  @override
  ConsumerState<LeaderboardScreen> createState() => _LeaderboardScreenState();
}

class _LeaderboardScreenState extends ConsumerState<LeaderboardScreen> with SingleTickerProviderStateMixin {
  late TabController _tabController;
  List<Map<String, dynamic>> _leaderboard = [];
  bool _isLoading = true;
  String _period = 'weekly';

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 3, vsync: this);
    _tabController.addListener(() {
      final periods = ['weekly', 'monthly', 'all_time'];
      _period = periods[_tabController.index];
      _loadLeaderboard();
    });
    _loadLeaderboard();
  }

  Future<void> _loadLeaderboard() async {
    setState(() => _isLoading = true);
    try {
      final api = ref.read(apiServiceProvider);
      final response = await api.get('/leagues/leaderboard/', queryParams: {'period': _period});
      final results = response.data['results'] as List? ?? response.data as List? ?? [];
      setState(() { _leaderboard = List<Map<String, dynamic>>.from(results); _isLoading = false; });
    } catch (_) { setState(() => _isLoading = false); }
  }

  @override
  void dispose() { _tabController.dispose(); super.dispose(); }

  Color _getRankColor(int rank) {
    switch (rank) {
      case 1: return Colors.amber;
      case 2: return Colors.grey.shade600;
      case 3: return Colors.brown.shade300;
      default: return AppTheme.primaryPurple.withValues(alpha: 0.15);
    }
  }

  Color _getRankBorderColor(int rank) {
    switch (rank) {
      case 1: return Colors.amber.withValues(alpha: 0.6);
      case 2: return Colors.grey.withValues(alpha: 0.5);
      case 3: return Colors.brown.withValues(alpha: 0.5);
      default: return Colors.transparent;
    }
  }

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;

    return GradientBackground(
      colors: isDark ? AppTheme.gradientSocial : AppTheme.gradientSocialLight,
      child: Scaffold(
        backgroundColor: Colors.transparent,
        extendBodyBehindAppBar: true,
        appBar: GlassAppBar(
          title: 'Leaderboard',
          bottom: PreferredSize(
            preferredSize: const Size.fromHeight(48),
            child: GlassContainer(
              margin: const EdgeInsets.symmetric(horizontal: 16),
              padding: const EdgeInsets.all(4),
              opacity: isDark ? 0.1 : 0.2,
              borderRadius: 12,
              child: TabBar(
                controller: _tabController,
                indicatorSize: TabBarIndicatorSize.tab,
                indicator: BoxDecoration(
                  color: AppTheme.primaryPurple.withValues(alpha: 0.3),
                  borderRadius: BorderRadius.circular(10),
                ),
                labelColor: isDark ? Colors.white : const Color(0xFF1E1B4B),
                unselectedLabelColor: isDark ? Colors.white54 : Colors.grey,
                labelStyle: const TextStyle(fontWeight: FontWeight.w600, fontSize: 13),
                dividerHeight: 0,
                tabs: const [Tab(text: 'Weekly'), Tab(text: 'Monthly'), Tab(text: 'All Time')],
              ),
            ),
          ),
        ),
        body: _isLoading
            ? const Center(child: LoadingShimmer())
            : _leaderboard.isEmpty
                ? Center(child: Text('No data yet', style: TextStyle(color: isDark ? Colors.white54 : Colors.grey)))
                : ListView.builder(
                    padding: EdgeInsets.fromLTRB(16, MediaQuery.of(context).padding.top + kToolbarHeight + 60, 16, 32),
                    itemCount: _leaderboard.length,
                    itemBuilder: (context, index) {
                      final entry = _leaderboard[index];
                      final rank = index + 1;
                      final isTopThree = rank <= 3;
                      return AnimatedListItem(
                        index: index,
                        child: GlassContainer(
                          margin: const EdgeInsets.only(bottom: 10),
                          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
                          opacity: isDark ? (isTopThree ? 0.18 : 0.12) : (isTopThree ? 0.35 : 0.25),
                          border: isTopThree ? Border.all(color: _getRankBorderColor(rank), width: 1.5) : null,
                          boxShadow: isTopThree ? [BoxShadow(color: _getRankBorderColor(rank).withValues(alpha: 0.2), blurRadius: 12)] : null,
                          child: Row(children: [
                            Container(
                              width: 40, height: 40,
                              decoration: BoxDecoration(
                                color: _getRankColor(rank),
                                borderRadius: BorderRadius.circular(12),
                                boxShadow: isTopThree ? [BoxShadow(color: _getRankColor(rank).withValues(alpha: 0.4), blurRadius: 8)] : null,
                              ),
                              child: Center(child: Text('$rank', style: TextStyle(color: isTopThree ? Colors.white : (isDark ? Colors.white70 : const Color(0xFF1E1B4B)), fontWeight: FontWeight.bold, fontSize: 16))),
                            ),
                            const SizedBox(width: 14),
                            Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                              Text(entry['display_name'] ?? entry['email'] ?? 'User', style: TextStyle(fontWeight: FontWeight.w600, fontSize: 15, color: isDark ? Colors.white : const Color(0xFF1E1B4B))),
                              const SizedBox(height: 2),
                              Text('Level ${entry['level'] ?? 1}', style: TextStyle(fontSize: 13, color: isDark ? Colors.white54 : Colors.grey[600])),
                            ])),
                            Column(crossAxisAlignment: CrossAxisAlignment.end, children: [
                              Row(children: [
                                AnimatedCounter(value: entry['xp'] ?? 0, style: TextStyle(fontWeight: FontWeight.bold, color: AppTheme.accent, fontSize: 16)),
                                Text(' XP', style: TextStyle(fontWeight: FontWeight.bold, color: AppTheme.accent, fontSize: 14)),
                              ]),
                              const SizedBox(height: 2),
                              Row(children: [
                                Icon(Icons.local_fire_department, size: 12, color: isDark ? Colors.white38 : Colors.grey),
                                const SizedBox(width: 2),
                                Text('${entry['streak_days'] ?? 0} days', style: TextStyle(fontSize: 12, color: isDark ? Colors.white38 : Colors.grey)),
                              ]),
                            ]),
                          ]),
                        ),
                      );
                    },
                  ),
      ),
    );
  }
}
