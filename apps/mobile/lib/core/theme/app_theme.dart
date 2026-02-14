import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'glass_theme_extensions.dart';

class AppTheme {
  // ── Brand Colors ──
  static const Color primaryPurple = Color(0xFF8B5CF6);
  static const Color primaryDark = Color(0xFF6D28D9);
  static const Color accent = Color(0xFFF59E0B);
  static const Color success = Color(0xFF10B981);
  static const Color error = Color(0xFFEF4444);
  static const Color warning = Color(0xFFF59E0B);

  // ── Gradient Palettes ──
  static const gradientAuth = [Color(0xFF1E1B4B), Color(0xFF4C1D95), Color(0xFF7C3AED)];
  static const gradientHome = [Color(0xFF0F172A), Color(0xFF1E1B4B), Color(0xFF312E81)];
  static const gradientDreams = [Color(0xFF1E1B4B), Color(0xFF3B0764), Color(0xFF6D28D9)];
  static const gradientCalendar = [Color(0xFF0C4A6E), Color(0xFF1E3A5F), Color(0xFF312E81)];
  static const gradientChat = [Color(0xFF172554), Color(0xFF1E1B4B), Color(0xFF4C1D95)];
  static const gradientSocial = [Color(0xFF14532D), Color(0xFF1E3A5F), Color(0xFF312E81)];
  static const gradientProfile = [Color(0xFF1E1B4B), Color(0xFF312E81), Color(0xFF4C1D95)];
  static const gradientStore = [Color(0xFF431407), Color(0xFF78350F), Color(0xFF4C1D95)];

  // ── Light Gradient Palettes ──
  static const gradientAuthLight = [Color(0xFFEDE9FE), Color(0xFFC4B5FD), Color(0xFFA78BFA)];
  static const gradientHomeLight = [Color(0xFFE0E7FF), Color(0xFFEDE9FE), Color(0xFFC4B5FD)];
  static const gradientDreamsLight = [Color(0xFFEDE9FE), Color(0xFFF3E8FF), Color(0xFFDDD6FE)];
  static const gradientCalendarLight = [Color(0xFFE0F2FE), Color(0xFFE0E7FF), Color(0xFFEDE9FE)];
  static const gradientChatLight = [Color(0xFFDBEAFE), Color(0xFFEDE9FE), Color(0xFFF3E8FF)];
  static const gradientSocialLight = [Color(0xFFD1FAE5), Color(0xFFE0E7FF), Color(0xFFEDE9FE)];
  static const gradientProfileLight = [Color(0xFFEDE9FE), Color(0xFFC4B5FD), Color(0xFFF3E8FF)];
  static const gradientStoreLight = [Color(0xFFFEF3C7), Color(0xFFFDE68A), Color(0xFFF3E8FF)];

  // ── Glass Constants ──
  static const double glassBlurSigma = 20.0;
  static const double glassOpacityLight = 0.18;
  static const double glassOpacityDark = 0.12;
  static const double glassBorderOpacity = 0.2;
  static const double glassDepthLevel1 = 0.05;
  static const double glassDepthLevel2 = 0.10;
  static const double glassDepthLevel3 = 0.15;
  static const double glassDepthLevel4 = 0.20;

  // ── Animation Durations ──
  static const Duration animFast = Duration(milliseconds: 200);
  static const Duration animNormal = Duration(milliseconds: 350);
  static const Duration animSlow = Duration(milliseconds: 500);
  static const Duration animStaggerDelay = Duration(milliseconds: 60);

  // ── Border Radius ──
  static const double radiusSm = 8.0;
  static const double radiusMd = 12.0;
  static const double radiusLg = 16.0;
  static const double radiusXl = 20.0;
  static const double radiusXxl = 28.0;

  static ThemeData get lightTheme {
    final textTheme = GoogleFonts.interTextTheme();
    return ThemeData(
      useMaterial3: true,
      colorScheme: ColorScheme.fromSeed(
        seedColor: primaryPurple,
        primary: primaryPurple,
        secondary: accent,
        brightness: Brightness.light,
      ),
      scaffoldBackgroundColor: Colors.transparent,
      textTheme: textTheme,
      appBarTheme: AppBarTheme(
        centerTitle: true,
        elevation: 0,
        backgroundColor: Colors.transparent,
        surfaceTintColor: Colors.transparent,
        titleTextStyle: textTheme.titleLarge?.copyWith(
          fontWeight: FontWeight.w600,
        ),
      ),
      cardTheme: CardThemeData(
        elevation: 0,
        color: Colors.transparent,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(radiusLg),
        ),
      ),
      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 14),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(radiusMd),
          ),
        ),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: Colors.white.withValues(alpha: 0.1),
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(radiusMd),
          borderSide: BorderSide.none,
        ),
        contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
      ),
      navigationBarTheme: NavigationBarThemeData(
        backgroundColor: Colors.transparent,
        indicatorColor: primaryPurple.withValues(alpha: 0.15),
        labelBehavior: NavigationDestinationLabelBehavior.alwaysShow,
      ),
      extensions: [GlassTheme.light],
    );
  }

  static ThemeData get darkTheme {
    final textTheme = GoogleFonts.interTextTheme(ThemeData.dark().textTheme);
    return ThemeData(
      useMaterial3: true,
      colorScheme: ColorScheme.fromSeed(
        seedColor: primaryPurple,
        primary: primaryPurple,
        secondary: accent,
        brightness: Brightness.dark,
      ),
      scaffoldBackgroundColor: Colors.transparent,
      textTheme: textTheme,
      appBarTheme: AppBarTheme(
        centerTitle: true,
        elevation: 0,
        backgroundColor: Colors.transparent,
        surfaceTintColor: Colors.transparent,
        titleTextStyle: textTheme.titleLarge?.copyWith(
          fontWeight: FontWeight.w600,
          color: Colors.white,
        ),
      ),
      cardTheme: CardThemeData(
        elevation: 0,
        color: Colors.transparent,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(radiusLg),
        ),
      ),
      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 14),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(radiusMd),
          ),
        ),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: Colors.white.withValues(alpha: 0.08),
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(radiusMd),
          borderSide: BorderSide.none,
        ),
        contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
      ),
      navigationBarTheme: NavigationBarThemeData(
        backgroundColor: Colors.transparent,
        indicatorColor: primaryPurple.withValues(alpha: 0.15),
        labelBehavior: NavigationDestinationLabelBehavior.alwaysShow,
      ),
      extensions: [GlassTheme.dark],
    );
  }
}
