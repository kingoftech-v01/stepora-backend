import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:url_launcher/url_launcher.dart';
import '../../core/theme/app_theme.dart';
import '../../config/api_constants.dart';
import '../../providers/auth_provider.dart';
import '../../services/api_service.dart';

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
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Subscription synced')),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Sync failed: $e')),
        );
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
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Subscription reactivated!')),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error: $e')),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final user = ref.watch(authProvider).user;
    final currentPlan = user?.subscription ?? 'free';
    final cancelAtPeriodEnd = _currentSubscription?['cancel_at_period_end'] == true;
    final periodEnd = _currentSubscription?['current_period_end']?.toString();

    return Scaffold(
      appBar: AppBar(
        title: const Text('Subscription'),
        actions: [
          IconButton(
            onPressed: _isSyncing ? null : _syncSubscription,
            icon: _isSyncing
                ? const SizedBox(
                    width: 18, height: 18,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : const Icon(Icons.sync),
            tooltip: 'Sync subscription',
          ),
        ],
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : RefreshIndicator(
              onRefresh: _loadData,
              child: ListView(
                padding: const EdgeInsets.all(16),
                children: [
                  Text(
                    'Choose Your Plan',
                    style: Theme.of(context).textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.bold),
                    textAlign: TextAlign.center,
                  ),
                  const SizedBox(height: 8),
                  Text(
                    'Unlock all features to achieve your dreams faster',
                    style: TextStyle(color: Colors.grey[600]),
                    textAlign: TextAlign.center,
                  ),
                  const SizedBox(height: 24),

                  if (_currentSubscription != null && currentPlan != 'free') ...[
                    Card(
                      color: AppTheme.primaryPurple.withValues(alpha: 0.05),
                      child: Padding(
                        padding: const EdgeInsets.all(16),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Row(
                              children: [
                                const Text('Current Subscription', style: TextStyle(fontWeight: FontWeight.bold)),
                                const Spacer(),
                                Container(
                                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                                  decoration: BoxDecoration(
                                    color: cancelAtPeriodEnd ? Colors.orange.shade100 : Colors.green.shade100,
                                    borderRadius: BorderRadius.circular(12),
                                  ),
                                  child: Text(
                                    cancelAtPeriodEnd ? 'Cancelling' : 'Active',
                                    style: TextStyle(
                                      fontSize: 12,
                                      fontWeight: FontWeight.w600,
                                      color: cancelAtPeriodEnd ? Colors.orange.shade800 : Colors.green.shade800,
                                    ),
                                  ),
                                ),
                              ],
                            ),
                            const SizedBox(height: 8),
                            Text('Plan: ${_currentSubscription!['plan_name'] ?? currentPlan}'),
                            if (periodEnd != null)
                              Text(cancelAtPeriodEnd
                                  ? 'Cancels on: ${periodEnd.substring(0, 10)}'
                                  : 'Renews: ${periodEnd.substring(0, 10)}'),
                            const SizedBox(height: 12),
                            Wrap(
                              spacing: 8,
                              children: [
                                OutlinedButton(
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
                                        ScaffoldMessenger.of(context).showSnackBar(
                                          SnackBar(content: Text('Error: $e')),
                                        );
                                      }
                                    }
                                  },
                                  child: const Text('Manage Billing'),
                                ),
                                if (cancelAtPeriodEnd)
                                  FilledButton(
                                    onPressed: _reactivateSubscription,
                                    style: FilledButton.styleFrom(backgroundColor: Colors.green),
                                    child: const Text('Reactivate'),
                                  )
                                else
                                  OutlinedButton(
                                    onPressed: () async {
                                      final confirmed = await showDialog<bool>(
                                        context: context,
                                        builder: (ctx) => AlertDialog(
                                          title: const Text('Cancel Subscription?'),
                                          content: const Text(
                                            'You will lose premium features at the end of your billing period.',
                                          ),
                                          actions: [
                                            TextButton(
                                              onPressed: () => Navigator.pop(ctx, false),
                                              child: const Text('Keep'),
                                            ),
                                            TextButton(
                                              onPressed: () => Navigator.pop(ctx, true),
                                              child: const Text('Cancel', style: TextStyle(color: Colors.red)),
                                            ),
                                          ],
                                        ),
                                      );
                                      if (confirmed != true) return;
                                      try {
                                        final api = ref.read(apiServiceProvider);
                                        await api.post(ApiConstants.subscriptionCancel);
                                        if (mounted) {
                                          ScaffoldMessenger.of(context).showSnackBar(
                                            const SnackBar(content: Text('Subscription cancelled')),
                                          );
                                          _loadData();
                                        }
                                      } catch (e) {
                                        if (mounted) {
                                          ScaffoldMessenger.of(context).showSnackBar(
                                            SnackBar(content: Text('Error: $e')),
                                          );
                                        }
                                      }
                                    },
                                    style: OutlinedButton.styleFrom(foregroundColor: Colors.red),
                                    child: const Text('Cancel'),
                                  ),
                              ],
                            ),
                          ],
                        ),
                      ),
                    ),
                    const SizedBox(height: 16),
                  ],

                  ..._plans.map((plan) {
                    final isCurrentPlan = plan['slug'] == currentPlan;
                    final isFree = plan['is_free'] == true;
                    return Card(
                      margin: const EdgeInsets.only(bottom: 16),
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(16),
                        side: isCurrentPlan
                            ? const BorderSide(color: AppTheme.primaryPurple, width: 2)
                            : BorderSide.none,
                      ),
                      child: Padding(
                        padding: const EdgeInsets.all(20),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Row(
                              children: [
                                Text(
                                  plan['name'] ?? '',
                                  style: Theme.of(context).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.bold),
                                ),
                                const Spacer(),
                                if (isCurrentPlan)
                                  const Chip(label: Text('Current'), backgroundColor: Color(0xFFE8DEF8)),
                              ],
                            ),
                            const SizedBox(height: 4),
                            Text(
                              isFree ? 'Free' : '\$${plan['price'] ?? '0'}/month',
                              style: TextStyle(
                                fontSize: 24,
                                fontWeight: FontWeight.bold,
                                color: AppTheme.primaryPurple,
                              ),
                            ),
                            const SizedBox(height: 12),
                            ...((plan['features'] as List?) ?? []).map((f) => Padding(
                              padding: const EdgeInsets.only(bottom: 6),
                              child: Row(
                                children: [
                                  Icon(Icons.check_circle, color: AppTheme.success, size: 18),
                                  const SizedBox(width: 8),
                                  Expanded(child: Text(f.toString())),
                                ],
                              ),
                            )),
                            const SizedBox(height: 16),
                            if (!isCurrentPlan && !isFree)
                              SizedBox(
                                width: double.infinity,
                                child: FilledButton(
                                  onPressed: () async {
                                    try {
                                      final api = ref.read(apiServiceProvider);
                                      final response = await api.post(
                                        ApiConstants.subscriptionCheckout,
                                        data: {'plan': plan['slug']},
                                      );
                                      final url = response.data['checkout_url'];
                                      if (url != null) {
                                        await launchUrl(
                                          Uri.parse(url),
                                          mode: LaunchMode.externalApplication,
                                        );
                                      }
                                    } catch (e) {
                                      if (mounted) {
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
                                  child: const Text('Upgrade'),
                                ),
                              ),
                          ],
                        ),
                      ),
                    );
                  }),
                ],
              ),
            ),
    );
  }
}
