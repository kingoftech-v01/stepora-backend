import React, { useState } from 'react';
import {
  View,
  StyleSheet,
  FlatList,
  TouchableOpacity,
  ActivityIndicator,
  Alert,
  Image,
  Dimensions,
  Modal,
  RefreshControl,
} from 'react-native';
import {
  Text,
  Button,
  Surface,
  FAB,
  Portal,
  Dialog,
  IconButton,
  useTheme,
} from 'react-native-paper';
import { SafeAreaView } from 'react-native-safe-area-context';
import Icon from 'react-native-vector-icons/MaterialCommunityIcons';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useRoute, RouteProp } from '@react-navigation/native';
import { api } from '../services/api';
import { AppTheme, spacing, borderRadius, colors, shadows, typography } from '../theme';
import { VisionBoard, HomeStackParamList } from '../types';
import { useAuthStore } from '../stores/authStore';

const { width: SCREEN_WIDTH, height: SCREEN_HEIGHT } = Dimensions.get('window');
const IMAGE_SIZE = (SCREEN_WIDTH - spacing.md * 3) / 2;

type VisionBoardRouteProp = RouteProp<HomeStackParamList, 'VisionBoard'>;

export const VisionBoardScreen: React.FC = () => {
  const theme = useTheme() as AppTheme;
  const route = useRoute<VisionBoardRouteProp>();
  const { dreamId } = route.params;
  const queryClient = useQueryClient();
  const user = useAuthStore((state) => state.user);

  const [previewImage, setPreviewImage] = useState<VisionBoard | null>(null);
  const [deleteDialogBoard, setDeleteDialogBoard] = useState<VisionBoard | null>(null);

  const isPro = user?.subscription === 'pro';

  const {
    data: boards,
    isLoading,
    isError,
    refetch,
  } = useQuery<VisionBoard[]>({
    queryKey: ['vision-boards', dreamId],
    queryFn: () => api.visionBoards.list(dreamId) as Promise<VisionBoard[]>,
  });

  const generateMutation = useMutation({
    mutationFn: () => api.visionBoards.generate(dreamId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['vision-boards', dreamId] });
      Alert.alert('Board Generated', 'Your new vision board image has been created!');
    },
    onError: (error: any) => {
      Alert.alert(
        'Generation Failed',
        error.message || 'Could not generate vision board. Please try again later.'
      );
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (boardId: string) => api.visionBoards.delete(dreamId, boardId),
    onSuccess: () => {
      setDeleteDialogBoard(null);
      queryClient.invalidateQueries({ queryKey: ['vision-boards', dreamId] });
    },
    onError: (error: any) => {
      Alert.alert('Error', error.message || 'Could not delete vision board.');
    },
  });

  const handleGenerate = () => {
    if (!isPro) {
      Alert.alert(
        'Pro Feature',
        'Vision board generation is available for Pro subscribers. Upgrade your plan to unlock this feature.',
        [{ text: 'OK' }]
      );
      return;
    }
    generateMutation.mutate();
  };

  const handleDelete = (board: VisionBoard) => {
    setDeleteDialogBoard(board);
  };

  const confirmDelete = () => {
    if (deleteDialogBoard) {
      deleteMutation.mutate(deleteDialogBoard.id);
    }
  };

  const formatDate = (dateStr: string): string => {
    return new Date(dateStr).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    });
  };

  const renderBoardItem = ({ item }: { item: VisionBoard }) => (
    <TouchableOpacity
      style={[styles.boardCard, shadows.sm]}
      onPress={() => setPreviewImage(item)}
      activeOpacity={0.8}
    >
      <Image
        source={{ uri: item.imageUrl }}
        style={[styles.boardImage, { backgroundColor: theme.colors.surfaceVariant }]}
        resizeMode="cover"
      />
      <View style={[styles.boardOverlay]}>
        <View style={styles.boardOverlayContent}>
          <Text style={styles.boardTitle} numberOfLines={1}>
            {item.title}
          </Text>
          <Text style={styles.boardDate}>
            {formatDate(item.createdAt)}
          </Text>
        </View>
        <IconButton
          icon="delete-outline"
          iconColor={colors.white}
          size={18}
          style={styles.deleteIconButton}
          onPress={(e) => {
            e.stopPropagation?.();
            handleDelete(item);
          }}
        />
      </View>
    </TouchableOpacity>
  );

  if (isLoading) {
    return (
      <SafeAreaView style={[styles.container, { backgroundColor: theme.colors.background }]} edges={['top']}>
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color={theme.colors.primary} />
          <Text style={[styles.loadingText, { color: theme.custom.colors.textSecondary }]}>
            Loading vision boards...
          </Text>
        </View>
      </SafeAreaView>
    );
  }

  if (isError) {
    return (
      <SafeAreaView style={[styles.container, { backgroundColor: theme.colors.background }]} edges={['top']}>
        <View style={styles.errorContainer}>
          <Icon name="image-broken-variant" size={64} color={colors.error} />
          <Text style={[styles.errorTitle, { color: theme.custom.colors.textPrimary }]}>
            Failed to Load
          </Text>
          <Text style={[styles.errorText, { color: theme.custom.colors.textSecondary }]}>
            Could not load vision boards. Please check your connection and try again.
          </Text>
          <Button mode="contained" onPress={() => refetch()} style={styles.retryButton}>
            Retry
          </Button>
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={[styles.container, { backgroundColor: theme.colors.background }]} edges={['top']}>
      {/* Header */}
      <View style={[styles.header, { backgroundColor: theme.colors.surface, borderBottomColor: theme.custom.colors.border }]}>
        <View>
          <Text style={[typography.h2, { color: theme.custom.colors.textPrimary }]}>
            Vision Board
          </Text>
          <Text style={[typography.bodySmall, { color: theme.custom.colors.textSecondary, marginTop: 2 }]}>
            Visualize your dream with AI-generated imagery
          </Text>
        </View>
        {!isPro && (
          <View style={styles.proBadge}>
            <Icon name="lock" size={12} color={colors.white} />
            <Text style={styles.proBadgeText}>PRO</Text>
          </View>
        )}
      </View>

      {/* Upgrade Prompt for non-Pro users */}
      {!isPro && (
        <Surface style={[styles.upgradeCard, shadows.md]} elevation={2}>
          <View style={styles.upgradeContent}>
            <View style={[styles.upgradeIconContainer, { backgroundColor: colors.warning + '20' }]}>
              <Icon name="star-shooting" size={28} color={colors.warning} />
            </View>
            <View style={styles.upgradeTextContainer}>
              <Text style={[typography.h4, { color: theme.custom.colors.textPrimary }]}>
                Unlock Vision Boards
              </Text>
              <Text style={[typography.bodySmall, { color: theme.custom.colors.textSecondary, marginTop: 4 }]}>
                Generate AI-powered vision boards to visualize your goals. Available exclusively with the Pro plan.
              </Text>
            </View>
          </View>
          <Button
            mode="contained"
            icon="arrow-up-bold"
            onPress={() => {
              Alert.alert('Upgrade', 'Navigate to the Subscription screen to upgrade your plan.');
            }}
            style={[styles.upgradeButton, { backgroundColor: colors.warning }]}
            textColor={colors.white}
          >
            Upgrade to Pro
          </Button>
        </Surface>
      )}

      {/* Generating Indicator */}
      {generateMutation.isPending && (
        <Surface style={[styles.generatingCard, shadows.sm]} elevation={1}>
          <ActivityIndicator size="small" color={colors.primary[500]} />
          <Text style={[styles.generatingText, { color: theme.custom.colors.textPrimary }]}>
            Generating your vision board... This may take a moment.
          </Text>
        </Surface>
      )}

      {/* Grid of Vision Boards */}
      <FlatList
        data={boards || []}
        renderItem={renderBoardItem}
        keyExtractor={(item) => item.id}
        numColumns={2}
        columnWrapperStyle={styles.gridRow}
        contentContainerStyle={styles.gridContent}
        showsVerticalScrollIndicator={false}
        refreshControl={
          <RefreshControl refreshing={isLoading} onRefresh={() => refetch()} />
        }
        ListEmptyComponent={
          <View style={styles.emptyState}>
            <Icon name="image-filter-hdr" size={80} color={theme.custom.colors.textMuted} />
            <Text style={[styles.emptyTitle, { color: theme.custom.colors.textPrimary }]}>
              No Vision Boards Yet
            </Text>
            <Text style={[styles.emptyText, { color: theme.custom.colors.textSecondary }]}>
              {isPro
                ? 'Tap the button below to generate your first AI vision board for this dream.'
                : 'Upgrade to Pro to create AI-generated vision boards that bring your dreams to life.'}
            </Text>
            {isPro && (
              <Button
                mode="contained"
                icon="auto-fix"
                onPress={handleGenerate}
                style={styles.generateButton}
                loading={generateMutation.isPending}
              >
                Generate Vision Board
              </Button>
            )}
          </View>
        }
      />

      {/* Generate FAB (Pro only) */}
      <FAB
        icon="auto-fix"
        label={isPro ? 'Generate' : 'PRO'}
        style={[
          styles.fab,
          { backgroundColor: isPro ? theme.colors.primary : colors.gray[400] },
        ]}
        color={colors.white}
        onPress={handleGenerate}
        loading={generateMutation.isPending}
        disabled={generateMutation.isPending}
      />

      {/* Image Preview Modal */}
      <Modal
        visible={previewImage !== null}
        transparent
        animationType="fade"
        onRequestClose={() => setPreviewImage(null)}
      >
        <View style={styles.previewOverlay}>
          <TouchableOpacity
            style={styles.previewCloseArea}
            onPress={() => setPreviewImage(null)}
            activeOpacity={1}
          >
            <View style={styles.previewHeader}>
              <IconButton
                icon="close"
                iconColor={colors.white}
                size={28}
                onPress={() => setPreviewImage(null)}
              />
            </View>
          </TouchableOpacity>

          {previewImage && (
            <View style={styles.previewContent}>
              <Image
                source={{ uri: previewImage.imageUrl }}
                style={styles.previewImage}
                resizeMode="contain"
              />
              <View style={styles.previewInfo}>
                <Text style={styles.previewTitle}>{previewImage.title}</Text>
                <Text style={styles.previewPrompt} numberOfLines={3}>
                  {previewImage.generatedPrompt}
                </Text>
                <Text style={styles.previewDate}>
                  Created {formatDate(previewImage.createdAt)}
                </Text>
              </View>
            </View>
          )}

          {previewImage && (
            <View style={styles.previewActions}>
              <Button
                mode="outlined"
                textColor={colors.white}
                icon="delete-outline"
                onPress={() => {
                  setPreviewImage(null);
                  handleDelete(previewImage);
                }}
                style={styles.previewDeleteButton}
              >
                Delete
              </Button>
            </View>
          )}
        </View>
      </Modal>

      {/* Delete Confirmation Dialog */}
      <Portal>
        <Dialog
          visible={deleteDialogBoard !== null}
          onDismiss={() => setDeleteDialogBoard(null)}
        >
          <Dialog.Icon icon="delete-alert" />
          <Dialog.Title style={styles.dialogTitle}>Delete Vision Board?</Dialog.Title>
          <Dialog.Content>
            <Text style={[typography.body, { color: theme.custom.colors.textSecondary }]}>
              Are you sure you want to delete "{deleteDialogBoard?.title}"? This action cannot be undone.
            </Text>
          </Dialog.Content>
          <Dialog.Actions>
            <Button onPress={() => setDeleteDialogBoard(null)}>Cancel</Button>
            <Button
              textColor={colors.error}
              onPress={confirmDelete}
              loading={deleteMutation.isPending}
            >
              Delete
            </Button>
          </Dialog.Actions>
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
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.md,
    borderBottomWidth: 1,
  },
  proBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.warning,
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: borderRadius.full,
    gap: 4,
  },
  proBadgeText: {
    color: colors.white,
    fontSize: 11,
    fontWeight: '700',
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
  errorContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: spacing.xl,
  },
  errorTitle: {
    ...typography.h3,
    marginTop: spacing.md,
    textAlign: 'center',
  },
  errorText: {
    ...typography.body,
    marginTop: spacing.sm,
    textAlign: 'center',
  },
  retryButton: {
    marginTop: spacing.lg,
  },
  upgradeCard: {
    margin: spacing.md,
    borderRadius: borderRadius.lg,
    padding: spacing.md,
    borderLeftWidth: 4,
    borderLeftColor: colors.warning,
  },
  upgradeContent: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: spacing.sm,
  },
  upgradeIconContainer: {
    width: 48,
    height: 48,
    borderRadius: 24,
    justifyContent: 'center',
    alignItems: 'center',
  },
  upgradeTextContainer: {
    flex: 1,
  },
  upgradeButton: {
    marginTop: spacing.md,
    borderRadius: borderRadius.sm,
  },
  generatingCard: {
    flexDirection: 'row',
    alignItems: 'center',
    margin: spacing.md,
    marginBottom: 0,
    padding: spacing.md,
    borderRadius: borderRadius.md,
    gap: spacing.sm,
  },
  generatingText: {
    ...typography.bodySmall,
    flex: 1,
  },
  gridContent: {
    padding: spacing.md,
    paddingBottom: 100,
  },
  gridRow: {
    justifyContent: 'space-between',
  },
  boardCard: {
    width: IMAGE_SIZE,
    height: IMAGE_SIZE * 1.2,
    borderRadius: borderRadius.lg,
    overflow: 'hidden',
    marginBottom: spacing.md,
  },
  boardImage: {
    width: '100%',
    height: '100%',
  },
  boardOverlay: {
    position: 'absolute',
    bottom: 0,
    left: 0,
    right: 0,
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: 'rgba(0,0,0,0.55)',
    paddingLeft: spacing.sm,
    paddingVertical: 4,
  },
  boardOverlayContent: {
    flex: 1,
  },
  boardTitle: {
    color: colors.white,
    fontSize: 13,
    fontWeight: '600',
  },
  boardDate: {
    color: 'rgba(255,255,255,0.7)',
    fontSize: 10,
    marginTop: 1,
  },
  deleteIconButton: {
    margin: 0,
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
    paddingHorizontal: spacing.md,
  },
  generateButton: {
    marginTop: spacing.lg,
  },
  fab: {
    position: 'absolute',
    right: spacing.md,
    bottom: spacing.md,
  },
  previewOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.92)',
    justifyContent: 'center',
  },
  previewCloseArea: {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
  },
  previewHeader: {
    flexDirection: 'row',
    justifyContent: 'flex-end',
    paddingTop: 48,
    paddingRight: spacing.sm,
  },
  previewContent: {
    alignItems: 'center',
    paddingHorizontal: spacing.md,
  },
  previewImage: {
    width: SCREEN_WIDTH - spacing.lg * 2,
    height: SCREEN_HEIGHT * 0.5,
    borderRadius: borderRadius.lg,
  },
  previewInfo: {
    marginTop: spacing.md,
    alignItems: 'center',
    paddingHorizontal: spacing.md,
  },
  previewTitle: {
    color: colors.white,
    ...typography.h3,
    textAlign: 'center',
  },
  previewPrompt: {
    color: 'rgba(255,255,255,0.7)',
    ...typography.bodySmall,
    textAlign: 'center',
    marginTop: spacing.xs,
  },
  previewDate: {
    color: 'rgba(255,255,255,0.5)',
    ...typography.caption,
    marginTop: spacing.sm,
  },
  previewActions: {
    flexDirection: 'row',
    justifyContent: 'center',
    marginTop: spacing.lg,
    paddingHorizontal: spacing.xl,
  },
  previewDeleteButton: {
    borderColor: 'rgba(255,255,255,0.3)',
  },
  dialogTitle: {
    textAlign: 'center',
  },
});
