import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../core/theme/app_theme.dart';
import '../../config/api_constants.dart';
import '../../services/api_service.dart';

class DreamTemplatesScreen extends ConsumerStatefulWidget {
  const DreamTemplatesScreen({super.key});

  @override
  ConsumerState<DreamTemplatesScreen> createState() => _DreamTemplatesScreenState();
}

class _DreamTemplatesScreenState extends ConsumerState<DreamTemplatesScreen> {
  List<Map<String, dynamic>> _templates = [];
  bool _isLoading = true;

  @override
  void initState() {
    super.initState();
    _loadTemplates();
  }

  Future<void> _loadTemplates() async {
    setState(() => _isLoading = true);
    try {
      final api = ref.read(apiServiceProvider);
      final response = await api.get(ApiConstants.dreamTemplates);
      final results = response.data['results'] as List? ?? response.data as List? ?? [];
      setState(() {
        _templates = List<Map<String, dynamic>>.from(results);
        _isLoading = false;
      });
    } catch (_) {
      setState(() => _isLoading = false);
    }
  }

  Future<void> _useTemplate(Map<String, dynamic> template) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text(template['title'] ?? 'Use Template'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(template['description'] ?? ''),
            if (template['template_goals'] != null) ...[
              const SizedBox(height: 12),
              Text('Goals:', style: const TextStyle(fontWeight: FontWeight.bold)),
              const SizedBox(height: 4),
              ...((template['template_goals'] as List?) ?? []).map((g) => Padding(
                padding: const EdgeInsets.only(left: 8, bottom: 2),
                child: Text('- ${g['title'] ?? g}'),
              )),
            ],
          ],
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancel')),
          FilledButton(
            onPressed: () => Navigator.pop(ctx, true),
            style: FilledButton.styleFrom(backgroundColor: AppTheme.primaryPurple),
            child: const Text('Create Dream'),
          ),
        ],
      ),
    );

    if (confirmed != true) return;

    try {
      final api = ref.read(apiServiceProvider);
      final response = await api.post('${ApiConstants.dreamTemplates}${template['id']}/use/');
      final newDreamId = response.data['id']?.toString();
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Dream created from template!')),
        );
        if (newDreamId != null) {
          context.go('/dreams/$newDreamId');
        } else {
          context.pop();
        }
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
    return Scaffold(
      appBar: AppBar(title: const Text('Dream Templates')),
      body: RefreshIndicator(
        onRefresh: _loadTemplates,
        child: _isLoading
            ? const Center(child: CircularProgressIndicator())
            : _templates.isEmpty
                ? ListView(
                    children: [
                      const SizedBox(height: 100),
                      Center(
                        child: Column(
                          children: [
                            Icon(Icons.library_books_outlined, size: 64, color: Colors.grey[300]),
                            const SizedBox(height: 16),
                            Text('No templates available', style: TextStyle(color: Colors.grey[500])),
                          ],
                        ),
                      ),
                    ],
                  )
                : ListView.builder(
                    padding: const EdgeInsets.all(16),
                    itemCount: _templates.length,
                    itemBuilder: (context, index) {
                      final template = _templates[index];
                      final isFeatured = template['is_featured'] == true;
                      return Card(
                        margin: const EdgeInsets.only(bottom: 12),
                        shape: isFeatured
                            ? RoundedRectangleBorder(
                                borderRadius: BorderRadius.circular(12),
                                side: BorderSide(color: AppTheme.accent, width: 2),
                              )
                            : null,
                        child: InkWell(
                          onTap: () => _useTemplate(template),
                          borderRadius: BorderRadius.circular(12),
                          child: Padding(
                            padding: const EdgeInsets.all(16),
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Row(
                                  children: [
                                    Expanded(
                                      child: Text(
                                        template['title'] ?? '',
                                        style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 16),
                                      ),
                                    ),
                                    if (isFeatured)
                                      Chip(
                                        label: const Text('Featured'),
                                        backgroundColor: AppTheme.accent.withValues(alpha: 0.1),
                                        labelStyle: TextStyle(color: AppTheme.accent, fontSize: 11),
                                      ),
                                  ],
                                ),
                                if (template['description'] != null) ...[
                                  const SizedBox(height: 8),
                                  Text(
                                    template['description'],
                                    style: TextStyle(color: Colors.grey[600]),
                                    maxLines: 2,
                                    overflow: TextOverflow.ellipsis,
                                  ),
                                ],
                                const SizedBox(height: 8),
                                Row(
                                  children: [
                                    if (template['category'] != null)
                                      Chip(
                                        label: Text(template['category']),
                                        backgroundColor: AppTheme.primaryPurple.withValues(alpha: 0.1),
                                        labelStyle: TextStyle(color: AppTheme.primaryPurple, fontSize: 12),
                                      ),
                                    const Spacer(),
                                    Text(
                                      '${(template['template_goals'] as List?)?.length ?? 0} goals',
                                      style: TextStyle(color: Colors.grey[500], fontSize: 13),
                                    ),
                                  ],
                                ),
                              ],
                            ),
                          ),
                        ),
                      );
                    },
                  ),
      ),
    );
  }
}
