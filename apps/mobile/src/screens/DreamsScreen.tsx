import React from 'react';
import {
  View,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
} from 'react-native';
import { Text, useTheme, ProgressBar, FAB } from 'react-native-paper';
import { SafeAreaView } from 'react-native-safe-area-context';
import Icon from 'react-native-vector-icons/MaterialCommunityIcons';

import { useDreamsStore } from '../stores/dreamsStore';
import { AppTheme, spacing, borderRadius, colors, shadows, typography } from '../theme';
import { Dream } from '../types';

// Mock data for demo
const MOCK_DREAMS: Dream[] = [
  {
    id: '1',
    title: 'Apprendre la guitare',
    description: 'Jouer mes chansons préférées',
    category: 'creativity',
    targetDate: new Date('2026-06-01'),
    priority: 1,
    status: 'active',
    progress: 35,
    createdAt: new Date(),
    updatedAt: new Date(),
    goals: [],
  },
  {
    id: '2',
    title: 'Courir un 10km',
    description: 'Participer à une course officielle',
    category: 'health',
    targetDate: new Date('2026-03-15'),
    priority: 2,
    status: 'active',
    progress: 65,
    createdAt: new Date(),
    updatedAt: new Date(),
    goals: [],
  },
  {
    id: '3',
    title: 'Lire 20 livres',
    description: 'Développer ma culture générale',
    category: 'education',
    targetDate: new Date('2026-12-31'),
    priority: 3,
    status: 'active',
    progress: 15,
    createdAt: new Date(),
    updatedAt: new Date(),
    goals: [],
  },
];

const getCategoryIcon = (category: string): string => {
  const icons: Record<string, string> = {
    career: 'briefcase',
    health: 'run',
    education: 'book-open-variant',
    personal: 'account-heart',
    finance: 'cash',
    travel: 'airplane',
    creativity: 'palette',
    wellness: 'meditation',
  };
  return icons[category] || 'star';
};

const getCategoryColor = (category: string): string => {
  const categoryColors: Record<string, string> = {
    career: colors.info,
    health: colors.success,
    education: colors.warning,
    personal: colors.primary[400],
    finance: colors.success,
    travel: colors.info,
    creativity: colors.primary[500],
    wellness: colors.secondary[500],
  };
  return categoryColors[category] || colors.primary[500];
};

interface DreamCardProps {
  dream: Dream;
  onPress: () => void;
}

const DreamCard: React.FC<DreamCardProps> = ({ dream, onPress }) => {
  const theme = useTheme() as AppTheme;
  const categoryColor = getCategoryColor(dream.category);

  return (
    <TouchableOpacity
      style={[styles.dreamCard, { backgroundColor: theme.colors.surface }, shadows.md]}
      onPress={onPress}
      activeOpacity={0.7}
    >
      <View style={[styles.cardAccent, { backgroundColor: categoryColor }]} />

      <View style={styles.cardContent}>
        <View style={styles.cardHeader}>
          <View style={[styles.iconContainer, { backgroundColor: `${categoryColor}20` }]}>
            <Icon name={getCategoryIcon(dream.category)} size={20} color={categoryColor} />
          </View>
          <View style={styles.cardTitleContainer}>
            <Text style={[styles.cardTitle, { color: theme.custom.colors.textPrimary }]}>
              {dream.title}
            </Text>
            <Text style={[styles.cardDescription, { color: theme.custom.colors.textSecondary }]}>
              {dream.description}
            </Text>
          </View>
        </View>

        <View style={styles.progressContainer}>
          <ProgressBar
            progress={dream.progress / 100}
            color={categoryColor}
            style={styles.progressBar}
          />
          <Text style={[styles.progressText, { color: categoryColor }]}>
            {dream.progress}%
          </Text>
        </View>

        <View style={styles.cardFooter}>
          <View style={styles.footerItem}>
            <Icon name="calendar" size={14} color={theme.custom.colors.textMuted} />
            <Text style={[styles.footerText, { color: theme.custom.colors.textSecondary }]}>
              {dream.targetDate?.toLocaleDateString('fr-FR', { month: 'short', year: 'numeric' })}
            </Text>
          </View>
          <TouchableOpacity style={[styles.viewButton, { backgroundColor: `${categoryColor}15` }]}>
            <Text style={[styles.viewButtonText, { color: categoryColor }]}>Voir</Text>
          </TouchableOpacity>
        </View>
      </View>
    </TouchableOpacity>
  );
};

export const DreamsScreen: React.FC = () => {
  const theme = useTheme() as AppTheme;
  const { totalCompleted, currentStreak, level, totalXP } = useDreamsStore();

  // Use mock data for demo
  const dreams = MOCK_DREAMS;
  const activeDreams = dreams.filter(d => d.status === 'active');

  return (
    <SafeAreaView
      style={[styles.container, { backgroundColor: theme.colors.background }]}
      edges={['top']}
    >
      {/* Header */}
      <View style={[styles.header, { backgroundColor: theme.colors.surface }]}>
        <View>
          <Text style={[styles.headerTitle, { color: theme.custom.colors.textPrimary }]}>
            Mes Rêves
          </Text>
          <Text style={[styles.headerSubtitle, { color: theme.custom.colors.textSecondary }]}>
            {activeDreams.length} objectif{activeDreams.length > 1 ? 's' : ''} en cours
          </Text>
        </View>
      </View>

      <ScrollView
        style={styles.scrollView}
        contentContainerStyle={styles.scrollContent}
        showsVerticalScrollIndicator={false}
      >
        {/* Stats Row */}
        <View style={styles.statsRow}>
          <View style={[styles.statCard, { backgroundColor: theme.colors.surface }, shadows.sm]}>
            <Text style={[styles.statValue, { color: colors.primary[500] }]}>
              {currentStreak || 12}
            </Text>
            <Text style={[styles.statLabel, { color: theme.custom.colors.textSecondary }]}>
              Jours de série
            </Text>
            <Text style={styles.statEmoji}>🔥</Text>
          </View>

          <View style={[styles.statCard, { backgroundColor: theme.colors.surface }, shadows.sm]}>
            <Text style={[styles.statValue, { color: colors.success }]}>
              {totalCompleted || 45}
            </Text>
            <Text style={[styles.statLabel, { color: theme.custom.colors.textSecondary }]}>
              Tâches faites
            </Text>
            <Text style={styles.statEmoji}>✅</Text>
          </View>

          <View style={[styles.statCard, { backgroundColor: theme.colors.surface }, shadows.sm]}>
            <Text style={[styles.statValue, { color: colors.warning }]}>
              Lv.{level || 8}
            </Text>
            <Text style={[styles.statLabel, { color: theme.custom.colors.textSecondary }]}>
              Dream Warrior
            </Text>
            <Text style={styles.statEmoji}>⚔️</Text>
          </View>
        </View>

        {/* Section Title */}
        <Text style={[styles.sectionTitle, { color: theme.custom.colors.textPrimary }]}>
          🔥 En cours
        </Text>

        {/* Dream Cards */}
        {activeDreams.map((dream) => (
          <DreamCard
            key={dream.id}
            dream={dream}
            onPress={() => console.log('Dream pressed:', dream.id)}
          />
        ))}
      </ScrollView>

      {/* FAB */}
      <FAB
        icon="plus"
        style={[styles.fab, { backgroundColor: theme.colors.primary }]}
        color={colors.white}
        onPress={() => console.log('Add new dream')}
      />
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
    alignItems: 'center',
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.md,
    borderBottomWidth: 1,
    borderBottomColor: colors.gray[200],
  },
  headerTitle: {
    ...typography.h2,
  },
  headerSubtitle: {
    ...typography.bodySmall,
    marginTop: 2,
  },
  scrollView: {
    flex: 1,
  },
  scrollContent: {
    padding: spacing.md,
    paddingBottom: 100,
  },
  statsRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: spacing.lg,
  },
  statCard: {
    flex: 1,
    padding: spacing.md,
    borderRadius: borderRadius.lg,
    marginHorizontal: spacing.xs,
    alignItems: 'center',
  },
  statValue: {
    fontSize: 24,
    fontWeight: '700',
  },
  statLabel: {
    fontSize: 11,
    marginTop: 4,
    textAlign: 'center',
  },
  statEmoji: {
    fontSize: 16,
    marginTop: 4,
  },
  sectionTitle: {
    ...typography.h4,
    marginBottom: spacing.md,
  },
  dreamCard: {
    flexDirection: 'row',
    borderRadius: borderRadius.lg,
    marginBottom: spacing.md,
    overflow: 'hidden',
  },
  cardAccent: {
    width: 6,
  },
  cardContent: {
    flex: 1,
    padding: spacing.md,
  },
  cardHeader: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    marginBottom: spacing.sm,
  },
  iconContainer: {
    width: 40,
    height: 40,
    borderRadius: 20,
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: spacing.sm,
  },
  cardTitleContainer: {
    flex: 1,
  },
  cardTitle: {
    ...typography.h4,
  },
  cardDescription: {
    ...typography.bodySmall,
    marginTop: 2,
  },
  progressContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: spacing.sm,
  },
  progressBar: {
    flex: 1,
    height: 8,
    borderRadius: 4,
  },
  progressText: {
    marginLeft: spacing.sm,
    fontSize: 12,
    fontWeight: '600',
  },
  cardFooter: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  footerItem: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  footerText: {
    fontSize: 12,
    marginLeft: 4,
  },
  viewButton: {
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.xs,
    borderRadius: borderRadius.xl,
  },
  viewButtonText: {
    fontSize: 12,
    fontWeight: '600',
  },
  fab: {
    position: 'absolute',
    right: spacing.md,
    bottom: spacing.md,
  },
});
