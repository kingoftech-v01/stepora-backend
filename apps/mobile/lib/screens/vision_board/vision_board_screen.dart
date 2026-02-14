import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:cached_network_image/cached_network_image.dart';
import '../../core/theme/app_theme.dart';
import '../../providers/dreams_provider.dart';
import '../../widgets/gradient_background.dart';
import '../../widgets/glass_container.dart';
import '../../widgets/glass_app_bar.dart';
import '../../widgets/glass_button.dart';
import '../../widgets/loading_shimmer.dart';

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
    final isDark = Theme.of(context).brightness == Brightness.dark;

    return GradientBackground(
      colors: isDark ? AppTheme.gradientDreams : AppTheme.gradientDreamsLight,
      child: Scaffold(
        backgroundColor: Colors.transparent,
        extendBodyBehindAppBar: true,
        appBar: GlassAppBar(
          title: 'Vision Board',
          actions: [
            IconButton(
              icon: Icon(Icons.refresh, color: isDark ? Colors.white70 : const Color(0xFF1E1B4B)),
              onPressed: _isGenerating ? null : _generate,
              tooltip: 'Generate new',
            ),
          ],
        ),
        body: _isLoading
            ? const Center(child: LoadingShimmer())
            : _imageUrl != null
                ? Stack(
                    children: [
                      // Full-screen image with interactive viewer
                      InteractiveViewer(
                        child: Center(
                          child: CachedNetworkImage(
                            imageUrl: _imageUrl!,
                            placeholder: (_, __) => const Center(child: LoadingShimmer()),
                            errorWidget: (_, __, ___) => Icon(Icons.error, color: isDark ? Colors.white38 : Colors.grey),
                            fit: BoxFit.contain,
                          ),
                        ),
                      ),
                      // Glass overlay controls at bottom
                      Positioned(
                        bottom: 0,
                        left: 0,
                        right: 0,
                        child: GlassContainer(
                          margin: const EdgeInsets.all(16),
                          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                          opacity: isDark ? 0.2 : 0.35,
                          child: Row(
                            mainAxisAlignment: MainAxisAlignment.center,
                            children: [
                              Icon(Icons.auto_awesome, color: AppTheme.primaryPurple, size: 18),
                              const SizedBox(width: 8),
                              Text('Pinch to zoom', style: TextStyle(color: isDark ? Colors.white54 : Colors.grey[600], fontSize: 13)),
                              const Spacer(),
                              GlassButton(
                                label: _isGenerating ? 'Generating...' : 'Regenerate',
                                icon: Icons.refresh,
                                isLoading: _isGenerating,
                                onPressed: _isGenerating ? null : _generate,
                              ),
                            ],
                          ),
                        ).animate().fadeIn(duration: 500.ms, delay: 300.ms).slideY(begin: 0.2, end: 0),
                      ),
                    ],
                  )
                : Center(
                    child: Padding(
                      padding: const EdgeInsets.all(32),
                      child: GlassContainer(
                        padding: const EdgeInsets.all(32),
                        opacity: isDark ? 0.15 : 0.3,
                        child: Column(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            Container(
                              padding: const EdgeInsets.all(24),
                              decoration: BoxDecoration(
                                shape: BoxShape.circle,
                                color: AppTheme.primaryPurple.withValues(alpha: 0.1),
                                boxShadow: [BoxShadow(color: AppTheme.primaryPurple.withValues(alpha: 0.15), blurRadius: 20)],
                              ),
                              child: Icon(Icons.image_outlined, size: 56, color: AppTheme.primaryPurple.withValues(alpha: 0.5)),
                            ).animate().fadeIn(duration: 500.ms).scale(begin: const Offset(0.8, 0.8), end: const Offset(1, 1)),
                            const SizedBox(height: 20),
                            Text(
                              'No vision board yet',
                              style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: isDark ? Colors.white : const Color(0xFF1E1B4B)),
                            ).animate().fadeIn(duration: 500.ms, delay: 100.ms),
                            const SizedBox(height: 8),
                            Text(
                              'Generate an AI-powered vision board for your dream!',
                              textAlign: TextAlign.center,
                              style: TextStyle(color: isDark ? Colors.white54 : Colors.grey[600]),
                            ).animate().fadeIn(duration: 500.ms, delay: 200.ms),
                            const SizedBox(height: 24),
                            GlassButton(
                              label: _isGenerating ? 'Generating...' : 'Generate Vision Board',
                              icon: Icons.auto_awesome,
                              isLoading: _isGenerating,
                              onPressed: _isGenerating ? null : _generate,
                            ).animate().fadeIn(duration: 500.ms, delay: 300.ms),
                          ],
                        ),
                      ).animate().fadeIn(duration: 400.ms),
                    ),
                  ),
      ),
    );
  }
}
