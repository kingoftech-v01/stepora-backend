import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../core/theme/app_theme.dart';
import '../../providers/social_provider.dart';

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

    return Scaffold(
      appBar: AppBar(
        title: const Text('Friends'),
        actions: [
          if (state.pendingCount > 0)
            Badge(
              label: Text('${state.pendingCount}'),
              child: IconButton(
                icon: const Icon(Icons.person_add),
                onPressed: () => context.push('/social/requests'),
              ),
            )
          else
            IconButton(
              icon: const Icon(Icons.person_add),
              onPressed: () => context.push('/social/requests'),
            ),
          IconButton(
            icon: const Icon(Icons.search),
            onPressed: () => context.push('/social/search'),
          ),
        ],
      ),
      body: state.isLoading
          ? const Center(child: CircularProgressIndicator())
          : state.friends.isEmpty
              ? Center(
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Icon(Icons.people_outline, size: 64, color: Colors.grey[300]),
                      const SizedBox(height: 16),
                      Text('No friends yet', style: TextStyle(color: Colors.grey[500], fontSize: 16)),
                      const SizedBox(height: 8),
                      FilledButton.icon(
                        onPressed: () => context.push('/social/search'),
                        icon: const Icon(Icons.search),
                        label: const Text('Find People'),
                        style: FilledButton.styleFrom(backgroundColor: AppTheme.primaryPurple),
                      ),
                    ],
                  ),
                )
              : RefreshIndicator(
                  onRefresh: () => ref.read(socialProvider.notifier).fetchFriends(),
                  child: ListView.builder(
                    padding: const EdgeInsets.all(16),
                    itemCount: state.friends.length,
                    itemBuilder: (context, index) {
                      final friend = state.friends[index];
                      return Card(
                        margin: const EdgeInsets.only(bottom: 8),
                        child: ListTile(
                          leading: CircleAvatar(
                            backgroundColor: AppTheme.primaryPurple.withValues(alpha: 0.1),
                            backgroundImage: friend.avatarUrl != null ? NetworkImage(friend.avatarUrl!) : null,
                            child: friend.avatarUrl == null
                                ? Text(friend.displayName.isNotEmpty ? friend.displayName[0].toUpperCase() : '?')
                                : null,
                          ),
                          title: Text(friend.displayName, style: const TextStyle(fontWeight: FontWeight.w600)),
                          subtitle: Text(friend.email),
                          trailing: PopupMenuButton(
                            itemBuilder: (_) => [
                              const PopupMenuItem(value: 'remove', child: Text('Remove Friend')),
                            ],
                            onSelected: (value) async {
                              if (value == 'remove') {
                                final confirmed = await showDialog<bool>(
                                  context: context,
                                  builder: (ctx) => AlertDialog(
                                    title: const Text('Remove Friend?'),
                                    actions: [
                                      TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancel')),
                                      TextButton(onPressed: () => Navigator.pop(ctx, true), child: const Text('Remove', style: TextStyle(color: Colors.red))),
                                    ],
                                  ),
                                );
                                if (confirmed == true) {
                                  await ref.read(socialProvider.notifier).removeFriend(friend.id);
                                }
                              }
                            },
                          ),
                        ),
                      );
                    },
                  ),
                ),
    );
  }
}
