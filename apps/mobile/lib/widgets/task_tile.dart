import 'package:flutter/material.dart';
import '../core/theme/app_theme.dart';
import '../models/task.dart';

class TaskTile extends StatelessWidget {
  final Task task;
  final VoidCallback? onComplete;
  final VoidCallback? onMicroStart;

  const TaskTile({
    super.key,
    required this.task,
    this.onComplete,
    this.onMicroStart,
  });

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 6),
      child: ListTile(
        leading: IconButton(
          icon: Icon(
            task.isCompleted ? Icons.check_circle : Icons.radio_button_unchecked,
            color: task.isCompleted ? AppTheme.success : Colors.grey[400],
          ),
          onPressed: task.isCompleted ? null : onComplete,
        ),
        title: Text(
          task.title,
          style: TextStyle(
            decoration: task.isCompleted ? TextDecoration.lineThrough : null,
            color: task.isCompleted ? Colors.grey[500] : null,
            fontWeight: FontWeight.w500,
          ),
        ),
        subtitle: Row(
          children: [
            _PriorityBadge(priority: task.priority),
            const SizedBox(width: 8),
            Icon(Icons.timer_outlined, size: 14, color: Colors.grey[500]),
            const SizedBox(width: 2),
            Text(
              '${task.estimatedMinutes}min',
              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                color: Colors.grey[500],
              ),
            ),
            const SizedBox(width: 8),
            Text(
              '+${task.xpReward} XP',
              style: TextStyle(
                fontSize: 11,
                color: AppTheme.accent,
                fontWeight: FontWeight.bold,
              ),
            ),
          ],
        ),
        trailing: task.isCompleted
            ? null
            : task.twoMinuteAction != null
                ? IconButton(
                    icon: Icon(Icons.rocket_launch, color: AppTheme.primaryPurple),
                    tooltip: '2-min start',
                    onPressed: onMicroStart,
                  )
                : null,
      ),
    );
  }
}

class _PriorityBadge extends StatelessWidget {
  final String priority;
  const _PriorityBadge({required this.priority});

  @override
  Widget build(BuildContext context) {
    final colors = {
      'high': AppTheme.error,
      'medium': AppTheme.warning,
      'low': AppTheme.success,
    };
    final color = colors[priority] ?? Colors.grey;

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(4),
      ),
      child: Text(
        priority.toUpperCase(),
        style: TextStyle(fontSize: 9, fontWeight: FontWeight.bold, color: color),
      ),
    );
  }
}
