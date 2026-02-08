import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../core/theme/app_theme.dart';
import '../../models/dream.dart';
import '../../models/goal.dart';
import '../../providers/dreams_provider.dart';
import '../../services/api_service.dart';
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

  Future<void> _changeStatus(String newStatus) async {
    try {
      await ref.read(dreamsProvider.notifier).updateDream(widget.dreamId, {'status': newStatus});
      _loadData();
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Error: $e')));
      }
    }
  }

  void _showAddGoalDialog() {
    final titleC = TextEditingController();
    final descC = TextEditingController();
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Add Goal'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextField(controller: titleC, decoration: const InputDecoration(labelText: 'Title', border: OutlineInputBorder())),
            const SizedBox(height: 12),
            TextField(controller: descC, decoration: const InputDecoration(labelText: 'Description', border: OutlineInputBorder()), maxLines: 2),
          ],
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Cancel')),
          FilledButton(
            onPressed: () async {
              if (titleC.text.trim().isEmpty) return;
              Navigator.pop(ctx);
              await ref.read(dreamsProvider.notifier).createGoal(widget.dreamId, {
                'title': titleC.text.trim(),
                'description': descC.text.trim(),
                'order': _goals.length,
              });
              _loadData();
            },
            style: FilledButton.styleFrom(backgroundColor: AppTheme.primaryPurple),
            child: const Text('Add'),
          ),
        ],
      ),
    );
  }

  void _showEditGoalDialog(Goal goal) {
    final titleC = TextEditingController(text: goal.title);
    final descC = TextEditingController(text: goal.description);
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Edit Goal'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextField(controller: titleC, decoration: const InputDecoration(labelText: 'Title', border: OutlineInputBorder())),
            const SizedBox(height: 12),
            TextField(controller: descC, decoration: const InputDecoration(labelText: 'Description', border: OutlineInputBorder()), maxLines: 2),
          ],
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Cancel')),
          FilledButton(
            onPressed: () async {
              if (titleC.text.trim().isEmpty) return;
              Navigator.pop(ctx);
              await ref.read(dreamsProvider.notifier).updateGoal(goal.id, {
                'title': titleC.text.trim(),
                'description': descC.text.trim(),
              });
              _loadData();
            },
            style: FilledButton.styleFrom(backgroundColor: AppTheme.primaryPurple),
            child: const Text('Save'),
          ),
        ],
      ),
    );
  }

  Future<void> _deleteGoal(Goal goal) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Delete Goal?'),
        content: Text('Delete "${goal.title}" and all its tasks?'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancel')),
          TextButton(onPressed: () => Navigator.pop(ctx, true), child: const Text('Delete', style: TextStyle(color: Colors.red))),
        ],
      ),
    );
    if (confirmed != true) return;
    await ref.read(dreamsProvider.notifier).deleteGoal(goal.id);
    _loadData();
  }

  void _showShareDialog(String dreamId) {
    final emailC = TextEditingController();
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Share Dream'),
        content: TextField(
          controller: emailC,
          keyboardType: TextInputType.emailAddress,
          decoration: const InputDecoration(labelText: 'User email', border: OutlineInputBorder()),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Cancel')),
          FilledButton(
            onPressed: () async {
              if (emailC.text.trim().isEmpty) return;
              Navigator.pop(ctx);
              try {
                await ref.read(dreamsProvider.notifier).shareDream(dreamId, emailC.text.trim());
                if (mounted) {
                  ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Dream shared!')));
                }
              } catch (e) {
                if (mounted) {
                  ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Error: $e')));
                }
              }
            },
            style: FilledButton.styleFrom(backgroundColor: AppTheme.primaryPurple),
            child: const Text('Share'),
          ),
        ],
      ),
    );
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
          PopupMenuButton<String>(
            icon: const Icon(Icons.swap_horiz),
            tooltip: 'Change status',
            onSelected: _changeStatus,
            itemBuilder: (_) => [
              for (final s in ['active', 'paused', 'archived', 'completed'])
                PopupMenuItem(
                  value: s,
                  enabled: s != dream.status,
                  child: Row(
                    children: [
                      Icon(_statusIcon(s), size: 18, color: s == dream.status ? Colors.grey : null),
                      const SizedBox(width: 8),
                      Text(s[0].toUpperCase() + s.substring(1)),
                      if (s == dream.status) ...[const Spacer(), const Icon(Icons.check, size: 16)],
                    ],
                  ),
                ),
            ],
          ),
          IconButton(
            icon: const Icon(Icons.chat_outlined),
            tooltip: 'AI Coach',
            onPressed: () => context.push('/chat/${dream.id}'),
          ),
          PopupMenuButton(
            itemBuilder: (context) => [
              const PopupMenuItem(value: 'edit', child: Text('Edit Dream')),
              const PopupMenuItem(value: 'calibrate', child: Text('Calibration')),
              const PopupMenuItem(value: 'generate', child: Text('Generate Plan')),
              const PopupMenuItem(value: 'vision', child: Text('Vision Board')),
              const PopupMenuItem(value: 'duplicate', child: Text('Duplicate Dream')),
              const PopupMenuItem(value: 'share', child: Text('Share Dream')),
              const PopupMenuItem(value: 'export_pdf', child: Text('Export PDF')),
              const PopupMenuItem(value: 'delete', child: Text('Delete Dream')),
            ],
            onSelected: (value) async {
              switch (value) {
                case 'edit':
                  context.push('/dreams/${dream.id}/edit');
                case 'calibrate':
                  context.push('/dreams/${dream.id}/calibration');
                case 'generate':
                  await ref.read(dreamsProvider.notifier).generatePlan(dream.id);
                  _loadData();
                case 'vision':
                  context.push('/vision-board/${dream.id}');
                case 'duplicate':
                  try {
                    await ref.read(dreamsProvider.notifier).duplicateDream(dream.id);
                    if (mounted) {
                      ScaffoldMessenger.of(context).showSnackBar(
                        const SnackBar(content: Text('Dream duplicated!')),
                      );
                    }
                  } catch (e) {
                    if (mounted) {
                      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Error: $e')));
                    }
                  }
                case 'share':
                  _showShareDialog(dream.id);
                case 'export_pdf':
                  try {
                    final api = ref.read(apiServiceProvider);
                    await api.post('/dreams/${dream.id}/export-pdf/');
                    if (mounted) {
                      ScaffoldMessenger.of(context).showSnackBar(
                        const SnackBar(content: Text('PDF export started! You will receive a download link via email.')),
                      );
                    }
                  } catch (e) {
                    if (mounted) {
                      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Error: $e')));
                    }
                  }
                case 'delete':
                  final confirmed = await showDialog<bool>(
                    context: context,
                    builder: (ctx) => AlertDialog(
                      title: const Text('Delete Dream?'),
                      content: const Text('This action cannot be undone.'),
                      actions: [
                        TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancel')),
                        TextButton(onPressed: () => Navigator.pop(ctx, true), child: const Text('Delete', style: TextStyle(color: Colors.red))),
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
                          backgroundColor: AppTheme.primaryPurple.withValues(alpha: 0.1),
                          labelStyle: TextStyle(color: AppTheme.primaryPurple),
                        ),
                        const Spacer(),
                        Chip(
                          label: Text(dream.status.toUpperCase()),
                          backgroundColor: _statusColor(dream.status).withValues(alpha: 0.1),
                          labelStyle: TextStyle(color: _statusColor(dream.status)),
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
                              backgroundColor: AppTheme.primaryPurple.withValues(alpha: 0.1),
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

            // Goals header with add button
            Row(
              children: [
                Text(
                  'Goals (${_goals.length})',
                  style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.bold),
                ),
                const Spacer(),
                TextButton.icon(
                  onPressed: _showAddGoalDialog,
                  icon: const Icon(Icons.add, size: 18),
                  label: const Text('Add Goal'),
                ),
              ],
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
                      const Text('No goals yet. Add one or generate an AI plan!'),
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
                onEditGoal: () => _showEditGoalDialog(goal),
                onDeleteGoal: () => _deleteGoal(goal),
                dreamsNotifier: ref.read(dreamsProvider.notifier),
                onReload: _loadData,
              )),
          ],
        ),
      ),
    );
  }

  IconData _statusIcon(String status) {
    switch (status) {
      case 'active': return Icons.play_arrow;
      case 'paused': return Icons.pause;
      case 'archived': return Icons.archive;
      case 'completed': return Icons.check_circle;
      default: return Icons.circle;
    }
  }

  Color _statusColor(String status) {
    switch (status) {
      case 'active': return AppTheme.success;
      case 'paused': return Colors.orange;
      case 'archived': return Colors.grey;
      case 'completed': return Colors.blue;
      default: return Colors.grey;
    }
  }
}

class _GoalCard extends StatefulWidget {
  final Goal goal;
  final Function(String) onTaskComplete;
  final Function(String) onMicroStart;
  final VoidCallback onEditGoal;
  final VoidCallback onDeleteGoal;
  final DreamsNotifier dreamsNotifier;
  final VoidCallback onReload;

  const _GoalCard({
    required this.goal,
    required this.onTaskComplete,
    required this.onMicroStart,
    required this.onEditGoal,
    required this.onDeleteGoal,
    required this.dreamsNotifier,
    required this.onReload,
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

  void _showAddTaskDialog() {
    final titleC = TextEditingController();
    final descC = TextEditingController();
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Add Task'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextField(controller: titleC, decoration: const InputDecoration(labelText: 'Title', border: OutlineInputBorder())),
            const SizedBox(height: 12),
            TextField(controller: descC, decoration: const InputDecoration(labelText: 'Description', border: OutlineInputBorder()), maxLines: 2),
          ],
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Cancel')),
          FilledButton(
            onPressed: () async {
              if (titleC.text.trim().isEmpty) return;
              Navigator.pop(ctx);
              await widget.dreamsNotifier.createTask(widget.goal.id, {
                'title': titleC.text.trim(),
                'description': descC.text.trim(),
                'order': _tasks.length,
              });
              _tasks = [];
              await _loadTasks();
              widget.onReload();
            },
            style: FilledButton.styleFrom(backgroundColor: AppTheme.primaryPurple),
            child: const Text('Add'),
          ),
        ],
      ),
    );
  }

  void _showEditTaskDialog(dynamic task) {
    final titleC = TextEditingController(text: task.title);
    final descC = TextEditingController(text: task.description);
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Edit Task'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextField(controller: titleC, decoration: const InputDecoration(labelText: 'Title', border: OutlineInputBorder())),
            const SizedBox(height: 12),
            TextField(controller: descC, decoration: const InputDecoration(labelText: 'Description', border: OutlineInputBorder()), maxLines: 2),
          ],
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Cancel')),
          FilledButton(
            onPressed: () async {
              if (titleC.text.trim().isEmpty) return;
              Navigator.pop(ctx);
              await widget.dreamsNotifier.updateTask(task.id, {
                'title': titleC.text.trim(),
                'description': descC.text.trim(),
              });
              _tasks = [];
              await _loadTasks();
            },
            style: FilledButton.styleFrom(backgroundColor: AppTheme.primaryPurple),
            child: const Text('Save'),
          ),
        ],
      ),
    );
  }

  Future<void> _deleteTask(dynamic task) async {
    await widget.dreamsNotifier.deleteTask(task.id);
    _tasks = [];
    await _loadTasks();
    widget.onReload();
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
                  : AppTheme.primaryPurple.withValues(alpha: 0.1),
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
            title: GestureDetector(
              onTap: widget.onEditGoal,
              child: Text(
                widget.goal.title,
                style: TextStyle(
                  fontWeight: FontWeight.w600,
                  decoration: widget.goal.isCompleted ? TextDecoration.lineThrough : null,
                ),
              ),
            ),
            subtitle: Text(
              '${widget.goal.completedTaskCount}/${widget.goal.taskCount} tasks',
            ),
            trailing: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                IconButton(
                  icon: const Icon(Icons.delete_outline, size: 20),
                  onPressed: widget.onDeleteGoal,
                  tooltip: 'Delete goal',
                ),
                IconButton(
                  icon: Icon(_expanded ? Icons.expand_less : Icons.expand_more),
                  onPressed: () {
                    setState(() => _expanded = !_expanded);
                    if (_expanded) _loadTasks();
                  },
                ),
              ],
            ),
          ),
          if (_expanded) ...[
            if (_loadingTasks)
              const Padding(
                padding: EdgeInsets.all(16),
                child: CircularProgressIndicator(),
              )
            else ...[
              ..._tasks.map((task) => Dismissible(
                key: Key(task.id),
                direction: DismissDirection.endToStart,
                background: Container(
                  alignment: Alignment.centerRight,
                  padding: const EdgeInsets.only(right: 16),
                  color: Colors.red.shade50,
                  child: const Icon(Icons.delete, color: Colors.red),
                ),
                confirmDismiss: (_) async => await showDialog<bool>(
                  context: context,
                  builder: (ctx) => AlertDialog(
                    title: const Text('Delete Task?'),
                    actions: [
                      TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancel')),
                      TextButton(onPressed: () => Navigator.pop(ctx, true), child: const Text('Delete', style: TextStyle(color: Colors.red))),
                    ],
                  ),
                ) ?? false,
                onDismissed: (_) => _deleteTask(task),
                child: GestureDetector(
                  onTap: () => _showEditTaskDialog(task),
                  child: TaskTile(
                    task: task,
                    onComplete: () => widget.onTaskComplete(task.id),
                    onMicroStart: () => widget.onMicroStart(task.id),
                  ),
                ),
              )),
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                child: OutlinedButton.icon(
                  onPressed: _showAddTaskDialog,
                  icon: const Icon(Icons.add, size: 18),
                  label: const Text('Add Task'),
                  style: OutlinedButton.styleFrom(
                    minimumSize: const Size(double.infinity, 36),
                  ),
                ),
              ),
            ],
          ],
        ],
      ),
    );
  }
}
