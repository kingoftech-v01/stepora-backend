import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../core/theme/app_theme.dart';
import '../../providers/auth_provider.dart';
import '../../services/api_service.dart';

class SubscriptionScreen extends ConsumerStatefulWidget {
  const SubscriptionScreen({super.key});

  @override
  ConsumerState<SubscriptionScreen> createState() => _SubscriptionScreenState();
}

class _SubscriptionScreenState extends ConsumerState<SubscriptionScreen> {
  List<Map<String, dynamic>> _plans = [];
  bool _isLoading = true;

  @override
  void initState() {
    super.initState();
    _loadPlans();
  }

  Future<void> _loadPlans() async {
    try {
      final api = ref.read(apiServiceProvider);
      final response = await api.get('/subscriptions/plans/');
      final results = response.data['results'] as List? ?? response.data as List? ?? [];
      setState(() {
        _plans = List<Map<String, dynamic>>.from(results);
        _isLoading = false;
      });
    } catch (_) {
      setState(() => _isLoading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final user = ref.watch(authProvider).user;
    final currentPlan = user?.subscription ?? 'free';

    return Scaffold(
      appBar: AppBar(title: const Text('Subscription')),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : ListView(
              padding: const EdgeInsets.all(16),
              children: [
                Text('Choose Your Plan', style: Theme.of(context).textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.bold), textAlign: TextAlign.center),
                const SizedBox(height: 8),
                Text('Unlock all features to achieve your dreams faster', style: TextStyle(color: Colors.grey[600]), textAlign: TextAlign.center),
                const SizedBox(height: 24),
                ..._plans.map((plan) {
                  final isCurrentPlan = plan['slug'] == currentPlan;
                  final isFree = plan['is_free'] == true;
                  return Card(
                    margin: const EdgeInsets.only(bottom: 16),
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(16),
                      side: isCurrentPlan ? const BorderSide(color: AppTheme.primaryPurple, width: 2) : BorderSide.none,
                    ),
                    child: Padding(
                      padding: const EdgeInsets.all(20),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Row(
                            children: [
                              Text(plan['name'] ?? '', style: Theme.of(context).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.bold)),
                              const Spacer(),
                              if (isCurrentPlan) const Chip(label: Text('Current'), backgroundColor: Color(0xFFE8DEF8)),
                            ],
                          ),
                          const SizedBox(height: 4),
                          Text(
                            isFree ? 'Free' : '\$${plan['price'] ?? '0'}/month',
                            style: TextStyle(fontSize: 24, fontWeight: FontWeight.bold, color: AppTheme.primaryPurple),
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
                                    final response = await api.post('/subscriptions/checkout/', data: {'plan': plan['slug']});
                                    final url = response.data['checkout_url'];
                                    if (url != null) {
                                      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Redirect to: $url')));
                                    }
                                  } catch (e) {
                                    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Error: $e')));
                                  }
                                },
                                style: FilledButton.styleFrom(backgroundColor: AppTheme.primaryPurple, padding: const EdgeInsets.symmetric(vertical: 14)),
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
    );
  }
}
