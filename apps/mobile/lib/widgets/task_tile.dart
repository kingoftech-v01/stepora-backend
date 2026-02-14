import 'package:flutter/material.dart';
import '../core/theme/app_theme.dart';
import '../models/task.dart';
import 'glass_container.dart';

class TaskTile extends StatefulWidget {
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
  State<TaskTile> createState() => _TaskTileState();
}

class _TaskTileState extends State<TaskTile>
    with SingleTickerProviderStateMixin {
  late AnimationController _controller;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 300),
    );
    if (widget.task.isCompleted) _controller.forward();
  }

  @override
  void didUpdateWidget(TaskTile oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (widget.task.isCompleted && !oldWidget.task.isCompleted) {
      _controller.forward();
    }
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    return GlassContainer(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
      opacity: isDark ? 0.1 : 0.2,
      child: Row(
        children: [
          GestureDetector(
            onTap: widget.task.isCompleted ? null : widget.onComplete,
            child: AnimatedBuilder(
              animation: _controller,
              builder: (context, child) {
                return Transform.scale(
                  scale: 1.0 + (_controller.value * 0.2),
                  child: Icon(
                    widget.task.isCompleted
                        ? Icons.check_circle
                        : Icons.radio_button_unchecked,
                    color: widget.task.isCompleted
                        ? AppTheme.success
                        : (isDark ? Colors.white38 : Colors.grey[600]),
                    size: 24,
                  ),
                );
              },
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  widget.task.title,
                  style: TextStyle(
                    decoration:
                        widget.task.isCompleted ? TextDecoration.lineThrough : null,
                    color: widget.task.isCompleted
                        ? (isDark ? Colors.white38 : Colors.grey[700])
                        : (isDark ? Colors.white : const Color(0xFF1E1B4B)),
                    fontWeight: FontWeight.w500,
                    fontSize: 14,
                  ),
                ),
                const SizedBox(height: 4),
                Row(
                  children: [
                    _PriorityBadge(priority: widget.task.priority, isDark: isDark),
                    const SizedBox(width: 8),
                    Icon(Icons.timer_outlined,
                        size: 13,
                        color: isDark ? Colors.white30 : Colors.grey[700]),
                    const SizedBox(width: 2),
                    Text(
                      '${widget.task.estimatedMinutes}min',
                      style: TextStyle(
                        fontSize: 11,
                        color: isDark ? Colors.white30 : Colors.grey[700],
                      ),
                    ),
                    const SizedBox(width: 8),
                    Text(
                      '+${widget.task.xpReward} XP',
                      style: TextStyle(
                        fontSize: 11,
                        color: AppTheme.accent,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),
          if (!widget.task.isCompleted && widget.task.twoMinuteAction != null)
            GestureDetector(
              onTap: widget.onMicroStart,
              child: Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: AppTheme.primaryPurple.withValues(alpha: 0.15),
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Icon(
                  Icons.rocket_launch,
                  color: AppTheme.primaryPurple,
                  size: 18,
                ),
              ),
            ),
        ],
      ),
    );
  }
}

class _PriorityBadge extends StatelessWidget {
  final String priority;
  final bool isDark;
  const _PriorityBadge({required this.priority, required this.isDark});

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
        color: color.withValues(alpha: isDark ? 0.2 : 0.1),
        borderRadius: BorderRadius.circular(4),
        border: Border.all(color: color.withValues(alpha: 0.3)),
      ),
      child: Text(
        priority.toUpperCase(),
        style: TextStyle(fontSize: 9, fontWeight: FontWeight.bold, color: color),
      ),
    );
  }
}
