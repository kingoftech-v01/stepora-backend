import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../core/theme/app_theme.dart';
import '../../models/store_item.dart';
import '../../providers/store_provider.dart';

class StoreScreen extends ConsumerStatefulWidget {
  const StoreScreen({super.key});

  @override
  ConsumerState<StoreScreen> createState() => _StoreScreenState();
}

class _StoreScreenState extends ConsumerState<StoreScreen> with SingleTickerProviderStateMixin {
  late TabController _tabController;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 2, vsync: this);
    Future.microtask(() => ref.read(storeProvider.notifier).loadAll());
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(storeProvider);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Store'),
        bottom: TabBar(
          controller: _tabController,
          tabs: const [
            Tab(text: 'Shop'),
            Tab(text: 'My Items'),
          ],
        ),
      ),
      body: state.isLoading
          ? const Center(child: CircularProgressIndicator())
          : TabBarView(
              controller: _tabController,
              children: [
                _ShopTab(state: state, ref: ref),
                _InventoryTab(state: state, ref: ref),
              ],
            ),
    );
  }
}

class _ShopTab extends StatelessWidget {
  final StoreState state;
  final WidgetRef ref;

  const _ShopTab({required this.state, required this.ref});

  @override
  Widget build(BuildContext context) {
    return RefreshIndicator(
      onRefresh: () => ref.read(storeProvider.notifier).loadAll(),
      child: CustomScrollView(
        slivers: [
          // Category filter chips
          if (state.categories.isNotEmpty)
            SliverToBoxAdapter(
              child: SizedBox(
                height: 50,
                child: ListView(
                  scrollDirection: Axis.horizontal,
                  padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                  children: [
                    Padding(
                      padding: const EdgeInsets.only(right: 8),
                      child: FilterChip(
                        label: const Text('All'),
                        selected: state.selectedCategory == null,
                        onSelected: (_) => ref.read(storeProvider.notifier).selectCategory(null),
                        selectedColor: AppTheme.primaryPurple.withValues(alpha: 0.15),
                      ),
                    ),
                    ...state.categories.map((cat) => Padding(
                      padding: const EdgeInsets.only(right: 8),
                      child: FilterChip(
                        label: Text(cat.name),
                        selected: state.selectedCategory == cat.slug,
                        onSelected: (_) => ref.read(storeProvider.notifier).selectCategory(cat.slug),
                        selectedColor: AppTheme.primaryPurple.withValues(alpha: 0.15),
                      ),
                    )),
                  ],
                ),
              ),
            ),

          // Featured items
          if (state.featuredItems.isNotEmpty) ...[
            const SliverToBoxAdapter(
              child: Padding(
                padding: EdgeInsets.fromLTRB(16, 8, 16, 8),
                child: Text('Featured', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
              ),
            ),
            SliverToBoxAdapter(
              child: SizedBox(
                height: 180,
                child: ListView.builder(
                  scrollDirection: Axis.horizontal,
                  padding: const EdgeInsets.symmetric(horizontal: 12),
                  itemCount: state.featuredItems.length,
                  itemBuilder: (context, index) {
                    final item = state.featuredItems[index];
                    return _FeaturedItemCard(item: item, ref: ref);
                  },
                ),
              ),
            ),
          ],

          // All items grid
          SliverToBoxAdapter(
            child: Padding(
              padding: const EdgeInsets.fromLTRB(16, 16, 16, 8),
              child: Text(
                state.selectedCategory != null ? 'Items' : 'All Items',
                style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
              ),
            ),
          ),
          state.filteredItems.isEmpty
              ? SliverFillRemaining(
                  child: Center(
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Icon(Icons.store_outlined, size: 64, color: Colors.grey[300]),
                        const SizedBox(height: 16),
                        Text('No items available', style: TextStyle(color: Colors.grey[500])),
                      ],
                    ),
                  ),
                )
              : SliverPadding(
                  padding: const EdgeInsets.symmetric(horizontal: 16),
                  sliver: SliverGrid(
                    gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                      crossAxisCount: 2,
                      childAspectRatio: 0.72,
                      crossAxisSpacing: 12,
                      mainAxisSpacing: 12,
                    ),
                    delegate: SliverChildBuilderDelegate(
                      (context, index) {
                        final item = state.filteredItems[index];
                        return _StoreItemCard(item: item, ref: ref);
                      },
                      childCount: state.filteredItems.length,
                    ),
                  ),
                ),
          const SliverToBoxAdapter(child: SizedBox(height: 16)),
        ],
      ),
    );
  }
}

class _FeaturedItemCard extends StatelessWidget {
  final StoreItem item;
  final WidgetRef ref;

  const _FeaturedItemCard({required this.item, required this.ref});

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 160,
      margin: const EdgeInsets.symmetric(horizontal: 4),
      child: Card(
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(16),
          side: BorderSide(color: item.rarityColor, width: 2),
        ),
        child: Padding(
          padding: const EdgeInsets.all(12),
          child: Column(
            children: [
              Expanded(
                child: Icon(_getItemIcon(item.itemType), size: 48, color: item.rarityColor),
              ),
              Text(
                item.name,
                style: const TextStyle(fontWeight: FontWeight.bold),
                textAlign: TextAlign.center,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
              ),
              const SizedBox(height: 2),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                decoration: BoxDecoration(
                  color: item.rarityColor.withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Text(
                  item.rarity.toUpperCase(),
                  style: TextStyle(fontSize: 10, fontWeight: FontWeight.bold, color: item.rarityColor),
                ),
              ),
              const SizedBox(height: 8),
              FilledButton(
                onPressed: () => _showPurchaseSheet(context, item, ref),
                style: FilledButton.styleFrom(
                  backgroundColor: item.rarityColor,
                  minimumSize: const Size(double.infinity, 32),
                  padding: EdgeInsets.zero,
                ),
                child: Text('${item.xpPrice ?? item.price} XP', style: const TextStyle(fontSize: 12)),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _StoreItemCard extends StatelessWidget {
  final StoreItem item;
  final WidgetRef ref;

  const _StoreItemCard({required this.item, required this.ref});

  @override
  Widget build(BuildContext context) {
    return Card(
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: BorderSide(color: item.rarityColor.withValues(alpha: 0.4), width: 1.5),
      ),
      child: InkWell(
        borderRadius: BorderRadius.circular(12),
        onTap: () => _showPurchaseSheet(context, item, ref),
        child: Padding(
          padding: const EdgeInsets.all(12),
          child: Column(
            children: [
              Expanded(
                child: Icon(_getItemIcon(item.itemType), size: 44, color: item.rarityColor),
              ),
              Text(
                item.name,
                style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 14),
                textAlign: TextAlign.center,
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
              ),
              const SizedBox(height: 4),
              Text(
                item.description,
                style: TextStyle(fontSize: 11, color: Colors.grey[600]),
                textAlign: TextAlign.center,
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
              ),
              const SizedBox(height: 8),
              Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                    decoration: BoxDecoration(
                      color: item.rarityColor.withValues(alpha: 0.1),
                      borderRadius: BorderRadius.circular(6),
                    ),
                    child: Text(
                      item.rarity,
                      style: TextStyle(fontSize: 10, color: item.rarityColor, fontWeight: FontWeight.w600),
                    ),
                  ),
                  const Spacer(),
                  Text(
                    '${item.xpPrice ?? item.price} XP',
                    style: TextStyle(
                      fontWeight: FontWeight.bold,
                      color: AppTheme.primaryPurple,
                    ),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _InventoryTab extends StatelessWidget {
  final StoreState state;
  final WidgetRef ref;

  const _InventoryTab({required this.state, required this.ref});

  @override
  Widget build(BuildContext context) {
    if (state.inventory.isEmpty) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.inventory_2_outlined, size: 64, color: Colors.grey[300]),
            const SizedBox(height: 16),
            Text('No items yet', style: TextStyle(color: Colors.grey[500], fontSize: 16)),
            const SizedBox(height: 8),
            Text('Purchase items from the Shop tab', style: TextStyle(color: Colors.grey[400])),
          ],
        ),
      );
    }

    return GridView.builder(
      padding: const EdgeInsets.all(16),
      gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
        crossAxisCount: 2,
        childAspectRatio: 0.8,
        crossAxisSpacing: 12,
        mainAxisSpacing: 12,
      ),
      itemCount: state.inventory.length,
      itemBuilder: (context, index) {
        final inv = state.inventory[index];
        return Card(
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(12),
            side: BorderSide(
              color: inv.isEquipped ? AppTheme.success : inv.item.rarityColor.withValues(alpha: 0.3),
              width: inv.isEquipped ? 2.5 : 1,
            ),
          ),
          child: InkWell(
            borderRadius: BorderRadius.circular(12),
            onTap: () async {
              try {
                await ref.read(storeProvider.notifier).equipItem(inv.id);
              } catch (e) {
                if (context.mounted) {
                  ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Error: $e')));
                }
              }
            },
            child: Stack(
              children: [
                Padding(
                  padding: const EdgeInsets.all(12),
                  child: Column(
                    children: [
                      Expanded(
                        child: Icon(_getItemIcon(inv.item.itemType), size: 44, color: inv.item.rarityColor),
                      ),
                      Text(
                        inv.item.name,
                        style: const TextStyle(fontWeight: FontWeight.w600),
                        textAlign: TextAlign.center,
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                      ),
                      const SizedBox(height: 4),
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                        decoration: BoxDecoration(
                          color: inv.item.rarityColor.withValues(alpha: 0.1),
                          borderRadius: BorderRadius.circular(6),
                        ),
                        child: Text(
                          inv.item.rarity,
                          style: TextStyle(fontSize: 10, color: inv.item.rarityColor, fontWeight: FontWeight.w600),
                        ),
                      ),
                      const SizedBox(height: 8),
                      SizedBox(
                        width: double.infinity,
                        child: inv.isEquipped
                            ? OutlinedButton(
                                onPressed: () async {
                                  await ref.read(storeProvider.notifier).equipItem(inv.id);
                                },
                                style: OutlinedButton.styleFrom(foregroundColor: AppTheme.success),
                                child: const Text('Unequip', style: TextStyle(fontSize: 12)),
                              )
                            : FilledButton(
                                onPressed: () async {
                                  await ref.read(storeProvider.notifier).equipItem(inv.id);
                                },
                                style: FilledButton.styleFrom(
                                  backgroundColor: AppTheme.primaryPurple,
                                  padding: EdgeInsets.zero,
                                ),
                                child: const Text('Equip', style: TextStyle(fontSize: 12)),
                              ),
                      ),
                    ],
                  ),
                ),
                if (inv.isEquipped)
                  Positioned(
                    top: 8,
                    right: 8,
                    child: Container(
                      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                      decoration: BoxDecoration(
                        color: AppTheme.success,
                        borderRadius: BorderRadius.circular(8),
                      ),
                      child: const Text(
                        'Equipped',
                        style: TextStyle(color: Colors.white, fontSize: 10, fontWeight: FontWeight.bold),
                      ),
                    ),
                  ),
              ],
            ),
          ),
        );
      },
    );
  }
}

void _showPurchaseSheet(BuildContext context, StoreItem item, WidgetRef ref) {
  showModalBottomSheet(
    context: context,
    shape: const RoundedRectangleBorder(
      borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
    ),
    builder: (ctx) => Padding(
      padding: const EdgeInsets.all(24),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(_getItemIcon(item.itemType), size: 64, color: item.rarityColor),
          const SizedBox(height: 12),
          Text(item.name, style: const TextStyle(fontSize: 20, fontWeight: FontWeight.bold)),
          const SizedBox(height: 8),
          Text(item.description, textAlign: TextAlign.center, style: TextStyle(color: Colors.grey[600])),
          const SizedBox(height: 8),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
            decoration: BoxDecoration(
              color: item.rarityColor.withValues(alpha: 0.1),
              borderRadius: BorderRadius.circular(12),
            ),
            child: Text(
              item.rarity.toUpperCase(),
              style: TextStyle(fontWeight: FontWeight.bold, color: item.rarityColor),
            ),
          ),
          const SizedBox(height: 20),
          SizedBox(
            width: double.infinity,
            child: FilledButton(
              onPressed: () async {
                Navigator.pop(ctx);
                try {
                  await ref.read(storeProvider.notifier).purchaseWithXp(item.id);
                  if (context.mounted) {
                    ScaffoldMessenger.of(context).showSnackBar(
                      const SnackBar(content: Text('Purchased!')),
                    );
                  }
                } catch (e) {
                  if (context.mounted) {
                    ScaffoldMessenger.of(context).showSnackBar(
                      SnackBar(content: Text('Error: $e')),
                    );
                  }
                }
              },
              style: FilledButton.styleFrom(
                backgroundColor: AppTheme.primaryPurple,
                padding: const EdgeInsets.symmetric(vertical: 14),
              ),
              child: Text('Buy for ${item.xpPrice ?? item.price} XP'),
            ),
          ),
          const SizedBox(height: 8),
        ],
      ),
    ),
  );
}

IconData _getItemIcon(String type) {
  switch (type) {
    case 'theme': return Icons.palette;
    case 'avatar': return Icons.face;
    case 'boost': return Icons.bolt;
    case 'streak_joker': return Icons.casino;
    case 'badge': return Icons.military_tech;
    case 'frame': return Icons.crop_square;
    default: return Icons.card_giftcard;
  }
}
