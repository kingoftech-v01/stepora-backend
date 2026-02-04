import React, { useCallback } from 'react';
import {
  View,
  StyleSheet,
  FlatList,
  TouchableOpacity,
  RefreshControl,
  ActivityIndicator,
} from 'react-native';
import { Text, Surface, Divider, IconButton, useTheme } from 'react-native-paper';
import { SafeAreaView } from 'react-native-safe-area-context';
import Icon from 'react-native-vector-icons/MaterialCommunityIcons';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useNavigation } from '@react-navigation/native';
import { api } from '../services/api';
import { spacing, borderRadius, colors, shadows, typography } from '../theme';

interface Notification {
  id: string;
  notification_type: string;
  title: string;
  body: string;
  data: Record<string, string | null>;
  status: string;
  read_at: string | null;
  created_at: string;
}

const TYPE_ICONS: Record<string, { icon: string; color: string }> = {
  reminder: { icon: 'clock-outline', color: colors.info },
  motivation: { icon: 'arm-flex', color: colors.primary[500] },
  progress: { icon: 'chart-line', color: colors.secondary[500] },
  achievement: { icon: 'trophy', color: colors.warning },
  check_in: { icon: 'hand-wave', color: colors.secondary[400] },
  rescue: { icon: 'heart', color: colors.error },
  buddy: { icon: 'account-heart', color: colors.primary[400] },
  system: { icon: 'information', color: colors.gray[500] },
  dream_completed: { icon: 'party-popper', color: colors.success },
  weekly_report: { icon: 'chart-bar', color: colors.info },
};

function getRelativeTime(dateString: string): string {
  const now = new Date();
  const date = new Date(dateString);
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);

  if (diffMins < 1) return 'Just now';
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays < 7) return `${diffDays}d ago`;
  return date.toLocaleDateString();
}

function NotificationItem({
  item,
  onPress,
}: {
  item: Notification;
  onPress: (item: Notification) => void;
}) {
  const isUnread = !item.read_at;
  const typeConfig = TYPE_ICONS[item.notification_type] || TYPE_ICONS.system;

  return (
    <TouchableOpacity
      onPress={() => onPress(item)}
      activeOpacity={0.7}
    >
      <Surface
        style={[
          styles.notificationCard,
          isUnread && styles.unreadCard,
        ]}
        elevation={isUnread ? 2 : 0}
      >
        <View style={[styles.iconContainer, { backgroundColor: typeConfig.color + '18' }]}>
          <Icon name={typeConfig.icon} size={22} color={typeConfig.color} />
        </View>
        <View style={styles.contentContainer}>
          <View style={styles.headerRow}>
            <Text
              style={[styles.title, isUnread && styles.unreadTitle]}
              numberOfLines={1}
            >
              {item.title}
            </Text>
            <Text style={styles.time}>{getRelativeTime(item.created_at)}</Text>
          </View>
          <Text style={styles.body} numberOfLines={2}>
            {item.body}
          </Text>
        </View>
        {isUnread && <View style={styles.unreadDot} />}
      </Surface>
    </TouchableOpacity>
  );
}

export function NotificationsScreen() {
  const navigation = useNavigation();
  const queryClient = useQueryClient();

  const {
    data: notifications,
    isLoading,
    refetch,
    isRefetching,
  } = useQuery<Notification[]>({
    queryKey: ['notifications'],
    queryFn: async () => {
      const res = await api.notifications.list();
      return res.data?.results ?? res.data ?? [];
    },
  });

  const markReadMutation = useMutation({
    mutationFn: (id: string) => api.notifications.markRead(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['notifications'] }),
  });

  const markAllReadMutation = useMutation({
    mutationFn: () => api.notifications.markAllRead(),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['notifications'] }),
  });

  const unreadCount = notifications?.filter((n) => !n.read_at).length ?? 0;

  const handleNotificationPress = useCallback(
    (item: Notification) => {
      // Mark as read
      if (!item.read_at) {
        markReadMutation.mutate(item.id);
      }

      // Deep-link based on notification data
      const { action, screen, dream_id } = item.data ?? {};
      if (screen === 'DreamDetail' && dream_id) {
        (navigation as any).navigate('HomeTab', {
          screen: 'DreamDetail',
          params: { dreamId: dream_id },
        });
      } else if (screen === 'Profile') {
        (navigation as any).navigate('ProfileTab', { screen: 'ProfileScreen' });
      } else if (screen === 'DreamsDashboard') {
        (navigation as any).navigate('HomeTab', { screen: 'HomeScreen' });
      }
    },
    [navigation, markReadMutation],
  );

  const renderEmpty = () => (
    <View style={styles.emptyContainer}>
      <Icon name="bell-off-outline" size={64} color={colors.gray[300]} />
      <Text style={styles.emptyTitle}>No notifications</Text>
      <Text style={styles.emptySubtitle}>
        You're all caught up! We'll notify you when something happens.
      </Text>
    </View>
  );

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity onPress={() => navigation.goBack()} style={styles.backButton}>
          <Icon name="arrow-left" size={24} color={colors.gray[800]} />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Notifications</Text>
        {unreadCount > 0 && (
          <TouchableOpacity
            onPress={() => markAllReadMutation.mutate()}
            disabled={markAllReadMutation.isPending}
            style={styles.markAllButton}
          >
            <Text style={styles.markAllText}>
              {markAllReadMutation.isPending ? 'Marking...' : 'Mark all read'}
            </Text>
          </TouchableOpacity>
        )}
        {unreadCount === 0 && <View style={styles.headerSpacer} />}
      </View>

      {/* Unread count badge */}
      {unreadCount > 0 && (
        <View style={styles.unreadBanner}>
          <Icon name="bell-ring-outline" size={16} color={colors.primary[600]} />
          <Text style={styles.unreadBannerText}>
            {unreadCount} unread notification{unreadCount !== 1 ? 's' : ''}
          </Text>
        </View>
      )}

      {/* Notification list */}
      {isLoading ? (
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color={colors.primary[500]} />
        </View>
      ) : (
        <FlatList
          data={notifications}
          keyExtractor={(item) => item.id}
          renderItem={({ item }) => (
            <NotificationItem item={item} onPress={handleNotificationPress} />
          )}
          ListEmptyComponent={renderEmpty}
          contentContainerStyle={
            notifications?.length === 0 ? styles.emptyListContent : styles.listContent
          }
          ItemSeparatorComponent={() => <View style={styles.separator} />}
          refreshControl={
            <RefreshControl
              refreshing={isRefetching}
              onRefresh={refetch}
              colors={[colors.primary[500]]}
              tintColor={colors.primary[500]}
            />
          }
          showsVerticalScrollIndicator={false}
        />
      )}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.gray[50],
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    backgroundColor: colors.white,
    borderBottomWidth: 1,
    borderBottomColor: colors.gray[200],
  },
  backButton: {
    padding: spacing.xs,
    marginRight: spacing.sm,
  },
  headerTitle: {
    ...typography.h3,
    flex: 1,
    color: colors.gray[800],
  },
  headerSpacer: {
    width: 80,
  },
  markAllButton: {
    paddingVertical: spacing.xs,
    paddingHorizontal: spacing.sm,
  },
  markAllText: {
    ...typography.bodySmall,
    color: colors.primary[500],
    fontWeight: '600',
  },
  unreadBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    backgroundColor: colors.primary[50],
    gap: spacing.xs,
  },
  unreadBannerText: {
    ...typography.bodySmall,
    color: colors.primary[600],
    fontWeight: '500',
  },
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  listContent: {
    paddingVertical: spacing.sm,
  },
  emptyListContent: {
    flex: 1,
    justifyContent: 'center',
  },
  notificationCard: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.md,
    backgroundColor: colors.white,
  },
  unreadCard: {
    backgroundColor: colors.primary[50] + '40',
  },
  iconContainer: {
    width: 40,
    height: 40,
    borderRadius: borderRadius.md,
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: spacing.sm,
  },
  contentContainer: {
    flex: 1,
  },
  headerRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 2,
  },
  title: {
    ...typography.bodySmall,
    fontWeight: '500',
    color: colors.gray[700],
    flex: 1,
    marginRight: spacing.sm,
  },
  unreadTitle: {
    fontWeight: '700',
    color: colors.gray[900],
  },
  time: {
    ...typography.caption,
    color: colors.gray[400],
  },
  body: {
    ...typography.caption,
    color: colors.gray[500],
    lineHeight: 18,
  },
  unreadDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: colors.primary[500],
    marginTop: 6,
    marginLeft: spacing.xs,
  },
  separator: {
    height: 1,
    backgroundColor: colors.gray[100],
    marginLeft: 56 + spacing.md,
  },
  emptyContainer: {
    alignItems: 'center',
    paddingHorizontal: spacing.xl,
  },
  emptyTitle: {
    ...typography.h3,
    color: colors.gray[600],
    marginTop: spacing.md,
  },
  emptySubtitle: {
    ...typography.bodySmall,
    color: colors.gray[400],
    textAlign: 'center',
    marginTop: spacing.xs,
  },
});
