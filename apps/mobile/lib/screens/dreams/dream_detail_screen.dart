import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../core/theme/app_theme.dart';
import '../../models/dream.dart';
import '../../models/goal.dart';
import '../../providers/dreams_provider.dart';
import '../../widgets/task_tile.dart';

class DreamDetailScreen extends ConsumerStatefulWidget {
  final String dreamId;
  const DreamDetailScreen({super.key, required this.dreamId});

  @override
  ConsumerState<DreamDetailScreen> createState() => _DreamDetailScreenState();
}

class _DreamDetailScreenState extends ConsumerState<DreamDetailScreen> {
  Dream? _dream;
  List<Goal> _goals = [];
  bool _isLoading = true;

  @override
  void initState() {
    super.initState();
    _loadData();
  }

  Future<void> _loadData() async {
    setState(() => _isLoading = true);
    try {
      final notifier = ref.read(dreamsProvider.notifier);
      final dream = await notifier.getDreamDetail(widget.dreamId);
      final goals = await notifier.getGoals(widget.dreamId);
      setState(() {
        _dream = dream;
        _goals = goals;
        _isLoading = false;
      });
    } catch (_) {
      setState(() => _isLoading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_isLoading) {
      return Scaffold(
        appBar: AppBar(),
        body: const Center(child: CircularProgressIndicator()),
      );
    }

    final dream = _dream;
    if (dream == null) {
      return Scaffold(
        appBar: AppBar(),
        body: const Center(child: Text('Dream not found')),
      );
    }

    return Scaffold(
      appBar: AppBar(
        title: Text(dream.title),
        actions: [
          IconButton(
            icon: const Icon(Icons.image_outlined),
            tooltip: 'Vision Board',
            onPressed: () => context.push('/vision-board/${dream.id}'),
          ),
          IconButton(
            icon: const Icon(Icons.chat_outlined),
            tooltip: 'AI Coach',
            onPressed: () => context.push('/chat/${dream.id}'),
          ),
          PopupMenuButton(
            itemBuilder: (context) => [
              const PopupMenuItem(value: 'calibrate', child: Text('Calibration')),
              const PopupMenuItem(value: 'generate', child: Text('Generate Plan')),
              const PopupMenuItem(value: 'delete', child: Text('Delete Dream')),
            ],
            onSelected: (value) async {
              if (value == 'calibrate') {
                context.push('/dreams/${dream.id}/calibration');
              } else if (value == 'generate') {
                await ref.read(dreamsProvider.notifier).generatePlan(dream.id);
                _loadData();
              } else if (value == 'delete') {
                final confirmed = await showDialog<bool>(
                  context: context,
                  builder: (ctx) => AlertDialog(
                    title: const Text('Delete Dream?'),
                    content: const Text('This action cannot be undone.'),
                    actions: [
                      TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancel')),
                      TextButton(onPressed: () => Navigator.pop(ctx, true), child: const Text('Delete')),
                    ],
                  ),
                );
                if (confirmed == true && context.mounted) {
                  await ref.read(dreamsProvider.notifier).deleteDream(dream.id);
                  context.pop();
                }
              }
            },
          ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: _loadData,
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            // Progress Card
            Card(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Chip(
                          label: Text(dream.categoryLabel),
                          backgroundColor: AppTheme.primaryPurple.withOpacity(0.1),
                          labelStyle: TextStyle(color: AppTheme.primaryPurple),
                        ),
                        const Spacer(),
                        Chip(
                          label: Text(dream.status.toUpperCase()),
                          backgroundColor: dream.status == 'active'
                              ? AppTheme.success.withOpacity(0.1)
                              : Colors.grey.withOpacity(0.1),
                          labelStyle: TextStyle(
                            color: dream.status == 'active' ? AppTheme.success : Colors.grey,
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 12),
                    if (dream.description.isNotEmpty) ...[
                      Text(dream.description, style: Theme.of(context).textTheme.bodyLarge),
                      const SizedBox(height: 16),
                    ],
                    Row(
                      children: [
                        Expanded(
                          child: ClipRRect(
                            borderRadius: BorderRadius.circular(8),
                            child: LinearProgressIndicator(
                              value: dream.progress / 100,
                              minHeight: 12,
                              backgroundColor: AppTheme.primaryPurple.withOpacity(0.1),
                              color: AppTheme.primaryPurple,
                            ),
                          ),
                        ),
                        const SizedBox(width: 12),
                        Text(
                          '${dream.progress.toInt()}%',
                          style: Theme.of(context).textTheme.titleMedium?.copyWith(
                            fontWeight: FontWeight.bold,
                            color: AppTheme.primaryPurple,
                          ),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 16),
            // Goals
            Text(
              'Goals (${_goals.length})',
              style: Theme.of(context).textTheme.titleMedium?.copyWith(
                fontWeight: FontWeight.bold,
              ),
            ),
            const SizedBox(height: 8),
            if (_goals.isEmpty)
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(24),
                  child: Column(
                    children: [
                      Icon(Icons.flag_outlined, size: 48, color: Colors.grey[300]),
                      const SizedBox(height: 8),
                      const Text('No goals yet. Generate an AI plan!'),
                    ],
                  ),
                ),
              )
            else
              ..._goals.map((goal) => _GoalCard(
                goal: goal,
                onTaskComplete: (taskId) async {
                  await ref.read(dreamsProvider.notifier).completeTask(taskId);
                  _loadData();
                },
                onMicroStart: (taskId) => context.push('/micro-start/$taskId'),
                dreamsNotifier: ref.read(dreamsProvider.notifier),
              )),
          ],
        ),
      ),
    );
  }
}

class _GoalCard extends StatefulWidget {
  final Goal goal;
  final Function(String) onTaskComplete;
  final Function(String) onMicroStart;
  final DreamsNotifier dreamsNotifier;

  const _GoalCard({
    required this.goal,
    required this.onTaskComplete,
    required this.onMicroStart,
    required this.dreamsNotifier,
  });

  @override
  State<_GoalCard> createState() => _GoalCardState();
}

class _GoalCardState extends State<_GoalCard> {
  bool _expanded = false;
  List<dynamic> _tasks = [];
  bool _loadingTasks = false;

  Future<void> _loadTasks() async {
    if (_tasks.isNotEmpty) return;
    setState(() => _loadingTasks = true);
    try {
      final tasks = await widget.dreamsNotifier.getTasks(widget.goal.id);
      setState(() {
        _tasks = tasks;
        _loadingTasks = false;
      });
    } catch (_) {
      setState(() => _loadingTasks = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      child: Column(
        children: [
          ListTile(
            leading: CircleAvatar(
              radius: 16,
              backgroundColor: widget.goal.isCompleted
                  ? AppTheme.success
                  : AppTheme.primaryPurple.withOpacity(0.1),
              child: widget.goal.isCompleted
                  ? const Icon(Icons.check, color: Colors.white, size: 16)
                  : Text(
                      '${widget.goal.orderIndex + 1}',
                      style: TextStyle(
                        color: AppTheme.primaryPurple,
                        fontWeight: FontWeight.bold,
                        fontSize: 12,
                      ),
                    ),
            ),
            title: Text(
              widget.goal.title,
              style: TextStyle(
                fontWeight: FontWeight.w600,
                decoration: widget.goal.isCompleted
                    ? TextDecoration.lineThrough
                    : null,
              ),
            ),
            subtitle: Text(
              '${widget.goal.completedTaskCount}/${widget.goal.taskCount} tasks',
            ),
            trailing: IconButton(
              icon: Icon(_expanded ? Icons.expand_less : Icons.expand_more),
              onPressed: () {
                setState(() => _expanded = !_expanded);
                if (_expanded) _loadTasks();
              },
            ),
          ),
          if (_expanded) ...[
            if (_loadingTasks)
              const Padding(
                padding: EdgeInsets.all(16),
                child: CircularProgressIndicator(),
              )
            else
              ..._tasks.map((task) => TaskTile(
                task: task,
                onComplete: () => widget.onTaskComplete(task.id),
                onMicroStart: () => widget.onMicroStart(task.id),
              )),
            const SizedBox(height: 8),
          ],
        ],
      ),
    );
  }
}
