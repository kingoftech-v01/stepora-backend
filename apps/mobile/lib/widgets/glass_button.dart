import 'package:flutter/material.dart';
import '../core/theme/app_theme.dart';

enum GlassButtonStyle { primary, secondary, danger }

class GlassButton extends StatefulWidget {
  final String label;
  final VoidCallback? onPressed;
  final bool isLoading;
  final GlassButtonStyle style;
  final IconData? icon;
  final double? width;

  const GlassButton({
    super.key,
    required this.label,
    this.onPressed,
    this.isLoading = false,
    this.style = GlassButtonStyle.primary,
    this.icon,
    this.width,
  });

  @override
  State<GlassButton> createState() => _GlassButtonState();
}

class _GlassButtonState extends State<GlassButton> {
  bool _isPressed = false;

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final isPrimary = widget.style == GlassButtonStyle.primary;
    final isDanger = widget.style == GlassButtonStyle.danger;

    final Color bgColor;
    final Color textColor;
    final Border? border;

    if (isPrimary) {
      bgColor = isDanger ? AppTheme.error : AppTheme.primaryPurple;
      textColor = Colors.white;
      border = null;
    } else if (isDanger) {
      bgColor = AppTheme.error.withValues(alpha: 0.1);
      textColor = AppTheme.error;
      border = Border.all(color: AppTheme.error.withValues(alpha: 0.3));
    } else {
      bgColor = isDark
          ? Colors.white.withValues(alpha: 0.08)
          : Colors.white.withValues(alpha: 0.5);
      textColor = isDark ? Colors.white : AppTheme.primaryPurple;
      border = Border.all(
        color: isDark
            ? Colors.white.withValues(alpha: 0.2)
            : AppTheme.primaryPurple.withValues(alpha: 0.2),
      );
    }

    return GestureDetector(
      onTapDown: (_) => setState(() => _isPressed = true),
      onTapUp: (_) {
        setState(() => _isPressed = false);
        widget.onPressed?.call();
      },
      onTapCancel: () => setState(() => _isPressed = false),
      child: AnimatedScale(
        scale: _isPressed ? 0.95 : 1.0,
        duration: const Duration(milliseconds: 150),
        curve: Curves.easeOutCubic,
        child: Container(
          width: widget.width ?? double.infinity,
          height: 52,
          decoration: BoxDecoration(
            color: isPrimary ? null : bgColor,
            borderRadius: BorderRadius.circular(AppTheme.radiusMd),
            gradient: isPrimary
                ? LinearGradient(
                    colors: [
                      isDanger ? AppTheme.error : AppTheme.primaryPurple,
                      isDanger ? const Color(0xFFDC2626) : AppTheme.primaryDark,
                    ],
                  )
                : null,
            border: border,
            boxShadow: isPrimary
                ? [
                    BoxShadow(
                      color: (isDanger ? AppTheme.error : AppTheme.primaryPurple)
                          .withValues(alpha: 0.3),
                      blurRadius: 8,
                      offset: const Offset(0, 2),
                    ),
                  ]
                : null,
          ),
          alignment: Alignment.center,
          child: widget.isLoading
              ? SizedBox(
                  width: 22,
                  height: 22,
                  child: CircularProgressIndicator(
                    strokeWidth: 2.5,
                    valueColor: AlwaysStoppedAnimation(textColor),
                  ),
                )
              : Row(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    if (widget.icon != null) ...[
                      Icon(widget.icon, color: textColor, size: 20),
                      const SizedBox(width: 8),
                    ],
                    Text(
                      widget.label,
                      style: TextStyle(
                        color: textColor,
                        fontWeight: FontWeight.w600,
                        fontSize: 16,
                      ),
                    ),
                  ],
                ),
        ),
      ),
    );
  }
}
