import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../core/theme/app_theme.dart';
import '../../core/utils/validators.dart';
import '../../providers/dreams_provider.dart';

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
    'health': 'Health & Fitness',
    'career': 'Career',
    'relationships': 'Relationships',
    'personal_growth': 'Personal Growth',
    'finance': 'Finance',
    'hobbies': 'Hobbies & Fun',
  };

  final _timeframes = const {
    '1_month': '1 Month',
    '3_months': '3 Months',
    '6_months': '6 Months',
    '1_year': '1 Year',
    '2_years': '2 Years',
    '5_years': '5 Years',
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
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error: $e')),
        );
      }
    } finally {
      if (mounted) setState(() => _isLoading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Create Dream'),
        actions: [
          TextButton.icon(
            onPressed: () => context.push('/dream-templates'),
            icon: const Icon(Icons.library_books_outlined),
            label: const Text('Templates'),
          ),
        ],
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(24),
        child: Form(
          key: _formKey,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Icon(Icons.auto_awesome, size: 48, color: AppTheme.primaryPurple),
              const SizedBox(height: 16),
              Text(
                'What do you dream of achieving?',
                style: Theme.of(context).textTheme.titleLarge?.copyWith(
                  fontWeight: FontWeight.bold,
                ),
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 32),
              TextFormField(
                controller: _titleController,
                textInputAction: TextInputAction.next,
                decoration: const InputDecoration(
                  labelText: 'Dream Title',
                  hintText: 'e.g., Run a marathon',
                  prefixIcon: Icon(Icons.lightbulb_outline),
                ),
                validator: (v) => Validators.required(v, 'Title'),
              ),
              const SizedBox(height: 16),
              TextFormField(
                controller: _descriptionController,
                maxLines: 3,
                decoration: const InputDecoration(
                  labelText: 'Description (optional)',
                  hintText: 'Describe your dream in detail...',
                  prefixIcon: Icon(Icons.description_outlined),
                  alignLabelWithHint: true,
                ),
              ),
              const SizedBox(height: 16),
              DropdownButtonFormField<String>(
                initialValue: _category,
                decoration: const InputDecoration(
                  labelText: 'Category',
                  prefixIcon: Icon(Icons.category_outlined),
                ),
                items: _categories.entries.map((e) => DropdownMenuItem(
                  value: e.key,
                  child: Text(e.value),
                )).toList(),
                onChanged: (v) => setState(() => _category = v!),
              ),
              const SizedBox(height: 16),
              DropdownButtonFormField<String>(
                initialValue: _timeframe,
                decoration: const InputDecoration(
                  labelText: 'Timeframe',
                  prefixIcon: Icon(Icons.timer_outlined),
                ),
                items: _timeframes.entries.map((e) => DropdownMenuItem(
                  value: e.key,
                  child: Text(e.value),
                )).toList(),
                onChanged: (v) => setState(() => _timeframe = v!),
              ),
              const SizedBox(height: 32),
              FilledButton(
                onPressed: _isLoading ? null : _create,
                style: FilledButton.styleFrom(
                  padding: const EdgeInsets.symmetric(vertical: 16),
                  backgroundColor: AppTheme.primaryPurple,
                ),
                child: _isLoading
                    ? const SizedBox(
                        height: 20, width: 20,
                        child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                      )
                    : const Text('Create Dream', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600)),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
