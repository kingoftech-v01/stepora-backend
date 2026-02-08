import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:url_launcher/url_launcher.dart';
import '../../core/theme/app_theme.dart';
import '../../providers/auth_provider.dart';
import '../../providers/locale_provider.dart';
import '../../providers/theme_provider.dart';
import '../../services/api_service.dart';

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

    return Scaffold(
      appBar: AppBar(
        title: const Text('Settings'),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back),
          onPressed: () => context.pop(),
        ),
      ),
      body: ListView(
        children: [
          _SectionHeader(title: 'Account'),
          _SettingsTile(
            icon: Icons.person_outline,
            title: 'Edit Profile',
            subtitle: user?.displayName ?? user?.email ?? '',
            onTap: () => context.push('/profile/edit'),
          ),
          _SettingsTile(
            icon: Icons.email_outlined,
            title: 'Email',
            subtitle: user?.email ?? '',
            onTap: () {
              showDialog(
                context: context,
                builder: (ctx) => AlertDialog(
                  title: const Text('Email'),
                  content: Text(
                    'Your email is ${user?.email ?? 'not set'}.\n\nTo change your email, please contact support.',
                  ),
                  actions: [
                    TextButton(
                      onPressed: () => Navigator.pop(ctx),
                      child: const Text('OK'),
                    ),
                  ],
                ),
              );
            },
          ),
          _SettingsTile(
            icon: Icons.lock_outline,
            title: 'Change Password',
            onTap: () => context.push('/change-password'),
          ),

          _SectionHeader(title: 'Appearance'),
          _ThemeTile(
            currentTheme: currentTheme,
            onChanged: (mode) => ref.read(themeProvider.notifier).setThemeMode(mode),
          ),

          _SectionHeader(title: 'Preferences'),
          _SettingsTile(
            icon: Icons.language,
            title: 'Language',
            subtitle: _languages[currentLangCode] ?? 'English',
            onTap: () {
              showModalBottomSheet(
                context: context,
                builder: (ctx) => SafeArea(
                  child: ListView(
                    shrinkWrap: true,
                    children: [
                      const Padding(
                        padding: EdgeInsets.all(16),
                        child: Text(
                          'Select Language',
                          style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
                        ),
                      ),
                      ..._languages.entries.map((entry) => ListTile(
                        title: Text(entry.value),
                        trailing: entry.key == currentLangCode
                            ? const Icon(Icons.check, color: AppTheme.primaryPurple)
                            : null,
                        onTap: () {
                          ref.read(localeProvider.notifier).setLocale(entry.key);
                          Navigator.pop(ctx);
                          ScaffoldMessenger.of(context).showSnackBar(
                            SnackBar(content: Text('Language set to ${entry.value}')),
                          );
                        },
                      )),
                    ],
                  ),
                ),
              );
            },
          ),
          _SettingsTile(
            icon: Icons.access_time,
            title: 'Timezone',
            subtitle: user?.timezone ?? 'UTC',
            onTap: () {
              final controller = TextEditingController(text: user?.timezone ?? 'UTC');
              showDialog(
                context: context,
                builder: (ctx) => AlertDialog(
                  title: const Text('Set Timezone'),
                  content: TextField(
                    controller: controller,
                    decoration: const InputDecoration(
                      hintText: 'e.g. America/New_York',
                      labelText: 'Timezone',
                    ),
                  ),
                  actions: [
                    TextButton(
                      onPressed: () => Navigator.pop(ctx),
                      child: const Text('Cancel'),
                    ),
                    TextButton(
                      onPressed: () async {
                        try {
                          final api = ref.read(apiServiceProvider);
                          await api.patch('/users/me/', data: {'timezone': controller.text});
                          await ref.read(authProvider.notifier).refreshUser();
                          if (ctx.mounted) Navigator.pop(ctx);
                        } catch (e) {
                          if (ctx.mounted) {
                            ScaffoldMessenger.of(context).showSnackBar(
                              SnackBar(content: Text('Error: $e')),
                            );
                          }
                        }
                      },
                      child: const Text('Save'),
                    ),
                  ],
                ),
              );
            },
          ),
          _SettingsTile(
            icon: Icons.notifications_outlined,
            title: 'Notifications',
            onTap: () => context.push('/notifications'),
          ),
          _SettingsTile(
            icon: Icons.calendar_month,
            title: 'Google Calendar',
            subtitle: 'Sync your events',
            onTap: () => context.push('/google-calendar'),
          ),

          _SectionHeader(title: 'Subscription'),
          _SettingsTile(
            icon: Icons.workspace_premium,
            title: 'Manage Subscription',
            subtitle: user?.subscription ?? 'Free',
            onTap: () => context.push('/subscription'),
          ),
          _SettingsTile(
            icon: Icons.store,
            title: 'Store',
            onTap: () => context.push('/store'),
          ),

          _SectionHeader(title: 'About'),
          _SettingsTile(
            icon: Icons.info_outline,
            title: 'App Version',
            subtitle: '1.0.0',
            onTap: () {
              showAboutDialog(
                context: context,
                applicationName: 'DreamPlanner',
                applicationVersion: '1.0.0',
                applicationLegalese: '\u00a9 2024 DreamPlanner',
              );
            },
          ),
          _SettingsTile(
            icon: Icons.description_outlined,
            title: 'Terms of Service',
            onTap: () => launchUrl(Uri.parse('https://dreamplanner.app/terms')),
          ),
          _SettingsTile(
            icon: Icons.privacy_tip_outlined,
            title: 'Privacy Policy',
            onTap: () => launchUrl(Uri.parse('https://dreamplanner.app/privacy')),
          ),

          const SizedBox(height: 24),

          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16),
            child: OutlinedButton.icon(
              onPressed: () => ref.read(authProvider.notifier).logout(),
              icon: const Icon(Icons.logout, color: AppTheme.error),
              label: const Text('Sign Out', style: TextStyle(color: AppTheme.error)),
              style: OutlinedButton.styleFrom(
                side: const BorderSide(color: AppTheme.error),
                padding: const EdgeInsets.symmetric(vertical: 14),
              ),
            ),
          ),

          const SizedBox(height: 16),

          _DeleteAccountTile(ref: ref),

          const SizedBox(height: 32),
        ],
      ),
    );
  }
}

class _ThemeTile extends StatelessWidget {
  final ThemeMode currentTheme;
  final ValueChanged<ThemeMode> onChanged;

  const _ThemeTile({required this.currentTheme, required this.onChanged});

  @override
  Widget build(BuildContext context) {
    return ListTile(
      leading: Icon(
        currentTheme == ThemeMode.dark
            ? Icons.dark_mode
            : currentTheme == ThemeMode.light
                ? Icons.light_mode
                : Icons.brightness_auto,
        color: AppTheme.primaryPurple,
      ),
      title: const Text('Theme'),
      subtitle: Text(
        currentTheme == ThemeMode.dark
            ? 'Dark'
            : currentTheme == ThemeMode.light
                ? 'Light'
                : 'System default',
      ),
      trailing: const Icon(Icons.chevron_right, size: 20),
      onTap: () {
        showModalBottomSheet(
          context: context,
          builder: (ctx) => SafeArea(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                const Padding(
                  padding: EdgeInsets.all(16),
                  child: Text(
                    'Choose Theme',
                    style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
                  ),
                ),
                ListTile(
                  leading: const Icon(Icons.brightness_auto),
                  title: const Text('System default'),
                  trailing: currentTheme == ThemeMode.system
                      ? const Icon(Icons.check, color: AppTheme.primaryPurple)
                      : null,
                  onTap: () {
                    onChanged(ThemeMode.system);
                    Navigator.pop(ctx);
                  },
                ),
                ListTile(
                  leading: const Icon(Icons.light_mode),
                  title: const Text('Light'),
                  trailing: currentTheme == ThemeMode.light
                      ? const Icon(Icons.check, color: AppTheme.primaryPurple)
                      : null,
                  onTap: () {
                    onChanged(ThemeMode.light);
                    Navigator.pop(ctx);
                  },
                ),
                ListTile(
                  leading: const Icon(Icons.dark_mode),
                  title: const Text('Dark'),
                  trailing: currentTheme == ThemeMode.dark
                      ? const Icon(Icons.check, color: AppTheme.primaryPurple)
                      : null,
                  onTap: () {
                    onChanged(ThemeMode.dark);
                    Navigator.pop(ctx);
                  },
                ),
                const SizedBox(height: 16),
              ],
            ),
          ),
        );
      },
    );
  }
}

class _DeleteAccountTile extends StatelessWidget {
  final WidgetRef ref;
  const _DeleteAccountTile({required this.ref});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16),
      child: OutlinedButton.icon(
        onPressed: () => _showDeleteAccountDialog(context),
        icon: const Icon(Icons.warning_amber_rounded, color: Colors.red),
        label: const Text('Delete Account', style: TextStyle(color: Colors.red)),
        style: OutlinedButton.styleFrom(
          side: const BorderSide(color: Colors.red),
          padding: const EdgeInsets.symmetric(vertical: 14),
        ),
      ),
    );
  }

  void _showDeleteAccountDialog(BuildContext context) {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Row(
          children: [
            Icon(Icons.warning_amber_rounded, color: Colors.red),
            SizedBox(width: 8),
            Text('Delete Account'),
          ],
        ),
        content: const Text(
          'This will permanently delete your account and all associated data. '
          'This action cannot be undone.\n\n'
          'Type DELETE to confirm.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('Cancel'),
          ),
          _DeleteConfirmButton(ref: ref, parentContext: context),
        ],
      ),
    );
  }
}

class _DeleteConfirmButton extends StatefulWidget {
  final WidgetRef ref;
  final BuildContext parentContext;
  const _DeleteConfirmButton({required this.ref, required this.parentContext});

  @override
  State<_DeleteConfirmButton> createState() => _DeleteConfirmButtonState();
}

class _DeleteConfirmButtonState extends State<_DeleteConfirmButton> {
  final _controller = TextEditingController();
  bool _isDeleting = false;

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        SizedBox(
          width: 200,
          child: TextField(
            controller: _controller,
            decoration: const InputDecoration(
              hintText: 'Type DELETE',
              border: OutlineInputBorder(),
              isDense: true,
            ),
            onChanged: (_) => setState(() {}),
          ),
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
                      ScaffoldMessenger.of(widget.parentContext).showSnackBar(
                        SnackBar(content: Text('Error deleting account: $e')),
                      );
                    }
                  }
                }
              : null,
          child: _isDeleting
              ? const SizedBox(
                  height: 16,
                  width: 16,
                  child: CircularProgressIndicator(strokeWidth: 2),
                )
              : const Text(
                  'Delete Forever',
                  style: TextStyle(color: Colors.red),
                ),
        ),
      ],
    );
  }
}

class _SectionHeader extends StatelessWidget {
  final String title;
  const _SectionHeader({required this.title});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 24, 16, 8),
      child: Text(
        title,
        style: TextStyle(
          fontSize: 13,
          fontWeight: FontWeight.w600,
          color: Colors.grey[600],
          letterSpacing: 0.5,
        ),
      ),
    );
  }
}

class _SettingsTile extends StatelessWidget {
  final IconData icon;
  final String title;
  final String? subtitle;
  final VoidCallback onTap;
  const _SettingsTile({required this.icon, required this.title, this.subtitle, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return ListTile(
      leading: Icon(icon, color: AppTheme.primaryPurple),
      title: Text(title),
      subtitle: subtitle != null ? Text(subtitle!) : null,
      trailing: const Icon(Icons.chevron_right, size: 20),
      onTap: onTap,
    );
  }
}
