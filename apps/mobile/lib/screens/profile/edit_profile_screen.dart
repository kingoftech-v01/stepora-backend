import 'dart:io';
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:image_picker/image_picker.dart';
import '../../core/theme/app_theme.dart';
import '../../providers/auth_provider.dart';
import '../../services/api_service.dart';
import '../../widgets/gradient_background.dart';
import '../../widgets/glass_container.dart';
import '../../widgets/glass_app_bar.dart';
import '../../widgets/glass_button.dart';
import '../../widgets/glass_text_field.dart';

class EditProfileScreen extends ConsumerStatefulWidget {
  const EditProfileScreen({super.key});

  @override
  ConsumerState<EditProfileScreen> createState() => _EditProfileScreenState();
}

class _EditProfileScreenState extends ConsumerState<EditProfileScreen> {
  final _formKey = GlobalKey<FormState>();
  late TextEditingController _displayNameController;
  late TextEditingController _timezoneController;
  bool _isLoading = false;
  bool _isUploadingPhoto = false;
  File? _selectedImage;

  @override
  void initState() {
    super.initState();
    final user = ref.read(authProvider).user;
    _displayNameController = TextEditingController(text: user?.displayName ?? '');
    _timezoneController = TextEditingController(text: user?.timezone ?? 'UTC');
  }

  @override
  void dispose() {
    _displayNameController.dispose();
    _timezoneController.dispose();
    super.dispose();
  }

  Future<void> _pickImage() async {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final picker = ImagePicker();
    final source = await showModalBottomSheet<ImageSource>(
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
              const SizedBox(height: 8),
              ListTile(
                leading: Container(
                  padding: const EdgeInsets.all(8),
                  decoration: BoxDecoration(color: AppTheme.primaryPurple.withValues(alpha: 0.15), borderRadius: BorderRadius.circular(10)),
                  child: Icon(Icons.camera_alt, color: AppTheme.primaryPurple),
                ),
                title: Text('Take Photo', style: TextStyle(color: isDark ? Colors.white : const Color(0xFF1E1B4B))),
                onTap: () => Navigator.pop(ctx, ImageSource.camera),
              ),
              ListTile(
                leading: Container(
                  padding: const EdgeInsets.all(8),
                  decoration: BoxDecoration(color: AppTheme.primaryPurple.withValues(alpha: 0.15), borderRadius: BorderRadius.circular(10)),
                  child: Icon(Icons.photo_library, color: AppTheme.primaryPurple),
                ),
                title: Text('Choose from Gallery', style: TextStyle(color: isDark ? Colors.white : const Color(0xFF1E1B4B))),
                onTap: () => Navigator.pop(ctx, ImageSource.gallery),
              ),
              const SizedBox(height: 16),
            ],
          ),
        ),
      ),
    );

    if (source == null) return;

    final picked = await picker.pickImage(source: source, maxWidth: 512, maxHeight: 512, imageQuality: 80);
    if (picked == null) return;

    setState(() => _selectedImage = File(picked.path));
    await _uploadAvatar(File(picked.path));
  }

  Future<void> _uploadAvatar(File imageFile) async {
    setState(() => _isUploadingPhoto = true);
    try {
      final api = ref.read(apiServiceProvider);
      final formData = FormData.fromMap({
        'avatar_image': await MultipartFile.fromFile(imageFile.path, filename: 'avatar.jpg'),
      });
      await api.post('/users/me/upload-avatar/', data: formData);
      await ref.read(authProvider.notifier).refreshUser();
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Profile photo updated!')));
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Upload failed: $e')));
      }
    } finally {
      if (mounted) setState(() => _isUploadingPhoto = false);
    }
  }

  Future<void> _save() async {
    if (!_formKey.currentState!.validate()) return;
    setState(() => _isLoading = true);
    try {
      final api = ref.read(apiServiceProvider);
      await api.put('/users/me/', data: {
        'display_name': _displayNameController.text.trim(),
        'timezone': _timezoneController.text.trim(),
      });
      await ref.read(authProvider.notifier).refreshUser();
      if (mounted) context.pop();
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Error: $e')));
      }
    } finally {
      if (mounted) setState(() => _isLoading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final user = ref.watch(authProvider).user;
    final avatarUrl = user?.avatarUrl;
    final isDark = Theme.of(context).brightness == Brightness.dark;

    return GradientBackground(
      colors: isDark ? AppTheme.gradientProfile : AppTheme.gradientProfileLight,
      child: Scaffold(
        backgroundColor: Colors.transparent,
        extendBodyBehindAppBar: true,
        appBar: const GlassAppBar(title: 'Edit Profile'),
        body: SingleChildScrollView(
          padding: EdgeInsets.fromLTRB(24, MediaQuery.of(context).padding.top + kToolbarHeight + 16, 24, 32),
          child: Form(
            key: _formKey,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                // Avatar with glass ring
                Center(
                  child: Stack(
                    children: [
                      Container(
                        padding: const EdgeInsets.all(4),
                        decoration: BoxDecoration(
                          shape: BoxShape.circle,
                          gradient: const LinearGradient(
                            colors: [AppTheme.primaryPurple, Color(0xFF8B5CF6), AppTheme.accent],
                          ),
                          boxShadow: [
                            BoxShadow(
                              color: AppTheme.primaryPurple.withValues(alpha: 0.4),
                              blurRadius: 20,
                              spreadRadius: 2,
                            ),
                          ],
                        ),
                        child: CircleAvatar(
                          radius: 50,
                          backgroundColor: isDark ? const Color(0xFF1E1B4B) : Colors.white,
                          backgroundImage: _selectedImage != null
                              ? FileImage(_selectedImage!) as ImageProvider
                              : avatarUrl != null ? NetworkImage(avatarUrl) : null,
                          child: (_selectedImage == null && avatarUrl == null)
                              ? Text(
                                  (user?.displayName ?? 'U')[0].toUpperCase(),
                                  style: TextStyle(fontSize: 36, fontWeight: FontWeight.bold, color: AppTheme.primaryPurple),
                                )
                              : null,
                        ),
                      ),
                      Positioned(
                        bottom: 0,
                        right: 0,
                        child: GestureDetector(
                          onTap: _isUploadingPhoto ? null : _pickImage,
                          child: Container(
                            padding: const EdgeInsets.all(8),
                            decoration: BoxDecoration(
                              gradient: const LinearGradient(colors: [AppTheme.primaryPurple, Color(0xFF8B5CF6)]),
                              shape: BoxShape.circle,
                              border: Border.all(color: isDark ? const Color(0xFF1E1B4B) : Colors.white, width: 3),
                              boxShadow: [BoxShadow(color: AppTheme.primaryPurple.withValues(alpha: 0.3), blurRadius: 8)],
                            ),
                            child: _isUploadingPhoto
                                ? const SizedBox(height: 16, width: 16, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                                : const Icon(Icons.camera_alt, size: 16, color: Colors.white),
                          ),
                        ),
                      ),
                    ],
                  ),
                ).animate().fadeIn(duration: 500.ms).scale(begin: const Offset(0.8, 0.8), end: const Offset(1, 1)),

                const SizedBox(height: 32),

                // Form fields in glass container
                GlassContainer(
                  padding: const EdgeInsets.all(20),
                  opacity: isDark ? 0.12 : 0.25,
                  child: Column(
                    children: [
                      GlassTextField(
                        controller: _displayNameController,
                        label: 'Display Name',
                        prefixIcon: Icon(Icons.person_outline, color: AppTheme.primaryPurple, size: 20),
                        validator: (v) => v == null || v.trim().isEmpty ? 'Name is required' : null,
                      ),
                      const SizedBox(height: 16),
                      GlassTextField(
                        controller: _timezoneController,
                        label: 'Timezone',
                        hint: 'e.g. America/New_York',
                        prefixIcon: Icon(Icons.access_time, color: AppTheme.primaryPurple, size: 20),
                      ),
                    ],
                  ),
                ).animate().fadeIn(duration: 500.ms, delay: 150.ms).slideY(begin: 0.05, end: 0),

                const SizedBox(height: 32),

                GlassButton(
                  label: 'Save',
                  icon: Icons.check,
                  isLoading: _isLoading,
                  onPressed: _isLoading ? null : _save,
                ).animate().fadeIn(duration: 500.ms, delay: 300.ms),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
