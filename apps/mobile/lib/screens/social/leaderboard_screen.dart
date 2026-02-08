import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../core/theme/app_theme.dart';
import '../../services/api_service.dart';

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
      setState(() {
        _leaderboard = List<Map<String, dynamic>>.from(results);
        _isLoading = false;
      });
    } catch (_) {
      setState(() => _isLoading = false);
    }
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Leaderboard'),
        bottom: TabBar(
          controller: _tabController,
          tabs: const [
            Tab(text: 'Weekly'),
            Tab(text: 'Monthly'),
            Tab(text: 'All Time'),
          ],
        ),
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : _leaderboard.isEmpty
              ? const Center(child: Text('No data yet'))
              : ListView.builder(
                  padding: const EdgeInsets.all(16),
                  itemCount: _leaderboard.length,
                  itemBuilder: (context, index) {
                    final entry = _leaderboard[index];
                    final rank = index + 1;
                    return Card(
                      margin: const EdgeInsets.only(bottom: 8),
                      color: rank <= 3 ? AppTheme.accent.withOpacity(0.05) : null,
                      child: ListTile(
                        leading: CircleAvatar(
                          backgroundColor: rank == 1
                              ? Colors.amber
                              : rank == 2
                                  ? Colors.grey[400]
                                  : rank == 3
                                      ? Colors.brown[300]
                                      : AppTheme.primaryPurple.withOpacity(0.1),
                          child: Text(
                            '$rank',
                            style: TextStyle(
                              color: rank <= 3 ? Colors.white : AppTheme.primaryPurple,
                              fontWeight: FontWeight.bold,
                            ),
                          ),
                        ),
                        title: Text(
                          entry['display_name'] ?? entry['email'] ?? 'User',
                          style: const TextStyle(fontWeight: FontWeight.w600),
                        ),
                        subtitle: Text('Level ${entry['level'] ?? 1}'),
                        trailing: Column(
                          mainAxisAlignment: MainAxisAlignment.center,
                          crossAxisAlignment: CrossAxisAlignment.end,
                          children: [
                            Text(
                              '${entry['xp'] ?? 0} XP',
                              style: TextStyle(
                                fontWeight: FontWeight.bold,
                                color: AppTheme.accent,
                                fontSize: 16,
                              ),
                            ),
                            Text(
                              '${entry['streak_days'] ?? 0} day streak',
                              style: Theme.of(context).textTheme.bodySmall,
                            ),
                          ],
                        ),
                      ),
                    );
                  },
                ),
    );
  }
}
