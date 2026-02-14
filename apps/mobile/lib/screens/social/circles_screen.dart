import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../core/theme/app_theme.dart';
import '../../services/api_service.dart';
import '../../widgets/gradient_background.dart';
import '../../widgets/glass_container.dart';
import '../../widgets/glass_app_bar.dart';
import '../../widgets/glass_button.dart';
import '../../widgets/glass_text_field.dart';
import '../../widgets/animated_list_item.dart';
import '../../widgets/loading_shimmer.dart';

class CirclesScreen extends ConsumerStatefulWidget {
  const CirclesScreen({super.key});

  @override
  ConsumerState<CirclesScreen> createState() => _CirclesScreenState();
}

class _CirclesScreenState extends ConsumerState<CirclesScreen> {
  List<Map<String, dynamic>> _circles = [];
  bool _isLoading = true;

  @override
  void initState() { super.initState(); _loadCircles(); }

  Future<void> _loadCircles() async {
    setState(() => _isLoading = true);
    try {
      final api = ref.read(apiServiceProvider);
      final response = await api.get('/circles/');
      final results = response.data['results'] as List? ?? response.data as List? ?? [];
      setState(() { _circles = List<Map<String, dynamic>>.from(results); _isLoading = false; });
    } catch (_) { setState(() => _isLoading = false); }
  }

  void _showCreateCircleDialog() {
    final nameController = TextEditingController();
    final descController = TextEditingController();
    String selectedCategory = 'personal_growth';
    bool isPublic = true;
    final isDark = Theme.of(context).brightness == Brightness.dark;

    const categories = ['career', 'health', 'fitness', 'education', 'finance', 'creativity', 'relationships', 'personal_growth', 'hobbies', 'other'];

    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setSheetState) => Container(
          decoration: BoxDecoration(
            color: isDark ? const Color(0xFF1E1B4B).withValues(alpha: 0.95) : Colors.white.withValues(alpha: 0.97),
            borderRadius: const BorderRadius.vertical(top: Radius.circular(24)),
          ),
          padding: EdgeInsets.fromLTRB(20, 20, 20, MediaQuery.of(ctx).viewInsets.bottom + 20),
          child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
            Center(child: Container(width: 40, height: 4, decoration: BoxDecoration(color: isDark ? Colors.white24 : Colors.grey[600], borderRadius: BorderRadius.circular(2)))),
            const SizedBox(height: 16),
            Text('Create Circle', style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold, color: isDark ? Colors.white : const Color(0xFF1E1B4B))),
            const SizedBox(height: 16),
            GlassTextField(controller: nameController, label: 'Circle Name', textInputAction: TextInputAction.next),
            const SizedBox(height: 12),
            GlassTextField(controller: descController, label: 'Description', maxLines: 3),
            const SizedBox(height: 12),
            DropdownButtonFormField<String>(
              value: selectedCategory,
              decoration: InputDecoration(
                labelText: 'Category', labelStyle: TextStyle(color: isDark ? Colors.white54 : Colors.grey),
                filled: true, fillColor: isDark ? Colors.white.withValues(alpha: 0.08) : Colors.white.withValues(alpha: 0.3),
                border: OutlineInputBorder(borderRadius: BorderRadius.circular(12), borderSide: BorderSide.none),
              ),
              dropdownColor: isDark ? const Color(0xFF2D2B55) : Colors.white,
              style: TextStyle(color: isDark ? Colors.white : const Color(0xFF1E1B4B)),
              items: categories.map((c) => DropdownMenuItem(value: c, child: Text(c.replaceAll('_', ' ').toUpperCase()))).toList(),
              onChanged: (v) => setSheetState(() => selectedCategory = v!),
            ),
            const SizedBox(height: 12),
            GlassContainer(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
              opacity: isDark ? 0.1 : 0.2,
              child: SwitchListTile(
                title: Text('Public Circle', style: TextStyle(color: isDark ? Colors.white : const Color(0xFF1E1B4B))),
                subtitle: Text('Anyone can join', style: TextStyle(color: isDark ? Colors.white54 : Colors.grey, fontSize: 13)),
                value: isPublic,
                activeColor: AppTheme.primaryPurple,
                onChanged: (v) => setSheetState(() => isPublic = v),
              ),
            ),
            const SizedBox(height: 16),
            SizedBox(
              width: double.infinity,
              child: GlassButton(
                label: 'Create',
                icon: Icons.add,
                onPressed: () async {
                  if (nameController.text.trim().isEmpty) return;
                  try {
                    final api = ref.read(apiServiceProvider);
                    await api.post('/circles/', data: {
                      'name': nameController.text.trim(), 'description': descController.text.trim(),
                      'category': selectedCategory, 'is_public': isPublic,
                    });
                    if (ctx.mounted) Navigator.pop(ctx);
                    _loadCircles();
                  } catch (e) {
                    if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Error: $e')));
                  }
                },
              ),
            ),
          ]),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;

    return GradientBackground(
      colors: isDark ? AppTheme.gradientSocial : AppTheme.gradientSocialLight,
      child: Scaffold(
        backgroundColor: Colors.transparent,
        extendBodyBehindAppBar: true,
        appBar: const GlassAppBar(title: 'Dream Circles'),
        body: RefreshIndicator(
          onRefresh: _loadCircles,
          child: _isLoading
              ? const Center(child: LoadingShimmer())
              : _circles.isEmpty
                  ? ListView(children: [
                      const SizedBox(height: 120),
                      Center(child: Column(children: [
                        Container(
                          padding: const EdgeInsets.all(24),
                          decoration: BoxDecoration(shape: BoxShape.circle, color: AppTheme.primaryPurple.withValues(alpha: 0.1)),
                          child: Icon(Icons.group_outlined, size: 48, color: isDark ? Colors.white24 : Colors.grey[600]),
                        ).animate().fadeIn(duration: 500.ms).scale(begin: const Offset(0.8, 0.8), end: const Offset(1, 1)),
                        const SizedBox(height: 16),
                        Text('No circles yet', style: TextStyle(color: isDark ? Colors.white54 : Colors.grey[700], fontSize: 16))
                          .animate().fadeIn(duration: 500.ms, delay: 100.ms),
                        const SizedBox(height: 16),
                        GlassButton(label: 'Create Circle', icon: Icons.add, onPressed: _showCreateCircleDialog)
                          .animate().fadeIn(duration: 500.ms, delay: 200.ms),
                      ])),
                    ])
                  : ListView.builder(
                      padding: EdgeInsets.fromLTRB(16, MediaQuery.of(context).padding.top + kToolbarHeight + 8, 16, 32),
                      itemCount: _circles.length,
                      itemBuilder: (context, index) {
                        final circle = _circles[index];
                        return AnimatedListItem(
                          index: index,
                          child: GestureDetector(
                            onTap: () => context.push('/circles/${circle['id']}'),
                            child: GlassContainer(
                              margin: const EdgeInsets.only(bottom: 12),
                              padding: const EdgeInsets.all(16),
                              opacity: isDark ? 0.12 : 0.25,
                              child: Row(children: [
                                Container(
                                  width: 48, height: 48,
                                  decoration: BoxDecoration(
                                    gradient: const LinearGradient(colors: [AppTheme.primaryPurple, Color(0xFF8B5CF6)]),
                                    borderRadius: BorderRadius.circular(14),
                                  ),
                                  child: Center(child: Text((circle['name'] ?? 'C')[0].toUpperCase(), style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold, fontSize: 20))),
                                ),
                                const SizedBox(width: 14),
                                Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                                  Text(circle['name'] ?? '', style: TextStyle(fontWeight: FontWeight.w600, fontSize: 15, color: isDark ? Colors.white : const Color(0xFF1E1B4B))),
                                  const SizedBox(height: 3),
                                  Text('${circle['member_count'] ?? circle['memberCount'] ?? 0} members', style: TextStyle(fontSize: 13, color: isDark ? Colors.white54 : Colors.grey[600])),
                                ])),
                                Icon(Icons.chevron_right, color: isDark ? Colors.white24 : Colors.grey[600]),
                              ]),
                            ),
                          ),
                        );
                      },
                    ),
        ),
        floatingActionButton: Container(
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            boxShadow: [BoxShadow(color: AppTheme.primaryPurple.withValues(alpha: 0.4), blurRadius: 16, spreadRadius: 2)],
          ),
          child: FloatingActionButton(
            onPressed: _showCreateCircleDialog,
            backgroundColor: AppTheme.primaryPurple,
            foregroundColor: Colors.white,
            child: const Icon(Icons.add),
          ),
        ).animate().fadeIn(duration: 500.ms, delay: 300.ms).scale(begin: const Offset(0.8, 0.8), end: const Offset(1, 1)),
      ),
    );
  }
}
