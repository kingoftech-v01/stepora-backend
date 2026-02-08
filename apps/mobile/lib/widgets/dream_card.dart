import 'package:flutter/material.dart';
import '../core/theme/app_theme.dart';
import '../models/dream.dart';

class DreamCard extends StatelessWidget {
  final Dream dream;
  final VoidCallback? onTap;

  const DreamCard({super.key, required this.dream, this.onTap});

  @override
  Widget build(BuildContext context) {
    return Card(
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(16),
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Icon(_getCategoryIcon(), color: AppTheme.primaryPurple, size: 24),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      dream.title,
                      style: Theme.of(context).textTheme.titleMedium?.copyWith(
                        fontWeight: FontWeight.bold,
                      ),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                  Chip(
                    label: Text(
                      dream.categoryLabel,
                      style: const TextStyle(fontSize: 11),
                    ),
                    backgroundColor: AppTheme.primaryPurple.withOpacity(0.1),
                    labelStyle: TextStyle(color: AppTheme.primaryPurple),
                    visualDensity: VisualDensity.compact,
                    padding: EdgeInsets.zero,
                  ),
                ],
              ),
              if (dream.description.isNotEmpty) ...[
                const SizedBox(height: 8),
                Text(
                  dream.description,
                  style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                    color: Colors.grey[600],
                  ),
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                ),
              ],
              const SizedBox(height: 12),
              Row(
                children: [
                  Expanded(
                    child: ClipRRect(
                      borderRadius: BorderRadius.circular(6),
                      child: LinearProgressIndicator(
                        value: dream.progress / 100,
                        minHeight: 8,
                        backgroundColor: AppTheme.primaryPurple.withOpacity(0.1),
                        color: dream.progress >= 100
                            ? AppTheme.success
                            : AppTheme.primaryPurple,
                      ),
                    ),
                  ),
                  const SizedBox(width: 8),
                  Text(
                    '${dream.progress.toInt()}%',
                    style: TextStyle(
                      fontWeight: FontWeight.bold,
                      color: AppTheme.primaryPurple,
                      fontSize: 13,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 8),
              Row(
                children: [
                  Icon(Icons.flag_outlined, size: 14, color: Colors.grey[500]),
                  const SizedBox(width: 4),
                  Text(
                    '${dream.completedGoalCount}/${dream.goalCount} goals',
                    style: Theme.of(context).textTheme.bodySmall?.copyWith(
                      color: Colors.grey[500],
                    ),
                  ),
                  const Spacer(),
                  Icon(Icons.schedule, size: 14, color: Colors.grey[500]),
                  const SizedBox(width: 4),
                  Text(
                    dream.timeframe.replaceAll('_', ' '),
                    style: Theme.of(context).textTheme.bodySmall?.copyWith(
                      color: Colors.grey[500],
                    ),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }

  IconData _getCategoryIcon() {
    switch (dream.category) {
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
