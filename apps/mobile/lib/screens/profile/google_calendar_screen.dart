import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:url_launcher/url_launcher.dart';
import '../../core/theme/app_theme.dart';
import '../../config/api_constants.dart';
import '../../services/api_service.dart';

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
          // Poll for connection status after user completes OAuth in browser
          Future.delayed(const Duration(seconds: 5), () {
            if (mounted) _checkStatus();
          });
        }
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error: $e')),
        );
      }
    }
  }

  Future<void> _sync() async {
    setState(() => _isSyncing = true);
    try {
      final api = ref.read(apiServiceProvider);
      await api.post(ApiConstants.googleCalendarSync);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Calendar synced!')),
        );
      }
      _checkStatus();
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Sync failed: $e')),
        );
      }
    } finally {
      if (mounted) setState(() => _isSyncing = false);
    }
  }

  Future<void> _disconnect() async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Disconnect Google Calendar?'),
        content: const Text('Your events will no longer sync automatically.'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancel')),
          TextButton(
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('Disconnect', style: TextStyle(color: Colors.red)),
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
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error: $e')),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Google Calendar')),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : ListView(
              padding: const EdgeInsets.all(24),
              children: [
                Card(
                  child: Padding(
                    padding: const EdgeInsets.all(24),
                    child: Column(
                      children: [
                        Icon(
                          _isConnected ? Icons.check_circle : Icons.calendar_month,
                          size: 64,
                          color: _isConnected ? AppTheme.success : Colors.grey[400],
                        ),
                        const SizedBox(height: 16),
                        Text(
                          _isConnected ? 'Connected' : 'Not Connected',
                          style: Theme.of(context).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.bold),
                        ),
                        const SizedBox(height: 8),
                        Text(
                          _isConnected
                              ? 'Your events are syncing with Google Calendar'
                              : 'Connect to sync your DreamPlanner events',
                          textAlign: TextAlign.center,
                          style: TextStyle(color: Colors.grey[600]),
                        ),
                        if (_lastSynced != null) ...[
                          const SizedBox(height: 8),
                          Text(
                            'Last synced: ${_lastSynced!.substring(0, 16).replaceAll('T', ' ')}',
                            style: TextStyle(color: Colors.grey[500], fontSize: 12),
                          ),
                        ],
                        const SizedBox(height: 24),
                        if (_isConnected) ...[
                          FilledButton.icon(
                            onPressed: _isSyncing ? null : _sync,
                            icon: _isSyncing
                                ? const SizedBox(
                                    height: 16,
                                    width: 16,
                                    child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                                  )
                                : const Icon(Icons.sync),
                            label: Text(_isSyncing ? 'Syncing...' : 'Sync Now'),
                            style: FilledButton.styleFrom(backgroundColor: AppTheme.primaryPurple),
                          ),
                          const SizedBox(height: 12),
                          OutlinedButton.icon(
                            onPressed: _disconnect,
                            icon: const Icon(Icons.link_off, color: Colors.red),
                            label: const Text('Disconnect', style: TextStyle(color: Colors.red)),
                            style: OutlinedButton.styleFrom(side: const BorderSide(color: Colors.red)),
                          ),
                        ] else
                          FilledButton.icon(
                            onPressed: _connect,
                            icon: const Icon(Icons.link),
                            label: const Text('Connect Google Calendar'),
                            style: FilledButton.styleFrom(backgroundColor: AppTheme.primaryPurple),
                          ),
                      ],
                    ),
                  ),
                ),
              ],
            ),
    );
  }
}
