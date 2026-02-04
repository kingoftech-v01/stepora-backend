import React, { useState } from 'react';
import {
  View,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  ActivityIndicator,
  Alert,
  RefreshControl,
} from 'react-native';
import { Text, Button, Surface, Chip, Divider, Portal, Dialog, useTheme } from 'react-native-paper';
import { SafeAreaView } from 'react-native-safe-area-context';
import Icon from 'react-native-vector-icons/MaterialCommunityIcons';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../services/api';
import { AppTheme, spacing, borderRadius, colors, shadows, typography } from '../theme';
import { SubscriptionPlan, UserSubscription } from '../types';

type BillingCycle = 'monthly' | 'yearly';

const PLAN_ICONS: Record<string, string> = {
  free: 'star-outline',
  premium: 'star',
  pro: 'star-shooting',
};

const PLAN_COLORS: Record<string, string> = {
  free: colors.gray[500],
  premium: colors.primary[500],
  pro: colors.warning,
};

export const SubscriptionScreen: React.FC = () => {
  const theme = useTheme() as AppTheme;
  const queryClient = useQueryClient();
  const [billingCycle, setBillingCycle] = useState<BillingCycle>('monthly');
  const [cancelDialogVisible, setCancelDialogVisible] = useState(false);

  const {
    data: plans,
    isLoading: plansLoading,
    isError: plansError,
    refetch: refetchPlans,
  } = useQuery<SubscriptionPlan[]>({
    queryKey: ['subscription-plans'],
    queryFn: () => api.subscriptions.getPlans() as Promise<SubscriptionPlan[]>,
  });

  const {
    data: currentSubscription,
    isLoading: subscriptionLoading,
    isError: subscriptionError,
    refetch: refetchSubscription,
  } = useQuery<UserSubscription>({
    queryKey: ['current-subscription'],
    queryFn: () => api.subscriptions.getCurrent() as Promise<UserSubscription>,
  });

  const checkoutMutation = useMutation({
    mutationFn: (priceId: string) => api.subscriptions.createCheckout(priceId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['current-subscription'] });
      Alert.alert('Success', 'Your subscription has been updated. You may need to complete payment in your browser.');
    },
    onError: (error: any) => {
      Alert.alert('Error', error.message || 'Failed to start checkout. Please try again.');
    },
  });

  const cancelMutation = useMutation({
    mutationFn: () => api.subscriptions.cancel(),
    onSuccess: () => {
      setCancelDialogVisible(false);
      queryClient.invalidateQueries({ queryKey: ['current-subscription'] });
      Alert.alert('Subscription Canceled', 'Your subscription will remain active until the end of the current billing period.');
    },
    onError: (error: any) => {
      Alert.alert('Error', error.message || 'Failed to cancel subscription. Please try again.');
    },
  });

  const resumeMutation = useMutation({
    mutationFn: () => api.subscriptions.resume(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['current-subscription'] });
      Alert.alert('Welcome Back', 'Your subscription has been resumed.');
    },
    onError: (error: any) => {
      Alert.alert('Error', error.message || 'Failed to resume subscription. Please try again.');
    },
  });

  const isLoading = plansLoading || subscriptionLoading;
  const isError = plansError || subscriptionError;

  const handleRefresh = () => {
    refetchPlans();
    refetchSubscription();
  };

  const handleSubscribe = (plan: SubscriptionPlan) => {
    if (plan.tier === 'free') return;

    const priceId =
      billingCycle === 'monthly'
        ? plan.stripePriceIdMonthly
        : plan.stripePriceIdYearly;

    checkoutMutation.mutate(priceId);
  };

  const getDisplayPrice = (plan: SubscriptionPlan): string => {
    if (plan.tier === 'free') return 'Free';
    if (billingCycle === 'monthly') {
      return `$${plan.priceMonthly.toFixed(2)}`;
    }
    const yearlyMonthly = plan.priceYearly / 12;
    return `$${yearlyMonthly.toFixed(2)}`;
  };

  const getYearlySavings = (plan: SubscriptionPlan): string | null => {
    if (plan.tier === 'free' || billingCycle === 'monthly') return null;
    const monthlyCost = plan.priceMonthly * 12;
    const savings = monthlyCost - plan.priceYearly;
    if (savings <= 0) return null;
    return `Save $${savings.toFixed(2)}/year`;
  };

  const isCurrentPlan = (plan: SubscriptionPlan): boolean => {
    if (!currentSubscription) return plan.tier === 'free';
    return currentSubscription.tier === plan.tier && currentSubscription.status === 'active';
  };

  const getButtonLabel = (plan: SubscriptionPlan): string => {
    if (isCurrentPlan(plan)) return 'Current Plan';
    if (plan.tier === 'free') return 'Downgrade';
    if (!currentSubscription || currentSubscription.tier === 'free') return 'Subscribe';
    return 'Upgrade';
  };

  const getStatusColor = (status: string): string => {
    switch (status) {
      case 'active':
        return colors.success;
      case 'trialing':
        return colors.info;
      case 'canceled':
        return colors.warning;
      case 'past_due':
        return colors.error;
      default:
        return colors.gray[500];
    }
  };

  const getStatusLabel = (status: string): string => {
    switch (status) {
      case 'active':
        return 'Active';
      case 'trialing':
        return 'Trial';
      case 'canceled':
        return 'Canceled';
      case 'past_due':
        return 'Past Due';
      default:
        return status;
    }
  };

  const formatDate = (dateStr: string): string => {
    return new Date(dateStr).toLocaleDateString('en-US', {
      month: 'long',
      day: 'numeric',
      year: 'numeric',
    });
  };

  if (isLoading) {
    return (
      <SafeAreaView style={[styles.container, { backgroundColor: theme.colors.background }]} edges={['top']}>
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color={theme.colors.primary} />
          <Text style={[styles.loadingText, { color: theme.custom.colors.textSecondary }]}>
            Loading subscription details...
          </Text>
        </View>
      </SafeAreaView>
    );
  }

  if (isError) {
    return (
      <SafeAreaView style={[styles.container, { backgroundColor: theme.colors.background }]} edges={['top']}>
        <View style={styles.errorContainer}>
          <Icon name="alert-circle-outline" size={64} color={colors.error} />
          <Text style={[styles.errorTitle, { color: theme.custom.colors.textPrimary }]}>
            Something went wrong
          </Text>
          <Text style={[styles.errorText, { color: theme.custom.colors.textSecondary }]}>
            We could not load subscription information. Please try again.
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
          Subscription
        </Text>
        <Text style={[typography.bodySmall, { color: theme.custom.colors.textSecondary, marginTop: 2 }]}>
          Choose the plan that fits your dreams
        </Text>
      </View>

      <ScrollView
        style={styles.scrollView}
        contentContainerStyle={styles.scrollContent}
        showsVerticalScrollIndicator={false}
        refreshControl={
          <RefreshControl
            refreshing={plansLoading || subscriptionLoading}
            onRefresh={handleRefresh}
          />
        }
      >
        {/* Current Subscription Status */}
        {currentSubscription && currentSubscription.tier !== 'free' && (
          <Surface style={[styles.currentPlanCard, shadows.md]} elevation={2}>
            <View style={styles.currentPlanHeader}>
              <View style={styles.currentPlanInfo}>
                <Icon
                  name={PLAN_ICONS[currentSubscription.tier] || 'star'}
                  size={28}
                  color={PLAN_COLORS[currentSubscription.tier] || colors.primary[500]}
                />
                <View style={styles.currentPlanText}>
                  <Text style={[typography.h3, { color: theme.custom.colors.textPrimary }]}>
                    {currentSubscription.tier.charAt(0).toUpperCase() + currentSubscription.tier.slice(1)} Plan
                  </Text>
                  <Chip
                    compact
                    style={[styles.statusChip, { backgroundColor: getStatusColor(currentSubscription.status) + '20' }]}
                    textStyle={{ color: getStatusColor(currentSubscription.status), fontSize: 11 }}
                  >
                    {getStatusLabel(currentSubscription.status)}
                  </Chip>
                </View>
              </View>
            </View>

            <Divider style={{ marginVertical: spacing.sm }} />

            <View style={styles.currentPlanDetails}>
              <View style={styles.detailRow}>
                <Text style={[typography.bodySmall, { color: theme.custom.colors.textSecondary }]}>
                  Current period ends
                </Text>
                <Text style={[typography.bodySmall, { color: theme.custom.colors.textPrimary, fontWeight: '600' }]}>
                  {formatDate(currentSubscription.currentPeriodEnd)}
                </Text>
              </View>

              {currentSubscription.cancelAtPeriodEnd && (
                <View style={[styles.cancelNotice, { backgroundColor: colors.warning + '15' }]}>
                  <Icon name="information-outline" size={18} color={colors.warning} />
                  <Text style={[styles.cancelNoticeText, { color: colors.warning }]}>
                    Your subscription will end on {formatDate(currentSubscription.currentPeriodEnd)}
                  </Text>
                </View>
              )}
            </View>

            {/* Cancel / Resume */}
            <View style={styles.currentPlanActions}>
              {currentSubscription.cancelAtPeriodEnd ? (
                <Button
                  mode="contained"
                  onPress={() => resumeMutation.mutate()}
                  loading={resumeMutation.isPending}
                  style={styles.resumeButton}
                >
                  Resume Subscription
                </Button>
              ) : (
                <Button
                  mode="outlined"
                  textColor={colors.error}
                  onPress={() => setCancelDialogVisible(true)}
                  style={styles.cancelButton}
                >
                  Cancel Subscription
                </Button>
              )}
            </View>
          </Surface>
        )}

        {/* Billing Cycle Toggle */}
        <View style={styles.billingToggleContainer}>
          <TouchableOpacity
            style={[
              styles.billingOption,
              billingCycle === 'monthly' && { backgroundColor: theme.colors.primary },
            ]}
            onPress={() => setBillingCycle('monthly')}
            activeOpacity={0.7}
          >
            <Text
              style={[
                styles.billingOptionText,
                { color: billingCycle === 'monthly' ? colors.white : theme.custom.colors.textPrimary },
              ]}
            >
              Monthly
            </Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={[
              styles.billingOption,
              billingCycle === 'yearly' && { backgroundColor: theme.colors.primary },
            ]}
            onPress={() => setBillingCycle('yearly')}
            activeOpacity={0.7}
          >
            <Text
              style={[
                styles.billingOptionText,
                { color: billingCycle === 'yearly' ? colors.white : theme.custom.colors.textPrimary },
              ]}
            >
              Yearly
            </Text>
            <View style={styles.saveBadge}>
              <Text style={styles.saveBadgeText}>2 months free</Text>
            </View>
          </TouchableOpacity>
        </View>

        {/* Plan Cards */}
        {plans && plans.length > 0 ? (
          plans.map((plan) => {
            const isCurrent = isCurrentPlan(plan);
            const planColor = PLAN_COLORS[plan.tier] || colors.primary[500];
            const savings = getYearlySavings(plan);

            return (
              <Surface
                key={plan.id}
                style={[
                  styles.planCard,
                  isCurrent && { borderWidth: 2, borderColor: planColor },
                  shadows.md,
                ]}
                elevation={isCurrent ? 3 : 1}
              >
                {isCurrent && (
                  <View style={[styles.currentBadge, { backgroundColor: planColor }]}>
                    <Text style={styles.currentBadgeText}>Current</Text>
                  </View>
                )}

                {plan.tier === 'pro' && !isCurrent && (
                  <View style={[styles.currentBadge, { backgroundColor: colors.warning }]}>
                    <Text style={styles.currentBadgeText}>Most Popular</Text>
                  </View>
                )}

                <View style={styles.planHeader}>
                  <Icon name={PLAN_ICONS[plan.tier] || 'star'} size={32} color={planColor} />
                  <Text style={[styles.planName, { color: theme.custom.colors.textPrimary }]}>
                    {plan.name}
                  </Text>
                </View>

                <View style={styles.priceContainer}>
                  <Text style={[styles.priceAmount, { color: planColor }]}>
                    {getDisplayPrice(plan)}
                  </Text>
                  {plan.tier !== 'free' && (
                    <Text style={[styles.pricePeriod, { color: theme.custom.colors.textSecondary }]}>
                      /month
                    </Text>
                  )}
                </View>

                {savings && (
                  <View style={[styles.savingsTag, { backgroundColor: colors.success + '15' }]}>
                    <Text style={[styles.savingsText, { color: colors.success }]}>{savings}</Text>
                  </View>
                )}

                <Divider style={{ marginVertical: spacing.md }} />

                {/* Feature list */}
                <View style={styles.featureList}>
                  {plan.features.map((feature, index) => (
                    <View key={index} style={styles.featureItem}>
                      <Icon name="check-circle" size={18} color={planColor} />
                      <Text style={[styles.featureText, { color: theme.custom.colors.textPrimary }]}>
                        {feature}
                      </Text>
                    </View>
                  ))}
                </View>

                <Button
                  mode={isCurrent ? 'outlined' : 'contained'}
                  onPress={() => handleSubscribe(plan)}
                  disabled={isCurrent || checkoutMutation.isPending}
                  loading={checkoutMutation.isPending}
                  style={[
                    styles.subscribeButton,
                    !isCurrent && { backgroundColor: planColor },
                  ]}
                  textColor={isCurrent ? planColor : colors.white}
                >
                  {getButtonLabel(plan)}
                </Button>
              </Surface>
            );
          })
        ) : (
          <View style={styles.emptyState}>
            <Icon name="tag-off-outline" size={64} color={theme.custom.colors.textMuted} />
            <Text style={[styles.emptyTitle, { color: theme.custom.colors.textPrimary }]}>
              No Plans Available
            </Text>
            <Text style={[styles.emptyText, { color: theme.custom.colors.textSecondary }]}>
              Subscription plans are currently unavailable. Please check back later.
            </Text>
          </View>
        )}
      </ScrollView>

      {/* Cancel Confirmation Dialog */}
      <Portal>
        <Dialog visible={cancelDialogVisible} onDismiss={() => setCancelDialogVisible(false)}>
          <Dialog.Icon icon="alert" />
          <Dialog.Title style={styles.dialogTitle}>Cancel Subscription?</Dialog.Title>
          <Dialog.Content>
            <Text style={[typography.body, { color: theme.custom.colors.textSecondary }]}>
              Are you sure you want to cancel your subscription? You will continue to have access to
              your current plan features until the end of your billing period.
            </Text>
          </Dialog.Content>
          <Dialog.Actions>
            <Button onPress={() => setCancelDialogVisible(false)}>Keep Plan</Button>
            <Button
              textColor={colors.error}
              onPress={() => cancelMutation.mutate()}
              loading={cancelMutation.isPending}
            >
              Cancel Subscription
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
  currentPlanCard: {
    borderRadius: borderRadius.lg,
    padding: spacing.md,
    marginBottom: spacing.lg,
  },
  currentPlanHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  currentPlanInfo: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  currentPlanText: {
    marginLeft: spacing.sm,
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
  },
  statusChip: {
    height: 24,
  },
  currentPlanDetails: {
    gap: spacing.sm,
  },
  detailRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  cancelNotice: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: spacing.sm,
    borderRadius: borderRadius.sm,
    gap: spacing.sm,
  },
  cancelNoticeText: {
    ...typography.bodySmall,
    flex: 1,
  },
  currentPlanActions: {
    marginTop: spacing.md,
  },
  resumeButton: {
    borderRadius: borderRadius.sm,
  },
  cancelButton: {
    borderColor: colors.error,
    borderRadius: borderRadius.sm,
  },
  billingToggleContainer: {
    flexDirection: 'row',
    backgroundColor: colors.gray[200],
    borderRadius: borderRadius.xl,
    padding: 4,
    marginBottom: spacing.lg,
  },
  billingOption: {
    flex: 1,
    paddingVertical: spacing.sm,
    borderRadius: borderRadius.xl,
    alignItems: 'center',
    justifyContent: 'center',
  },
  billingOptionText: {
    fontSize: 14,
    fontWeight: '600',
  },
  saveBadge: {
    backgroundColor: colors.success,
    borderRadius: borderRadius.full,
    paddingHorizontal: 8,
    paddingVertical: 2,
    marginTop: 4,
  },
  saveBadgeText: {
    color: colors.white,
    fontSize: 10,
    fontWeight: '700',
  },
  planCard: {
    borderRadius: borderRadius.lg,
    padding: spacing.md,
    marginBottom: spacing.md,
    overflow: 'hidden',
  },
  currentBadge: {
    position: 'absolute',
    top: 0,
    right: 0,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.xs,
    borderBottomLeftRadius: borderRadius.sm,
  },
  currentBadgeText: {
    color: colors.white,
    fontSize: 11,
    fontWeight: '700',
  },
  planHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    marginBottom: spacing.sm,
  },
  planName: {
    ...typography.h3,
  },
  priceContainer: {
    flexDirection: 'row',
    alignItems: 'baseline',
    marginBottom: spacing.xs,
  },
  priceAmount: {
    fontSize: 36,
    fontWeight: '700',
  },
  pricePeriod: {
    ...typography.body,
    marginLeft: 4,
  },
  savingsTag: {
    alignSelf: 'flex-start',
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.xs,
    borderRadius: borderRadius.full,
    marginBottom: spacing.xs,
  },
  savingsText: {
    fontSize: 12,
    fontWeight: '600',
  },
  featureList: {
    gap: spacing.sm,
    marginBottom: spacing.md,
  },
  featureItem: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
  },
  featureText: {
    ...typography.bodySmall,
    flex: 1,
  },
  subscribeButton: {
    borderRadius: borderRadius.sm,
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
  dialogTitle: {
    textAlign: 'center',
  },
});
