import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../core/theme/app_theme.dart';
import '../../providers/dreams_provider.dart';

class MicroStartScreen extends ConsumerStatefulWidget {
  final String taskId;
  const MicroStartScreen({super.key, required this.taskId});

  @override
  ConsumerState<MicroStartScreen> createState() => _MicroStartScreenState();
}

class _MicroStartScreenState extends ConsumerState<MicroStartScreen> {
  Map<String, dynamic>? _data;
  bool _isLoading = true;
  bool _started = false;
  int _seconds = 120; // 2 minutes

  @override
  void initState() {
    super.initState();
    _loadMicroStart();
  }

  Future<void> _loadMicroStart() async {
    try {
      final data = await ref.read(dreamsProvider.notifier).startMicroStart(widget.taskId);
      setState(() {
        _data = data;
        _isLoading = false;
      });
    } catch (_) {
      setState(() => _isLoading = false);
    }
  }

  void _startTimer() {
    setState(() => _started = true);
    Future.doWhile(() async {
      await Future.delayed(const Duration(seconds: 1));
      if (!mounted || _seconds <= 0) return false;
      setState(() => _seconds--);
      return _seconds > 0;
    });
  }

  @override
  Widget build(BuildContext context) {
    if (_isLoading) {
      return Scaffold(appBar: AppBar(), body: const Center(child: CircularProgressIndicator()));
    }

    return Scaffold(
      appBar: AppBar(title: const Text('2-Minute Start')),
      body: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Icon(
              _started ? Icons.timer : Icons.rocket_launch,
              size: 80,
              color: AppTheme.primaryPurple,
            ),
            const SizedBox(height: 24),
            Text(
              _started ? 'Keep going!' : 'Ready to start?',
              style: Theme.of(context).textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.bold),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 16),
            Card(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  children: [
                    Text(
                      _data?['task_title'] ?? 'Task',
                      style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w600),
                      textAlign: TextAlign.center,
                    ),
                    if (_data?['two_minute_action'] != null) ...[
                      const SizedBox(height: 8),
                      Text(
                        _data!['two_minute_action'],
                        style: TextStyle(color: Colors.grey[600]),
                        textAlign: TextAlign.center,
                      ),
                    ],
                  ],
                ),
              ),
            ),
            const SizedBox(height: 32),
            if (_started) ...[
              Text(
                '${_seconds ~/ 60}:${(_seconds % 60).toString().padLeft(2, '0')}',
                style: Theme.of(context).textTheme.displayMedium?.copyWith(
                  fontWeight: FontWeight.bold,
                  color: _seconds <= 10 ? AppTheme.error : AppTheme.primaryPurple,
                ),
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 8),
              LinearProgressIndicator(
                value: 1 - (_seconds / 120),
                backgroundColor: AppTheme.primaryPurple.withValues(alpha: 0.1),
                color: AppTheme.primaryPurple,
                minHeight: 8,
              ),
              const SizedBox(height: 32),
              if (_seconds <= 0) ...[
                const Icon(Icons.celebration, size: 48, color: AppTheme.accent),
                const SizedBox(height: 8),
                const Text('Great job! You did it!', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold), textAlign: TextAlign.center),
                const SizedBox(height: 16),
                Row(
                  children: [
                    Expanded(
                      child: OutlinedButton(
                        onPressed: () => context.pop(),
                        child: const Text('Done'),
                      ),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: FilledButton(
                        onPressed: () async {
                          await ref.read(dreamsProvider.notifier).completeTask(widget.taskId);
                          if (context.mounted) context.pop();
                        },
                        style: FilledButton.styleFrom(backgroundColor: AppTheme.success),
                        child: const Text('Complete Task'),
                      ),
                    ),
                  ],
                ),
              ],
            ] else
              FilledButton.icon(
                onPressed: _startTimer,
                icon: const Icon(Icons.play_arrow),
                label: const Text('Start 2-Minute Timer', style: TextStyle(fontSize: 16)),
                style: FilledButton.styleFrom(
                  backgroundColor: AppTheme.primaryPurple,
                  padding: const EdgeInsets.symmetric(vertical: 16),
                ),
              ),
          ],
        ),
      ),
    );
  }
}
