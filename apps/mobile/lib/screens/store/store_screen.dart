import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../core/theme/app_theme.dart';
import '../../models/store_item.dart';
import '../../providers/store_provider.dart';
import '../../widgets/gradient_background.dart';
import '../../widgets/glass_container.dart';
import '../../widgets/glass_app_bar.dart';
import '../../widgets/glass_button.dart';
import '../../widgets/animated_list_item.dart';
import '../../widgets/loading_shimmer.dart';

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
  void dispose() { _tabController.dispose(); super.dispose(); }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(storeProvider);
    final isDark = Theme.of(context).brightness == Brightness.dark;

    return GradientBackground(
      colors: isDark ? AppTheme.gradientStore : AppTheme.gradientStoreLight,
      child: Scaffold(
        backgroundColor: Colors.transparent,
        extendBodyBehindAppBar: true,
        appBar: GlassAppBar(
          title: 'Store',
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
                tabs: const [
                  Tab(text: 'Shop'),
                  Tab(text: 'My Items'),
                ],
              ),
            ),
          ),
        ),
        body: state.isLoading
            ? const Center(child: LoadingShimmer())
            : TabBarView(
                controller: _tabController,
                children: [
                  _ShopTab(state: state, ref: ref, isDark: isDark),
                  _InventoryTab(state: state, ref: ref, isDark: isDark),
                ],
              ),
      ),
    );
  }
}

class _ShopTab extends StatelessWidget {
  final StoreState state;
  final WidgetRef ref;
  final bool isDark;

  const _ShopTab({required this.state, required this.ref, required this.isDark});

  @override
  Widget build(BuildContext context) {
    return RefreshIndicator(
      onRefresh: () => ref.read(storeProvider.notifier).loadAll(),
      child: CustomScrollView(
        slivers: [
          SliverToBoxAdapter(child: SizedBox(height: MediaQuery.of(context).padding.top + kToolbarHeight + 60)),

          // Category filter chips
          if (state.categories.isNotEmpty)
            SliverToBoxAdapter(
              child: SizedBox(
                height: 46,
                child: ListView(
                  scrollDirection: Axis.horizontal,
                  padding: const EdgeInsets.symmetric(horizontal: 16),
                  children: [
                    _GlassFilterChip(
                      label: 'All',
                      isSelected: state.selectedCategory == null,
                      isDark: isDark,
                      onTap: () => ref.read(storeProvider.notifier).selectCategory(null),
                    ),
                    ...state.categories.map((cat) => _GlassFilterChip(
                      label: cat.name,
                      isSelected: state.selectedCategory == cat.slug,
                      isDark: isDark,
                      onTap: () => ref.read(storeProvider.notifier).selectCategory(cat.slug),
                    )),
                  ],
                ),
              ),
            ),

          // Featured items
          if (state.featuredItems.isNotEmpty) ...[
            SliverToBoxAdapter(
              child: Padding(
                padding: const EdgeInsets.fromLTRB(16, 16, 16, 8),
                child: Text('Featured', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: isDark ? Colors.white : const Color(0xFF1E1B4B)))
                  .animate().fadeIn(duration: 400.ms),
              ),
            ),
            SliverToBoxAdapter(
              child: SizedBox(
                height: 190,
                child: ListView.builder(
                  scrollDirection: Axis.horizontal,
                  padding: const EdgeInsets.symmetric(horizontal: 12),
                  itemCount: state.featuredItems.length,
                  itemBuilder: (context, index) {
                    final item = state.featuredItems[index];
                    return AnimatedListItem(
                      index: index,
                      child: _FeaturedItemCard(item: item, ref: ref, isDark: isDark),
                    );
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
                style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: isDark ? Colors.white : const Color(0xFF1E1B4B)),
              ).animate().fadeIn(duration: 400.ms),
            ),
          ),
          state.filteredItems.isEmpty
              ? SliverFillRemaining(
                  child: Center(
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Container(
                          padding: const EdgeInsets.all(20),
                          decoration: BoxDecoration(shape: BoxShape.circle, color: AppTheme.primaryPurple.withValues(alpha: 0.1)),
                          child: Icon(Icons.store_outlined, size: 48, color: isDark ? Colors.white24 : Colors.grey[600]),
                        ).animate().fadeIn(duration: 500.ms),
                        const SizedBox(height: 16),
                        Text('No items available', style: TextStyle(color: isDark ? Colors.white54 : Colors.grey[700]))
                          .animate().fadeIn(duration: 500.ms, delay: 100.ms),
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
                      crossAxisSpacing: 10,
                      mainAxisSpacing: 10,
                    ),
                    delegate: SliverChildBuilderDelegate(
                      (context, index) {
                        final item = state.filteredItems[index];
                        return AnimatedListItem(
                          index: index,
                          child: _StoreItemCard(item: item, ref: ref, isDark: isDark),
                        );
                      },
                      childCount: state.filteredItems.length,
                    ),
                  ),
                ),
          const SliverToBoxAdapter(child: SizedBox(height: 32)),
        ],
      ),
    );
  }
}

class _GlassFilterChip extends StatelessWidget {
  final String label;
  final bool isSelected;
  final bool isDark;
  final VoidCallback onTap;
  const _GlassFilterChip({required this.label, required this.isSelected, required this.isDark, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(right: 8),
      child: GestureDetector(
        onTap: onTap,
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
          decoration: BoxDecoration(
            color: isSelected
                ? AppTheme.primaryPurple.withValues(alpha: 0.25)
                : (isDark ? Colors.white.withValues(alpha: 0.08) : Colors.white.withValues(alpha: 0.3)),
            borderRadius: BorderRadius.circular(20),
            border: Border.all(
              color: isSelected
                  ? AppTheme.primaryPurple.withValues(alpha: 0.5)
                  : (isDark ? Colors.white.withValues(alpha: 0.15) : Colors.white.withValues(alpha: 0.5)),
            ),
          ),
          child: Text(
            label,
            style: TextStyle(
              fontSize: 13,
              fontWeight: isSelected ? FontWeight.w600 : FontWeight.w400,
              color: isSelected
                  ? AppTheme.primaryPurple
                  : (isDark ? Colors.white70 : const Color(0xFF1E1B4B)),
            ),
          ),
        ),
      ),
    );
  }
}

class _FeaturedItemCard extends StatelessWidget {
  final StoreItem item;
  final WidgetRef ref;
  final bool isDark;

  const _FeaturedItemCard({required this.item, required this.ref, required this.isDark});

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 160,
      margin: const EdgeInsets.symmetric(horizontal: 4),
      child: GlassContainer(
        padding: const EdgeInsets.all(12),
        opacity: isDark ? 0.15 : 0.3,
        border: Border.all(color: item.rarityColor.withValues(alpha: 0.5), width: 1.5),
        child: Column(
          children: [
            Expanded(
              child: Container(
                decoration: BoxDecoration(
                  color: item.rarityColor.withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(12),
                  boxShadow: [BoxShadow(color: item.rarityColor.withValues(alpha: 0.15), blurRadius: 12)],
                ),
                child: Center(child: Icon(_getItemIcon(item.itemType), size: 40, color: item.rarityColor)),
              ),
            ),
            const SizedBox(height: 8),
            Text(
              item.name,
              style: TextStyle(fontWeight: FontWeight.bold, fontSize: 13, color: isDark ? Colors.white : const Color(0xFF1E1B4B)),
              textAlign: TextAlign.center,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
            ),
            const SizedBox(height: 4),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
              decoration: BoxDecoration(color: item.rarityColor.withValues(alpha: 0.12), borderRadius: BorderRadius.circular(8)),
              child: Text(item.rarity.toUpperCase(), style: TextStyle(fontSize: 9, fontWeight: FontWeight.bold, color: item.rarityColor)),
            ),
            const SizedBox(height: 8),
            GlassButton(
              label: '${item.xpPrice ?? item.price} XP',
              onPressed: () => _showPurchaseSheet(context, item, ref, isDark),
            ),
          ],
        ),
      ),
    );
  }
}

class _StoreItemCard extends StatelessWidget {
  final StoreItem item;
  final WidgetRef ref;
  final bool isDark;

  const _StoreItemCard({required this.item, required this.ref, required this.isDark});

  @override
  Widget build(BuildContext context) {
    return GlassContainer(
      padding: const EdgeInsets.all(12),
      opacity: isDark ? 0.12 : 0.25,
      border: Border.all(color: item.rarityColor.withValues(alpha: 0.3), width: 1),
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          borderRadius: BorderRadius.circular(16),
          onTap: () => _showPurchaseSheet(context, item, ref, isDark),
          child: Column(
            children: [
              Expanded(
                child: Container(
                  decoration: BoxDecoration(
                    color: item.rarityColor.withValues(alpha: 0.08),
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Center(child: Icon(_getItemIcon(item.itemType), size: 36, color: item.rarityColor)),
                ),
              ),
              const SizedBox(height: 8),
              Text(
                item.name,
                style: TextStyle(fontWeight: FontWeight.w600, fontSize: 13, color: isDark ? Colors.white : const Color(0xFF1E1B4B)),
                textAlign: TextAlign.center,
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
              ),
              const SizedBox(height: 3),
              Text(
                item.description,
                style: TextStyle(fontSize: 10, color: isDark ? Colors.white38 : Colors.grey[600]),
                textAlign: TextAlign.center,
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
              ),
              const SizedBox(height: 6),
              Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 2),
                    decoration: BoxDecoration(color: item.rarityColor.withValues(alpha: 0.12), borderRadius: BorderRadius.circular(6)),
                    child: Text(item.rarity, style: TextStyle(fontSize: 9, color: item.rarityColor, fontWeight: FontWeight.w600)),
                  ),
                  const Spacer(),
                  Text(
                    '${item.xpPrice ?? item.price} XP',
                    style: TextStyle(fontWeight: FontWeight.bold, fontSize: 12, color: AppTheme.primaryPurple),
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
  final bool isDark;

  const _InventoryTab({required this.state, required this.ref, required this.isDark});

  @override
  Widget build(BuildContext context) {
    if (state.inventory.isEmpty) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Container(
              padding: const EdgeInsets.all(20),
              decoration: BoxDecoration(shape: BoxShape.circle, color: AppTheme.primaryPurple.withValues(alpha: 0.1)),
              child: Icon(Icons.inventory_2_outlined, size: 48, color: isDark ? Colors.white24 : Colors.grey[600]),
            ).animate().fadeIn(duration: 500.ms),
            const SizedBox(height: 16),
            Text('No items yet', style: TextStyle(color: isDark ? Colors.white54 : Colors.grey[700], fontSize: 16))
              .animate().fadeIn(duration: 500.ms, delay: 100.ms),
            const SizedBox(height: 8),
            Text('Purchase items from the Shop tab', style: TextStyle(color: isDark ? Colors.white38 : Colors.grey[600]))
              .animate().fadeIn(duration: 500.ms, delay: 200.ms),
          ],
        ),
      );
    }

    return GridView.builder(
      padding: EdgeInsets.fromLTRB(16, MediaQuery.of(context).padding.top + kToolbarHeight + 60, 16, 32),
      gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
        crossAxisCount: 2,
        childAspectRatio: 0.78,
        crossAxisSpacing: 10,
        mainAxisSpacing: 10,
      ),
      itemCount: state.inventory.length,
      itemBuilder: (context, index) {
        final inv = state.inventory[index];
        return AnimatedListItem(
          index: index,
          child: GlassContainer(
            padding: const EdgeInsets.all(12),
            opacity: isDark ? 0.12 : 0.25,
            border: Border.all(
              color: inv.isEquipped ? AppTheme.success.withValues(alpha: 0.5) : inv.item.rarityColor.withValues(alpha: 0.3),
              width: inv.isEquipped ? 2 : 1,
            ),
            child: Stack(
              children: [
                Column(
                  children: [
                    Expanded(
                      child: Container(
                        decoration: BoxDecoration(
                          color: inv.item.rarityColor.withValues(alpha: 0.08),
                          borderRadius: BorderRadius.circular(12),
                        ),
                        child: Center(child: Icon(_getItemIcon(inv.item.itemType), size: 36, color: inv.item.rarityColor)),
                      ),
                    ),
                    const SizedBox(height: 6),
                    Text(
                      inv.item.name,
                      style: TextStyle(fontWeight: FontWeight.w600, fontSize: 13, color: isDark ? Colors.white : const Color(0xFF1E1B4B)),
                      textAlign: TextAlign.center,
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                    ),
                    const SizedBox(height: 4),
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 2),
                      decoration: BoxDecoration(color: inv.item.rarityColor.withValues(alpha: 0.12), borderRadius: BorderRadius.circular(6)),
                      child: Text(inv.item.rarity, style: TextStyle(fontSize: 9, color: inv.item.rarityColor, fontWeight: FontWeight.w600)),
                    ),
                    const SizedBox(height: 8),
                    SizedBox(
                      width: double.infinity,
                      child: GlassButton(
                        label: inv.isEquipped ? 'Unequip' : 'Equip',
                        style: inv.isEquipped ? GlassButtonStyle.secondary : GlassButtonStyle.primary,
                        onPressed: () async {
                          try {
                            await ref.read(storeProvider.notifier).equipItem(inv.id);
                          } catch (e) {
                            if (context.mounted) {
                              ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Error: $e')));
                            }
                          }
                        },
                      ),
                    ),
                  ],
                ),
                if (inv.isEquipped)
                  Positioned(
                    top: 4,
                    right: 4,
                    child: Container(
                      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                      decoration: BoxDecoration(
                        color: AppTheme.success,
                        borderRadius: BorderRadius.circular(8),
                        boxShadow: [BoxShadow(color: AppTheme.success.withValues(alpha: 0.3), blurRadius: 6)],
                      ),
                      child: const Text('Equipped', style: TextStyle(color: Colors.white, fontSize: 9, fontWeight: FontWeight.bold)),
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

void _showPurchaseSheet(BuildContext context, StoreItem item, WidgetRef ref, bool isDark) {
  showModalBottomSheet(
    context: context,
    backgroundColor: Colors.transparent,
    builder: (ctx) => Container(
      decoration: BoxDecoration(
        color: isDark ? const Color(0xFF1E1B4B).withValues(alpha: 0.95) : Colors.white.withValues(alpha: 0.95),
        borderRadius: const BorderRadius.vertical(top: Radius.circular(24)),
      ),
      padding: const EdgeInsets.all(24),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            margin: const EdgeInsets.only(bottom: 16),
            width: 40, height: 4,
            decoration: BoxDecoration(color: isDark ? Colors.white24 : Colors.grey[600], borderRadius: BorderRadius.circular(2)),
          ),
          Container(
            padding: const EdgeInsets.all(20),
            decoration: BoxDecoration(
              color: item.rarityColor.withValues(alpha: 0.1),
              shape: BoxShape.circle,
              boxShadow: [BoxShadow(color: item.rarityColor.withValues(alpha: 0.2), blurRadius: 20)],
            ),
            child: Icon(_getItemIcon(item.itemType), size: 48, color: item.rarityColor),
          ),
          const SizedBox(height: 16),
          Text(item.name, style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold, color: isDark ? Colors.white : const Color(0xFF1E1B4B))),
          const SizedBox(height: 8),
          Text(item.description, textAlign: TextAlign.center, style: TextStyle(color: isDark ? Colors.white54 : Colors.grey[600])),
          const SizedBox(height: 10),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
            decoration: BoxDecoration(color: item.rarityColor.withValues(alpha: 0.12), borderRadius: BorderRadius.circular(12)),
            child: Text(item.rarity.toUpperCase(), style: TextStyle(fontWeight: FontWeight.bold, color: item.rarityColor, fontSize: 12)),
          ),
          const SizedBox(height: 24),
          SizedBox(
            width: double.infinity,
            child: GlassButton(
              label: 'Buy for ${item.xpPrice ?? item.price} XP',
              icon: Icons.bolt,
              onPressed: () async {
                Navigator.pop(ctx);
                try {
                  await ref.read(storeProvider.notifier).purchaseWithXp(item.id);
                  if (context.mounted) {
                    ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Purchased!')));
                  }
                } catch (e) {
                  if (context.mounted) {
                    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Error: $e')));
                  }
                }
              },
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
