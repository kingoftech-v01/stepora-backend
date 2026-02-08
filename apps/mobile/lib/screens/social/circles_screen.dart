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

  void _showCreateCircleDialog() {
    final nameController = TextEditingController();
    final descController = TextEditingController();
    String selectedCategory = 'personal_growth';
    bool isPublic = true;

    const categories = [
      'career', 'health', 'fitness', 'education', 'finance',
      'creativity', 'relationships', 'personal_growth', 'hobbies', 'other',
    ];

    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setSheetState) => Padding(
          padding: EdgeInsets.fromLTRB(16, 16, 16, MediaQuery.of(ctx).viewInsets.bottom + 16),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text('Create Circle', style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold)),
              const SizedBox(height: 16),
              TextField(
                controller: nameController,
                decoration: const InputDecoration(labelText: 'Circle Name', border: OutlineInputBorder()),
              ),
              const SizedBox(height: 12),
              TextField(
                controller: descController,
                decoration: const InputDecoration(labelText: 'Description', border: OutlineInputBorder()),
                maxLines: 3,
              ),
              const SizedBox(height: 12),
              DropdownButtonFormField<String>(
                initialValue: selectedCategory,
                decoration: const InputDecoration(labelText: 'Category', border: OutlineInputBorder()),
                items: categories.map((c) => DropdownMenuItem(
                  value: c,
                  child: Text(c.replaceAll('_', ' ').toUpperCase()),
                )).toList(),
                onChanged: (v) => setSheetState(() => selectedCategory = v!),
              ),
              const SizedBox(height: 12),
              SwitchListTile(
                title: const Text('Public Circle'),
                subtitle: const Text('Anyone can join'),
                value: isPublic,
                onChanged: (v) => setSheetState(() => isPublic = v),
              ),
              const SizedBox(height: 16),
              SizedBox(
                width: double.infinity,
                child: FilledButton(
                  onPressed: () async {
                    if (nameController.text.trim().isEmpty) return;
                    try {
                      final api = ref.read(apiServiceProvider);
                      await api.post('/circles/', data: {
                        'name': nameController.text.trim(),
                        'description': descController.text.trim(),
                        'category': selectedCategory,
                        'is_public': isPublic,
                      });
                      if (ctx.mounted) Navigator.pop(ctx);
                      _loadCircles();
                    } catch (e) {
                      if (mounted) {
                        ScaffoldMessenger.of(context).showSnackBar(
                          SnackBar(content: Text('Error: $e')),
                        );
                      }
                    }
                  },
                  style: FilledButton.styleFrom(backgroundColor: AppTheme.primaryPurple),
                  child: const Text('Create'),
                ),
              ),
            ],
          ),
        ),
      ),
    );
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
                        const SizedBox(height: 16),
                        FilledButton.icon(
                          onPressed: _showCreateCircleDialog,
                          icon: const Icon(Icons.add),
                          label: const Text('Create Circle'),
                          style: FilledButton.styleFrom(backgroundColor: AppTheme.primaryPurple),
                        ),
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
                          subtitle: Text('${circle['member_count'] ?? circle['memberCount'] ?? 0} members'),
                          trailing: const Icon(Icons.chevron_right),
                          onTap: () => context.push('/circles/${circle['id']}'),
                        ),
                      );
                    },
                  ),
      ),
      floatingActionButton: FloatingActionButton(
        onPressed: _showCreateCircleDialog,
        backgroundColor: AppTheme.primaryPurple,
        foregroundColor: Colors.white,
        child: const Icon(Icons.add),
      ),
    );
  }
}
