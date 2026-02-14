import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../core/theme/app_theme.dart';
import '../../providers/dreams_provider.dart';
import '../../widgets/gradient_background.dart';
import '../../widgets/glass_container.dart';
import '../../widgets/glass_app_bar.dart';
import '../../widgets/glass_button.dart';
import '../../widgets/animated_counter.dart';
import '../../widgets/animated_progress_ring.dart';
import '../../widgets/loading_shimmer.dart';

class MicroStartScreen extends ConsumerStatefulWidget {
  final String taskId;
  const MicroStartScreen({super.key, required this.taskId});

  @override
  ConsumerState<MicroStartScreen> createState() => _MicroStartScreenState();
}

class _MicroStartScreenState extends ConsumerState<MicroStartScreen> with TickerProviderStateMixin {
  Map<String, dynamic>? _data;
  bool _isLoading = true;
  bool _started = false;
  int _seconds = 120; // 2 minutes
  late AnimationController _pulseController;

  @override
  void initState() {
    super.initState();
    _pulseController = AnimationController(vsync: this, duration: const Duration(milliseconds: 1500))
      ..repeat(reverse: true);
    _loadMicroStart();
  }

  @override
  void dispose() {
    _pulseController.dispose();
    super.dispose();
  }

  Future<void> _loadMicroStart() async {
    try {
      final data = await ref.read(dreamsProvider.notifier).startMicroStart(widget.taskId);
      setState(() { _data = data; _isLoading = false; });
    } catch (_) {
      setState(() => _isLoading = false);
    }
  }

  void _startTimer() {
    setState(() => _started = true);
    Future.doWhile(() async {
      await Future.delayed(const Duration(seconds: 1));
      if (!mounted || _seconds <= 0) return false;
      setState(() => _seconds--);
      return _seconds > 0;
    });
  }

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;

    if (_isLoading) {
      return GradientBackground(
        colors: isDark ? AppTheme.gradientDreams : AppTheme.gradientDreamsLight,
        child: Scaffold(
          backgroundColor: Colors.transparent,
          extendBodyBehindAppBar: true,
          appBar: const GlassAppBar(title: '2-Minute Start'),
          body: const Center(child: LoadingShimmer()),
        ),
      );
    }

    final progress = 1 - (_seconds / 120);
    final timerColor = _seconds <= 10 ? AppTheme.error : AppTheme.primaryPurple;

    return GradientBackground(
      colors: isDark ? AppTheme.gradientDreams : AppTheme.gradientDreamsLight,
      child: Scaffold(
        backgroundColor: Colors.transparent,
        extendBodyBehindAppBar: true,
        appBar: const GlassAppBar(title: '2-Minute Start'),
        body: Padding(
          padding: EdgeInsets.fromLTRB(24, MediaQuery.of(context).padding.top + kToolbarHeight + 16, 24, 32),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              // Main icon / timer area
              if (_started) ...[
                // Animated progress ring with timer
                Center(
                  child: SizedBox(
                    width: 200, height: 200,
                    child: Stack(
                      alignment: Alignment.center,
                      children: [
                        AnimatedProgressRing(
                          progress: progress,
                          size: 200,
                          strokeWidth: 10,
                          color: timerColor,
                        ),
                        Column(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            AnimatedCounter(
                              value: _seconds ~/ 60,
                              style: TextStyle(
                                fontSize: 48,
                                fontWeight: FontWeight.bold,
                                color: timerColor,
                              ),
                            ),
                            Text(
                              ':${(_seconds % 60).toString().padLeft(2, '0')}',
                              style: TextStyle(fontSize: 36, fontWeight: FontWeight.w300, color: timerColor),
                            ),
                          ],
                        ),
                      ],
                    ),
                  ),
                ).animate().fadeIn(duration: 500.ms),
                const SizedBox(height: 24),
                Text(
                  _seconds <= 0 ? 'Time\'s up!' : 'Keep going!',
                  style: TextStyle(fontSize: 22, fontWeight: FontWeight.bold, color: isDark ? Colors.white : const Color(0xFF1E1B4B)),
                  textAlign: TextAlign.center,
                ).animate().fadeIn(duration: 400.ms),
              ] else ...[
                // Pre-start rocket icon with pulse
                Center(
                  child: AnimatedBuilder(
                    animation: _pulseController,
                    builder: (context, child) {
                      final scale = 1.0 + 0.05 * _pulseController.value;
                      return Transform.scale(
                        scale: scale,
                        child: Container(
                          padding: const EdgeInsets.all(28),
                          decoration: BoxDecoration(
                            shape: BoxShape.circle,
                            color: AppTheme.primaryPurple.withValues(alpha: 0.1),
                            boxShadow: [
                              BoxShadow(
                                color: AppTheme.primaryPurple.withValues(alpha: 0.2 * _pulseController.value),
                                blurRadius: 30,
                                spreadRadius: 5,
                              ),
                            ],
                          ),
                          child: Icon(Icons.rocket_launch, size: 64, color: AppTheme.primaryPurple),
                        ),
                      );
                    },
                  ),
                ).animate().fadeIn(duration: 600.ms).scale(begin: const Offset(0.7, 0.7), end: const Offset(1, 1)),
                const SizedBox(height: 28),
                Text(
                  'Ready to start?',
                  style: TextStyle(fontSize: 22, fontWeight: FontWeight.bold, color: isDark ? Colors.white : const Color(0xFF1E1B4B)),
                  textAlign: TextAlign.center,
                ).animate().fadeIn(duration: 500.ms, delay: 150.ms),
              ],

              const SizedBox(height: 20),

              // Task info card
              GlassContainer(
                padding: const EdgeInsets.all(18),
                opacity: isDark ? 0.15 : 0.3,
                child: Column(
                  children: [
                    Text(
                      _data?['task_title'] ?? 'Task',
                      style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600, color: isDark ? Colors.white : const Color(0xFF1E1B4B)),
                      textAlign: TextAlign.center,
                    ),
                    if (_data?['two_minute_action'] != null) ...[
                      const SizedBox(height: 8),
                      Text(
                        _data!['two_minute_action'],
                        style: TextStyle(color: isDark ? Colors.white54 : Colors.grey[600]),
                        textAlign: TextAlign.center,
                      ),
                    ],
                  ],
                ),
              ).animate().fadeIn(duration: 500.ms, delay: 200.ms).slideY(begin: 0.05, end: 0),

              const SizedBox(height: 28),

              // Actions
              if (_started) ...[
                // Animated progress bar
                ClipRRect(
                  borderRadius: BorderRadius.circular(6),
                  child: TweenAnimationBuilder<double>(
                    tween: Tween(begin: 0, end: progress),
                    duration: const Duration(milliseconds: 500),
                    curve: Curves.easeOutCubic,
                    builder: (context, value, _) => Stack(
                      children: [
                        Container(
                          height: 8,
                          decoration: BoxDecoration(
                            color: timerColor.withValues(alpha: 0.1),
                            borderRadius: BorderRadius.circular(6),
                          ),
                        ),
                        FractionallySizedBox(
                          widthFactor: value,
                          child: Container(
                            height: 8,
                            decoration: BoxDecoration(
                              gradient: LinearGradient(colors: [timerColor.withValues(alpha: 0.7), timerColor]),
                              borderRadius: BorderRadius.circular(6),
                              boxShadow: [BoxShadow(color: timerColor.withValues(alpha: 0.3), blurRadius: 6)],
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                ).animate().fadeIn(duration: 400.ms),

                if (_seconds <= 0) ...[
                  const SizedBox(height: 28),
                  // Celebration
                  Row(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Icon(Icons.celebration, size: 36, color: AppTheme.accent)
                        .animate().fadeIn(duration: 400.ms).scale(begin: const Offset(0.5, 0.5), end: const Offset(1, 1)),
                      const SizedBox(width: 8),
                      Text('Great job!', style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold, color: AppTheme.accent))
                        .animate().fadeIn(duration: 400.ms, delay: 100.ms),
                      const SizedBox(width: 8),
                      Icon(Icons.celebration, size: 36, color: AppTheme.accent)
                        .animate().fadeIn(duration: 400.ms, delay: 200.ms).scale(begin: const Offset(0.5, 0.5), end: const Offset(1, 1)),
                    ],
                  ),
                  const SizedBox(height: 20),
                  Row(
                    children: [
                      Expanded(
                        child: GlassButton(
                          label: 'Done',
                          style: GlassButtonStyle.secondary,
                          onPressed: () => context.pop(),
                        ),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: GlassButton(
                          label: 'Complete Task',
                          icon: Icons.check,
                          onPressed: () async {
                            await ref.read(dreamsProvider.notifier).completeTask(widget.taskId);
                            if (context.mounted) context.pop();
                          },
                        ),
                      ),
                    ],
                  ).animate().fadeIn(duration: 500.ms, delay: 300.ms),
                ],
              ] else
                GlassButton(
                  label: 'Start 2-Minute Timer',
                  icon: Icons.play_arrow,
                  onPressed: _startTimer,
                ).animate().fadeIn(duration: 500.ms, delay: 300.ms).scale(begin: const Offset(0.95, 0.95), end: const Offset(1, 1)),
            ],
          ),
        ),
      ),
    );
  }
}
