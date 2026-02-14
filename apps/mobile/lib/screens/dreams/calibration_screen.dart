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
import '../../widgets/animated_progress_bar.dart';
import '../../widgets/loading_shimmer.dart';

class CalibrationScreen extends ConsumerStatefulWidget {
  final String dreamId;
  const CalibrationScreen({super.key, required this.dreamId});

  @override
  ConsumerState<CalibrationScreen> createState() => _CalibrationScreenState();
}

class _CalibrationScreenState extends ConsumerState<CalibrationScreen> {
  List<Map<String, dynamic>> _questions = [];
  final Map<String, dynamic> _answers = {};
  int _currentIndex = 0;
  bool _isLoading = true;
  bool _isSubmitting = false;

  @override
  void initState() { super.initState(); _loadQuestions(); }

  Future<void> _loadQuestions() async {
    try {
      final api = ref.read(apiServiceProvider);
      final response = await api.get('/dreams/${widget.dreamId}/calibration/');
      setState(() { _questions = List<Map<String, dynamic>>.from(response.data['questions'] ?? []); _isLoading = false; });
    } catch (_) { setState(() => _isLoading = false); }
  }

  Future<void> _submit() async {
    setState(() => _isSubmitting = true);
    try {
      final api = ref.read(apiServiceProvider);
      await api.post('/dreams/${widget.dreamId}/calibration/', data: {'answers': _answers});
      if (mounted) context.pop();
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Error: $e')));
    } finally { if (mounted) setState(() => _isSubmitting = false); }
  }

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;

    return GradientBackground(
      colors: isDark ? AppTheme.gradientDreams : AppTheme.gradientDreamsLight,
      child: Scaffold(
        backgroundColor: Colors.transparent,
        extendBodyBehindAppBar: true,
        appBar: GlassAppBar(title: _isLoading || _questions.isEmpty ? 'Calibration' : 'Question ${_currentIndex + 1}/${_questions.length}'),
        body: _isLoading
            ? const Center(child: LoadingShimmer())
            : _questions.isEmpty
                ? Center(child: Text('No calibration questions available.', style: TextStyle(color: isDark ? Colors.white54 : Colors.grey)))
                : SafeArea(
                    child: Padding(
                      padding: const EdgeInsets.all(24),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.stretch,
                        children: [
                          AnimatedProgressBar(
                            progress: (_currentIndex + 1) / _questions.length,
                            height: 6,
                          ),
                          const SizedBox(height: 32),

                          AnimatedSwitcher(
                            duration: AppTheme.animNormal,
                            child: _buildQuestionContent(isDark),
                          ),

                          const Spacer(),
                          Row(
                            children: [
                              if (_currentIndex > 0)
                                Expanded(
                                  child: GlassButton(
                                    label: 'Previous',
                                    onPressed: () => setState(() => _currentIndex--),
                                    style: GlassButtonStyle.secondary,
                                  ),
                                ),
                              if (_currentIndex > 0) const SizedBox(width: 12),
                              Expanded(
                                child: GlassButton(
                                  label: _currentIndex < _questions.length - 1 ? 'Next' : 'Submit',
                                  onPressed: _currentIndex < _questions.length - 1
                                      ? () => setState(() => _currentIndex++)
                                      : _isSubmitting ? null : _submit,
                                  isLoading: _isSubmitting,
                                ),
                              ),
                            ],
                          ),
                        ],
                      ),
                    ),
                  ),
      ),
    );
  }

  Widget _buildQuestionContent(bool isDark) {
    final question = _questions[_currentIndex];
    final type = question['type'] ?? 'scale';

    return GlassContainer(
      key: ValueKey(_currentIndex),
      padding: const EdgeInsets.all(24),
      opacity: isDark ? 0.12 : 0.25,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text(question['text'] ?? '', style: TextStyle(fontSize: 20, fontWeight: FontWeight.w600, color: isDark ? Colors.white : const Color(0xFF1E1B4B))),
          const SizedBox(height: 8),
          if (question['description'] != null)
            Text(question['description'], style: TextStyle(fontSize: 14, color: isDark ? Colors.white60 : Colors.grey[600])),
          const SizedBox(height: 24),
          if (type == 'scale') _buildScaleQuestion(question, isDark),
          if (type == 'choice') _buildChoiceQuestion(question, isDark),
          if (type == 'text') _buildTextQuestion(question, isDark),
        ],
      ),
    ).animate().fadeIn(duration: 300.ms).slideX(begin: 0.05, end: 0);
  }

  Widget _buildScaleQuestion(Map<String, dynamic> question, bool isDark) {
    final key = question['key'] ?? '';
    final value = (_answers[key] ?? 5).toDouble();
    return Column(children: [
      SliderTheme(
        data: SliderThemeData(activeTrackColor: AppTheme.primaryPurple, thumbColor: AppTheme.primaryPurple, overlayColor: AppTheme.primaryPurple.withValues(alpha: 0.2), inactiveTrackColor: isDark ? Colors.white12 : Colors.grey[600]),
        child: Slider(value: value, min: 1, max: 10, divisions: 9, label: value.toInt().toString(),
          onChanged: (v) => setState(() => _answers[key] = v.toInt())),
      ),
      Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
        Text(question['min_label'] ?? '1', style: TextStyle(fontSize: 12, color: isDark ? Colors.white38 : Colors.grey)),
        Text(question['max_label'] ?? '10', style: TextStyle(fontSize: 12, color: isDark ? Colors.white38 : Colors.grey)),
      ]),
    ]);
  }

  Widget _buildChoiceQuestion(Map<String, dynamic> question, bool isDark) {
    final key = question['key'] ?? '';
    final options = List<String>.from(question['options'] ?? []);
    return Column(children: options.map((option) {
      final isSelected = _answers[key] == option;
      return Padding(
        padding: const EdgeInsets.only(bottom: 8),
        child: GestureDetector(
          onTap: () => setState(() => _answers[key] = option),
          child: Container(
            width: double.infinity,
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
            decoration: BoxDecoration(
              color: isSelected ? AppTheme.primaryPurple.withValues(alpha: 0.2) : (isDark ? Colors.white.withValues(alpha: 0.05) : Colors.white.withValues(alpha: 0.2)),
              borderRadius: BorderRadius.circular(10),
              border: Border.all(color: isSelected ? AppTheme.primaryPurple : (isDark ? Colors.white12 : Colors.grey.withValues(alpha: 0.3))),
            ),
            child: Text(option, style: TextStyle(color: isSelected ? AppTheme.primaryPurple : (isDark ? Colors.white : const Color(0xFF1E1B4B)))),
          ),
        ),
      );
    }).toList());
  }

  Widget _buildTextQuestion(Map<String, dynamic> question, bool isDark) {
    final key = question['key'] ?? '';
    return TextFormField(
      maxLines: 3,
      style: TextStyle(color: isDark ? Colors.white : const Color(0xFF1E1B4B)),
      decoration: InputDecoration(
        hintText: 'Your answer...', hintStyle: TextStyle(color: isDark ? Colors.white30 : Colors.grey),
        filled: true, fillColor: isDark ? Colors.white.withValues(alpha: 0.05) : Colors.white.withValues(alpha: 0.2),
        border: OutlineInputBorder(borderRadius: BorderRadius.circular(10), borderSide: BorderSide.none),
      ),
      initialValue: _answers[key]?.toString(),
      onChanged: (v) => _answers[key] = v,
    );
  }
}
