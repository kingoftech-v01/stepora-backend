import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../core/theme/app_theme.dart';
import '../../providers/social_provider.dart';
import '../../widgets/gradient_background.dart';
import '../../widgets/glass_container.dart';
import '../../widgets/glass_app_bar.dart';
import '../../widgets/glass_button.dart';
import '../../widgets/animated_list_item.dart';
import '../../widgets/loading_shimmer.dart';

class FriendsScreen extends ConsumerStatefulWidget {
  const FriendsScreen({super.key});

  @override
  ConsumerState<FriendsScreen> createState() => _FriendsScreenState();
}

class _FriendsScreenState extends ConsumerState<FriendsScreen> {
  @override
  void initState() {
    super.initState();
    Future.microtask(() {
      ref.read(socialProvider.notifier).fetchFriends();
      ref.read(socialProvider.notifier).fetchPendingRequests();
    });
  }

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
          title: 'Friends',
          actions: [
            if (state.pendingCount > 0)
              Badge(
                label: Text('${state.pendingCount}'),
                child: IconButton(icon: Icon(Icons.person_add, color: isDark ? Colors.white70 : const Color(0xFF1E1B4B)), onPressed: () => context.push('/social/requests')),
              )
            else
              IconButton(icon: Icon(Icons.person_add, color: isDark ? Colors.white70 : const Color(0xFF1E1B4B)), onPressed: () => context.push('/social/requests')),
            IconButton(icon: Icon(Icons.search, color: isDark ? Colors.white70 : const Color(0xFF1E1B4B)), onPressed: () => context.push('/social/search')),
          ],
        ),
        body: state.isLoading
            ? const Center(child: LoadingShimmer())
            : state.friends.isEmpty
                ? Center(child: Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 48),
                    child: Column(mainAxisAlignment: MainAxisAlignment.center, children: [
                      Container(
                        padding: const EdgeInsets.all(24),
                        decoration: BoxDecoration(shape: BoxShape.circle, color: AppTheme.primaryPurple.withValues(alpha: 0.1)),
                        child: Icon(Icons.people_outline, size: 48, color: isDark ? Colors.white24 : Colors.grey[600]),
                      ).animate().fadeIn(duration: 500.ms).scale(begin: const Offset(0.8, 0.8), end: const Offset(1, 1)),
                      const SizedBox(height: 16),
                      Text('No friends yet', style: TextStyle(color: isDark ? Colors.white54 : Colors.grey[700], fontSize: 16))
                        .animate().fadeIn(duration: 500.ms, delay: 100.ms),
                      const SizedBox(height: 16),
                      SizedBox(
                        width: 200,
                        child: GlassButton(label: 'Find People', icon: Icons.search, onPressed: () => context.push('/social/search')),
                      ).animate().fadeIn(duration: 500.ms, delay: 200.ms),
                    ]),
                  ))
                : RefreshIndicator(
                    onRefresh: () => ref.read(socialProvider.notifier).fetchFriends(),
                    child: ListView.builder(
                      padding: EdgeInsets.fromLTRB(16, MediaQuery.of(context).padding.top + kToolbarHeight + 8, 16, 32),
                      itemCount: state.friends.length,
                      itemBuilder: (context, index) {
                        final friend = state.friends[index];
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
                                backgroundImage: friend.avatarUrl != null ? NetworkImage(friend.avatarUrl!) : null,
                                child: friend.avatarUrl == null
                                    ? Text(friend.displayName.isNotEmpty ? friend.displayName[0].toUpperCase() : '?', style: TextStyle(color: AppTheme.primaryPurple, fontWeight: FontWeight.bold))
                                    : null,
                              ),
                              const SizedBox(width: 12),
                              Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                                Text(friend.displayName, style: TextStyle(fontWeight: FontWeight.w600, color: isDark ? Colors.white : const Color(0xFF1E1B4B))),
                                Text(friend.email, style: TextStyle(fontSize: 13, color: isDark ? Colors.white54 : Colors.grey[600])),
                              ])),
                              PopupMenuButton(
                                icon: Icon(Icons.more_vert, color: isDark ? Colors.white38 : Colors.grey),
                                color: isDark ? const Color(0xFF2D2B55) : Colors.white,
                                itemBuilder: (_) => [const PopupMenuItem(value: 'remove', child: Text('Remove Friend'))],
                                onSelected: (value) async {
                                  if (value == 'remove') {
                                    final confirmed = await showDialog<bool>(
                                      context: context,
                                      builder: (ctx) => AlertDialog(
                                        backgroundColor: isDark ? const Color(0xFF1E1B4B) : Colors.white,
                                        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
                                        title: Text('Remove Friend?', style: TextStyle(color: isDark ? Colors.white : const Color(0xFF1E1B4B))),
                                        actions: [
                                          TextButton(onPressed: () => Navigator.pop(ctx, false), child: Text('Cancel', style: TextStyle(color: isDark ? Colors.white54 : Colors.grey))),
                                          TextButton(onPressed: () => Navigator.pop(ctx, true), child: const Text('Remove', style: TextStyle(color: Colors.red))),
                                        ],
                                      ),
                                    );
                                    if (confirmed == true) await ref.read(socialProvider.notifier).removeFriend(friend.id);
                                  }
                                },
                              ),
                            ]),
                          ),
                        );
                      },
                    ),
                  ),
      ),
    );
  }
}
