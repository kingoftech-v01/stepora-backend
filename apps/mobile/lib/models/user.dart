import 'package:equatable/equatable.dart';

class User extends Equatable {
  final String id;
  final String email;
  final String displayName;
  final String? avatarUrl;
  final String timezone;
  final String subscription;
  final DateTime? subscriptionEnds;
  final int xp;
  final int level;
  final int streakDays;
  final DateTime? lastActivity;
  final bool canCreateDream;
  final bool isPremium;
  final DateTime createdAt;

  const User({
    required this.id,
    required this.email,
    this.displayName = '',
    this.avatarUrl,
    this.timezone = 'Europe/Paris',
    this.subscription = 'free',
    this.subscriptionEnds,
    this.xp = 0,
    this.level = 1,
    this.streakDays = 0,
    this.lastActivity,
    this.canCreateDream = true,
    this.isPremium = false,
    required this.createdAt,
  });

  factory User.fromJson(Map<String, dynamic> json) {
    return User(
      id: json['id'],
      email: json['email'],
      displayName: json['display_name'] ?? '',
      avatarUrl: json['avatar_url'],
      timezone: json['timezone'] ?? 'Europe/Paris',
      subscription: json['subscription'] ?? 'free',
      subscriptionEnds: json['subscription_ends'] != null
          ? DateTime.parse(json['subscription_ends'])
          : null,
      xp: json['xp'] ?? 0,
      level: json['level'] ?? 1,
      streakDays: json['streak_days'] ?? 0,
      lastActivity: json['last_activity'] != null
          ? DateTime.parse(json['last_activity'])
          : null,
      canCreateDream: json['can_create_dream'] ?? true,
      isPremium: json['is_premium'] ?? false,
      createdAt: DateTime.parse(json['created_at']),
    );
  }

  Map<String, dynamic> toJson() => {
    'display_name': displayName,
    'avatar_url': avatarUrl,
    'timezone': timezone,
  };

  @override
  List<Object?> get props => [id, email];
}

class GamificationProfile {
  final int healthXp;
  final int careerXp;
  final int relationshipsXp;
  final int personalGrowthXp;
  final int financeXp;
  final int hobbiesXp;
  final int healthLevel;
  final int careerLevel;
  final int relationshipsLevel;
  final int personalGrowthLevel;
  final List<dynamic> badges;
  final List<dynamic> achievements;
  final int streakJokers;

  const GamificationProfile({
    this.healthXp = 0,
    this.careerXp = 0,
    this.relationshipsXp = 0,
    this.personalGrowthXp = 0,
    this.financeXp = 0,
    this.hobbiesXp = 0,
    this.healthLevel = 1,
    this.careerLevel = 1,
    this.relationshipsLevel = 1,
    this.personalGrowthLevel = 1,
    this.badges = const [],
    this.achievements = const [],
    this.streakJokers = 0,
  });

  factory GamificationProfile.fromJson(Map<String, dynamic> json) {
    return GamificationProfile(
      healthXp: json['health_xp'] ?? 0,
      careerXp: json['career_xp'] ?? 0,
      relationshipsXp: json['relationships_xp'] ?? 0,
      personalGrowthXp: json['personal_growth_xp'] ?? 0,
      financeXp: json['finance_xp'] ?? 0,
      hobbiesXp: json['hobbies_xp'] ?? 0,
      healthLevel: json['health_level'] ?? 1,
      careerLevel: json['career_level'] ?? 1,
      relationshipsLevel: json['relationships_level'] ?? 1,
      personalGrowthLevel: json['personal_growth_level'] ?? 1,
      badges: json['badges'] ?? [],
      achievements: json['achievements'] ?? [],
      streakJokers: json['streak_jokers'] ?? 0,
    );
  }
}
