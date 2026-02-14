import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../core/theme/app_theme.dart';
import '../../providers/social_provider.dart';
import '../../widgets/gradient_background.dart';
import '../../widgets/glass_container.dart';
import '../../widgets/glass_app_bar.dart';
import '../../widgets/animated_list_item.dart';

class FriendRequestsScreen extends ConsumerStatefulWidget {
  const FriendRequestsScreen({super.key});

  @override
  ConsumerState<FriendRequestsScreen> createState() => _FriendRequestsScreenState();
}

class _FriendRequestsScreenState extends ConsumerState<FriendRequestsScreen> with SingleTickerProviderStateMixin {
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
  void dispose() { _tabController.dispose(); super.dispose(); }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(socialProvider);
    final isDark = Theme.of(context).brightness == Brightness.dark;

    return GradientBackground(
      colors: isDark ? AppTheme.gradientSocial : AppTheme.gradientSocialLight,
      child: Scaffold(
        backgroundColor: Colors.transparent,
        extendBodyBehindAppBar: true,
        appBar: GlassAppBar(
          title: 'Friend Requests',
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
                tabs: [
                  Tab(text: 'Received (${state.pendingRequests.length})'),
                  Tab(text: 'Sent (${state.sentRequests.length})'),
                ],
              ),
            ),
          ),
        ),
        body: TabBarView(
          controller: _tabController,
          children: [
            // Received
            state.pendingRequests.isEmpty
                ? Center(child: Column(mainAxisAlignment: MainAxisAlignment.center, children: [
                    Container(
                      padding: const EdgeInsets.all(20),
                      decoration: BoxDecoration(shape: BoxShape.circle, color: AppTheme.primaryPurple.withValues(alpha: 0.1)),
                      child: Icon(Icons.mail_outline, size: 48, color: isDark ? Colors.white24 : Colors.grey[600]),
                    ).animate().fadeIn(duration: 500.ms),
                    const SizedBox(height: 16),
                    Text('No pending requests', style: TextStyle(color: isDark ? Colors.white54 : Colors.grey[700]))
                      .animate().fadeIn(duration: 500.ms, delay: 100.ms),
                  ]))
                : ListView.builder(
                    padding: EdgeInsets.fromLTRB(16, MediaQuery.of(context).padding.top + kToolbarHeight + 60, 16, 32),
                    itemCount: state.pendingRequests.length,
                    itemBuilder: (context, index) {
                      final req = state.pendingRequests[index];
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
                              child: Text(
                                req.fromUser.displayName.isNotEmpty ? req.fromUser.displayName[0].toUpperCase() : '?',
                                style: TextStyle(color: AppTheme.primaryPurple, fontWeight: FontWeight.bold),
                              ),
                            ),
                            const SizedBox(width: 12),
                            Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                              Text(req.fromUser.displayName, style: TextStyle(fontWeight: FontWeight.w600, color: isDark ? Colors.white : const Color(0xFF1E1B4B))),
                              Text(req.fromUser.email, style: TextStyle(fontSize: 13, color: isDark ? Colors.white54 : Colors.grey[600])),
                            ])),
                            Row(mainAxisSize: MainAxisSize.min, children: [
                              GestureDetector(
                                onTap: () => ref.read(socialProvider.notifier).acceptRequest(req.id),
                                child: Container(
                                  padding: const EdgeInsets.all(8),
                                  decoration: BoxDecoration(color: AppTheme.success.withValues(alpha: 0.15), borderRadius: BorderRadius.circular(10)),
                                  child: Icon(Icons.check, color: AppTheme.success, size: 20),
                                ),
                              ),
                              const SizedBox(width: 8),
                              GestureDetector(
                                onTap: () => ref.read(socialProvider.notifier).rejectRequest(req.id),
                                child: Container(
                                  padding: const EdgeInsets.all(8),
                                  decoration: BoxDecoration(color: Colors.red.withValues(alpha: 0.15), borderRadius: BorderRadius.circular(10)),
                                  child: Icon(Icons.close, color: Colors.red.shade400, size: 20),
                                ),
                              ),
                            ]),
                          ]),
                        ),
                      );
                    },
                  ),

            // Sent
            state.sentRequests.isEmpty
                ? Center(child: Column(mainAxisAlignment: MainAxisAlignment.center, children: [
                    Container(
                      padding: const EdgeInsets.all(20),
                      decoration: BoxDecoration(shape: BoxShape.circle, color: Colors.orange.withValues(alpha: 0.1)),
                      child: Icon(Icons.send_outlined, size: 48, color: isDark ? Colors.white24 : Colors.grey[600]),
                    ).animate().fadeIn(duration: 500.ms),
                    const SizedBox(height: 16),
                    Text('No sent requests', style: TextStyle(color: isDark ? Colors.white54 : Colors.grey[700]))
                      .animate().fadeIn(duration: 500.ms, delay: 100.ms),
                  ]))
                : ListView.builder(
                    padding: EdgeInsets.fromLTRB(16, MediaQuery.of(context).padding.top + kToolbarHeight + 60, 16, 32),
                    itemCount: state.sentRequests.length,
                    itemBuilder: (context, index) {
                      final req = state.sentRequests[index];
                      return AnimatedListItem(
                        index: index,
                        child: GlassContainer(
                          margin: const EdgeInsets.only(bottom: 10),
                          padding: const EdgeInsets.all(14),
                          opacity: isDark ? 0.12 : 0.25,
                          child: Row(children: [
                            Container(
                              padding: const EdgeInsets.all(10),
                              decoration: BoxDecoration(color: Colors.orange.withValues(alpha: 0.12), borderRadius: BorderRadius.circular(12)),
                              child: Icon(Icons.hourglass_top, color: Colors.orange.shade400, size: 20),
                            ),
                            const SizedBox(width: 12),
                            Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                              Text(req.fromUser.displayName, style: TextStyle(fontWeight: FontWeight.w600, color: isDark ? Colors.white : const Color(0xFF1E1B4B))),
                              Text(req.fromUser.email, style: TextStyle(fontSize: 13, color: isDark ? Colors.white54 : Colors.grey[600])),
                            ])),
                            Container(
                              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                              decoration: BoxDecoration(color: Colors.orange.withValues(alpha: 0.12), borderRadius: BorderRadius.circular(6)),
                              child: Text(req.status, style: TextStyle(color: Colors.orange.shade400, fontSize: 12, fontWeight: FontWeight.w600)),
                            ),
                          ]),
                        ),
                      );
                    },
                  ),
          ],
        ),
      ),
    );
  }
}
