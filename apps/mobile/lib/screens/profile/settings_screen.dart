import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:url_launcher/url_launcher.dart';
import '../../core/theme/app_theme.dart';
import '../../providers/auth_provider.dart';
import '../../providers/locale_provider.dart';
import '../../providers/theme_provider.dart';
import '../../services/api_service.dart';
import '../../widgets/gradient_background.dart';
import '../../widgets/glass_container.dart';
import '../../widgets/glass_app_bar.dart';
import '../../widgets/glass_button.dart';
import '../../widgets/glass_text_field.dart';
import '../../widgets/animated_list_item.dart';

class SettingsScreen extends ConsumerWidget {
  const SettingsScreen({super.key});

  static const _languages = {
    'en': 'English',
    'fr': 'Français',
    'es': 'Español',
    'de': 'Deutsch',
    'it': 'Italiano',
    'pt': 'Português',
    'nl': 'Nederlands',
    'pl': 'Polski',
    'ru': 'Русский',
    'hi': 'हिन्दी',
    'ar': 'العربية',
    'zh': '中文',
    'ja': '日本語',
    'ko': '한국어',
    'tr': 'Türkçe',
  };

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final user = ref.watch(authProvider).user;
    final currentTheme = ref.watch(themeProvider);
    final currentLocale = ref.watch(localeProvider);
    final currentLangCode = currentLocale?.languageCode ?? 'en';
    final isDark = Theme.of(context).brightness == Brightness.dark;

    return GradientBackground(
      colors: isDark ? AppTheme.gradientProfile : AppTheme.gradientProfileLight,
      child: Scaffold(
        backgroundColor: Colors.transparent,
        extendBodyBehindAppBar: true,
        appBar: const GlassAppBar(title: 'Settings'),
        body: ListView(
          padding: EdgeInsets.fromLTRB(16, MediaQuery.of(context).padding.top + kToolbarHeight + 8, 16, 32),
          children: [
            // Account Section
            _GlassSectionHeader(title: 'Account', isDark: isDark).animate().fadeIn(duration: 300.ms),
            const SizedBox(height: 8),
            ...[
              _GlassSettingsTile(
                icon: Icons.person_outline,
                title: 'Edit Profile',
                subtitle: user?.displayName ?? user?.email ?? '',
                isDark: isDark,
                onTap: () => context.push('/profile/edit'),
              ),
              _GlassSettingsTile(
                icon: Icons.email_outlined,
                title: 'Email',
                subtitle: user?.email ?? '',
                isDark: isDark,
                onTap: () => _showEmailDialog(context, user?.email, isDark),
              ),
              _GlassSettingsTile(
                icon: Icons.lock_outline,
                title: 'Change Password',
                isDark: isDark,
                onTap: () => context.push('/change-password'),
              ),
            ].asMap().entries.map((e) => AnimatedListItem(index: e.key, child: e.value)).toList(),

            const SizedBox(height: 16),
            _GlassSectionHeader(title: 'Appearance', isDark: isDark).animate().fadeIn(duration: 300.ms, delay: 100.ms),
            const SizedBox(height: 8),
            AnimatedListItem(
              index: 3,
              child: _GlassThemeTile(
                currentTheme: currentTheme,
                isDark: isDark,
                onChanged: (mode) => ref.read(themeProvider.notifier).setThemeMode(mode),
              ),
            ),

            const SizedBox(height: 16),
            _GlassSectionHeader(title: 'Preferences', isDark: isDark).animate().fadeIn(duration: 300.ms, delay: 200.ms),
            const SizedBox(height: 8),
            ...[
              _GlassSettingsTile(
                icon: Icons.language,
                title: 'Language',
                subtitle: _languages[currentLangCode] ?? 'English',
                isDark: isDark,
                onTap: () => _showLanguageSheet(context, ref, currentLangCode, isDark),
              ),
              _GlassSettingsTile(
                icon: Icons.access_time,
                title: 'Timezone',
                subtitle: user?.timezone ?? 'UTC',
                isDark: isDark,
                onTap: () => _showTimezoneDialog(context, ref, user?.timezone, isDark),
              ),
              _GlassSettingsTile(
                icon: Icons.notifications_outlined,
                title: 'Notifications',
                isDark: isDark,
                onTap: () => context.push('/notifications'),
              ),
              _GlassSettingsTile(
                icon: Icons.calendar_month,
                title: 'Google Calendar',
                subtitle: 'Sync your events',
                isDark: isDark,
                onTap: () => context.push('/google-calendar'),
              ),
            ].asMap().entries.map((e) => AnimatedListItem(index: e.key + 4, child: e.value)).toList(),

            const SizedBox(height: 16),
            _GlassSectionHeader(title: 'Subscription', isDark: isDark).animate().fadeIn(duration: 300.ms, delay: 300.ms),
            const SizedBox(height: 8),
            ...[
              _GlassSettingsTile(
                icon: Icons.workspace_premium,
                title: 'Manage Subscription',
                subtitle: user?.subscription ?? 'Free',
                isDark: isDark,
                onTap: () => context.push('/subscription'),
              ),
              _GlassSettingsTile(
                icon: Icons.store,
                title: 'Store',
                isDark: isDark,
                onTap: () => context.push('/store'),
              ),
            ].asMap().entries.map((e) => AnimatedListItem(index: e.key + 8, child: e.value)).toList(),

            const SizedBox(height: 16),
            _GlassSectionHeader(title: 'About', isDark: isDark).animate().fadeIn(duration: 300.ms, delay: 400.ms),
            const SizedBox(height: 8),
            ...[
              _GlassSettingsTile(
                icon: Icons.info_outline,
                title: 'App Version',
                subtitle: '1.0.0',
                isDark: isDark,
                onTap: () {
                  showAboutDialog(
                    context: context,
                    applicationName: 'DreamPlanner',
                    applicationVersion: '1.0.0',
                    applicationLegalese: '\u00a9 2024 DreamPlanner',
                  );
                },
              ),
              _GlassSettingsTile(
                icon: Icons.description_outlined,
                title: 'Terms of Service',
                isDark: isDark,
                onTap: () => launchUrl(Uri.parse('https://dreamplanner.app/terms')),
              ),
              _GlassSettingsTile(
                icon: Icons.privacy_tip_outlined,
                title: 'Privacy Policy',
                isDark: isDark,
                onTap: () => launchUrl(Uri.parse('https://dreamplanner.app/privacy')),
              ),
            ].asMap().entries.map((e) => AnimatedListItem(index: e.key + 10, child: e.value)).toList(),

            const SizedBox(height: 24),
            GlassButton(
              label: 'Sign Out',
              icon: Icons.logout,
              style: GlassButtonStyle.danger,
              onPressed: () => ref.read(authProvider.notifier).logout(),
            ).animate().fadeIn(duration: 500.ms, delay: 500.ms),
            const SizedBox(height: 12),
            _GlassDeleteAccountButton(ref: ref, isDark: isDark),
          ],
        ),
      ),
    );
  }

  void _showEmailDialog(BuildContext context, String? email, bool isDark) {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: isDark ? const Color(0xFF1E1B4B) : Colors.white,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
        title: Text('Email', style: TextStyle(color: isDark ? Colors.white : const Color(0xFF1E1B4B))),
        content: Text(
          'Your email is ${email ?? 'not set'}.\n\nTo change your email, please contact support.',
          style: TextStyle(color: isDark ? Colors.white70 : Colors.grey[700]),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: Text('OK', style: TextStyle(color: AppTheme.primaryPurple)),
          ),
        ],
      ),
    );
  }

  void _showLanguageSheet(BuildContext context, WidgetRef ref, String currentLangCode, bool isDark) {
    showModalBottomSheet(
      context: context,
      backgroundColor: Colors.transparent,
      builder: (ctx) => Container(
        decoration: BoxDecoration(
          color: isDark ? const Color(0xFF1E1B4B).withValues(alpha: 0.95) : Colors.white.withValues(alpha: 0.95),
          borderRadius: const BorderRadius.vertical(top: Radius.circular(24)),
        ),
        child: SafeArea(
          child: ListView(
            shrinkWrap: true,
            children: [
              Center(
                child: Container(
                  margin: const EdgeInsets.only(top: 12),
                  width: 40, height: 4,
                  decoration: BoxDecoration(color: isDark ? Colors.white24 : Colors.grey[600], borderRadius: BorderRadius.circular(2)),
                ),
              ),
              Padding(
                padding: const EdgeInsets.all(16),
                child: Text('Select Language', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: isDark ? Colors.white : const Color(0xFF1E1B4B))),
              ),
              ..._languages.entries.map((entry) => ListTile(
                title: Text(entry.value, style: TextStyle(color: isDark ? Colors.white : const Color(0xFF1E1B4B))),
                trailing: entry.key == currentLangCode
                    ? Icon(Icons.check_circle, color: AppTheme.primaryPurple)
                    : null,
                onTap: () {
                  ref.read(localeProvider.notifier).setLocale(entry.key);
                  Navigator.pop(ctx);
                  ScaffoldMessenger.of(context).showSnackBar(
                    SnackBar(content: Text('Language set to ${entry.value}')),
                  );
                },
              )),
              const SizedBox(height: 16),
            ],
          ),
        ),
      ),
    );
  }

  void _showTimezoneDialog(BuildContext context, WidgetRef ref, String? timezone, bool isDark) {
    final controller = TextEditingController(text: timezone ?? 'UTC');
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: isDark ? const Color(0xFF1E1B4B) : Colors.white,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
        title: Text('Set Timezone', style: TextStyle(color: isDark ? Colors.white : const Color(0xFF1E1B4B))),
        content: GlassTextField(controller: controller, label: 'Timezone', hint: 'e.g. America/New_York'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: Text('Cancel', style: TextStyle(color: isDark ? Colors.white54 : Colors.grey)),
          ),
          GlassButton(
            label: 'Save',
            onPressed: () async {
              try {
                final api = ref.read(apiServiceProvider);
                await api.patch('/users/me/', data: {'timezone': controller.text});
                await ref.read(authProvider.notifier).refreshUser();
                if (ctx.mounted) Navigator.pop(ctx);
              } catch (e) {
                if (ctx.mounted) {
                  ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Error: $e')));
                }
              }
            },
          ),
        ],
      ),
    );
  }
}

class _GlassSectionHeader extends StatelessWidget {
  final String title;
  final bool isDark;
  const _GlassSectionHeader({required this.title, required this.isDark});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(left: 4, top: 8),
      child: Text(
        title.toUpperCase(),
        style: TextStyle(
          fontSize: 12,
          fontWeight: FontWeight.w700,
          color: isDark ? Colors.white38 : Colors.grey[700],
          letterSpacing: 1.2,
        ),
      ),
    );
  }
}

class _GlassSettingsTile extends StatelessWidget {
  final IconData icon;
  final String title;
  final String? subtitle;
  final bool isDark;
  final VoidCallback onTap;
  const _GlassSettingsTile({required this.icon, required this.title, this.subtitle, required this.isDark, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 6),
      child: GlassContainer(
        opacity: isDark ? 0.1 : 0.2,
        child: Material(
          color: Colors.transparent,
          child: InkWell(
            borderRadius: BorderRadius.circular(16),
            onTap: onTap,
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
              child: Row(
                children: [
                  Container(
                    padding: const EdgeInsets.all(8),
                    decoration: BoxDecoration(
                      color: AppTheme.primaryPurple.withValues(alpha: isDark ? 0.2 : 0.1),
                      borderRadius: BorderRadius.circular(10),
                    ),
                    child: Icon(icon, color: AppTheme.primaryPurple, size: 20),
                  ),
                  const SizedBox(width: 14),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(title, style: TextStyle(fontWeight: FontWeight.w500, color: isDark ? Colors.white : const Color(0xFF1E1B4B))),
                        if (subtitle != null)
                          Text(subtitle!, style: TextStyle(fontSize: 12, color: isDark ? Colors.white38 : Colors.grey[700])),
                      ],
                    ),
                  ),
                  Icon(Icons.chevron_right, color: isDark ? Colors.white24 : Colors.grey[600], size: 20),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class _GlassThemeTile extends StatelessWidget {
  final ThemeMode currentTheme;
  final bool isDark;
  final ValueChanged<ThemeMode> onChanged;
  const _GlassThemeTile({required this.currentTheme, required this.isDark, required this.onChanged});

  @override
  Widget build(BuildContext context) {
    final themeIcon = currentTheme == ThemeMode.dark
        ? Icons.dark_mode
        : currentTheme == ThemeMode.light
            ? Icons.light_mode
            : Icons.brightness_auto;
    final themeLabel = currentTheme == ThemeMode.dark
        ? 'Dark'
        : currentTheme == ThemeMode.light
            ? 'Light'
            : 'System default';

    return Padding(
      padding: const EdgeInsets.only(bottom: 6),
      child: GlassContainer(
        opacity: isDark ? 0.1 : 0.2,
        child: Material(
          color: Colors.transparent,
          child: InkWell(
            borderRadius: BorderRadius.circular(16),
            onTap: () => _showThemeSheet(context),
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
              child: Row(
                children: [
                  Container(
                    padding: const EdgeInsets.all(8),
                    decoration: BoxDecoration(
                      color: AppTheme.primaryPurple.withValues(alpha: isDark ? 0.2 : 0.1),
                      borderRadius: BorderRadius.circular(10),
                    ),
                    child: Icon(themeIcon, color: AppTheme.primaryPurple, size: 20),
                  ),
                  const SizedBox(width: 14),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text('Theme', style: TextStyle(fontWeight: FontWeight.w500, color: isDark ? Colors.white : const Color(0xFF1E1B4B))),
                        Text(themeLabel, style: TextStyle(fontSize: 12, color: isDark ? Colors.white38 : Colors.grey[700])),
                      ],
                    ),
                  ),
                  Icon(Icons.chevron_right, color: isDark ? Colors.white24 : Colors.grey[600], size: 20),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }

  void _showThemeSheet(BuildContext context) {
    showModalBottomSheet(
      context: context,
      backgroundColor: Colors.transparent,
      builder: (ctx) => Container(
        decoration: BoxDecoration(
          color: isDark ? const Color(0xFF1E1B4B).withValues(alpha: 0.95) : Colors.white.withValues(alpha: 0.95),
          borderRadius: const BorderRadius.vertical(top: Radius.circular(24)),
        ),
        child: SafeArea(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Container(
                margin: const EdgeInsets.only(top: 12),
                width: 40, height: 4,
                decoration: BoxDecoration(color: isDark ? Colors.white24 : Colors.grey[600], borderRadius: BorderRadius.circular(2)),
              ),
              Padding(
                padding: const EdgeInsets.all(16),
                child: Text('Choose Theme', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: isDark ? Colors.white : const Color(0xFF1E1B4B))),
              ),
              _themeOption(ctx, Icons.brightness_auto, 'System default', ThemeMode.system),
              _themeOption(ctx, Icons.light_mode, 'Light', ThemeMode.light),
              _themeOption(ctx, Icons.dark_mode, 'Dark', ThemeMode.dark),
              const SizedBox(height: 16),
            ],
          ),
        ),
      ),
    );
  }

  Widget _themeOption(BuildContext ctx, IconData icon, String label, ThemeMode mode) {
    final selected = currentTheme == mode;
    return ListTile(
      leading: Icon(icon, color: isDark ? Colors.white70 : const Color(0xFF1E1B4B)),
      title: Text(label, style: TextStyle(color: isDark ? Colors.white : const Color(0xFF1E1B4B))),
      trailing: selected ? Icon(Icons.check_circle, color: AppTheme.primaryPurple) : null,
      onTap: () {
        onChanged(mode);
        Navigator.pop(ctx);
      },
    );
  }
}

class _GlassDeleteAccountButton extends StatelessWidget {
  final WidgetRef ref;
  final bool isDark;
  const _GlassDeleteAccountButton({required this.ref, required this.isDark});

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: () => _showDeleteAccountDialog(context),
      child: GlassContainer(
        opacity: isDark ? 0.1 : 0.15,
        border: Border.all(color: Colors.red.withValues(alpha: 0.3)),
        child: Padding(
          padding: const EdgeInsets.symmetric(vertical: 14),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(Icons.warning_amber_rounded, color: Colors.red.shade400, size: 20),
              const SizedBox(width: 8),
              Text('Delete Account', style: TextStyle(color: Colors.red.shade400, fontWeight: FontWeight.w600)),
            ],
          ),
        ),
      ),
    ).animate().fadeIn(duration: 500.ms, delay: 600.ms);
  }

  void _showDeleteAccountDialog(BuildContext context) {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: isDark ? const Color(0xFF1E1B4B) : Colors.white,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
        title: Row(
          children: [
            Icon(Icons.warning_amber_rounded, color: Colors.red.shade400),
            const SizedBox(width: 8),
            Text('Delete Account', style: TextStyle(color: isDark ? Colors.white : const Color(0xFF1E1B4B))),
          ],
        ),
        content: Text(
          'This will permanently delete your account and all associated data. '
          'This action cannot be undone.\n\n'
          'Type DELETE to confirm.',
          style: TextStyle(color: isDark ? Colors.white70 : Colors.grey[700]),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: Text('Cancel', style: TextStyle(color: isDark ? Colors.white54 : Colors.grey)),
          ),
          _DeleteConfirmButton(ref: ref, parentContext: context, isDark: isDark),
        ],
      ),
    );
  }
}

class _DeleteConfirmButton extends StatefulWidget {
  final WidgetRef ref;
  final BuildContext parentContext;
  final bool isDark;
  const _DeleteConfirmButton({required this.ref, required this.parentContext, required this.isDark});

  @override
  State<_DeleteConfirmButton> createState() => _DeleteConfirmButtonState();
}

class _DeleteConfirmButtonState extends State<_DeleteConfirmButton> {
  final _controller = TextEditingController();
  bool _isDeleting = false;

  @override
  void dispose() { _controller.dispose(); super.dispose(); }

  @override
  Widget build(BuildContext context) {
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        SizedBox(
          width: 200,
          child: GlassTextField(controller: _controller, label: 'Type DELETE', onChanged: (_) => setState(() {})),
        ),
        const SizedBox(height: 8),
        TextButton(
          onPressed: _controller.text == 'DELETE' && !_isDeleting
              ? () async {
                  setState(() => _isDeleting = true);
                  try {
                    final api = widget.ref.read(apiServiceProvider);
                    await api.delete('/users/me/');
                    await widget.ref.read(authProvider.notifier).logout();
                  } catch (e) {
                    if (mounted) {
                      Navigator.pop(context);
                      ScaffoldMessenger.of(widget.parentContext).showSnackBar(SnackBar(content: Text('Error deleting account: $e')));
                    }
                  }
                }
              : null,
          child: _isDeleting
              ? const SizedBox(height: 16, width: 16, child: CircularProgressIndicator(strokeWidth: 2))
              : Text('Delete Forever', style: TextStyle(color: Colors.red.shade400)),
        ),
      ],
    );
  }
}
