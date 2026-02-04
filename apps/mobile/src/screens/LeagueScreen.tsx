import React, { useMemo } from 'react';
import {
  View,
  StyleSheet,
  ScrollView,
  ActivityIndicator,
  RefreshControl,
} from 'react-native';
import { Text, Surface, Avatar, Chip, Divider, Button, useTheme } from 'react-native-paper';
import { SafeAreaView } from 'react-native-safe-area-context';
import Icon from 'react-native-vector-icons/MaterialCommunityIcons';
import { useQuery } from '@tanstack/react-query';
import { api } from '../services/api';
import { AppTheme, spacing, borderRadius, colors, shadows, typography } from '../theme';
import { League, LeagueStanding, Season } from '../types';

const TIER_ICONS: Record<string, string> = {
  bronze: 'shield',
  silver: 'shield-half-full',
  gold: 'shield-star',
  platinum: 'shield-crown',
  diamond: 'diamond-stone',
  master: 'crown',
  legend: 'trophy',
};

const TIER_COLORS: Record<string, string> = {
  bronze: '#CD7F32',
  silver: '#C0C0C0',
  gold: '#FFD700',
  platinum: '#E5E4E2',
  diamond: '#B9F2FF',
  master: colors.primary[500],
  legend: colors.warning,
};

const RANK_MEDAL_COLORS: Record<number, string> = {
  1: '#FFD700',
  2: '#C0C0C0',
  3: '#CD7F32',
};

export const LeagueScreen: React.FC = () => {
  const theme = useTheme() as AppTheme;

  const {
    data: currentLeague,
    isLoading: leagueLoading,
    isError: leagueError,
    refetch: refetchLeague,
  } = useQuery<League>({
    queryKey: ['league-current'],
    queryFn: () => api.leagues.getCurrent() as Promise<League>,
  });

  const {
    data: myStanding,
    isLoading: standingLoading,
    refetch: refetchStanding,
  } = useQuery<LeagueStanding>({
    queryKey: ['league-my-standing'],
    queryFn: () => api.leagues.getMyStanding() as Promise<LeagueStanding>,
  });

  const {
    data: standings,
    isLoading: standingsLoading,
    refetch: refetchStandings,
  } = useQuery<LeagueStanding[]>({
    queryKey: ['league-standings', currentLeague?.id],
    queryFn: () =>
      api.leagues.getStandings(currentLeague!.id) as Promise<LeagueStanding[]>,
    enabled: !!currentLeague?.id,
  });

  const {
    data: season,
    isLoading: seasonLoading,
    refetch: refetchSeason,
  } = useQuery<Season>({
    queryKey: ['league-season'],
    queryFn: () => api.leagues.getCurrentSeason() as Promise<Season>,
  });

  const isLoading = leagueLoading || standingLoading || standingsLoading || seasonLoading;

  const handleRefresh = () => {
    refetchLeague();
    refetchStanding();
    refetchStandings();
    refetchSeason();
  };

  const daysRemaining = useMemo(() => {
    if (!season?.endDate) return null;
    const end = new Date(season.endDate);
    const now = new Date();
    const diff = Math.ceil((end.getTime() - now.getTime()) / (1000 * 60 * 60 * 24));
    return Math.max(0, diff);
  }, [season?.endDate]);

  const tierColor = currentLeague ? TIER_COLORS[currentLeague.tier] || colors.primary[500] : colors.gray[400];
  const tierIcon = currentLeague ? TIER_ICONS[currentLeague.tier] || 'shield' : 'shield';

  const getZoneType = (rank: number, totalStandings: number): 'promotion' | 'demotion' | 'safe' => {
    if (rank <= 3) return 'promotion';
    if (totalStandings > 3 && rank > totalStandings - 3) return 'demotion';
    return 'safe';
  };

  const getZoneColor = (zone: 'promotion' | 'demotion' | 'safe'): string => {
    switch (zone) {
      case 'promotion':
        return colors.success;
      case 'demotion':
        return colors.error;
      default:
        return 'transparent';
    }
  };

  if (isLoading && !currentLeague) {
    return (
      <SafeAreaView style={[styles.container, { backgroundColor: theme.colors.background }]} edges={['top']}>
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color={theme.colors.primary} />
          <Text style={[styles.loadingText, { color: theme.custom.colors.textSecondary }]}>
            Loading league data...
          </Text>
        </View>
      </SafeAreaView>
    );
  }

  if (leagueError) {
    return (
      <SafeAreaView style={[styles.container, { backgroundColor: theme.colors.background }]} edges={['top']}>
        <View style={styles.errorContainer}>
          <Icon name="alert-circle-outline" size={64} color={colors.error} />
          <Text style={[styles.errorTitle, { color: theme.custom.colors.textPrimary }]}>
            Could Not Load League
          </Text>
          <Text style={[styles.errorText, { color: theme.custom.colors.textSecondary }]}>
            There was a problem loading your league information. Please try again.
          </Text>
          <Button mode="contained" onPress={handleRefresh} style={styles.retryButton}>
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
        <Text style={[typography.h2, { color: theme.custom.colors.textPrimary }]}>
          League
        </Text>
      </View>

      <ScrollView
        style={styles.scrollView}
        contentContainerStyle={styles.scrollContent}
        showsVerticalScrollIndicator={false}
        refreshControl={
          <RefreshControl refreshing={isLoading} onRefresh={handleRefresh} />
        }
      >
        {/* Current League Badge */}
        {currentLeague && (
          <Surface style={[styles.leagueBadgeCard, shadows.md]} elevation={3}>
            <View style={[styles.leagueIconContainer, { backgroundColor: tierColor + '20' }]}>
              <Icon name={tierIcon} size={56} color={tierColor} />
            </View>
            <Text style={[styles.leagueTierName, { color: tierColor }]}>
              {currentLeague.name}
            </Text>
            <Text style={[styles.leagueTierLabel, { color: theme.custom.colors.textSecondary }]}>
              {currentLeague.tier.charAt(0).toUpperCase() + currentLeague.tier.slice(1)} League
            </Text>

            {/* Score Range */}
            <View style={[styles.scoreRange, { backgroundColor: theme.colors.surfaceVariant }]}>
              <Text style={[styles.scoreRangeText, { color: theme.custom.colors.textSecondary }]}>
                Score range: {currentLeague.minScore} - {currentLeague.maxScore}
              </Text>
            </View>
          </Surface>
        )}

        {/* Season Info */}
        {season && (
          <Surface style={[styles.seasonCard, shadows.sm]} elevation={1}>
            <View style={styles.seasonHeader}>
              <Icon name="calendar-star" size={22} color={colors.primary[500]} />
              <Text style={[styles.seasonName, { color: theme.custom.colors.textPrimary }]}>
                {season.name}
              </Text>
            </View>
            <Divider style={{ marginVertical: spacing.sm }} />
            <View style={styles.seasonDetails}>
              <View style={styles.seasonDetailItem}>
                <Text style={[styles.seasonDetailLabel, { color: theme.custom.colors.textSecondary }]}>
                  Start
                </Text>
                <Text style={[styles.seasonDetailValue, { color: theme.custom.colors.textPrimary }]}>
                  {new Date(season.startDate).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
                </Text>
              </View>
              <View style={[styles.seasonDivider, { backgroundColor: theme.custom.colors.border }]} />
              <View style={styles.seasonDetailItem}>
                <Text style={[styles.seasonDetailLabel, { color: theme.custom.colors.textSecondary }]}>
                  End
                </Text>
                <Text style={[styles.seasonDetailValue, { color: theme.custom.colors.textPrimary }]}>
                  {new Date(season.endDate).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
                </Text>
              </View>
              <View style={[styles.seasonDivider, { backgroundColor: theme.custom.colors.border }]} />
              <View style={styles.seasonDetailItem}>
                <Text style={[styles.seasonDetailLabel, { color: theme.custom.colors.textSecondary }]}>
                  Remaining
                </Text>
                <Text style={[styles.seasonDetailValue, { color: daysRemaining !== null && daysRemaining <= 7 ? colors.warning : theme.custom.colors.textPrimary }]}>
                  {daysRemaining !== null ? `${daysRemaining} day${daysRemaining !== 1 ? 's' : ''}` : '--'}
                </Text>
              </View>
            </View>
          </Surface>
        )}

        {/* My Standing */}
        {myStanding && (
          <Surface style={[styles.myStandingCard, shadows.sm]} elevation={1}>
            <View style={styles.myStandingHeader}>
              <Icon name="account-star" size={22} color={colors.primary[500]} />
              <Text style={[styles.myStandingTitle, { color: theme.custom.colors.textPrimary }]}>
                Your Standing
              </Text>
            </View>
            <Divider style={{ marginVertical: spacing.sm }} />
            <View style={styles.myStandingStats}>
              <View style={styles.myStatItem}>
                <Text style={[styles.myStatValue, { color: colors.primary[500] }]}>
                  #{myStanding.rank}
                </Text>
                <Text style={[styles.myStatLabel, { color: theme.custom.colors.textSecondary }]}>
                  Rank
                </Text>
              </View>
              <View style={[styles.myStatDivider, { backgroundColor: theme.custom.colors.border }]} />
              <View style={styles.myStatItem}>
                <Text style={[styles.myStatValue, { color: colors.warning }]}>
                  {myStanding.weeklyScore}
                </Text>
                <Text style={[styles.myStatLabel, { color: theme.custom.colors.textSecondary }]}>
                  Weekly Score
                </Text>
              </View>
              <View style={[styles.myStatDivider, { backgroundColor: theme.custom.colors.border }]} />
              <View style={styles.myStatItem}>
                <Text style={[styles.myStatValue, { color: colors.success }]}>
                  {myStanding.badges?.length || 0}
                </Text>
                <Text style={[styles.myStatLabel, { color: theme.custom.colors.textSecondary }]}>
                  Badges
                </Text>
              </View>
            </View>
          </Surface>
        )}

        {/* Leaderboard */}
        <View style={styles.leaderboardSection}>
          <View style={styles.leaderboardHeader}>
            <Text style={[typography.h3, { color: theme.custom.colors.textPrimary }]}>
              Leaderboard
            </Text>
            {standings && standings.length > 0 && (
              <Text style={[typography.bodySmall, { color: theme.custom.colors.textSecondary }]}>
                {standings.length} participants
              </Text>
            )}
          </View>

          {/* Zone Legend */}
          <View style={styles.zoneLegend}>
            <View style={styles.zoneLegendItem}>
              <View style={[styles.zoneDot, { backgroundColor: colors.success }]} />
              <Text style={[styles.zoneLegendText, { color: theme.custom.colors.textSecondary }]}>
                Promotion zone (top 3)
              </Text>
            </View>
            <View style={styles.zoneLegendItem}>
              <View style={[styles.zoneDot, { backgroundColor: colors.error }]} />
              <Text style={[styles.zoneLegendText, { color: theme.custom.colors.textSecondary }]}>
                Demotion zone (bottom 3)
              </Text>
            </View>
          </View>

          {/* Standings List */}
          {standings && standings.length > 0 ? (
            standings.map((standing, index) => {
              const zone = getZoneType(standing.rank, standings.length);
              const zoneColor = getZoneColor(zone);
              const isCurrentUser = myStanding && standing.userId === myStanding.userId;
              const medalColor = RANK_MEDAL_COLORS[standing.rank];

              return (
                <Surface
                  key={standing.id}
                  style={[
                    styles.standingRow,
                    zone !== 'safe' && { borderLeftWidth: 4, borderLeftColor: zoneColor },
                    isCurrentUser && { borderWidth: 2, borderColor: colors.primary[500] },
                    shadows.sm,
                  ]}
                  elevation={isCurrentUser ? 2 : 0}
                >
                  {/* Rank */}
                  <View style={styles.rankContainer}>
                    {medalColor ? (
                      <View style={[styles.medalCircle, { backgroundColor: medalColor + '30' }]}>
                        <Icon
                          name={standing.rank === 1 ? 'crown' : 'medal'}
                          size={18}
                          color={medalColor}
                        />
                      </View>
                    ) : (
                      <View style={[styles.rankCircle, { backgroundColor: theme.colors.surfaceVariant }]}>
                        <Text style={[styles.rankNumber, { color: theme.custom.colors.textSecondary }]}>
                          {standing.rank}
                        </Text>
                      </View>
                    )}
                  </View>

                  {/* Avatar */}
                  {standing.avatarUrl ? (
                    <Avatar.Image size={40} source={{ uri: standing.avatarUrl }} />
                  ) : (
                    <Avatar.Icon size={40} icon="account" />
                  )}

                  {/* User Info */}
                  <View style={styles.standingInfo}>
                    <Text
                      style={[
                        styles.standingUsername,
                        { color: isCurrentUser ? colors.primary[500] : theme.custom.colors.textPrimary },
                      ]}
                      numberOfLines={1}
                    >
                      {standing.username}
                      {isCurrentUser ? ' (You)' : ''}
                    </Text>
                    {standing.badges && standing.badges.length > 0 && (
                      <View style={styles.badgeRow}>
                        {standing.badges.slice(0, 3).map((badge, i) => (
                          <Chip
                            key={i}
                            compact
                            style={styles.standingBadge}
                            textStyle={styles.standingBadgeText}
                          >
                            {badge}
                          </Chip>
                        ))}
                        {standing.badges.length > 3 && (
                          <Text style={[styles.moreBadges, { color: theme.custom.colors.textMuted }]}>
                            +{standing.badges.length - 3}
                          </Text>
                        )}
                      </View>
                    )}
                  </View>

                  {/* Score */}
                  <View style={styles.standingScore}>
                    <Text style={[styles.scoreValue, { color: theme.custom.colors.textPrimary }]}>
                      {standing.weeklyScore}
                    </Text>
                    <Text style={[styles.scoreLabel, { color: theme.custom.colors.textSecondary }]}>
                      pts
                    </Text>
                  </View>

                  {/* Zone indicator arrow */}
                  {zone === 'promotion' && (
                    <Icon name="arrow-up-bold" size={16} color={colors.success} style={styles.zoneArrow} />
                  )}
                  {zone === 'demotion' && (
                    <Icon name="arrow-down-bold" size={16} color={colors.error} style={styles.zoneArrow} />
                  )}
                </Surface>
              );
            })
          ) : (
            !isLoading && (
              <View style={styles.emptyState}>
                <Icon name="trophy-outline" size={64} color={theme.custom.colors.textMuted} />
                <Text style={[styles.emptyTitle, { color: theme.custom.colors.textPrimary }]}>
                  No Standings Yet
                </Text>
                <Text style={[styles.emptyText, { color: theme.custom.colors.textSecondary }]}>
                  Complete tasks and earn points to appear on the leaderboard!
                </Text>
              </View>
            )
          )}
        </View>
      </ScrollView>
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  header: {
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.md,
    borderBottomWidth: 1,
  },
  scrollView: {
    flex: 1,
  },
  scrollContent: {
    padding: spacing.md,
    paddingBottom: 100,
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
  leagueBadgeCard: {
    borderRadius: borderRadius.lg,
    padding: spacing.lg,
    alignItems: 'center',
    marginBottom: spacing.md,
  },
  leagueIconContainer: {
    width: 100,
    height: 100,
    borderRadius: 50,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: spacing.sm,
  },
  leagueTierName: {
    ...typography.h2,
    fontWeight: '700',
  },
  leagueTierLabel: {
    ...typography.bodySmall,
    marginTop: 2,
  },
  scoreRange: {
    marginTop: spacing.sm,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.xs,
    borderRadius: borderRadius.full,
  },
  scoreRangeText: {
    ...typography.caption,
  },
  seasonCard: {
    borderRadius: borderRadius.lg,
    padding: spacing.md,
    marginBottom: spacing.md,
  },
  seasonHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
  },
  seasonName: {
    ...typography.h4,
  },
  seasonDetails: {
    flexDirection: 'row',
    justifyContent: 'space-around',
    alignItems: 'center',
  },
  seasonDetailItem: {
    alignItems: 'center',
    flex: 1,
  },
  seasonDetailLabel: {
    ...typography.caption,
    marginBottom: 4,
  },
  seasonDetailValue: {
    fontSize: 15,
    fontWeight: '600',
  },
  seasonDivider: {
    width: 1,
    height: 36,
  },
  myStandingCard: {
    borderRadius: borderRadius.lg,
    padding: spacing.md,
    marginBottom: spacing.lg,
  },
  myStandingHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
  },
  myStandingTitle: {
    ...typography.h4,
  },
  myStandingStats: {
    flexDirection: 'row',
    justifyContent: 'space-around',
    alignItems: 'center',
  },
  myStatItem: {
    alignItems: 'center',
    flex: 1,
  },
  myStatValue: {
    fontSize: 28,
    fontWeight: '700',
  },
  myStatLabel: {
    ...typography.caption,
    marginTop: 4,
  },
  myStatDivider: {
    width: 1,
    height: 44,
  },
  leaderboardSection: {
    marginBottom: spacing.lg,
  },
  leaderboardHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: spacing.sm,
  },
  zoneLegend: {
    flexDirection: 'row',
    gap: spacing.md,
    marginBottom: spacing.md,
  },
  zoneLegendItem: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  zoneDot: {
    width: 10,
    height: 10,
    borderRadius: 5,
  },
  zoneLegendText: {
    ...typography.caption,
  },
  standingRow: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: spacing.sm,
    borderRadius: borderRadius.md,
    marginBottom: spacing.sm,
  },
  rankContainer: {
    width: 36,
    alignItems: 'center',
    marginRight: spacing.sm,
  },
  medalCircle: {
    width: 32,
    height: 32,
    borderRadius: 16,
    justifyContent: 'center',
    alignItems: 'center',
  },
  rankCircle: {
    width: 32,
    height: 32,
    borderRadius: 16,
    justifyContent: 'center',
    alignItems: 'center',
  },
  rankNumber: {
    fontSize: 14,
    fontWeight: '700',
  },
  standingInfo: {
    flex: 1,
    marginLeft: spacing.sm,
  },
  standingUsername: {
    fontSize: 15,
    fontWeight: '600',
  },
  badgeRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: 4,
    flexWrap: 'wrap',
    gap: 4,
  },
  standingBadge: {
    height: 22,
  },
  standingBadgeText: {
    fontSize: 9,
  },
  moreBadges: {
    fontSize: 11,
    marginLeft: 2,
  },
  standingScore: {
    alignItems: 'center',
    marginLeft: spacing.sm,
  },
  scoreValue: {
    fontSize: 17,
    fontWeight: '700',
  },
  scoreLabel: {
    fontSize: 10,
  },
  zoneArrow: {
    marginLeft: 6,
  },
  emptyState: {
    alignItems: 'center',
    padding: spacing.xxl,
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
});
