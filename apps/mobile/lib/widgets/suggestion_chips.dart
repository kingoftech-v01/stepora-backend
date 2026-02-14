import 'dart:ui';
import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import '../core/theme/app_theme.dart';

class SuggestionChips extends StatelessWidget {
  final List<String> suggestions;
  final Function(String) onSelected;

  const SuggestionChips({
    super.key,
    required this.suggestions,
    required this.onSelected,
  });

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      child: Wrap(
        spacing: 8,
        runSpacing: 8,
        children: suggestions.asMap().entries.map((entry) {
          final index = entry.key;
          final text = entry.value;
          return GestureDetector(
            onTap: () => onSelected(text),
            child: ClipRRect(
              borderRadius: BorderRadius.circular(20),
              child: BackdropFilter(
                filter: ImageFilter.blur(sigmaX: 8, sigmaY: 8),
                child: Container(
                  padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
                  decoration: BoxDecoration(
                    color: isDark
                        ? Colors.white.withValues(alpha: 0.08)
                        : Colors.white.withValues(alpha: 0.3),
                    borderRadius: BorderRadius.circular(20),
                    border: Border.all(
                      color: AppTheme.primaryPurple.withValues(alpha: 0.3),
                    ),
                  ),
                  child: Text(
                    text,
                    style: TextStyle(
                      fontSize: 13,
                      color: isDark ? Colors.white : AppTheme.primaryPurple,
                    ),
                  ),
                ),
              ),
            ),
          )
              .animate()
              .fadeIn(
                duration: 300.ms,
                delay: Duration(milliseconds: index * 60),
                curve: Curves.easeOutCubic,
              )
              .slideX(
                begin: 0.1,
                end: 0,
                duration: 300.ms,
                delay: Duration(milliseconds: index * 60),
                curve: Curves.easeOutCubic,
              );
        }).toList(),
      ),
    );
  }
}
