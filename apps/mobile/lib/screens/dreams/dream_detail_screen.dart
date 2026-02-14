import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../core/theme/app_theme.dart';
import '../../models/dream.dart';
import '../../models/goal.dart';
import '../../providers/dreams_provider.dart';
import '../../services/api_service.dart';
import '../../widgets/task_tile.dart';
import '../../widgets/gradient_background.dart';
import '../../widgets/glass_container.dart';
import '../../widgets/glass_app_bar.dart';
import '../../widgets/animated_progress_ring.dart';
import '../../widgets/animated_list_item.dart';
import '../../widgets/loading_shimmer.dart';

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
      setState(() { _dream = dream; _goals = goals; _isLoading = false; });
    } catch (_) {
      setState(() => _isLoading = false);
    }
  }

  Future<void> _changeStatus(String newStatus) async {
    try {
      await ref.read(dreamsProvider.notifier).updateDream(widget.dreamId, {'status': newStatus});
      _loadData();
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Error: $e')));
    }
  }

  void _showAddGoalDialog() {
    final titleC = TextEditingController();
    final descC = TextEditingController();
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Add Goal'),
        content: Column(mainAxisSize: MainAxisSize.min, children: [
          TextField(controller: titleC, decoration: const InputDecoration(labelText: 'Title', border: OutlineInputBorder())),
          const SizedBox(height: 12),
          TextField(controller: descC, decoration: const InputDecoration(labelText: 'Description', border: OutlineInputBorder()), maxLines: 2),
        ]),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Cancel')),
          FilledButton(
            onPressed: () async {
              if (titleC.text.trim().isEmpty) return;
              Navigator.pop(ctx);
              await ref.read(dreamsProvider.notifier).createGoal(widget.dreamId, {'title': titleC.text.trim(), 'description': descC.text.trim(), 'order': _goals.length});
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
        content: Column(mainAxisSize: MainAxisSize.min, children: [
          TextField(controller: titleC, decoration: const InputDecoration(labelText: 'Title', border: OutlineInputBorder())),
          const SizedBox(height: 12),
          TextField(controller: descC, decoration: const InputDecoration(labelText: 'Description', border: OutlineInputBorder()), maxLines: 2),
        ]),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Cancel')),
          FilledButton(
            onPressed: () async {
              if (titleC.text.trim().isEmpty) return;
              Navigator.pop(ctx);
              await ref.read(dreamsProvider.notifier).updateGoal(goal.id, {'title': titleC.text.trim(), 'description': descC.text.trim()});
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
        content: TextField(controller: emailC, keyboardType: TextInputType.emailAddress, decoration: const InputDecoration(labelText: 'User email', border: OutlineInputBorder())),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Cancel')),
          FilledButton(
            onPressed: () async {
              if (emailC.text.trim().isEmpty) return;
              Navigator.pop(ctx);
              try {
                await ref.read(dreamsProvider.notifier).shareDream(dreamId, emailC.text.trim());
                if (mounted) ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Dream shared!')));
              } catch (e) {
                if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Error: $e')));
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
    final isDark = Theme.of(context).brightness == Brightness.dark;

    return GradientBackground(
      colors: isDark ? AppTheme.gradientDreams : AppTheme.gradientDreamsLight,
      child: Scaffold(
        backgroundColor: Colors.transparent,
        extendBodyBehindAppBar: true,
        appBar: _isLoading || _dream == null
            ? const GlassAppBar(title: 'Dream')
            : GlassAppBar(
                title: _dream!.title,
                actions: [
                  PopupMenuButton<String>(
                    icon: Icon(Icons.swap_horiz, color: isDark ? Colors.white : const Color(0xFF1E1B4B)),
                    tooltip: 'Change status',
                    onSelected: _changeStatus,
                    itemBuilder: (_) => [
                      for (final s in ['active', 'paused', 'archived', 'completed'])
                        PopupMenuItem(value: s, enabled: s != _dream!.status, child: Row(children: [
                          Icon(_statusIcon(s), size: 18, color: s == _dream!.status ? Colors.grey : null),
                          const SizedBox(width: 8),
                          Text(s[0].toUpperCase() + s.substring(1)),
                          if (s == _dream!.status) ...[const Spacer(), const Icon(Icons.check, size: 16)],
                        ])),
                    ],
                  ),
                  IconButton(
                    icon: Icon(Icons.chat_outlined, color: isDark ? Colors.white : const Color(0xFF1E1B4B)),
                    tooltip: 'AI Coach',
                    onPressed: () => context.push('/chat/${_dream!.id}'),
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
                        case 'edit': context.push('/dreams/${_dream!.id}/edit');
                        case 'calibrate': context.push('/dreams/${_dream!.id}/calibration');
                        case 'generate':
                          await ref.read(dreamsProvider.notifier).generatePlan(_dream!.id);
                          _loadData();
                        case 'vision': context.push('/vision-board/${_dream!.id}');
                        case 'duplicate':
                          try {
                            await ref.read(dreamsProvider.notifier).duplicateDream(_dream!.id);
                            if (mounted) ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Dream duplicated!')));
                          } catch (e) { if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Error: $e'))); }
                        case 'share': _showShareDialog(_dream!.id);
                        case 'export_pdf':
                          try {
                            final api = ref.read(apiServiceProvider);
                            await api.post('/dreams/${_dream!.id}/export-pdf/');
                            if (mounted) ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('PDF export started!')));
                          } catch (e) { if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Error: $e'))); }
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
                            await ref.read(dreamsProvider.notifier).deleteDream(_dream!.id);
                            context.pop();
                          }
                      }
                    },
                  ),
                ],
              ),
        body: _isLoading
            ? const Center(child: LoadingShimmer())
            : _dream == null
                ? Center(child: Text('Dream not found', style: TextStyle(color: isDark ? Colors.white54 : Colors.grey)))
                : RefreshIndicator(
                    onRefresh: _loadData,
                    child: ListView(
                      padding: EdgeInsets.fromLTRB(16, MediaQuery.of(context).padding.top + kToolbarHeight + 8, 16, 32),
                      children: [
                        // Progress hero card
                        Hero(
                          tag: 'dream-${_dream!.id}',
                          child: GlassContainer(
                            padding: const EdgeInsets.all(20),
                            opacity: isDark ? 0.12 : 0.25,
                            child: Column(
                              children: [
                                Row(
                                  children: [
                                    AnimatedProgressRing(
                                      progress: _dream!.progress / 100,
                                      size: 80,
                                      strokeWidth: 6,
                                      child: Text(
                                        '${_dream!.progress.toInt()}%',
                                        style: TextStyle(
                                          fontSize: 18,
                                          fontWeight: FontWeight.bold,
                                          color: isDark ? Colors.white : AppTheme.primaryPurple,
                                        ),
                                      ),
                                    ),
                                    const SizedBox(width: 16),
                                    Expanded(
                                      child: Column(
                                        crossAxisAlignment: CrossAxisAlignment.start,
                                        children: [
                                          Container(
                                            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                                            decoration: BoxDecoration(
                                              color: _statusColor(_dream!.status).withValues(alpha: 0.15),
                                              borderRadius: BorderRadius.circular(6),
                                            ),
                                            child: Text(
                                              _dream!.status.toUpperCase(),
                                              style: TextStyle(fontSize: 11, fontWeight: FontWeight.bold, color: _statusColor(_dream!.status)),
                                            ),
                                          ),
                                          if (_dream!.description.isNotEmpty) ...[
                                            const SizedBox(height: 8),
                                            Text(
                                              _dream!.description,
                                              style: TextStyle(fontSize: 14, color: isDark ? Colors.white70 : Colors.grey[700]),
                                              maxLines: 3,
                                              overflow: TextOverflow.ellipsis,
                                            ),
                                          ],
                                          const SizedBox(height: 8),
                                          Row(children: [
                                            Container(
                                              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                                              decoration: BoxDecoration(
                                                color: AppTheme.primaryPurple.withValues(alpha: 0.12),
                                                borderRadius: BorderRadius.circular(6),
                                              ),
                                              child: Text(_dream!.categoryLabel, style: TextStyle(fontSize: 11, color: isDark ? Colors.white70 : AppTheme.primaryPurple)),
                                            ),
                                            const SizedBox(width: 8),
                                            Icon(Icons.schedule, size: 13, color: isDark ? Colors.white30 : Colors.grey),
                                            const SizedBox(width: 4),
                                            Text(_dream!.timeframe.replaceAll('_', ' '), style: TextStyle(fontSize: 11, color: isDark ? Colors.white30 : Colors.grey)),
                                          ]),
                                        ],
                                      ),
                                    ),
                                  ],
                                ),
                              ],
                            ),
                          ),
                        ).animate().fadeIn(duration: 500.ms),
                        const SizedBox(height: 20),

                        // Goals header
                        Row(
                          children: [
                            Text('Goals (${_goals.length})', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: isDark ? Colors.white : const Color(0xFF1E1B4B))),
                            const Spacer(),
                            GestureDetector(
                              onTap: _showAddGoalDialog,
                              child: Container(
                                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
                                decoration: BoxDecoration(
                                  color: AppTheme.primaryPurple.withValues(alpha: 0.15),
                                  borderRadius: BorderRadius.circular(16),
                                  border: Border.all(color: AppTheme.primaryPurple.withValues(alpha: 0.3)),
                                ),
                                child: Row(mainAxisSize: MainAxisSize.min, children: [
                                  Icon(Icons.add, size: 14, color: AppTheme.primaryPurple),
                                  const SizedBox(width: 4),
                                  Text('Add Goal', style: TextStyle(fontSize: 12, color: AppTheme.primaryPurple, fontWeight: FontWeight.w600)),
                                ]),
                              ),
                            ),
                          ],
                        ).animate().fadeIn(duration: 400.ms, delay: 200.ms),
                        const SizedBox(height: 12),

                        if (_goals.isEmpty)
                          GlassContainer(
                            padding: const EdgeInsets.all(24),
                            opacity: isDark ? 0.08 : 0.15,
                            child: Column(children: [
                              Icon(Icons.flag_outlined, size: 48, color: isDark ? Colors.white24 : Colors.grey[600]),
                              const SizedBox(height: 8),
                              Text('No goals yet. Add one or generate an AI plan!', style: TextStyle(color: isDark ? Colors.white38 : Colors.grey[700])),
                            ]),
                          ).animate().fadeIn(duration: 400.ms, delay: 300.ms)
                        else
                          ..._goals.asMap().entries.map((entry) => AnimatedListItem(
                            index: entry.key,
                            child: _GoalCard(
                              goal: entry.value,
                              isDark: isDark,
                              onTaskComplete: (taskId) async {
                                await ref.read(dreamsProvider.notifier).completeTask(taskId);
                                _loadData();
                              },
                              onMicroStart: (taskId) => context.push('/micro-start/$taskId'),
                              onEditGoal: () => _showEditGoalDialog(entry.value),
                              onDeleteGoal: () => _deleteGoal(entry.value),
                              dreamsNotifier: ref.read(dreamsProvider.notifier),
                              onReload: _loadData,
                            ),
                          )),
                      ],
                    ),
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
  final bool isDark;
  final Function(String) onTaskComplete;
  final Function(String) onMicroStart;
  final VoidCallback onEditGoal;
  final VoidCallback onDeleteGoal;
  final DreamsNotifier dreamsNotifier;
  final VoidCallback onReload;

  const _GoalCard({
    required this.goal, required this.isDark, required this.onTaskComplete,
    required this.onMicroStart, required this.onEditGoal, required this.onDeleteGoal,
    required this.dreamsNotifier, required this.onReload,
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
      setState(() { _tasks = tasks; _loadingTasks = false; });
    } catch (_) { setState(() => _loadingTasks = false); }
  }

  void _showAddTaskDialog() {
    final titleC = TextEditingController();
    final descC = TextEditingController();
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Add Task'),
        content: Column(mainAxisSize: MainAxisSize.min, children: [
          TextField(controller: titleC, decoration: const InputDecoration(labelText: 'Title', border: OutlineInputBorder())),
          const SizedBox(height: 12),
          TextField(controller: descC, decoration: const InputDecoration(labelText: 'Description', border: OutlineInputBorder()), maxLines: 2),
        ]),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Cancel')),
          FilledButton(
            onPressed: () async {
              if (titleC.text.trim().isEmpty) return;
              Navigator.pop(ctx);
              await widget.dreamsNotifier.createTask(widget.goal.id, {'title': titleC.text.trim(), 'description': descC.text.trim(), 'order': _tasks.length});
              _tasks = []; await _loadTasks(); widget.onReload();
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
        content: Column(mainAxisSize: MainAxisSize.min, children: [
          TextField(controller: titleC, decoration: const InputDecoration(labelText: 'Title', border: OutlineInputBorder())),
          const SizedBox(height: 12),
          TextField(controller: descC, decoration: const InputDecoration(labelText: 'Description', border: OutlineInputBorder()), maxLines: 2),
        ]),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Cancel')),
          FilledButton(
            onPressed: () async {
              if (titleC.text.trim().isEmpty) return;
              Navigator.pop(ctx);
              await widget.dreamsNotifier.updateTask(task.id, {'title': titleC.text.trim(), 'description': descC.text.trim()});
              _tasks = []; await _loadTasks();
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
    _tasks = []; await _loadTasks(); widget.onReload();
  }

  @override
  Widget build(BuildContext context) {
    return GlassContainer(
      margin: const EdgeInsets.only(bottom: 10),
      opacity: widget.isDark ? 0.1 : 0.2,
      child: Column(
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(12, 12, 4, 4),
            child: Row(
              children: [
                Container(
                  width: 32, height: 32,
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    color: widget.goal.isCompleted
                        ? AppTheme.success
                        : AppTheme.primaryPurple.withValues(alpha: 0.15),
                  ),
                  child: Center(child: widget.goal.isCompleted
                      ? const Icon(Icons.check, color: Colors.white, size: 16)
                      : Text('${widget.goal.orderIndex + 1}', style: TextStyle(color: AppTheme.primaryPurple, fontWeight: FontWeight.bold, fontSize: 13))),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      GestureDetector(
                        onTap: widget.onEditGoal,
                        child: Text(widget.goal.title, style: TextStyle(
                          fontWeight: FontWeight.w600, fontSize: 15,
                          decoration: widget.goal.isCompleted ? TextDecoration.lineThrough : null,
                          color: widget.isDark ? Colors.white : const Color(0xFF1E1B4B),
                        )),
                      ),
                      const SizedBox(height: 2),
                      Text('${widget.goal.completedTaskCount}/${widget.goal.taskCount} tasks', style: TextStyle(fontSize: 12, color: widget.isDark ? Colors.white38 : Colors.grey)),
                    ],
                  ),
                ),
                IconButton(icon: Icon(Icons.delete_outline, size: 18, color: widget.isDark ? Colors.white30 : Colors.grey), onPressed: widget.onDeleteGoal),
                IconButton(
                  icon: Icon(_expanded ? Icons.expand_less : Icons.expand_more, color: widget.isDark ? Colors.white54 : Colors.grey),
                  onPressed: () { setState(() => _expanded = !_expanded); if (_expanded) _loadTasks(); },
                ),
              ],
            ),
          ),
          AnimatedCrossFade(
            duration: AppTheme.animNormal,
            crossFadeState: _expanded ? CrossFadeState.showSecond : CrossFadeState.showFirst,
            firstChild: const SizedBox.shrink(),
            secondChild: Padding(
              padding: const EdgeInsets.fromLTRB(12, 0, 12, 12),
              child: Column(children: [
                if (_loadingTasks)
                  const Padding(padding: EdgeInsets.all(16), child: CircularProgressIndicator())
                else ...[
                  ..._tasks.map((task) => Dismissible(
                    key: Key(task.id),
                    direction: DismissDirection.endToStart,
                    background: Container(
                      alignment: Alignment.centerRight, padding: const EdgeInsets.only(right: 16),
                      decoration: BoxDecoration(color: Colors.red.withValues(alpha: 0.1), borderRadius: BorderRadius.circular(12)),
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
                    child: GestureDetector(onTap: () => _showEditTaskDialog(task), child: TaskTile(
                      task: task,
                      onComplete: () => widget.onTaskComplete(task.id),
                      onMicroStart: () => widget.onMicroStart(task.id),
                    )),
                  )),
                  GestureDetector(
                    onTap: _showAddTaskDialog,
                    child: Container(
                      width: double.infinity, padding: const EdgeInsets.symmetric(vertical: 10),
                      decoration: BoxDecoration(
                        border: Border.all(color: AppTheme.primaryPurple.withValues(alpha: 0.3), width: 1),
                        borderRadius: BorderRadius.circular(10),
                        color: AppTheme.primaryPurple.withValues(alpha: 0.05),
                      ),
                      child: Row(mainAxisAlignment: MainAxisAlignment.center, children: [
                        Icon(Icons.add, size: 16, color: AppTheme.primaryPurple),
                        const SizedBox(width: 4),
                        Text('Add Task', style: TextStyle(color: AppTheme.primaryPurple, fontWeight: FontWeight.w500, fontSize: 13)),
                      ]),
                    ),
                  ),
                ],
              ]),
            ),
          ),
        ],
      ),
    );
  }
}
