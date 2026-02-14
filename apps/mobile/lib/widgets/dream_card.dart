import 'package:flutter/material.dart';
import '../core/theme/app_theme.dart';
import '../models/dream.dart';
import 'glass_container.dart';
import 'animated_progress_bar.dart';

class DreamCard extends StatefulWidget {
  final Dream dream;
  final VoidCallback? onTap;

  const DreamCard({super.key, required this.dream, this.onTap});

  @override
  State<DreamCard> createState() => _DreamCardState();
}

class _DreamCardState extends State<DreamCard> {
  bool _isPressed = false;

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    return GestureDetector(
      onTapDown: (_) => setState(() => _isPressed = true),
      onTapUp: (_) {
        setState(() => _isPressed = false);
        widget.onTap?.call();
      },
      onTapCancel: () => setState(() => _isPressed = false),
      child: AnimatedScale(
        scale: _isPressed ? 0.98 : 1.0,
        duration: const Duration(milliseconds: 150),
        curve: Curves.easeOutCubic,
        child: Hero(
          tag: 'dream-${widget.dream.id}',
          child: GlassContainer(
            margin: const EdgeInsets.only(bottom: 12),
            padding: const EdgeInsets.all(16),
            opacity: isDark ? 0.12 : 0.25,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Container(
                      padding: const EdgeInsets.all(8),
                      decoration: BoxDecoration(
                        color: AppTheme.primaryPurple.withValues(alpha: 0.15),
                        borderRadius: BorderRadius.circular(10),
                      ),
                      child: Icon(
                        _getCategoryIcon(),
                        color: AppTheme.primaryPurple,
                        size: 20,
                      ),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Text(
                        widget.dream.title,
                        style: TextStyle(
                          fontWeight: FontWeight.bold,
                          fontSize: 16,
                          color: isDark ? Colors.white : const Color(0xFF1E1B4B),
                        ),
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ),
                    ),
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                      decoration: BoxDecoration(
                        color: AppTheme.primaryPurple.withValues(alpha: 0.12),
                        borderRadius: BorderRadius.circular(8),
                        border: Border.all(
                          color: AppTheme.primaryPurple.withValues(alpha: 0.2),
                        ),
                      ),
                      child: Text(
                        widget.dream.categoryLabel,
                        style: TextStyle(
                          fontSize: 11,
                          color: isDark ? Colors.white70 : AppTheme.primaryPurple,
                          fontWeight: FontWeight.w500,
                        ),
                      ),
                    ),
                  ],
                ),
                if (widget.dream.description.isNotEmpty) ...[
                  const SizedBox(height: 10),
                  Text(
                    widget.dream.description,
                    style: TextStyle(
                      fontSize: 14,
                      color: isDark ? Colors.white60 : Colors.grey[600],
                    ),
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                  ),
                ],
                const SizedBox(height: 14),
                Row(
                  children: [
                    Expanded(
                      child: AnimatedProgressBar(
                        progress: widget.dream.progress / 100,
                        height: 6,
                        color: widget.dream.progress >= 100
                            ? AppTheme.success
                            : AppTheme.primaryPurple,
                      ),
                    ),
                    const SizedBox(width: 10),
                    Text(
                      '${widget.dream.progress.toInt()}%',
                      style: TextStyle(
                        fontWeight: FontWeight.bold,
                        color: isDark ? Colors.white : AppTheme.primaryPurple,
                        fontSize: 13,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 10),
                Row(
                  children: [
                    Icon(Icons.flag_outlined,
                        size: 14,
                        color: isDark ? Colors.white38 : Colors.grey[700]),
                    const SizedBox(width: 4),
                    Text(
                      '${widget.dream.completedGoalCount}/${widget.dream.goalCount} goals',
                      style: TextStyle(
                        fontSize: 12,
                        color: isDark ? Colors.white38 : Colors.grey[700],
                      ),
                    ),
                    const Spacer(),
                    Icon(Icons.schedule,
                        size: 14,
                        color: isDark ? Colors.white38 : Colors.grey[700]),
                    const SizedBox(width: 4),
                    Text(
                      widget.dream.timeframe.replaceAll('_', ' '),
                      style: TextStyle(
                        fontSize: 12,
                        color: isDark ? Colors.white38 : Colors.grey[700],
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

  IconData _getCategoryIcon() {
    switch (widget.dream.category) {
      case 'health': return Icons.favorite;
      case 'career': return Icons.work;
      case 'relationships': return Icons.people;
      case 'personal_growth': return Icons.psychology;
      case 'finance': return Icons.account_balance;
      case 'hobbies': return Icons.palette;
      default: return Icons.auto_awesome;
    }
  }
}
