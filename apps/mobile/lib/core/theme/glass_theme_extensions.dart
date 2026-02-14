import 'package:flutter/material.dart';

class GlassTheme extends ThemeExtension<GlassTheme> {
  final Color glassColor;
  final double glassOpacity;
  final double blurSigma;
  final double borderOpacity;
  final Color textPrimary;
  final Color textSecondary;

  const GlassTheme({
    required this.glassColor,
    required this.glassOpacity,
    required this.blurSigma,
    required this.borderOpacity,
    required this.textPrimary,
    required this.textSecondary,
  });

  static const light = GlassTheme(
    glassColor: Colors.white,
    glassOpacity: 0.18,
    blurSigma: 20.0,
    borderOpacity: 0.25,
    textPrimary: Color(0xFF1E1B4B),
    textSecondary: Color(0xFF6B7280),
  );

  static const dark = GlassTheme(
    glassColor: Colors.white,
    glassOpacity: 0.12,
    blurSigma: 20.0,
    borderOpacity: 0.2,
    textPrimary: Colors.white,
    textSecondary: Color(0xFFD1D5DB),
  );

  @override
  GlassTheme copyWith({
    Color? glassColor,
    double? glassOpacity,
    double? blurSigma,
    double? borderOpacity,
    Color? textPrimary,
    Color? textSecondary,
  }) {
    return GlassTheme(
      glassColor: glassColor ?? this.glassColor,
      glassOpacity: glassOpacity ?? this.glassOpacity,
      blurSigma: blurSigma ?? this.blurSigma,
      borderOpacity: borderOpacity ?? this.borderOpacity,
      textPrimary: textPrimary ?? this.textPrimary,
      textSecondary: textSecondary ?? this.textSecondary,
    );
  }

  @override
  GlassTheme lerp(covariant ThemeExtension<GlassTheme>? other, double t) {
    if (other is! GlassTheme) return this;
    return GlassTheme(
      glassColor: Color.lerp(glassColor, other.glassColor, t)!,
      glassOpacity: _lerpDouble(glassOpacity, other.glassOpacity, t),
      blurSigma: _lerpDouble(blurSigma, other.blurSigma, t),
      borderOpacity: _lerpDouble(borderOpacity, other.borderOpacity, t),
      textPrimary: Color.lerp(textPrimary, other.textPrimary, t)!,
      textSecondary: Color.lerp(textSecondary, other.textSecondary, t)!,
    );
  }

  static double _lerpDouble(double a, double b, double t) => a + (b - a) * t;
}
