import React, { useState, useCallback } from 'react';
import {
  View,
  StyleSheet,
  FlatList,
  TouchableOpacity,
  ActivityIndicator,
  Alert,
  Image,
  RefreshControl,
  Dimensions,
} from 'react-native';
import {
  Text,
  Button,
  Surface,
  Chip,
  Portal,
  Dialog,
  Divider,
  IconButton,
  useTheme,
} from 'react-native-paper';
import { SafeAreaView } from 'react-native-safe-area-context';
import Icon from 'react-native-vector-icons/MaterialCommunityIcons';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../services/api';
import { AppTheme, spacing, borderRadius, colors, shadows, typography } from '../theme';
import { StoreCategory, StoreItem, UserInventoryItem } from '../types';

const { width: SCREEN_WIDTH } = Dimensions.get('window');
const ITEM_CARD_WIDTH = (SCREEN_WIDTH - spacing.md * 3) / 2;

type ViewMode = 'shop' | 'inventory';

const CATEGORY_ICONS: Record<string, string> = {
  skins: 'palette-swatch',
  badge_frames: 'card-account-details-star-outline',
  themes: 'theme-light-dark',
  avatars: 'account-circle',
  effects: 'auto-fix',
};

export const StoreScreen: React.FC = () => {
  const theme = useTheme() as AppTheme;
  const queryClient = useQueryClient();
  const [viewMode, setViewMode] = useState<ViewMode>('shop');
  const [selectedCategorySlug, setSelectedCategorySlug] = useState<string | null>(null);
  const [purchaseDialogItem, setPurchaseDialogItem] = useState<StoreItem | null>(null);

  const {
    data: categories,
    isLoading: categoriesLoading,
  } = useQuery<StoreCategory[]>({
    queryKey: ['store-categories'],
    queryFn: () => api.store.getCategories() as Promise<StoreCategory[]>,
  });

  const {
    data: items,
    isLoading: itemsLoading,
    refetch: refetchItems,
  } = useQuery<StoreItem[]>({
    queryKey: ['store-items', selectedCategorySlug],
    queryFn: () =>
      api.store.getItems(
        selectedCategorySlug ? { category: selectedCategorySlug } : undefined
      ) as Promise<StoreItem[]>,
  });

  const {
    data: inventory,
    isLoading: inventoryLoading,
    refetch: refetchInventory,
  } = useQuery<UserInventoryItem[]>({
    queryKey: ['store-inventory'],
    queryFn: () => api.store.getInventory() as Promise<UserInventoryItem[]>,
    enabled: viewMode === 'inventory',
  });

  const purchaseMutation = useMutation({
    mutationFn: (itemId: string) => api.store.purchase(itemId),
    onSuccess: () => {
      setPurchaseDialogItem(null);
      queryClient.invalidateQueries({ queryKey: ['store-inventory'] });
      queryClient.invalidateQueries({ queryKey: ['store-items'] });
      Alert.alert('Purchase Successful', 'The item has been added to your inventory.');
    },
    onError: (error: any) => {
      Alert.alert('Purchase Failed', error.message || 'Could not complete the purchase. Please try again.');
    },
  });

  const equipMutation = useMutation({
    mutationFn: (inventoryId: string) => api.store.equipItem(inventoryId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['store-inventory'] });
    },
    onError: (error: any) => {
      Alert.alert('Error', error.message || 'Could not equip item.');
    },
  });

  const unequipMutation = useMutation({
    mutationFn: (inventoryId: string) => api.store.unequipItem(inventoryId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['store-inventory'] });
    },
    onError: (error: any) => {
      Alert.alert('Error', error.message || 'Could not unequip item.');
    },
  });

  const handleRefresh = useCallback(() => {
    if (viewMode === 'shop') {
      refetchItems();
    } else {
      refetchInventory();
    }
  }, [viewMode, refetchItems, refetchInventory]);

  const handleToggleEquip = (invItem: UserInventoryItem) => {
    if (invItem.isEquipped) {
      unequipMutation.mutate(invItem.id);
    } else {
      equipMutation.mutate(invItem.id);
    }
  };

  const renderCategoryTab = (category: StoreCategory) => {
    const isSelected = selectedCategorySlug === category.slug;
    return (
      <Chip
        key={category.id}
        selected={isSelected}
        onPress={() => setSelectedCategorySlug(isSelected ? null : category.slug)}
        icon={() => (
          <Icon
            name={CATEGORY_ICONS[category.slug] || category.icon || 'tag'}
            size={16}
            color={isSelected ? colors.white : theme.custom.colors.textPrimary}
          />
        )}
        style={[
          styles.categoryChip,
          isSelected && { backgroundColor: theme.colors.primary },
        ]}
        textStyle={isSelected ? { color: colors.white } : undefined}
      >
        {category.name}
      </Chip>
    );
  };

  const renderStoreItem = ({ item }: { item: StoreItem }) => (
    <TouchableOpacity
      style={[styles.itemCard, { backgroundColor: theme.colors.surface }, shadows.sm]}
      onPress={() => setPurchaseDialogItem(item)}
      activeOpacity={0.7}
    >
      <View style={[styles.itemImageContainer, { backgroundColor: theme.colors.surfaceVariant }]}>
        {item.imageUrl ? (
          <Image source={{ uri: item.imageUrl }} style={styles.itemImage} resizeMode="cover" />
        ) : (
          <Icon
            name={CATEGORY_ICONS[item.itemType] || 'star'}
            size={48}
            color={theme.custom.colors.textMuted}
          />
        )}
      </View>
      <View style={styles.itemInfo}>
        <Text
          style={[styles.itemName, { color: theme.custom.colors.textPrimary }]}
          numberOfLines={1}
        >
          {item.name}
        </Text>
        <Text
          style={[styles.itemDescription, { color: theme.custom.colors.textSecondary }]}
          numberOfLines={1}
        >
          {item.description}
        </Text>
        <View style={styles.itemPriceRow}>
          <Icon name="diamond-stone" size={14} color={colors.primary[500]} />
          <Text style={[styles.itemPrice, { color: colors.primary[500] }]}>
            {item.price}
          </Text>
        </View>
      </View>
    </TouchableOpacity>
  );

  const renderInventoryItem = ({ item: invItem }: { item: UserInventoryItem }) => (
    <Surface style={[styles.inventoryCard, shadows.sm]} elevation={1}>
      <View style={[styles.inventoryImageContainer, { backgroundColor: theme.colors.surfaceVariant }]}>
        {invItem.item.imageUrl ? (
          <Image source={{ uri: invItem.item.imageUrl }} style={styles.inventoryImage} resizeMode="cover" />
        ) : (
          <Icon
            name={CATEGORY_ICONS[invItem.item.itemType] || 'star'}
            size={36}
            color={theme.custom.colors.textMuted}
          />
        )}
      </View>
      <View style={styles.inventoryInfo}>
        <Text
          style={[styles.inventoryName, { color: theme.custom.colors.textPrimary }]}
          numberOfLines={1}
        >
          {invItem.item.name}
        </Text>
        <Text style={[styles.inventoryType, { color: theme.custom.colors.textSecondary }]}>
          {invItem.item.itemType.replace('_', ' ').replace(/\b\w/g, (l) => l.toUpperCase())}
        </Text>
        {invItem.isEquipped && (
          <Chip
            compact
            style={[styles.equippedChip, { backgroundColor: colors.success + '20' }]}
            textStyle={{ color: colors.success, fontSize: 10 }}
          >
            Equipped
          </Chip>
        )}
      </View>
      <Button
        mode={invItem.isEquipped ? 'outlined' : 'contained'}
        compact
        onPress={() => handleToggleEquip(invItem)}
        loading={equipMutation.isPending || unequipMutation.isPending}
        style={styles.equipButton}
      >
        {invItem.isEquipped ? 'Unequip' : 'Equip'}
      </Button>
    </Surface>
  );

  const isContentLoading = viewMode === 'shop' ? itemsLoading : inventoryLoading;
  const currentData = viewMode === 'shop' ? items : inventory;

  return (
    <SafeAreaView style={[styles.container, { backgroundColor: theme.colors.background }]} edges={['top']}>
      {/* Header */}
      <View style={[styles.header, { backgroundColor: theme.colors.surface, borderBottomColor: theme.custom.colors.border }]}>
        <Text style={[typography.h2, { color: theme.custom.colors.textPrimary }]}>
          Store
        </Text>

        {/* View Mode Toggle */}
        <View style={styles.viewToggle}>
          <TouchableOpacity
            style={[
              styles.viewToggleOption,
              viewMode === 'shop' && { backgroundColor: theme.colors.primary },
            ]}
            onPress={() => setViewMode('shop')}
            activeOpacity={0.7}
          >
            <Icon
              name="store"
              size={18}
              color={viewMode === 'shop' ? colors.white : theme.custom.colors.textSecondary}
            />
            <Text
              style={[
                styles.viewToggleText,
                { color: viewMode === 'shop' ? colors.white : theme.custom.colors.textSecondary },
              ]}
            >
              Shop
            </Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={[
              styles.viewToggleOption,
              viewMode === 'inventory' && { backgroundColor: theme.colors.primary },
            ]}
            onPress={() => setViewMode('inventory')}
            activeOpacity={0.7}
          >
            <Icon
              name="treasure-chest"
              size={18}
              color={viewMode === 'inventory' ? colors.white : theme.custom.colors.textSecondary}
            />
            <Text
              style={[
                styles.viewToggleText,
                { color: viewMode === 'inventory' ? colors.white : theme.custom.colors.textSecondary },
              ]}
            >
              My Items
            </Text>
          </TouchableOpacity>
        </View>
      </View>

      {/* Category Tabs (shop mode only) */}
      {viewMode === 'shop' && categories && categories.length > 0 && (
        <View style={[styles.categoryContainer, { backgroundColor: theme.colors.surface, borderBottomColor: theme.custom.colors.border }]}>
          <FlatList
            data={categories}
            renderItem={({ item }) => renderCategoryTab(item)}
            keyExtractor={(item) => item.id}
            horizontal
            showsHorizontalScrollIndicator={false}
            contentContainerStyle={styles.categoryList}
          />
        </View>
      )}

      {/* Loading State */}
      {(categoriesLoading || isContentLoading) && (
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color={theme.colors.primary} />
          <Text style={[styles.loadingText, { color: theme.custom.colors.textSecondary }]}>
            {viewMode === 'shop' ? 'Loading store items...' : 'Loading your inventory...'}
          </Text>
        </View>
      )}

      {/* Shop Grid */}
      {viewMode === 'shop' && !itemsLoading && (
        <FlatList
          data={items || []}
          renderItem={renderStoreItem}
          keyExtractor={(item) => item.id}
          numColumns={2}
          columnWrapperStyle={styles.gridRow}
          contentContainerStyle={styles.gridContent}
          showsVerticalScrollIndicator={false}
          refreshControl={
            <RefreshControl refreshing={itemsLoading} onRefresh={handleRefresh} />
          }
          ListEmptyComponent={
            <View style={styles.emptyState}>
              <Icon name="store-off-outline" size={64} color={theme.custom.colors.textMuted} />
              <Text style={[styles.emptyTitle, { color: theme.custom.colors.textPrimary }]}>
                No Items Found
              </Text>
              <Text style={[styles.emptyText, { color: theme.custom.colors.textSecondary }]}>
                {selectedCategorySlug
                  ? 'No items in this category yet. Check back soon!'
                  : 'The store is currently empty. Check back later for new items.'}
              </Text>
            </View>
          }
        />
      )}

      {/* Inventory List */}
      {viewMode === 'inventory' && !inventoryLoading && (
        <FlatList
          data={inventory || []}
          renderItem={renderInventoryItem}
          keyExtractor={(item) => item.id}
          contentContainerStyle={styles.inventoryContent}
          showsVerticalScrollIndicator={false}
          refreshControl={
            <RefreshControl refreshing={inventoryLoading} onRefresh={handleRefresh} />
          }
          ListEmptyComponent={
            <View style={styles.emptyState}>
              <Icon name="treasure-chest-outline" size={64} color={theme.custom.colors.textMuted} />
              <Text style={[styles.emptyTitle, { color: theme.custom.colors.textPrimary }]}>
                No Items Yet
              </Text>
              <Text style={[styles.emptyText, { color: theme.custom.colors.textSecondary }]}>
                You have not purchased any items yet. Visit the shop to browse available items!
              </Text>
              <Button
                mode="contained"
                onPress={() => setViewMode('shop')}
                style={styles.browseButton}
                icon="store"
              >
                Browse Shop
              </Button>
            </View>
          }
        />
      )}

      {/* Purchase Dialog */}
      <Portal>
        <Dialog
          visible={purchaseDialogItem !== null}
          onDismiss={() => setPurchaseDialogItem(null)}
        >
          {purchaseDialogItem && (
            <>
              <Dialog.Title>Confirm Purchase</Dialog.Title>
              <Dialog.Content>
                <View style={styles.purchaseDialogContent}>
                  <View style={[styles.purchaseImageContainer, { backgroundColor: theme.colors.surfaceVariant }]}>
                    {purchaseDialogItem.imageUrl ? (
                      <Image
                        source={{ uri: purchaseDialogItem.imageUrl }}
                        style={styles.purchaseImage}
                        resizeMode="cover"
                      />
                    ) : (
                      <Icon
                        name={CATEGORY_ICONS[purchaseDialogItem.itemType] || 'star'}
                        size={48}
                        color={theme.custom.colors.textMuted}
                      />
                    )}
                  </View>
                  <Text
                    style={[typography.h4, { color: theme.custom.colors.textPrimary, textAlign: 'center', marginTop: spacing.sm }]}
                  >
                    {purchaseDialogItem.name}
                  </Text>
                  <Text
                    style={[typography.bodySmall, { color: theme.custom.colors.textSecondary, textAlign: 'center', marginTop: spacing.xs }]}
                  >
                    {purchaseDialogItem.description}
                  </Text>

                  <Divider style={{ marginVertical: spacing.md }} />

                  <View style={styles.purchasePriceRow}>
                    <Text style={[typography.body, { color: theme.custom.colors.textSecondary }]}>
                      Price
                    </Text>
                    <View style={styles.purchasePriceValue}>
                      <Icon name="diamond-stone" size={18} color={colors.primary[500]} />
                      <Text style={[styles.purchasePriceAmount, { color: colors.primary[500] }]}>
                        {purchaseDialogItem.price}
                      </Text>
                    </View>
                  </View>
                </View>
              </Dialog.Content>
              <Dialog.Actions>
                <Button onPress={() => setPurchaseDialogItem(null)}>Cancel</Button>
                <Button
                  mode="contained"
                  onPress={() => purchaseMutation.mutate(purchaseDialogItem.id)}
                  loading={purchaseMutation.isPending}
                >
                  Buy Now
                </Button>
              </Dialog.Actions>
            </>
          )}
        </Dialog>
      </Portal>
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  header: {
    paddingHorizontal: spacing.md,
    paddingTop: spacing.md,
    paddingBottom: spacing.sm,
    borderBottomWidth: 1,
  },
  viewToggle: {
    flexDirection: 'row',
    backgroundColor: colors.gray[200],
    borderRadius: borderRadius.xl,
    padding: 3,
    marginTop: spacing.sm,
  },
  viewToggleOption: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: spacing.sm,
    borderRadius: borderRadius.xl,
    gap: 6,
  },
  viewToggleText: {
    fontSize: 13,
    fontWeight: '600',
  },
  categoryContainer: {
    borderBottomWidth: 1,
    paddingVertical: spacing.sm,
  },
  categoryList: {
    paddingHorizontal: spacing.md,
    gap: spacing.sm,
  },
  categoryChip: {
    marginRight: 0,
  },
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  loadingText: {
    ...typography.body,
    marginTop: spacing.md,
  },
  gridContent: {
    padding: spacing.md,
    paddingBottom: 100,
  },
  gridRow: {
    justifyContent: 'space-between',
  },
  itemCard: {
    width: ITEM_CARD_WIDTH,
    borderRadius: borderRadius.lg,
    marginBottom: spacing.md,
    overflow: 'hidden',
  },
  itemImageContainer: {
    width: '100%',
    height: ITEM_CARD_WIDTH * 0.85,
    justifyContent: 'center',
    alignItems: 'center',
  },
  itemImage: {
    width: '100%',
    height: '100%',
  },
  itemInfo: {
    padding: spacing.sm,
  },
  itemName: {
    fontSize: 14,
    fontWeight: '600',
  },
  itemDescription: {
    fontSize: 11,
    marginTop: 2,
  },
  itemPriceRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: spacing.xs,
    gap: 4,
  },
  itemPrice: {
    fontSize: 14,
    fontWeight: '700',
  },
  inventoryContent: {
    padding: spacing.md,
    paddingBottom: 100,
  },
  inventoryCard: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: spacing.sm,
    borderRadius: borderRadius.lg,
    marginBottom: spacing.sm,
  },
  inventoryImageContainer: {
    width: 60,
    height: 60,
    borderRadius: borderRadius.md,
    justifyContent: 'center',
    alignItems: 'center',
    overflow: 'hidden',
  },
  inventoryImage: {
    width: '100%',
    height: '100%',
  },
  inventoryInfo: {
    flex: 1,
    marginLeft: spacing.sm,
  },
  inventoryName: {
    fontSize: 15,
    fontWeight: '600',
  },
  inventoryType: {
    fontSize: 12,
    marginTop: 2,
  },
  equippedChip: {
    alignSelf: 'flex-start',
    marginTop: 4,
    height: 22,
  },
  equipButton: {
    marginLeft: spacing.sm,
  },
  emptyState: {
    alignItems: 'center',
    padding: spacing.xxl,
    paddingTop: 80,
  },
  emptyTitle: {
    ...typography.h3,
    marginTop: spacing.md,
    textAlign: 'center',
  },
  emptyText: {
    ...typography.body,
    marginTop: spacing.sm,
    textAlign: 'center',
  },
  browseButton: {
    marginTop: spacing.lg,
  },
  purchaseDialogContent: {
    alignItems: 'center',
  },
  purchaseImageContainer: {
    width: 120,
    height: 120,
    borderRadius: borderRadius.lg,
    justifyContent: 'center',
    alignItems: 'center',
    overflow: 'hidden',
  },
  purchaseImage: {
    width: '100%',
    height: '100%',
  },
  purchasePriceRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    width: '100%',
  },
  purchasePriceValue: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
  },
  purchasePriceAmount: {
    fontSize: 20,
    fontWeight: '700',
  },
});
