import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:url_launcher/url_launcher.dart';
import '../../core/theme/app_theme.dart';
import '../../config/api_constants.dart';
import '../../services/api_service.dart';
import '../../widgets/gradient_background.dart';
import '../../widgets/glass_container.dart';
import '../../widgets/glass_app_bar.dart';
import '../../widgets/glass_button.dart';
import '../../widgets/loading_shimmer.dart';

class GoogleCalendarScreen extends ConsumerStatefulWidget {
  const GoogleCalendarScreen({super.key});

  @override
  ConsumerState<GoogleCalendarScreen> createState() => _GoogleCalendarScreenState();
}

class _GoogleCalendarScreenState extends ConsumerState<GoogleCalendarScreen> {
  bool _isConnected = false;
  bool _isLoading = true;
  bool _isSyncing = false;
  String? _lastSynced;

  @override
  void initState() {
    super.initState();
    _checkStatus();
  }

  Future<void> _checkStatus() async {
    try {
      final api = ref.read(apiServiceProvider);
      final response = await api.get(ApiConstants.googleCalendarAuth);
      setState(() {
        _isConnected = response.data['is_connected'] == true;
        _lastSynced = response.data['last_synced']?.toString();
        _isLoading = false;
      });
    } catch (_) {
      setState(() => _isLoading = false);
    }
  }

  Future<void> _connect() async {
    try {
      final api = ref.read(apiServiceProvider);
      final response = await api.post(ApiConstants.googleCalendarAuth);
      final authUrl = response.data['auth_url']?.toString();
      if (authUrl != null && mounted) {
        final uri = Uri.parse(authUrl);
        final launched = await launchUrl(uri, mode: LaunchMode.externalApplication);
        if (!launched && mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('Could not open browser for Google sign-in')),
          );
        } else if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('Complete sign-in in your browser, then return here and tap refresh')),
          );
          Future.delayed(const Duration(seconds: 5), () {
            if (mounted) _checkStatus();
          });
        }
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Error: $e')));
      }
    }
  }

  Future<void> _sync() async {
    setState(() => _isSyncing = true);
    try {
      final api = ref.read(apiServiceProvider);
      await api.post(ApiConstants.googleCalendarSync);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Calendar synced!')));
      }
      _checkStatus();
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Sync failed: $e')));
      }
    } finally {
      if (mounted) setState(() => _isSyncing = false);
    }
  }

  Future<void> _disconnect() async {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: isDark ? const Color(0xFF1E1B4B) : Colors.white,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
        title: Text('Disconnect Google Calendar?', style: TextStyle(color: isDark ? Colors.white : const Color(0xFF1E1B4B))),
        content: Text('Your events will no longer sync automatically.', style: TextStyle(color: isDark ? Colors.white70 : Colors.grey[700])),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: Text('Cancel', style: TextStyle(color: isDark ? Colors.white54 : Colors.grey))),
          TextButton(
            onPressed: () => Navigator.pop(ctx, true),
            child: Text('Disconnect', style: TextStyle(color: Colors.red.shade400)),
          ),
        ],
      ),
    );
    if (confirmed != true) return;
    try {
      final api = ref.read(apiServiceProvider);
      await api.post(ApiConstants.googleCalendarDisconnect);
      setState(() => _isConnected = false);
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Error: $e')));
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;

    return GradientBackground(
      colors: isDark ? AppTheme.gradientProfile : AppTheme.gradientProfileLight,
      child: Scaffold(
        backgroundColor: Colors.transparent,
        extendBodyBehindAppBar: true,
        appBar: const GlassAppBar(title: 'Google Calendar'),
        body: _isLoading
            ? const Center(child: LoadingShimmer())
            : ListView(
                padding: EdgeInsets.fromLTRB(24, MediaQuery.of(context).padding.top + kToolbarHeight + 16, 24, 32),
                children: [
                  GlassContainer(
                    padding: const EdgeInsets.all(32),
                    opacity: isDark ? 0.15 : 0.3,
                    child: Column(
                      children: [
                        // Status icon with glow
                        Container(
                          padding: const EdgeInsets.all(20),
                          decoration: BoxDecoration(
                            shape: BoxShape.circle,
                            color: (_isConnected ? AppTheme.success : Colors.grey).withValues(alpha: 0.1),
                            boxShadow: _isConnected
                                ? [BoxShadow(color: AppTheme.success.withValues(alpha: 0.2), blurRadius: 20, spreadRadius: 2)]
                                : null,
                          ),
                          child: Icon(
                            _isConnected ? Icons.check_circle : Icons.calendar_month,
                            size: 48,
                            color: _isConnected ? AppTheme.success : (isDark ? Colors.white24 : Colors.grey[600]),
                          ),
                        ).animate().fadeIn(duration: 500.ms).scale(begin: const Offset(0.8, 0.8), end: const Offset(1, 1)),
                        const SizedBox(height: 20),
                        Text(
                          _isConnected ? 'Connected' : 'Not Connected',
                          style: TextStyle(
                            fontSize: 20,
                            fontWeight: FontWeight.bold,
                            color: isDark ? Colors.white : const Color(0xFF1E1B4B),
                          ),
                        ).animate().fadeIn(duration: 500.ms, delay: 100.ms),
                        const SizedBox(height: 8),
                        Text(
                          _isConnected
                              ? 'Your events are syncing with Google Calendar'
                              : 'Connect to sync your DreamPlanner events',
                          textAlign: TextAlign.center,
                          style: TextStyle(color: isDark ? Colors.white54 : Colors.grey[600]),
                        ).animate().fadeIn(duration: 500.ms, delay: 150.ms),
                        if (_lastSynced != null) ...[
                          const SizedBox(height: 8),
                          Container(
                            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                            decoration: BoxDecoration(
                              color: isDark ? Colors.white.withValues(alpha: 0.05) : Colors.black.withValues(alpha: 0.03),
                              borderRadius: BorderRadius.circular(8),
                            ),
                            child: Text(
                              'Last synced: ${_lastSynced!.substring(0, 16).replaceAll('T', ' ')}',
                              style: TextStyle(color: isDark ? Colors.white38 : Colors.grey[700], fontSize: 12),
                            ),
                          ).animate().fadeIn(duration: 500.ms, delay: 200.ms),
                        ],
                        const SizedBox(height: 28),
                        if (_isConnected) ...[
                          GlassButton(
                            label: _isSyncing ? 'Syncing...' : 'Sync Now',
                            icon: Icons.sync,
                            isLoading: _isSyncing,
                            onPressed: _isSyncing ? null : _sync,
                          ).animate().fadeIn(duration: 500.ms, delay: 250.ms),
                          const SizedBox(height: 12),
                          GlassButton(
                            label: 'Disconnect',
                            icon: Icons.link_off,
                            style: GlassButtonStyle.danger,
                            onPressed: _disconnect,
                          ).animate().fadeIn(duration: 500.ms, delay: 300.ms),
                        ] else
                          GlassButton(
                            label: 'Connect Google Calendar',
                            icon: Icons.link,
                            onPressed: _connect,
                          ).animate().fadeIn(duration: 500.ms, delay: 250.ms),
                      ],
                    ),
                  ).animate().fadeIn(duration: 400.ms),

                  const SizedBox(height: 24),

                  // Info cards
                  GlassContainer(
                    padding: const EdgeInsets.all(16),
                    opacity: isDark ? 0.1 : 0.2,
                    child: Row(
                      children: [
                        Container(
                          padding: const EdgeInsets.all(8),
                          decoration: BoxDecoration(
                            color: AppTheme.primaryPurple.withValues(alpha: 0.15),
                            borderRadius: BorderRadius.circular(10),
                          ),
                          child: Icon(Icons.info_outline, color: AppTheme.primaryPurple, size: 20),
                        ),
                        const SizedBox(width: 12),
                        Expanded(
                          child: Text(
                            'Sync your tasks and events between DreamPlanner and Google Calendar for seamless scheduling.',
                            style: TextStyle(fontSize: 13, color: isDark ? Colors.white54 : Colors.grey[600]),
                          ),
                        ),
                      ],
                    ),
                  ).animate().fadeIn(duration: 500.ms, delay: 300.ms),
                ],
              ),
      ),
    );
  }
}
