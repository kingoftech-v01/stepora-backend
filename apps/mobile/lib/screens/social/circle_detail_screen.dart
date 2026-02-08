import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../core/theme/app_theme.dart';
import '../../services/api_service.dart';

class CircleDetailScreen extends ConsumerStatefulWidget {
  final String circleId;
  const CircleDetailScreen({super.key, required this.circleId});

  @override
  ConsumerState<CircleDetailScreen> createState() => _CircleDetailScreenState();
}

class _CircleDetailScreenState extends ConsumerState<CircleDetailScreen> {
  Map<String, dynamic>? _circle;
  List<Map<String, dynamic>> _members = [];
  bool _isLoading = true;

  @override
  void initState() {
    super.initState();
    _loadCircle();
  }

  Future<void> _loadCircle() async {
    try {
      final api = ref.read(apiServiceProvider);
      final response = await api.get('/circles/${widget.circleId}/');
      setState(() {
        _circle = response.data;
        _members = List<Map<String, dynamic>>.from(response.data['members'] ?? []);
        _isLoading = false;
      });
    } catch (_) {
      setState(() => _isLoading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_isLoading) {
      return Scaffold(appBar: AppBar(), body: const Center(child: CircularProgressIndicator()));
    }

    return Scaffold(
      appBar: AppBar(title: Text(_circle?['name'] ?? 'Circle')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(_circle?['name'] ?? '', style: Theme.of(context).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.bold)),
                  if (_circle?['description'] != null) ...[
                    const SizedBox(height: 8),
                    Text(_circle!['description'], style: TextStyle(color: Colors.grey[600])),
                  ],
                  const SizedBox(height: 12),
                  Chip(
                    label: Text('${_circle?['category'] ?? 'General'}'),
                    backgroundColor: AppTheme.primaryPurple.withValues(alpha: 0.1),
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 16),
          Text('Members (${_members.length})', style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.bold)),
          const SizedBox(height: 8),
          ..._members.map((member) => Card(
            margin: const EdgeInsets.only(bottom: 8),
            child: ListTile(
              leading: CircleAvatar(
                backgroundColor: AppTheme.primaryPurple.withValues(alpha: 0.1),
                child: Text(
                  (member['display_name'] ?? 'U')[0].toUpperCase(),
                  style: TextStyle(color: AppTheme.primaryPurple),
                ),
              ),
              title: Text(member['display_name'] ?? member['email'] ?? ''),
              subtitle: Text('Level ${member['level'] ?? 1}'),
              trailing: Text('${member['xp'] ?? 0} XP', style: TextStyle(color: AppTheme.accent, fontWeight: FontWeight.bold)),
            ),
          )),
        ],
      ),
    );
  }
}
