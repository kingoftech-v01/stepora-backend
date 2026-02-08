import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../core/theme/app_theme.dart';
import '../../providers/dreams_provider.dart';
import '../../services/api_service.dart';

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

  static const _categories = {
    'health': 'Health & Fitness',
    'career': 'Career',
    'relationships': 'Relationships',
    'personal_growth': 'Personal Growth',
    'finance': 'Finance',
    'hobbies': 'Hobbies & Fun',
  };

  static const _timeframes = {
    '1_month': '1 Month',
    '3_months': '3 Months',
    '6_months': '6 Months',
    '1_year': '1 Year',
    '2_years': '2 Years',
    '5_years': '5 Years',
  };

  static const _statuses = {
    'active': 'Active',
    'paused': 'Paused',
    'archived': 'Archived',
    'completed': 'Completed',
  };

  @override
  void initState() {
    super.initState();
    _loadDream();
  }

  @override
  void dispose() {
    _titleController.dispose();
    _descriptionController.dispose();
    super.dispose();
  }

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
    } catch (_) {
      setState(() => _isLoading = false);
    }
  }

  Future<void> _save() async {
    if (!_formKey.currentState!.validate()) return;
    setState(() => _isSaving = true);
    try {
      final api = ref.read(apiServiceProvider);
      await api.put('/dreams/${widget.dreamId}/', data: {
        'title': _titleController.text.trim(),
        'description': _descriptionController.text.trim(),
        'category': _category,
        'timeframe': _timeframe,
        'status': _status,
      });
      if (mounted) context.pop();
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error: $e')),
        );
      }
    } finally {
      if (mounted) setState(() => _isSaving = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_isLoading) {
      return Scaffold(
        appBar: AppBar(title: const Text('Edit Dream')),
        body: const Center(child: CircularProgressIndicator()),
      );
    }

    return Scaffold(
      appBar: AppBar(title: const Text('Edit Dream')),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(24),
        child: Form(
          key: _formKey,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              TextFormField(
                controller: _titleController,
                textInputAction: TextInputAction.next,
                decoration: const InputDecoration(
                  labelText: 'Dream Title',
                  prefixIcon: Icon(Icons.lightbulb_outline),
                ),
                validator: (v) => v == null || v.trim().isEmpty ? 'Title is required' : null,
              ),
              const SizedBox(height: 16),
              TextFormField(
                controller: _descriptionController,
                maxLines: 3,
                decoration: const InputDecoration(
                  labelText: 'Description',
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
              const SizedBox(height: 16),
              DropdownButtonFormField<String>(
                initialValue: _status,
                decoration: const InputDecoration(
                  labelText: 'Status',
                  prefixIcon: Icon(Icons.flag_outlined),
                ),
                items: _statuses.entries.map((e) => DropdownMenuItem(
                  value: e.key,
                  child: Text(e.value),
                )).toList(),
                onChanged: (v) => setState(() => _status = v!),
              ),
              const SizedBox(height: 32),
              FilledButton(
                onPressed: _isSaving ? null : _save,
                style: FilledButton.styleFrom(
                  padding: const EdgeInsets.symmetric(vertical: 16),
                  backgroundColor: AppTheme.primaryPurple,
                ),
                child: _isSaving
                    ? const SizedBox(
                        height: 20, width: 20,
                        child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                      )
                    : const Text('Save Changes', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600)),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
