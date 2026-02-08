import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../config/api_constants.dart';
import '../services/api_service.dart';

class SocialUser {
  final String id;
  final String email;
  final String displayName;
  final String? avatarUrl;
  final bool isFriend;
  final bool isFollowing;

  const SocialUser({
    required this.id,
    required this.email,
    this.displayName = '',
    this.avatarUrl,
    this.isFriend = false,
    this.isFollowing = false,
  });

  factory SocialUser.fromJson(Map<String, dynamic> json) {
    return SocialUser(
      id: json['id']?.toString() ?? '',
      email: json['email'] ?? '',
      displayName: json['display_name'] ?? json['username'] ?? json['email'] ?? '',
      avatarUrl: json['avatar_url'] ?? json['avatar'],
      isFriend: json['is_friend'] ?? false,
      isFollowing: json['is_following'] ?? false,
    );
  }
}

class FriendRequest {
  final String id;
  final SocialUser fromUser;
  final String status;
  final DateTime createdAt;

  const FriendRequest({
    required this.id,
    required this.fromUser,
    this.status = 'pending',
    required this.createdAt,
  });

  factory FriendRequest.fromJson(Map<String, dynamic> json) {
    return FriendRequest(
      id: json['id']?.toString() ?? '',
      fromUser: SocialUser.fromJson(json['from_user'] ?? json['sender'] ?? {}),
      status: json['status'] ?? 'pending',
      createdAt: DateTime.parse(json['created_at'] ?? DateTime.now().toIso8601String()),
    );
  }
}

class SocialState {
  final List<SocialUser> friends;
  final List<FriendRequest> pendingRequests;
  final List<FriendRequest> sentRequests;
  final List<SocialUser> searchResults;
  final bool isLoading;
  final int pendingCount;

  const SocialState({
    this.friends = const [],
    this.pendingRequests = const [],
    this.sentRequests = const [],
    this.searchResults = const [],
    this.isLoading = false,
    this.pendingCount = 0,
  });

  SocialState copyWith({
    List<SocialUser>? friends,
    List<FriendRequest>? pendingRequests,
    List<FriendRequest>? sentRequests,
    List<SocialUser>? searchResults,
    bool? isLoading,
    int? pendingCount,
  }) {
    return SocialState(
      friends: friends ?? this.friends,
      pendingRequests: pendingRequests ?? this.pendingRequests,
      sentRequests: sentRequests ?? this.sentRequests,
      searchResults: searchResults ?? this.searchResults,
      isLoading: isLoading ?? this.isLoading,
      pendingCount: pendingCount ?? this.pendingCount,
    );
  }
}

class SocialNotifier extends Notifier<SocialState> {
  late ApiService _api;

  @override
  SocialState build() {
    _api = ref.read(apiServiceProvider);
    return const SocialState();
  }

  Future<void> fetchFriends() async {
    state = state.copyWith(isLoading: true);
    try {
      final response = await _api.get(ApiConstants.socialFriends);
      final results = response.data['results'] as List? ?? response.data as List? ?? [];
      state = state.copyWith(
        friends: results.map((j) => SocialUser.fromJson(j)).toList(),
        isLoading: false,
      );
    } catch (_) {
      state = state.copyWith(isLoading: false);
    }
  }

  Future<void> fetchPendingRequests() async {
    try {
      final response = await _api.get(ApiConstants.socialFriendsPending);
      final results = response.data['results'] as List? ?? response.data as List? ?? [];
      final requests = results.map((j) => FriendRequest.fromJson(j)).toList();
      state = state.copyWith(pendingRequests: requests, pendingCount: requests.length);
    } catch (_) {}
  }

  Future<void> fetchSentRequests() async {
    try {
      final response = await _api.get(ApiConstants.socialFriendsSent);
      final results = response.data['results'] as List? ?? response.data as List? ?? [];
      state = state.copyWith(sentRequests: results.map((j) => FriendRequest.fromJson(j)).toList());
    } catch (_) {}
  }

  Future<void> searchUsers(String query) async {
    if (query.trim().isEmpty) {
      state = state.copyWith(searchResults: []);
      return;
    }
    try {
      final response = await _api.get(ApiConstants.socialSearch, queryParams: {'q': query});
      final results = response.data['results'] as List? ?? response.data as List? ?? [];
      state = state.copyWith(searchResults: results.map((j) => SocialUser.fromJson(j)).toList());
    } catch (_) {}
  }

  Future<void> sendFriendRequest(String userId) async {
    await _api.post(ApiConstants.socialFriendRequest, data: {'to_user': userId});
  }

  Future<void> acceptRequest(String requestId) async {
    await _api.post(ApiConstants.socialFriendAccept(requestId));
    await fetchPendingRequests();
    await fetchFriends();
  }

  Future<void> rejectRequest(String requestId) async {
    await _api.post(ApiConstants.socialFriendReject(requestId));
    await fetchPendingRequests();
  }

  Future<void> removeFriend(String userId) async {
    await _api.delete(ApiConstants.socialFriendRemove(userId));
    await fetchFriends();
  }

  Future<void> followUser(String userId) async {
    await _api.post(ApiConstants.socialFollow, data: {'user_id': userId});
  }

  Future<void> unfollowUser(String userId) async {
    await _api.delete(ApiConstants.socialUnfollow(userId));
  }
}

final socialProvider = NotifierProvider<SocialNotifier, SocialState>(SocialNotifier.new);
