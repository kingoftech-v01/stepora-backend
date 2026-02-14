import 'dart:ui';
import 'package:flutter/material.dart';
import '../core/theme/app_theme.dart';

class ChatInput extends StatefulWidget {
  final Function(String) onSend;

  const ChatInput({super.key, required this.onSend});

  @override
  State<ChatInput> createState() => _ChatInputState();
}

class _ChatInputState extends State<ChatInput> {
  final _controller = TextEditingController();
  bool _hasText = false;

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  void _send() {
    final text = _controller.text.trim();
    if (text.isEmpty) return;
    widget.onSend(text);
    _controller.clear();
    setState(() => _hasText = false);
  }

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    return ClipRRect(
      child: BackdropFilter(
        filter: ImageFilter.blur(sigmaX: 20, sigmaY: 20),
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
          decoration: BoxDecoration(
            color: isDark
                ? Colors.black.withValues(alpha: 0.2)
                : Colors.white.withValues(alpha: 0.5),
            border: Border(
              top: BorderSide(
                color: Colors.white.withValues(alpha: isDark ? 0.1 : 0.3),
              ),
            ),
          ),
          child: SafeArea(
            child: Row(
              children: [
                Expanded(
                  child: Container(
                    decoration: BoxDecoration(
                      color: isDark
                          ? Colors.white.withValues(alpha: 0.08)
                          : Colors.white.withValues(alpha: 0.4),
                      borderRadius: BorderRadius.circular(24),
                      border: Border.all(
                        color: Colors.white.withValues(alpha: isDark ? 0.12 : 0.3),
                      ),
                    ),
                    child: TextField(
                      controller: _controller,
                      textInputAction: TextInputAction.send,
                      maxLines: 4,
                      minLines: 1,
                      onChanged: (v) => setState(() => _hasText = v.trim().isNotEmpty),
                      onSubmitted: (_) => _send(),
                      style: TextStyle(
                        color: isDark ? Colors.white : const Color(0xFF1E1B4B),
                      ),
                      decoration: InputDecoration(
                        hintText: 'Type a message...',
                        hintStyle: TextStyle(
                          color: isDark ? Colors.white38 : Colors.grey[600],
                        ),
                        border: InputBorder.none,
                        contentPadding:
                            const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
                      ),
                    ),
                  ),
                ),
                const SizedBox(width: 8),
                AnimatedScale(
                  scale: _hasText ? 1.0 : 0.8,
                  duration: const Duration(milliseconds: 200),
                  child: Container(
                    decoration: BoxDecoration(
                      gradient: _hasText
                          ? const LinearGradient(
                              colors: [AppTheme.primaryPurple, AppTheme.primaryDark],
                            )
                          : null,
                      color: _hasText
                          ? null
                          : (isDark
                              ? Colors.white.withValues(alpha: 0.1)
                              : Colors.grey[600]),
                      shape: BoxShape.circle,
                    ),
                    child: IconButton(
                      onPressed: _hasText ? _send : null,
                      icon: const Icon(Icons.send, size: 20),
                      color: Colors.white,
                    ),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
