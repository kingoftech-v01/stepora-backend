import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../core/theme/app_theme.dart';
import '../../services/api_service.dart';

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
  void initState() {
    super.initState();
    _loadQuestions();
  }

  Future<void> _loadQuestions() async {
    try {
      final api = ref.read(apiServiceProvider);
      final response = await api.get('/dreams/${widget.dreamId}/calibration/');
      setState(() {
        _questions = List<Map<String, dynamic>>.from(response.data['questions'] ?? []);
        _isLoading = false;
      });
    } catch (_) {
      setState(() => _isLoading = false);
    }
  }

  Future<void> _submit() async {
    setState(() => _isSubmitting = true);
    try {
      final api = ref.read(apiServiceProvider);
      await api.post('/dreams/${widget.dreamId}/calibration/', data: {
        'answers': _answers,
      });
      if (mounted) context.pop();
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error: $e')),
        );
      }
    } finally {
      if (mounted) setState(() => _isSubmitting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_isLoading) {
      return Scaffold(
        appBar: AppBar(title: const Text('Calibration')),
        body: const Center(child: CircularProgressIndicator()),
      );
    }

    if (_questions.isEmpty) {
      return Scaffold(
        appBar: AppBar(title: const Text('Calibration')),
        body: const Center(child: Text('No calibration questions available.')),
      );
    }

    final question = _questions[_currentIndex];
    final type = question['type'] ?? 'scale';

    return Scaffold(
      appBar: AppBar(
        title: Text('Question ${_currentIndex + 1}/${_questions.length}'),
      ),
      body: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            LinearProgressIndicator(
              value: (_currentIndex + 1) / _questions.length,
              backgroundColor: AppTheme.primaryPurple.withValues(alpha: 0.1),
              color: AppTheme.primaryPurple,
            ),
            const SizedBox(height: 32),
            Text(
              question['text'] ?? '',
              style: Theme.of(context).textTheme.titleLarge?.copyWith(
                fontWeight: FontWeight.w600,
              ),
            ),
            const SizedBox(height: 8),
            if (question['description'] != null)
              Text(
                question['description'],
                style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                  color: Colors.grey[600],
                ),
              ),
            const SizedBox(height: 32),
            if (type == 'scale') _buildScaleQuestion(question),
            if (type == 'choice') _buildChoiceQuestion(question),
            if (type == 'text') _buildTextQuestion(question),
            const Spacer(),
            Row(
              children: [
                if (_currentIndex > 0)
                  Expanded(
                    child: OutlinedButton(
                      onPressed: () => setState(() => _currentIndex--),
                      child: const Text('Previous'),
                    ),
                  ),
                if (_currentIndex > 0) const SizedBox(width: 12),
                Expanded(
                  child: FilledButton(
                    onPressed: _currentIndex < _questions.length - 1
                        ? () => setState(() => _currentIndex++)
                        : _isSubmitting ? null : _submit,
                    style: FilledButton.styleFrom(backgroundColor: AppTheme.primaryPurple),
                    child: _isSubmitting
                        ? const SizedBox(height: 20, width: 20, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                        : Text(_currentIndex < _questions.length - 1 ? 'Next' : 'Submit'),
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildScaleQuestion(Map<String, dynamic> question) {
    final key = question['key'] ?? '';
    final value = (_answers[key] ?? 5).toDouble();
    return Column(
      children: [
        Slider(
          value: value,
          min: 1,
          max: 10,
          divisions: 9,
          label: value.toInt().toString(),
          activeColor: AppTheme.primaryPurple,
          onChanged: (v) => setState(() => _answers[key] = v.toInt()),
        ),
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Text(question['min_label'] ?? '1', style: Theme.of(context).textTheme.bodySmall),
            Text(question['max_label'] ?? '10', style: Theme.of(context).textTheme.bodySmall),
          ],
        ),
      ],
    );
  }

  Widget _buildChoiceQuestion(Map<String, dynamic> question) {
    final key = question['key'] ?? '';
    final options = List<String>.from(question['options'] ?? []);
    return Column(
      children: options.map((option) {
        final isSelected = _answers[key] == option;
        return Padding(
          padding: const EdgeInsets.only(bottom: 8),
          child: ChoiceChip(
            label: Text(option),
            selected: isSelected,
            selectedColor: AppTheme.primaryPurple.withValues(alpha: 0.2),
            onSelected: (_) => setState(() => _answers[key] = option),
          ),
        );
      }).toList(),
    );
  }

  Widget _buildTextQuestion(Map<String, dynamic> question) {
    final key = question['key'] ?? '';
    return TextFormField(
      maxLines: 3,
      decoration: const InputDecoration(hintText: 'Your answer...'),
      initialValue: _answers[key]?.toString(),
      onChanged: (v) => _answers[key] = v,
    );
  }
}
