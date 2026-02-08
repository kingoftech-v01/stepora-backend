import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../core/theme/app_theme.dart';
import '../../services/api_service.dart';

class CirclesScreen extends ConsumerStatefulWidget {
  const CirclesScreen({super.key});

  @override
  ConsumerState<CirclesScreen> createState() => _CirclesScreenState();
}

class _CirclesScreenState extends ConsumerState<CirclesScreen> {
  List<Map<String, dynamic>> _circles = [];
  bool _isLoading = true;

  @override
  void initState() {
    super.initState();
    _loadCircles();
  }

  Future<void> _loadCircles() async {
    setState(() => _isLoading = true);
    try {
      final api = ref.read(apiServiceProvider);
      final response = await api.get('/circles/');
      final results = response.data['results'] as List? ?? response.data as List? ?? [];
      setState(() {
        _circles = List<Map<String, dynamic>>.from(results);
        _isLoading = false;
      });
    } catch (_) {
      setState(() => _isLoading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Dream Circles')),
      body: RefreshIndicator(
        onRefresh: _loadCircles,
        child: _isLoading
            ? const Center(child: CircularProgressIndicator())
            : _circles.isEmpty
                ? Center(
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Icon(Icons.group_outlined, size: 64, color: Colors.grey[300]),
                        const SizedBox(height: 16),
                        Text('No circles yet', style: TextStyle(color: Colors.grey[500], fontSize: 16)),
                      ],
                    ),
                  )
                : ListView.builder(
                    padding: const EdgeInsets.all(16),
                    itemCount: _circles.length,
                    itemBuilder: (context, index) {
                      final circle = _circles[index];
                      return Card(
                        margin: const EdgeInsets.only(bottom: 12),
                        child: ListTile(
                          leading: CircleAvatar(
                            backgroundColor: AppTheme.primaryPurple,
                            child: Text(
                              (circle['name'] ?? 'C')[0].toUpperCase(),
                              style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold),
                            ),
                          ),
                          title: Text(circle['name'] ?? '', style: const TextStyle(fontWeight: FontWeight.w600)),
                          subtitle: Text('${circle['member_count'] ?? 0} members'),
                          trailing: const Icon(Icons.chevron_right),
                          onTap: () => context.push('/circles/${circle['id']}'),
                        ),
                      );
                    },
                  ),
      ),
      floatingActionButton: FloatingActionButton(
        onPressed: () { /* Create circle dialog */ },
        backgroundColor: AppTheme.primaryPurple,
        foregroundColor: Colors.white,
        child: const Icon(Icons.add),
      ),
    );
  }
}
