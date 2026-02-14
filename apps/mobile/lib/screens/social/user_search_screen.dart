import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../core/theme/app_theme.dart';
import '../../providers/social_provider.dart';
import '../../widgets/gradient_background.dart';
import '../../widgets/glass_container.dart';
import '../../widgets/glass_app_bar.dart';
import '../../widgets/animated_list_item.dart';

class UserSearchScreen extends ConsumerStatefulWidget {
  const UserSearchScreen({super.key});

  @override
  ConsumerState<UserSearchScreen> createState() => _UserSearchScreenState();
}

class _UserSearchScreenState extends ConsumerState<UserSearchScreen> {
  final _searchController = TextEditingController();
  Timer? _debounce;

  @override
  void dispose() { _searchController.dispose(); _debounce?.cancel(); super.dispose(); }

  void _onSearchChanged(String query) {
    _debounce?.cancel();
    _debounce = Timer(const Duration(milliseconds: 400), () {
      ref.read(socialProvider.notifier).searchUsers(query);
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
          titleWidget: TextField(
            controller: _searchController,
            autofocus: true,
            style: TextStyle(color: isDark ? Colors.white : const Color(0xFF1E1B4B)),
            decoration: InputDecoration(
              hintText: 'Search users...',
              hintStyle: TextStyle(color: isDark ? Colors.white38 : Colors.grey),
              border: InputBorder.none,
            ),
            onChanged: _onSearchChanged,
          ),
        ),
        body: state.searchResults.isEmpty
            ? Center(child: Column(mainAxisAlignment: MainAxisAlignment.center, children: [
                Container(
                  padding: const EdgeInsets.all(20),
                  decoration: BoxDecoration(shape: BoxShape.circle, color: AppTheme.primaryPurple.withValues(alpha: 0.1)),
                  child: Icon(Icons.search, size: 48, color: isDark ? Colors.white24 : Colors.grey[600]),
                ).animate().fadeIn(duration: 500.ms),
                const SizedBox(height: 16),
                Text(
                  _searchController.text.isEmpty ? 'Search for users by name or email' : 'No results found',
                  style: TextStyle(color: isDark ? Colors.white54 : Colors.grey[700]),
                ).animate().fadeIn(duration: 500.ms, delay: 100.ms),
              ]))
            : ListView.builder(
                padding: EdgeInsets.fromLTRB(16, MediaQuery.of(context).padding.top + kToolbarHeight + 8, 16, 32),
                itemCount: state.searchResults.length,
                itemBuilder: (context, index) {
                  final user = state.searchResults[index];
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
                          backgroundImage: user.avatarUrl != null ? NetworkImage(user.avatarUrl!) : null,
                          child: user.avatarUrl == null
                              ? Text(user.displayName.isNotEmpty ? user.displayName[0].toUpperCase() : '?', style: TextStyle(color: AppTheme.primaryPurple, fontWeight: FontWeight.bold))
                              : null,
                        ),
                        const SizedBox(width: 12),
                        Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                          Text(user.displayName, style: TextStyle(fontWeight: FontWeight.w600, color: isDark ? Colors.white : const Color(0xFF1E1B4B))),
                          Text(user.email, style: TextStyle(fontSize: 13, color: isDark ? Colors.white54 : Colors.grey[600])),
                        ])),
                        if (user.isFriend)
                          Container(
                            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                            decoration: BoxDecoration(color: AppTheme.success.withValues(alpha: 0.12), borderRadius: BorderRadius.circular(6)),
                            child: Text('Friend', style: TextStyle(color: AppTheme.success, fontSize: 12, fontWeight: FontWeight.w600)),
                          )
                        else
                          Row(mainAxisSize: MainAxisSize.min, children: [
                            _actionButton(Icons.person_add, 'Add', () async {
                              try {
                                await ref.read(socialProvider.notifier).sendFriendRequest(user.id);
                                if (mounted) ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Friend request sent!')));
                              } catch (e) {
                                if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Error: $e')));
                              }
                            }),
                            if (!user.isFollowing) ...[
                              const SizedBox(width: 6),
                              _actionButton(Icons.add_circle_outline, 'Follow', () async {
                                try {
                                  await ref.read(socialProvider.notifier).followUser(user.id);
                                  if (mounted) ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Following!')));
                                } catch (e) {
                                  if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Error: $e')));
                                }
                              }),
                            ],
                          ]),
                      ]),
                    ),
                  );
                },
              ),
      ),
    );
  }

  Widget _actionButton(IconData icon, String tooltip, VoidCallback onTap) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    return Tooltip(
      message: tooltip,
      child: GestureDetector(
        onTap: onTap,
        child: Container(
          padding: const EdgeInsets.all(8),
          decoration: BoxDecoration(
            color: AppTheme.primaryPurple.withValues(alpha: isDark ? 0.2 : 0.1),
            borderRadius: BorderRadius.circular(8),
          ),
          child: Icon(icon, color: AppTheme.primaryPurple, size: 18),
        ),
      ),
    );
  }
}
