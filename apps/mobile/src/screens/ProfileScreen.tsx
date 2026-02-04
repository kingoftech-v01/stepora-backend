import React from 'react';
import { View, StyleSheet, ScrollView, TouchableOpacity } from 'react-native';
import { Text, useTheme, ProgressBar } from 'react-native-paper';
import { SafeAreaView } from 'react-native-safe-area-context';
import Icon from 'react-native-vector-icons/MaterialCommunityIcons';
import LinearGradient from 'react-native-linear-gradient';

import { useAuthStore } from '../stores/authStore';
import { useDreamsStore } from '../stores/dreamsStore';
import { AppTheme, spacing, borderRadius, colors, shadows, typography } from '../theme';

const BADGES = [
  { id: '1', emoji: '🌅', name: 'Lève-tôt', color: colors.warning },
  { id: '2', emoji: '🔥', name: '7 jours', color: colors.error },
  { id: '3', emoji: '🎯', name: 'Focus', color: colors.success },
  { id: '4', emoji: '📚', name: '10 tâches', color: colors.info },
  { id: '5', emoji: '🔒', name: '???', color: colors.gray[400], locked: true },
];

const SETTINGS_ITEMS = [
  { icon: 'calendar-clock', label: 'Horaires de travail', screen: 'WorkSchedule' },
  { icon: 'bell-outline', label: 'Notifications', screen: 'Notifications' },
  { icon: 'theme-light-dark', label: 'Apparence', value: 'Clair', screen: 'Appearance' },
  { icon: 'star', label: 'Passer Premium', isPremium: true, screen: 'Premium' },
];

interface SettingItemProps {
  icon: string;
  label: string;
  value?: string;
  isPremium?: boolean;
  onPress: () => void;
}

const SettingItem: React.FC<SettingItemProps> = ({ icon, label, value, isPremium, onPress }) => {
  const theme = useTheme() as AppTheme;

  return (
    <TouchableOpacity
      style={styles.settingItem}
      onPress={onPress}
      activeOpacity={0.7}
    >
      <View style={styles.settingLeft}>
        <Icon
          name={icon}
          size={22}
          color={isPremium ? colors.warning : theme.custom.colors.textPrimary}
        />
        <Text
          style={[
            styles.settingLabel,
            { color: isPremium ? colors.warning : theme.custom.colors.textPrimary },
          ]}
        >
          {label}
        </Text>
      </View>

      <View style={styles.settingRight}>
        {isPremium && (
          <View style={styles.proBadge}>
            <Text style={styles.proBadgeText}>PRO</Text>
          </View>
        )}
        {value && (
          <Text style={[styles.settingValue, { color: theme.custom.colors.textSecondary }]}>
            {value}
          </Text>
        )}
        <Icon name="chevron-right" size={20} color={theme.custom.colors.textMuted} />
      </View>
    </TouchableOpacity>
  );
};

export const ProfileScreen: React.FC = () => {
  const theme = useTheme() as AppTheme;
  const { user } = useAuthStore();
  const { totalCompleted, currentStreak, level, totalXP } = useDreamsStore();

  // Mock user data for demo
  const displayName = user?.displayName || 'Marie Dupont';
  const userLevel = level || 8;
  const userXP = totalXP || 2450;
  const nextLevelXP = 3000;
  const xpProgress = userXP / nextLevelXP;

  return (
    <SafeAreaView style={[styles.container, { backgroundColor: theme.colors.background }]} edges={['top']}>
      <ScrollView showsVerticalScrollIndicator={false}>
        {/* Header with gradient */}
        <LinearGradient
          colors={[colors.primary[500], colors.primary[600]]}
          style={styles.headerGradient}
        >
          {/* Avatar */}
          <View style={styles.avatarContainer}>
            <View style={styles.avatar}>
              <Text style={styles.avatarEmoji}>👩</Text>
            </View>
            <View style={styles.levelBadge}>
              <Text style={styles.levelText}>{userLevel}</Text>
            </View>
          </View>

          {/* Name & Title */}
          <Text style={styles.userName}>{displayName}</Text>
          <Text style={styles.userTitle}>Dream Warrior</Text>

          {/* XP Progress */}
          <View style={styles.xpContainer}>
            <ProgressBar
              progress={xpProgress}
              color={colors.white}
              style={styles.xpBar}
            />
            <Text style={styles.xpText}>
              {userXP.toLocaleString()} / {nextLevelXP.toLocaleString()} XP
            </Text>
          </View>
        </LinearGradient>

        {/* Stats Cards */}
        <View style={styles.statsRow}>
          <View style={[styles.statCard, { backgroundColor: theme.colors.surface }, shadows.md]}>
            <Text style={[styles.statValue, { color: colors.primary[500] }]}>3</Text>
            <Text style={[styles.statLabel, { color: theme.custom.colors.textSecondary }]}>
              Rêves{'\n'}en cours
            </Text>
          </View>

          <View style={[styles.statCard, { backgroundColor: theme.colors.surface }, shadows.md]}>
            <Text style={[styles.statValue, { color: colors.success }]}>
              {totalCompleted || 45}
            </Text>
            <Text style={[styles.statLabel, { color: theme.custom.colors.textSecondary }]}>
              Tâches{'\n'}complétées
            </Text>
          </View>

          <View style={[styles.statCard, { backgroundColor: theme.colors.surface }, shadows.md]}>
            <Text style={[styles.statValue, { color: colors.warning }]}>
              {currentStreak || 12}
            </Text>
            <Text style={[styles.statLabel, { color: theme.custom.colors.textSecondary }]}>
              Jours de{'\n'}série 🔥
            </Text>
          </View>
        </View>

        {/* Badges Section */}
        <View style={styles.section}>
          <View style={styles.sectionHeader}>
            <Text style={[styles.sectionTitle, { color: theme.custom.colors.textPrimary }]}>
              🏆 Badges
            </Text>
            <TouchableOpacity>
              <Text style={[styles.seeAllText, { color: colors.primary[500] }]}>Voir tout</Text>
            </TouchableOpacity>
          </View>

          <View style={[styles.badgesContainer, { backgroundColor: theme.colors.surface }, shadows.sm]}>
            {BADGES.map((badge) => (
              <View key={badge.id} style={styles.badgeItem}>
                <View style={[styles.badgeCircle, { backgroundColor: badge.color + '20' }]}>
                  <Text style={[styles.badgeEmoji, badge.locked && styles.badgeEmojiLocked]}>
                    {badge.emoji}
                  </Text>
                </View>
                <Text
                  style={[
                    styles.badgeName,
                    { color: badge.locked ? theme.custom.colors.textMuted : theme.custom.colors.textSecondary },
                  ]}
                >
                  {badge.name}
                </Text>
              </View>
            ))}
          </View>
        </View>

        {/* Settings Section */}
        <View style={styles.section}>
          <Text style={[styles.sectionTitle, { color: theme.custom.colors.textPrimary }]}>
            ⚙️ Paramètres
          </Text>

          <View style={[styles.settingsContainer, { backgroundColor: theme.colors.surface }, shadows.sm]}>
            {SETTINGS_ITEMS.map((item, index) => (
              <React.Fragment key={item.label}>
                <SettingItem
                  icon={item.icon}
                  label={item.label}
                  value={item.value}
                  isPremium={item.isPremium}
                  onPress={() => console.log('Navigate to:', item.screen)}
                />
                {index < SETTINGS_ITEMS.length - 1 && (
                  <View style={[styles.divider, { backgroundColor: theme.custom.colors.border }]} />
                )}
              </React.Fragment>
            ))}

            <View style={[styles.divider, { backgroundColor: theme.custom.colors.border }]} />

            {/* Logout */}
            <TouchableOpacity style={styles.settingItem} activeOpacity={0.7}>
              <View style={styles.settingLeft}>
                <Icon name="logout" size={22} color={colors.error} />
                <Text style={[styles.settingLabel, { color: colors.error }]}>
                  Se déconnecter
                </Text>
              </View>
            </TouchableOpacity>
          </View>
        </View>

        {/* App version */}
        <Text style={[styles.version, { color: theme.custom.colors.textMuted }]}>
          DreamPlanner v1.0.0
        </Text>
      </ScrollView>
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  headerGradient: {
    paddingTop: spacing.xl,
    paddingBottom: spacing.xl,
    paddingHorizontal: spacing.md,
    alignItems: 'center',
  },
  avatarContainer: {
    position: 'relative',
    marginBottom: spacing.md,
  },
  avatar: {
    width: 100,
    height: 100,
    borderRadius: 50,
    backgroundColor: colors.white,
    justifyContent: 'center',
    alignItems: 'center',
    borderWidth: 4,
    borderColor: 'rgba(255,255,255,0.3)',
  },
  avatarEmoji: {
    fontSize: 50,
  },
  levelBadge: {
    position: 'absolute',
    bottom: 0,
    right: 0,
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: colors.warning,
    justifyContent: 'center',
    alignItems: 'center',
    borderWidth: 3,
    borderColor: colors.primary[500],
  },
  levelText: {
    color: colors.white,
    fontSize: 14,
    fontWeight: '700',
  },
  userName: {
    ...typography.h2,
    color: colors.white,
    marginBottom: 4,
  },
  userTitle: {
    fontSize: 14,
    color: 'rgba(255,255,255,0.8)',
    marginBottom: spacing.md,
  },
  xpContainer: {
    width: '80%',
    alignItems: 'center',
  },
  xpBar: {
    width: '100%',
    height: 6,
    borderRadius: 3,
    backgroundColor: 'rgba(255,255,255,0.3)',
  },
  xpText: {
    fontSize: 10,
    color: 'rgba(255,255,255,0.9)',
    marginTop: 6,
  },
  statsRow: {
    flexDirection: 'row',
    marginTop: -spacing.xl,
    marginHorizontal: spacing.md,
    marginBottom: spacing.md,
  },
  statCard: {
    flex: 1,
    padding: spacing.md,
    borderRadius: borderRadius.lg,
    marginHorizontal: spacing.xs,
    alignItems: 'center',
  },
  statValue: {
    fontSize: 28,
    fontWeight: '700',
  },
  statLabel: {
    fontSize: 11,
    textAlign: 'center',
    marginTop: 4,
  },
  section: {
    paddingHorizontal: spacing.md,
    marginBottom: spacing.lg,
  },
  sectionHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: spacing.sm,
  },
  sectionTitle: {
    ...typography.h4,
  },
  seeAllText: {
    fontSize: 14,
  },
  badgesContainer: {
    flexDirection: 'row',
    justifyContent: 'space-around',
    padding: spacing.md,
    borderRadius: borderRadius.lg,
  },
  badgeItem: {
    alignItems: 'center',
  },
  badgeCircle: {
    width: 48,
    height: 48,
    borderRadius: 24,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: spacing.xs,
  },
  badgeEmoji: {
    fontSize: 24,
  },
  badgeEmojiLocked: {
    opacity: 0.5,
  },
  badgeName: {
    fontSize: 10,
  },
  settingsContainer: {
    borderRadius: borderRadius.lg,
    overflow: 'hidden',
  },
  settingItem: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: spacing.md,
    paddingHorizontal: spacing.md,
  },
  settingLeft: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  settingLabel: {
    fontSize: 15,
    marginLeft: spacing.md,
  },
  settingRight: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  settingValue: {
    fontSize: 14,
    marginRight: spacing.sm,
  },
  proBadge: {
    backgroundColor: colors.warning,
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 10,
    marginRight: spacing.sm,
  },
  proBadgeText: {
    color: colors.white,
    fontSize: 10,
    fontWeight: '600',
  },
  divider: {
    height: 1,
    marginLeft: 54,
  },
  version: {
    textAlign: 'center',
    fontSize: 12,
    paddingVertical: spacing.lg,
  },
});
