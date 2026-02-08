import 'package:flutter/material.dart';
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
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      child: Wrap(
        spacing: 8,
        runSpacing: 8,
        children: suggestions.map((text) => ActionChip(
          label: Text(text, style: const TextStyle(fontSize: 13)),
          backgroundColor: AppTheme.primaryPurple.withOpacity(0.08),
          side: BorderSide(color: AppTheme.primaryPurple.withOpacity(0.3)),
          onPressed: () => onSelected(text),
        )).toList(),
      ),
    );
  }
}
