import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../core/theme/app_theme.dart';
import '../../providers/social_provider.dart';

class FriendRequestsScreen extends ConsumerStatefulWidget {
  const FriendRequestsScreen({super.key});

  @override
  ConsumerState<FriendRequestsScreen> createState() => _FriendRequestsScreenState();
}

class _FriendRequestsScreenState extends ConsumerState<FriendRequestsScreen>
    with SingleTickerProviderStateMixin {
  late TabController _tabController;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 2, vsync: this);
    Future.microtask(() {
      ref.read(socialProvider.notifier).fetchPendingRequests();
      ref.read(socialProvider.notifier).fetchSentRequests();
    });
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(socialProvider);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Friend Requests'),
        bottom: TabBar(
          controller: _tabController,
          tabs: [
            Tab(text: 'Received (${state.pendingRequests.length})'),
            Tab(text: 'Sent (${state.sentRequests.length})'),
          ],
        ),
      ),
      body: TabBarView(
        controller: _tabController,
        children: [
          // Received
          state.pendingRequests.isEmpty
              ? Center(
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Icon(Icons.mail_outline, size: 64, color: Colors.grey[300]),
                      const SizedBox(height: 16),
                      Text('No pending requests', style: TextStyle(color: Colors.grey[500])),
                    ],
                  ),
                )
              : ListView.builder(
                  padding: const EdgeInsets.all(16),
                  itemCount: state.pendingRequests.length,
                  itemBuilder: (context, index) {
                    final req = state.pendingRequests[index];
                    return Card(
                      margin: const EdgeInsets.only(bottom: 8),
                      child: ListTile(
                        leading: CircleAvatar(
                          backgroundColor: AppTheme.primaryPurple.withValues(alpha: 0.1),
                          child: Text(
                            req.fromUser.displayName.isNotEmpty
                                ? req.fromUser.displayName[0].toUpperCase()
                                : '?',
                          ),
                        ),
                        title: Text(req.fromUser.displayName, style: const TextStyle(fontWeight: FontWeight.w600)),
                        subtitle: Text(req.fromUser.email),
                        trailing: Row(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            IconButton(
                              icon: const Icon(Icons.check_circle, color: Colors.green),
                              tooltip: 'Accept',
                              onPressed: () => ref.read(socialProvider.notifier).acceptRequest(req.id),
                            ),
                            IconButton(
                              icon: const Icon(Icons.cancel, color: Colors.red),
                              tooltip: 'Reject',
                              onPressed: () => ref.read(socialProvider.notifier).rejectRequest(req.id),
                            ),
                          ],
                        ),
                      ),
                    );
                  },
                ),
          // Sent
          state.sentRequests.isEmpty
              ? Center(
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Icon(Icons.send_outlined, size: 64, color: Colors.grey[300]),
                      const SizedBox(height: 16),
                      Text('No sent requests', style: TextStyle(color: Colors.grey[500])),
                    ],
                  ),
                )
              : ListView.builder(
                  padding: const EdgeInsets.all(16),
                  itemCount: state.sentRequests.length,
                  itemBuilder: (context, index) {
                    final req = state.sentRequests[index];
                    return Card(
                      margin: const EdgeInsets.only(bottom: 8),
                      child: ListTile(
                        leading: CircleAvatar(
                          backgroundColor: Colors.orange.withValues(alpha: 0.1),
                          child: const Icon(Icons.hourglass_top, color: Colors.orange, size: 20),
                        ),
                        title: Text(req.fromUser.displayName, style: const TextStyle(fontWeight: FontWeight.w600)),
                        subtitle: Text(req.fromUser.email),
                        trailing: Chip(
                          label: Text(req.status, style: const TextStyle(fontSize: 12)),
                          backgroundColor: Colors.orange.withValues(alpha: 0.1),
                        ),
                      ),
                    );
                  },
                ),
        ],
      ),
    );
  }
}
