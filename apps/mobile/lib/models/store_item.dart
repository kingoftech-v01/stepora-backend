import 'dart:ui';
import 'package:equatable/equatable.dart';

class StoreItem extends Equatable {
  final String id;
  final String name;
  final String description;
  final String itemType;
  final String rarity;
  final int price;
  final int? xpPrice;
  final String? imageUrl;
  final bool isFeatured;
  final String? categorySlug;

  const StoreItem({
    required this.id,
    required this.name,
    this.description = '',
    this.itemType = '',
    this.rarity = 'common',
    this.price = 0,
    this.xpPrice,
    this.imageUrl,
    this.isFeatured = false,
    this.categorySlug,
  });

  factory StoreItem.fromJson(Map<String, dynamic> json) {
    return StoreItem(
      id: json['id']?.toString() ?? '',
      name: json['name'] ?? '',
      description: json['description'] ?? '',
      itemType: json['item_type'] ?? '',
      rarity: json['rarity'] ?? 'common',
      price: json['price'] ?? 0,
      xpPrice: json['xp_price'],
      imageUrl: json['image_url'] ?? json['image'],
      isFeatured: json['is_featured'] ?? false,
      categorySlug: json['category']?.toString(),
    );
  }

  Color get rarityColor {
    switch (rarity) {
      case 'rare': return const Color(0xFF2196F3);
      case 'epic': return const Color(0xFF9C27B0);
      case 'legendary': return const Color(0xFFFF9800);
      default: return const Color(0xFF9E9E9E);
    }
  }

  @override
  List<Object?> get props => [id];
}

class InventoryItem extends Equatable {
  final String id;
  final StoreItem item;
  final bool isEquipped;
  final DateTime purchasedAt;

  const InventoryItem({
    required this.id,
    required this.item,
    this.isEquipped = false,
    required this.purchasedAt,
  });

  factory InventoryItem.fromJson(Map<String, dynamic> json) {
    return InventoryItem(
      id: json['id']?.toString() ?? '',
      item: StoreItem.fromJson(json['item'] ?? json),
      isEquipped: json['is_equipped'] ?? false,
      purchasedAt: DateTime.parse(json['purchased_at'] ?? json['created_at'] ?? DateTime.now().toIso8601String()),
    );
  }

  @override
  List<Object?> get props => [id];
}

class StoreCategory extends Equatable {
  final String slug;
  final String name;

  const StoreCategory({required this.slug, required this.name});

  factory StoreCategory.fromJson(Map<String, dynamic> json) {
    return StoreCategory(
      slug: json['slug'] ?? json['id']?.toString() ?? '',
      name: json['name'] ?? '',
    );
  }

  @override
  List<Object?> get props => [slug];
}
