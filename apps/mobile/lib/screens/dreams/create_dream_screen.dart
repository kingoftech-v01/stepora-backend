import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../core/theme/app_theme.dart';
import '../../core/utils/validators.dart';
import '../../providers/dreams_provider.dart';
import '../../widgets/gradient_background.dart';
import '../../widgets/glass_container.dart';
import '../../widgets/glass_app_bar.dart';
import '../../widgets/glass_text_field.dart';
import '../../widgets/glass_button.dart';

class CreateDreamScreen extends ConsumerStatefulWidget {
  const CreateDreamScreen({super.key});

  @override
  ConsumerState<CreateDreamScreen> createState() => _CreateDreamScreenState();
}

class _CreateDreamScreenState extends ConsumerState<CreateDreamScreen> {
  final _formKey = GlobalKey<FormState>();
  final _titleController = TextEditingController();
  final _descriptionController = TextEditingController();
  String _category = 'personal_growth';
  String _timeframe = '6_months';
  bool _isLoading = false;

  final _categories = const {
    'health': 'Health & Fitness', 'career': 'Career', 'relationships': 'Relationships',
    'personal_growth': 'Personal Growth', 'finance': 'Finance', 'hobbies': 'Hobbies & Fun',
  };

  final _timeframes = const {
    '1_month': '1 Month', '3_months': '3 Months', '6_months': '6 Months',
    '1_year': '1 Year', '2_years': '2 Years', '5_years': '5 Years',
  };

  @override
  void dispose() {
    _titleController.dispose();
    _descriptionController.dispose();
    super.dispose();
  }

  Future<void> _create() async {
    if (!_formKey.currentState!.validate()) return;
    setState(() => _isLoading = true);
    try {
      final dream = await ref.read(dreamsProvider.notifier).createDream({
        'title': _titleController.text.trim(),
        'description': _descriptionController.text.trim(),
        'category': _category,
        'timeframe': _timeframe,
      });
      if (mounted) context.go('/dreams/${dream.id}');
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Error: $e')));
    } finally {
      if (mounted) setState(() => _isLoading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;

    return GradientBackground(
      colors: isDark ? AppTheme.gradientDreams : AppTheme.gradientDreamsLight,
      child: Scaffold(
        backgroundColor: Colors.transparent,
        extendBodyBehindAppBar: true,
        appBar: GlassAppBar(
          title: 'Create Dream',
          actions: [
            TextButton.icon(
              onPressed: () => context.push('/dream-templates'),
              icon: Icon(Icons.library_books_outlined, color: isDark ? Colors.white70 : AppTheme.primaryPurple, size: 18),
              label: Text('Templates', style: TextStyle(color: isDark ? Colors.white70 : AppTheme.primaryPurple)),
            ),
          ],
        ),
        body: SafeArea(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(24),
            child: Form(
              key: _formKey,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Icon(Icons.auto_awesome, size: 48, color: AppTheme.primaryPurple,
                    shadows: [Shadow(color: AppTheme.primaryPurple.withValues(alpha: 0.4), blurRadius: 16)],
                  ).animate().fadeIn(duration: 500.ms),
                  const SizedBox(height: 16),
                  Text(
                    'What do you dream of achieving?',
                    style: TextStyle(fontSize: 22, fontWeight: FontWeight.bold, color: isDark ? Colors.white : const Color(0xFF1E1B4B)),
                    textAlign: TextAlign.center,
                  ).animate().fadeIn(duration: 500.ms, delay: 100.ms),
                  const SizedBox(height: 28),

                  GlassContainer(
                    padding: const EdgeInsets.all(24),
                    opacity: isDark ? 0.12 : 0.25,
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        GlassTextField(
                          controller: _titleController,
                          label: 'Dream Title',
                          hint: 'e.g., Run a marathon',
                          textInputAction: TextInputAction.next,
                          prefixIcon: Icon(Icons.lightbulb_outline, color: isDark ? Colors.white54 : Colors.grey),
                          validator: (v) => Validators.required(v, 'Title'),
                        ),
                        const SizedBox(height: 16),
                        GlassTextField(
                          controller: _descriptionController,
                          label: 'Description (optional)',
                          hint: 'Describe your dream in detail...',
                          maxLines: 3,
                          prefixIcon: Icon(Icons.description_outlined, color: isDark ? Colors.white54 : Colors.grey),
                        ),
                        const SizedBox(height: 16),
                        _buildGlassDropdown('Category', Icons.category_outlined, _category, _categories, isDark, (v) => setState(() => _category = v!)),
                        const SizedBox(height: 16),
                        _buildGlassDropdown('Timeframe', Icons.timer_outlined, _timeframe, _timeframes, isDark, (v) => setState(() => _timeframe = v!)),
                        const SizedBox(height: 28),
                        GlassButton(
                          label: 'Create Dream',
                          onPressed: _isLoading ? null : _create,
                          isLoading: _isLoading,
                          icon: Icons.auto_awesome,
                        ),
                      ],
                    ),
                  ).animate().fadeIn(duration: 500.ms, delay: 200.ms).slideY(begin: 0.1, end: 0),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildGlassDropdown(String label, IconData icon, String value, Map<String, String> items, bool isDark, ValueChanged<String?> onChanged) {
    return DropdownButtonFormField<String>(
      initialValue: value,
      decoration: InputDecoration(
        labelText: label,
        labelStyle: TextStyle(color: isDark ? Colors.white54 : Colors.grey),
        prefixIcon: Icon(icon, color: isDark ? Colors.white54 : Colors.grey),
        filled: true,
        fillColor: isDark ? Colors.white.withValues(alpha: 0.08) : Colors.white.withValues(alpha: 0.3),
        border: OutlineInputBorder(borderRadius: BorderRadius.circular(AppTheme.radiusMd), borderSide: BorderSide.none),
        enabledBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(AppTheme.radiusMd), borderSide: BorderSide(color: isDark ? Colors.white.withValues(alpha: 0.15) : Colors.white.withValues(alpha: 0.4))),
      ),
      dropdownColor: isDark ? const Color(0xFF2D2B55) : Colors.white,
      style: TextStyle(color: isDark ? Colors.white : const Color(0xFF1E1B4B)),
      items: items.entries.map((e) => DropdownMenuItem(value: e.key, child: Text(e.value))).toList(),
      onChanged: onChanged,
    );
  }
}
