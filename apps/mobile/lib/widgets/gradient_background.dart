import 'package:flutter/material.dart';

class GradientBackground extends StatelessWidget {
  final Widget child;
  final List<Color> colors;
  final bool animate;

  const GradientBackground({
    super.key,
    required this.child,
    required this.colors,
    this.animate = true,
  });

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    return Container(
      color: isDark ? const Color(0xFF1E1B4B) : const Color(0xFFEDE9FE),
      child: child,
    );
  }
}
