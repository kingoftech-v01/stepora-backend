import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../models/user.dart';
import '../services/auth_service.dart';
import '../services/api_service.dart';

class AuthState {
  final String? token;
  final User? user;
  final bool isLoading;
  final String? error;

  const AuthState({
    this.token,
    this.user,
    this.isLoading = false,
    this.error,
  });

  AuthState copyWith({
    String? token,
    User? user,
    bool? isLoading,
    String? error,
    bool clearError = false,
    bool clearToken = false,
    bool clearUser = false,
  }) {
    return AuthState(
      token: clearToken ? null : (token ?? this.token),
      user: clearUser ? null : (user ?? this.user),
      isLoading: isLoading ?? this.isLoading,
      error: clearError ? null : (error ?? this.error),
    );
  }
}

class AuthNotifier extends Notifier<AuthState> {
  late AuthService _authService;
  late ApiService _apiService;

  @override
  AuthState build() {
    _authService = ref.read(authServiceProvider);
    _apiService = ref.read(apiServiceProvider);
    _checkAuth();
    return const AuthState();
  }

  Future<void> _checkAuth() async {
    final token = await _apiService.getToken();
    if (token != null) {
      state = state.copyWith(token: token, isLoading: true);
      try {
        final user = await _authService.getUserProfile();
        state = state.copyWith(user: user, isLoading: false);
      } catch (_) {
        await _apiService.clearToken();
        state = const AuthState();
      }
    }
  }

  Future<void> login(String email, String password) async {
    state = state.copyWith(isLoading: true, clearError: true);
    try {
      final result = await _authService.login(email, password);
      final user = await _authService.getUserProfile();
      state = state.copyWith(token: result.token, user: user, isLoading: false);
    } catch (e) {
      state = state.copyWith(
        isLoading: false,
        error: _extractError(e),
      );
    }
  }

  Future<void> register(String email, String password, String password2) async {
    state = state.copyWith(isLoading: true, clearError: true);
    try {
      final result = await _authService.register(email, password, password2);
      final user = await _authService.getUserProfile();
      state = state.copyWith(token: result.token, user: user, isLoading: false);
    } catch (e) {
      state = state.copyWith(
        isLoading: false,
        error: _extractError(e),
      );
    }
  }

  Future<void> loginWithGoogle(String accessToken) async {
    state = state.copyWith(isLoading: true, clearError: true);
    try {
      final result = await _authService.loginWithGoogle(accessToken);
      final user = await _authService.getUserProfile();
      state = state.copyWith(token: result.token, user: user, isLoading: false);
    } catch (e) {
      state = state.copyWith(isLoading: false, error: _extractError(e));
    }
  }

  Future<void> loginWithApple({
    required String identityToken,
    required String authorizationCode,
    String? firstName,
    String? lastName,
  }) async {
    state = state.copyWith(isLoading: true, clearError: true);
    try {
      final result = await _authService.loginWithApple(
        identityToken: identityToken,
        authorizationCode: authorizationCode,
        firstName: firstName,
        lastName: lastName,
      );
      final user = await _authService.getUserProfile();
      state = state.copyWith(token: result.token, user: user, isLoading: false);
    } catch (e) {
      state = state.copyWith(isLoading: false, error: _extractError(e));
    }
  }

  Future<void> logout() async {
    await _authService.logout();
    state = const AuthState();
  }

  Future<void> refreshUser() async {
    try {
      final user = await _authService.getUserProfile();
      state = state.copyWith(user: user);
    } catch (_) {}
  }

  String _extractError(dynamic e) {
    if (e is Exception) {
      return e.toString().replaceAll('Exception: ', '');
    }
    return 'An error occurred';
  }
}

final authProvider = NotifierProvider<AuthNotifier, AuthState>(AuthNotifier.new);
