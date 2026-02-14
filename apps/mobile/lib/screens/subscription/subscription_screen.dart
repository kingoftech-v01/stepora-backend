import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:url_launcher/url_launcher.dart';
import '../../core/theme/app_theme.dart';
import '../../config/api_constants.dart';
import '../../providers/auth_provider.dart';
import '../../services/api_service.dart';
import '../../widgets/gradient_background.dart';
import '../../widgets/glass_container.dart';
import '../../widgets/glass_app_bar.dart';
import '../../widgets/glass_button.dart';
import '../../widgets/animated_list_item.dart';
import '../../widgets/loading_shimmer.dart';

class SubscriptionScreen extends ConsumerStatefulWidget {
  const SubscriptionScreen({super.key});

  @override
  ConsumerState<SubscriptionScreen> createState() => _SubscriptionScreenState();
}

class _SubscriptionScreenState extends ConsumerState<SubscriptionScreen> {
  List<Map<String, dynamic>> _plans = [];
  Map<String, dynamic>? _currentSubscription;
  bool _isLoading = true;
  bool _isSyncing = false;

  @override
  void initState() {
    super.initState();
    _loadData();
  }

  Future<void> _loadData() async {
    try {
      final api = ref.read(apiServiceProvider);
      final plansResponse = await api.get(ApiConstants.subscriptionPlans);
      final results = plansResponse.data['results'] as List? ?? plansResponse.data as List? ?? [];
      try {
        final currentResponse = await api.get(ApiConstants.subscriptionCurrent);
        _currentSubscription = currentResponse.data;
      } catch (_) {}
      setState(() {
        _plans = List<Map<String, dynamic>>.from(results);
        _isLoading = false;
      });
    } catch (_) {
      setState(() => _isLoading = false);
    }
  }

  Future<void> _syncSubscription() async {
    setState(() => _isSyncing = true);
    try {
      final api = ref.read(apiServiceProvider);
      await api.post(ApiConstants.subscriptionSync);
      await _loadData();
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Subscription synced')));
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Sync failed: $e')));
      }
    } finally {
      setState(() => _isSyncing = false);
    }
  }

  Future<void> _reactivateSubscription() async {
    try {
      final api = ref.read(apiServiceProvider);
      await api.post(ApiConstants.subscriptionReactivate);
      await _loadData();
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Subscription reactivated!')));
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Error: $e')));
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final user = ref.watch(authProvider).user;
    final currentPlan = user?.subscription ?? 'free';
    final cancelAtPeriodEnd = _currentSubscription?['cancel_at_period_end'] == true;
    final periodEnd = _currentSubscription?['current_period_end']?.toString();
    final isDark = Theme.of(context).brightness == Brightness.dark;

    return GradientBackground(
      colors: isDark ? AppTheme.gradientStore : AppTheme.gradientStoreLight,
      child: Scaffold(
        backgroundColor: Colors.transparent,
        extendBodyBehindAppBar: true,
        appBar: GlassAppBar(
          title: 'Subscription',
          actions: [
            IconButton(
              onPressed: _isSyncing ? null : _syncSubscription,
              icon: _isSyncing
                  ? SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2, color: isDark ? Colors.white54 : Colors.grey))
                  : Icon(Icons.sync, color: isDark ? Colors.white70 : const Color(0xFF1E1B4B)),
              tooltip: 'Sync subscription',
            ),
          ],
        ),
        body: _isLoading
            ? const Center(child: LoadingShimmer())
            : RefreshIndicator(
                onRefresh: _loadData,
                child: ListView(
                  padding: EdgeInsets.fromLTRB(16, MediaQuery.of(context).padding.top + kToolbarHeight + 8, 16, 32),
                  children: [
                    Text(
                      'Choose Your Plan',
                      style: TextStyle(fontSize: 22, fontWeight: FontWeight.bold, color: isDark ? Colors.white : const Color(0xFF1E1B4B)),
                      textAlign: TextAlign.center,
                    ).animate().fadeIn(duration: 400.ms),
                    const SizedBox(height: 6),
                    Text(
                      'Unlock all features to achieve your dreams faster',
                      style: TextStyle(color: isDark ? Colors.white54 : Colors.grey[600]),
                      textAlign: TextAlign.center,
                    ).animate().fadeIn(duration: 400.ms, delay: 100.ms),
                    const SizedBox(height: 20),

                    // Current subscription card
                    if (_currentSubscription != null && currentPlan != 'free') ...[
                      GlassContainer(
                        padding: const EdgeInsets.all(18),
                        opacity: isDark ? 0.15 : 0.3,
                        border: Border.all(color: AppTheme.primaryPurple.withValues(alpha: 0.4)),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Row(
                              children: [
                                Text('Current Subscription', style: TextStyle(fontWeight: FontWeight.bold, color: isDark ? Colors.white : const Color(0xFF1E1B4B))),
                                const Spacer(),
                                Container(
                                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                                  decoration: BoxDecoration(
                                    color: cancelAtPeriodEnd
                                        ? Colors.orange.withValues(alpha: 0.15)
                                        : AppTheme.success.withValues(alpha: 0.15),
                                    borderRadius: BorderRadius.circular(12),
                                    border: Border.all(
                                      color: cancelAtPeriodEnd
                                          ? Colors.orange.withValues(alpha: 0.3)
                                          : AppTheme.success.withValues(alpha: 0.3),
                                    ),
                                  ),
                                  child: Text(
                                    cancelAtPeriodEnd ? 'Cancelling' : 'Active',
                                    style: TextStyle(
                                      fontSize: 11,
                                      fontWeight: FontWeight.w600,
                                      color: cancelAtPeriodEnd ? Colors.orange : AppTheme.success,
                                    ),
                                  ),
                                ),
                              ],
                            ),
                            const SizedBox(height: 10),
                            Text('Plan: ${_currentSubscription!['plan_name'] ?? currentPlan}',
                              style: TextStyle(color: isDark ? Colors.white70 : Colors.grey[700])),
                            if (periodEnd != null)
                              Text(
                                cancelAtPeriodEnd ? 'Cancels on: ${periodEnd.substring(0, 10)}' : 'Renews: ${periodEnd.substring(0, 10)}',
                                style: TextStyle(color: isDark ? Colors.white54 : Colors.grey[600], fontSize: 13),
                              ),
                            const SizedBox(height: 14),
                            Wrap(
                              spacing: 8,
                              children: [
                                GlassButton(
                                  label: 'Manage Billing',
                                  style: GlassButtonStyle.secondary,
                                  onPressed: () async {
                                    try {
                                      final api = ref.read(apiServiceProvider);
                                      final response = await api.post(ApiConstants.subscriptionPortal);
                                      final url = response.data['url'];
                                      if (url != null) {
                                        await launchUrl(Uri.parse(url), mode: LaunchMode.externalApplication);
                                      }
                                    } catch (e) {
                                      if (mounted) {
                                        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Error: $e')));
                                      }
                                    }
                                  },
                                ),
                                if (cancelAtPeriodEnd)
                                  GlassButton(label: 'Reactivate', onPressed: _reactivateSubscription)
                                else
                                  GlassButton(
                                    label: 'Cancel',
                                    style: GlassButtonStyle.danger,
                                    onPressed: () => _showCancelDialog(isDark),
                                  ),
                              ],
                            ),
                          ],
                        ),
                      ).animate().fadeIn(duration: 500.ms, delay: 200.ms),
                      const SizedBox(height: 16),
                    ],

                    // Plan cards
                    ..._plans.asMap().entries.map((entry) {
                      final index = entry.key;
                      final plan = entry.value;
                      final isCurrentPlan = plan['slug'] == currentPlan;
                      final isFree = plan['is_free'] == true;
                      return AnimatedListItem(
                        index: index,
                        child: Padding(
                          padding: const EdgeInsets.only(bottom: 14),
                          child: GlassContainer(
                            padding: const EdgeInsets.all(20),
                            opacity: isDark ? 0.12 : 0.25,
                            border: isCurrentPlan
                                ? Border.all(color: AppTheme.primaryPurple.withValues(alpha: 0.6), width: 2)
                                : null,
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Row(
                                  children: [
                                    Text(
                                      plan['name'] ?? '',
                                      style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: isDark ? Colors.white : const Color(0xFF1E1B4B)),
                                    ),
                                    const Spacer(),
                                    if (isCurrentPlan)
                                      Container(
                                        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                                        decoration: BoxDecoration(
                                          color: AppTheme.primaryPurple.withValues(alpha: 0.15),
                                          borderRadius: BorderRadius.circular(12),
                                          border: Border.all(color: AppTheme.primaryPurple.withValues(alpha: 0.3)),
                                        ),
                                        child: Text('Current', style: TextStyle(color: AppTheme.primaryPurple, fontSize: 11, fontWeight: FontWeight.w600)),
                                      ),
                                  ],
                                ),
                                const SizedBox(height: 6),
                                Text(
                                  isFree ? 'Free' : '\$${plan['price'] ?? '0'}/month',
                                  style: TextStyle(fontSize: 24, fontWeight: FontWeight.bold, color: AppTheme.primaryPurple),
                                ),
                                const SizedBox(height: 14),
                                ...((plan['features'] as List?) ?? []).map((f) => Padding(
                                  padding: const EdgeInsets.only(bottom: 8),
                                  child: Row(
                                    children: [
                                      Container(
                                        padding: const EdgeInsets.all(2),
                                        decoration: BoxDecoration(color: AppTheme.success.withValues(alpha: 0.15), shape: BoxShape.circle),
                                        child: Icon(Icons.check, color: AppTheme.success, size: 14),
                                      ),
                                      const SizedBox(width: 10),
                                      Expanded(child: Text(f.toString(), style: TextStyle(color: isDark ? Colors.white70 : Colors.grey[700]))),
                                    ],
                                  ),
                                )),
                                if (!isCurrentPlan && !isFree) ...[
                                  const SizedBox(height: 12),
                                  SizedBox(
                                    width: double.infinity,
                                    child: GlassButton(
                                      label: 'Upgrade',
                                      icon: Icons.rocket_launch,
                                      onPressed: () async {
                                        try {
                                          final api = ref.read(apiServiceProvider);
                                          final response = await api.post(ApiConstants.subscriptionCheckout, data: {'plan': plan['slug']});
                                          final url = response.data['checkout_url'];
                                          if (url != null) {
                                            await launchUrl(Uri.parse(url), mode: LaunchMode.externalApplication);
                                          }
                                        } catch (e) {
                                          if (mounted) {
                                            ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Error: $e')));
                                          }
                                        }
                                      },
                                    ),
                                  ),
                                ],
                              ],
                            ),
                          ),
                        ),
                      );
                    }),
                  ],
                ),
              ),
      ),
    );
  }

  void _showCancelDialog(bool isDark) {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: isDark ? const Color(0xFF1E1B4B) : Colors.white,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
        title: Text('Cancel Subscription?', style: TextStyle(color: isDark ? Colors.white : const Color(0xFF1E1B4B))),
        content: Text(
          'You will lose premium features at the end of your billing period.',
          style: TextStyle(color: isDark ? Colors.white70 : Colors.grey[700]),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: Text('Keep', style: TextStyle(color: AppTheme.primaryPurple)),
          ),
          TextButton(
            onPressed: () async {
              Navigator.pop(ctx);
              try {
                final api = ref.read(apiServiceProvider);
                await api.post(ApiConstants.subscriptionCancel);
                if (mounted) {
                  ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Subscription cancelled')));
                  _loadData();
                }
              } catch (e) {
                if (mounted) {
                  ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Error: $e')));
                }
              }
            },
            child: Text('Cancel', style: TextStyle(color: Colors.red.shade400)),
          ),
        ],
      ),
    );
  }
}
