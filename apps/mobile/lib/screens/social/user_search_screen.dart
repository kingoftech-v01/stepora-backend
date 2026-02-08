import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../core/theme/app_theme.dart';
import '../../providers/social_provider.dart';

class UserSearchScreen extends ConsumerStatefulWidget {
  const UserSearchScreen({super.key});

  @override
  ConsumerState<UserSearchScreen> createState() => _UserSearchScreenState();
}

class _UserSearchScreenState extends ConsumerState<UserSearchScreen> {
  final _searchController = TextEditingController();
  Timer? _debounce;

  @override
  void dispose() {
    _searchController.dispose();
    _debounce?.cancel();
    super.dispose();
  }

  void _onSearchChanged(String query) {
    _debounce?.cancel();
    _debounce = Timer(const Duration(milliseconds: 400), () {
      ref.read(socialProvider.notifier).searchUsers(query);
    });
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(socialProvider);

    return Scaffold(
      appBar: AppBar(
        title: TextField(
          controller: _searchController,
          autofocus: true,
          decoration: const InputDecoration(
            hintText: 'Search users...',
            border: InputBorder.none,
          ),
          onChanged: _onSearchChanged,
        ),
      ),
      body: state.searchResults.isEmpty
          ? Center(
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Icon(Icons.search, size: 64, color: Colors.grey[300]),
                  const SizedBox(height: 16),
                  Text(
                    _searchController.text.isEmpty ? 'Search for users by name or email' : 'No results found',
                    style: TextStyle(color: Colors.grey[500]),
                  ),
                ],
              ),
            )
          : ListView.builder(
              padding: const EdgeInsets.all(16),
              itemCount: state.searchResults.length,
              itemBuilder: (context, index) {
                final user = state.searchResults[index];
                return Card(
                  margin: const EdgeInsets.only(bottom: 8),
                  child: ListTile(
                    leading: CircleAvatar(
                      backgroundColor: AppTheme.primaryPurple.withValues(alpha: 0.1),
                      backgroundImage: user.avatarUrl != null ? NetworkImage(user.avatarUrl!) : null,
                      child: user.avatarUrl == null
                          ? Text(user.displayName.isNotEmpty ? user.displayName[0].toUpperCase() : '?')
                          : null,
                    ),
                    title: Text(user.displayName, style: const TextStyle(fontWeight: FontWeight.w600)),
                    subtitle: Text(user.email),
                    trailing: user.isFriend
                        ? const Chip(label: Text('Friend'))
                        : Row(
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              IconButton(
                                icon: const Icon(Icons.person_add),
                                tooltip: 'Add Friend',
                                onPressed: () async {
                                  try {
                                    await ref.read(socialProvider.notifier).sendFriendRequest(user.id);
                                    if (mounted) {
                                      ScaffoldMessenger.of(context).showSnackBar(
                                        const SnackBar(content: Text('Friend request sent!')),
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
                              if (!user.isFollowing)
                                IconButton(
                                  icon: const Icon(Icons.add_circle_outline),
                                  tooltip: 'Follow',
                                  onPressed: () async {
                                    try {
                                      await ref.read(socialProvider.notifier).followUser(user.id);
                                      if (mounted) {
                                        ScaffoldMessenger.of(context).showSnackBar(
                                          const SnackBar(content: Text('Following!')),
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
                            ],
                          ),
                  ),
                );
              },
            ),
    );
  }
}
