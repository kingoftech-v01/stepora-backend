import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../config/api_constants.dart';
import '../models/store_item.dart';
import '../services/api_service.dart';

class StoreState {
  final List<StoreItem> items;
  final List<StoreItem> featuredItems;
  final List<StoreCategory> categories;
  final List<InventoryItem> inventory;
  final bool isLoading;
  final String? selectedCategory;

  const StoreState({
    this.items = const [],
    this.featuredItems = const [],
    this.categories = const [],
    this.inventory = const [],
    this.isLoading = false,
    this.selectedCategory,
  });

  StoreState copyWith({
    List<StoreItem>? items,
    List<StoreItem>? featuredItems,
    List<StoreCategory>? categories,
    List<InventoryItem>? inventory,
    bool? isLoading,
    String? selectedCategory,
    bool clearCategory = false,
  }) {
    return StoreState(
      items: items ?? this.items,
      featuredItems: featuredItems ?? this.featuredItems,
      categories: categories ?? this.categories,
      inventory: inventory ?? this.inventory,
      isLoading: isLoading ?? this.isLoading,
      selectedCategory: clearCategory ? null : (selectedCategory ?? this.selectedCategory),
    );
  }

  List<StoreItem> get filteredItems {
    if (selectedCategory == null) return items;
    return items.where((i) => i.categorySlug == selectedCategory).toList();
  }
}

class StoreNotifier extends Notifier<StoreState> {
  late ApiService _api;

  @override
  StoreState build() {
    _api = ref.read(apiServiceProvider);
    return const StoreState();
  }

  Future<void> fetchItems() async {
    state = state.copyWith(isLoading: true);
    try {
      final response = await _api.get(ApiConstants.storeItems);
      final results = response.data['results'] as List? ?? response.data as List? ?? [];
      state = state.copyWith(
        items: results.map((j) => StoreItem.fromJson(j)).toList(),
        isLoading: false,
      );
    } catch (_) {
      state = state.copyWith(isLoading: false);
    }
  }

  Future<void> fetchFeaturedItems() async {
    try {
      final response = await _api.get(ApiConstants.storeFeatured);
      final results = response.data['results'] as List? ?? response.data as List? ?? [];
      state = state.copyWith(
        featuredItems: results.map((j) => StoreItem.fromJson(j)).toList(),
      );
    } catch (_) {}
  }

  Future<void> fetchCategories() async {
    try {
      final response = await _api.get(ApiConstants.storeCategories);
      final results = response.data['results'] as List? ?? response.data as List? ?? [];
      state = state.copyWith(
        categories: results.map((j) => StoreCategory.fromJson(j)).toList(),
      );
    } catch (_) {}
  }

  Future<void> fetchInventory() async {
    try {
      final response = await _api.get(ApiConstants.storeInventory);
      final results = response.data['results'] as List? ?? response.data as List? ?? [];
      state = state.copyWith(
        inventory: results.map((j) => InventoryItem.fromJson(j)).toList(),
      );
    } catch (_) {}
  }

  void selectCategory(String? slug) {
    if (slug == null) {
      state = state.copyWith(clearCategory: true);
    } else {
      state = state.copyWith(selectedCategory: slug);
    }
  }

  Future<void> purchaseWithXp(String itemId) async {
    await _api.post(ApiConstants.storePurchaseXp, data: {'item_id': itemId});
    await fetchInventory();
  }

  Future<void> equipItem(String inventoryId) async {
    await _api.post(ApiConstants.storeInventoryEquip(inventoryId));
    await fetchInventory();
  }

  Future<void> loadAll() async {
    state = state.copyWith(isLoading: true);
    await Future.wait([
      fetchItems(),
      fetchFeaturedItems(),
      fetchCategories(),
      fetchInventory(),
    ]);
    state = state.copyWith(isLoading: false);
  }
}

final storeProvider = NotifierProvider<StoreNotifier, StoreState>(StoreNotifier.new);
