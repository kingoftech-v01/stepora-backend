import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:cached_network_image/cached_network_image.dart';
import '../../core/theme/app_theme.dart';
import '../../providers/dreams_provider.dart';

class VisionBoardScreen extends ConsumerStatefulWidget {
  final String dreamId;
  const VisionBoardScreen({super.key, required this.dreamId});

  @override
  ConsumerState<VisionBoardScreen> createState() => _VisionBoardScreenState();
}

class _VisionBoardScreenState extends ConsumerState<VisionBoardScreen> {
  String? _imageUrl;
  bool _isLoading = true;
  bool _isGenerating = false;

  @override
  void initState() {
    super.initState();
    _loadDream();
  }

  Future<void> _loadDream() async {
    try {
      final dream = await ref.read(dreamsProvider.notifier).getDreamDetail(widget.dreamId);
      setState(() {
        _imageUrl = dream.visionBoardUrl;
        _isLoading = false;
      });
    } catch (_) {
      setState(() => _isLoading = false);
    }
  }

  Future<void> _generate() async {
    setState(() => _isGenerating = true);
    try {
      final url = await ref.read(dreamsProvider.notifier).generateVisionBoard(widget.dreamId);
      setState(() {
        _imageUrl = url;
        _isGenerating = false;
      });
    } catch (e) {
      setState(() => _isGenerating = false);
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Error: $e')));
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Vision Board'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: _isGenerating ? null : _generate,
            tooltip: 'Generate new',
          ),
        ],
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : _imageUrl != null
              ? InteractiveViewer(
                  child: Center(
                    child: CachedNetworkImage(
                      imageUrl: _imageUrl!,
                      placeholder: (_, __) => const Center(child: CircularProgressIndicator()),
                      errorWidget: (_, __, ___) => const Icon(Icons.error),
                      fit: BoxFit.contain,
                    ),
                  ),
                )
              : Center(
                  child: Padding(
                    padding: const EdgeInsets.all(32),
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Icon(Icons.image_outlined, size: 80, color: AppTheme.primaryPurple.withValues(alpha: 0.3)),
                        const SizedBox(height: 16),
                        Text('No vision board yet', style: Theme.of(context).textTheme.titleMedium),
                        const SizedBox(height: 8),
                        Text('Generate an AI-powered vision board for your dream!', textAlign: TextAlign.center, style: TextStyle(color: Colors.grey[600])),
                        const SizedBox(height: 24),
                        FilledButton.icon(
                          onPressed: _isGenerating ? null : _generate,
                          icon: _isGenerating ? const SizedBox(width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white)) : const Icon(Icons.auto_awesome),
                          label: Text(_isGenerating ? 'Generating...' : 'Generate Vision Board'),
                          style: FilledButton.styleFrom(backgroundColor: AppTheme.primaryPurple),
                        ),
                      ],
                    ),
                  ),
                ),
    );
  }
}
