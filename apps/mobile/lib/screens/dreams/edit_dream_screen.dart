import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../core/theme/app_theme.dart';
import '../../providers/dreams_provider.dart';
import '../../services/api_service.dart';
import '../../widgets/gradient_background.dart';
import '../../widgets/glass_container.dart';
import '../../widgets/glass_app_bar.dart';
import '../../widgets/glass_text_field.dart';
import '../../widgets/glass_button.dart';
import '../../widgets/loading_shimmer.dart';

class EditDreamScreen extends ConsumerStatefulWidget {
  final String dreamId;
  const EditDreamScreen({super.key, required this.dreamId});

  @override
  ConsumerState<EditDreamScreen> createState() => _EditDreamScreenState();
}

class _EditDreamScreenState extends ConsumerState<EditDreamScreen> {
  final _formKey = GlobalKey<FormState>();
  final _titleController = TextEditingController();
  final _descriptionController = TextEditingController();
  String _category = 'personal_growth';
  String _timeframe = '6_months';
  String _status = 'active';
  bool _isLoading = true;
  bool _isSaving = false;

  static const _categories = {'health': 'Health & Fitness', 'career': 'Career', 'relationships': 'Relationships', 'personal_growth': 'Personal Growth', 'finance': 'Finance', 'hobbies': 'Hobbies & Fun'};
  static const _timeframes = {'1_month': '1 Month', '3_months': '3 Months', '6_months': '6 Months', '1_year': '1 Year', '2_years': '2 Years', '5_years': '5 Years'};
  static const _statuses = {'active': 'Active', 'paused': 'Paused', 'archived': 'Archived', 'completed': 'Completed'};

  @override
  void initState() { super.initState(); _loadDream(); }

  @override
  void dispose() { _titleController.dispose(); _descriptionController.dispose(); super.dispose(); }

  Future<void> _loadDream() async {
    try {
      final dream = await ref.read(dreamsProvider.notifier).getDreamDetail(widget.dreamId);
      _titleController.text = dream.title;
      _descriptionController.text = dream.description;
      setState(() {
        _category = _categories.containsKey(dream.category) ? dream.category : 'personal_growth';
        _timeframe = _timeframes.containsKey(dream.timeframe) ? dream.timeframe : '6_months';
        _status = _statuses.containsKey(dream.status) ? dream.status : 'active';
        _isLoading = false;
      });
    } catch (_) { setState(() => _isLoading = false); }
  }

  Future<void> _save() async {
    if (!_formKey.currentState!.validate()) return;
    setState(() => _isSaving = true);
    try {
      final api = ref.read(apiServiceProvider);
      await api.put('/dreams/${widget.dreamId}/', data: {
        'title': _titleController.text.trim(), 'description': _descriptionController.text.trim(),
        'category': _category, 'timeframe': _timeframe, 'status': _status,
      });
      if (mounted) context.pop();
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Error: $e')));
    } finally { if (mounted) setState(() => _isSaving = false); }
  }

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;

    return GradientBackground(
      colors: isDark ? AppTheme.gradientDreams : AppTheme.gradientDreamsLight,
      child: Scaffold(
        backgroundColor: Colors.transparent,
        extendBodyBehindAppBar: true,
        appBar: const GlassAppBar(title: 'Edit Dream'),
        body: _isLoading
            ? const Center(child: LoadingShimmer())
            : SafeArea(
                child: SingleChildScrollView(
                  padding: const EdgeInsets.all(24),
                  child: Form(
                    key: _formKey,
                    child: GlassContainer(
                      padding: const EdgeInsets.all(24),
                      opacity: isDark ? 0.12 : 0.25,
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.stretch,
                        children: [
                          GlassTextField(controller: _titleController, label: 'Dream Title', textInputAction: TextInputAction.next,
                            prefixIcon: Icon(Icons.lightbulb_outline, color: isDark ? Colors.white54 : Colors.grey),
                            validator: (v) => v == null || v.trim().isEmpty ? 'Title is required' : null),
                          const SizedBox(height: 16),
                          GlassTextField(controller: _descriptionController, label: 'Description', maxLines: 3,
                            prefixIcon: Icon(Icons.description_outlined, color: isDark ? Colors.white54 : Colors.grey)),
                          const SizedBox(height: 16),
                          _buildDropdown('Category', Icons.category_outlined, _category, _categories, isDark, (v) => setState(() => _category = v!)),
                          const SizedBox(height: 16),
                          _buildDropdown('Timeframe', Icons.timer_outlined, _timeframe, _timeframes, isDark, (v) => setState(() => _timeframe = v!)),
                          const SizedBox(height: 16),
                          _buildDropdown('Status', Icons.flag_outlined, _status, _statuses, isDark, (v) => setState(() => _status = v!)),
                          const SizedBox(height: 28),
                          GlassButton(label: 'Save Changes', onPressed: _isSaving ? null : _save, isLoading: _isSaving),
                        ],
                      ),
                    ).animate().fadeIn(duration: 500.ms).slideY(begin: 0.1, end: 0),
                  ),
                ),
              ),
      ),
    );
  }

  Widget _buildDropdown(String label, IconData icon, String value, Map<String, String> items, bool isDark, ValueChanged<String?> onChanged) {
    return DropdownButtonFormField<String>(
      initialValue: value,
      decoration: InputDecoration(
        labelText: label, labelStyle: TextStyle(color: isDark ? Colors.white54 : Colors.grey),
        prefixIcon: Icon(icon, color: isDark ? Colors.white54 : Colors.grey),
        filled: true, fillColor: isDark ? Colors.white.withValues(alpha: 0.08) : Colors.white.withValues(alpha: 0.3),
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
