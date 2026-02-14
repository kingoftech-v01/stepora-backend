import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../core/theme/app_theme.dart';
import '../../config/api_constants.dart';
import '../../services/api_service.dart';
import '../../widgets/gradient_background.dart';
import '../../widgets/glass_container.dart';
import '../../widgets/glass_app_bar.dart';
import '../../widgets/animated_list_item.dart';
import '../../widgets/loading_shimmer.dart';

class DreamTemplatesScreen extends ConsumerStatefulWidget {
  const DreamTemplatesScreen({super.key});

  @override
  ConsumerState<DreamTemplatesScreen> createState() => _DreamTemplatesScreenState();
}

class _DreamTemplatesScreenState extends ConsumerState<DreamTemplatesScreen> {
  List<Map<String, dynamic>> _templates = [];
  bool _isLoading = true;

  @override
  void initState() { super.initState(); _loadTemplates(); }

  Future<void> _loadTemplates() async {
    setState(() => _isLoading = true);
    try {
      final api = ref.read(apiServiceProvider);
      final response = await api.get(ApiConstants.dreamTemplates);
      final results = response.data['results'] as List? ?? response.data as List? ?? [];
      setState(() { _templates = List<Map<String, dynamic>>.from(results); _isLoading = false; });
    } catch (_) { setState(() => _isLoading = false); }
  }

  Future<void> _useTemplate(Map<String, dynamic> template) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text(template['title'] ?? 'Use Template'),
        content: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(template['description'] ?? ''),
          if (template['template_goals'] != null) ...[
            const SizedBox(height: 12),
            const Text('Goals:', style: TextStyle(fontWeight: FontWeight.bold)),
            const SizedBox(height: 4),
            ...((template['template_goals'] as List?) ?? []).map((g) => Padding(
              padding: const EdgeInsets.only(left: 8, bottom: 2),
              child: Text('- ${g['title'] ?? g}'),
            )),
          ],
        ]),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancel')),
          FilledButton(onPressed: () => Navigator.pop(ctx, true), style: FilledButton.styleFrom(backgroundColor: AppTheme.primaryPurple), child: const Text('Create Dream')),
        ],
      ),
    );
    if (confirmed != true) return;
    try {
      final api = ref.read(apiServiceProvider);
      final response = await api.post('${ApiConstants.dreamTemplates}${template['id']}/use/');
      final newDreamId = response.data['id']?.toString();
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Dream created from template!')));
        if (newDreamId != null) { context.go('/dreams/$newDreamId'); } else { context.pop(); }
      }
    } catch (e) { if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Error: $e'))); }
  }

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;

    return GradientBackground(
      colors: isDark ? AppTheme.gradientDreams : AppTheme.gradientDreamsLight,
      child: Scaffold(
        backgroundColor: Colors.transparent,
        extendBodyBehindAppBar: true,
        appBar: const GlassAppBar(title: 'Dream Templates'),
        body: RefreshIndicator(
          onRefresh: _loadTemplates,
          child: _isLoading
              ? const Center(child: LoadingShimmer())
              : _templates.isEmpty
                  ? ListView(children: [
                      const SizedBox(height: 100),
                      Center(child: Column(children: [
                        Icon(Icons.library_books_outlined, size: 64, color: isDark ? Colors.white24 : Colors.grey[600]),
                        const SizedBox(height: 16),
                        Text('No templates available', style: TextStyle(color: isDark ? Colors.white54 : Colors.grey[700])),
                      ])),
                    ])
                  : ListView.builder(
                      padding: EdgeInsets.fromLTRB(16, MediaQuery.of(context).padding.top + kToolbarHeight + 8, 16, 32),
                      itemCount: _templates.length,
                      itemBuilder: (context, index) {
                        final template = _templates[index];
                        final isFeatured = template['is_featured'] == true;
                        return AnimatedListItem(
                          index: index,
                          child: GestureDetector(
                            onTap: () => _useTemplate(template),
                            child: GlassContainer(
                              margin: const EdgeInsets.only(bottom: 12),
                              padding: const EdgeInsets.all(16),
                              opacity: isDark ? 0.12 : 0.25,
                              border: isFeatured ? Border.all(color: AppTheme.accent.withValues(alpha: 0.5), width: 1.5) : null,
                              boxShadow: isFeatured ? [BoxShadow(color: AppTheme.accent.withValues(alpha: 0.15), blurRadius: 12)] : null,
                              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                                Row(children: [
                                  Expanded(child: Text(template['title'] ?? '', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16, color: isDark ? Colors.white : const Color(0xFF1E1B4B)))),
                                  if (isFeatured)
                                    Container(
                                      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                                      decoration: BoxDecoration(color: AppTheme.accent.withValues(alpha: 0.15), borderRadius: BorderRadius.circular(6), border: Border.all(color: AppTheme.accent.withValues(alpha: 0.3))),
                                      child: Text('Featured', style: TextStyle(color: AppTheme.accent, fontSize: 11, fontWeight: FontWeight.w600)),
                                    ),
                                ]),
                                if (template['description'] != null) ...[
                                  const SizedBox(height: 8),
                                  Text(template['description'], style: TextStyle(color: isDark ? Colors.white60 : Colors.grey[600]), maxLines: 2, overflow: TextOverflow.ellipsis),
                                ],
                                const SizedBox(height: 10),
                                Row(children: [
                                  if (template['category'] != null)
                                    Container(
                                      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                                      decoration: BoxDecoration(color: AppTheme.primaryPurple.withValues(alpha: 0.12), borderRadius: BorderRadius.circular(6)),
                                      child: Text(template['category'], style: TextStyle(color: isDark ? Colors.white70 : AppTheme.primaryPurple, fontSize: 12)),
                                    ),
                                  const Spacer(),
                                  Text('${(template['template_goals'] as List?)?.length ?? 0} goals', style: TextStyle(color: isDark ? Colors.white38 : Colors.grey[700], fontSize: 13)),
                                ]),
                              ]),
                            ),
                          ),
                        );
                      },
                    ),
        ),
      ),
    );
  }
}
