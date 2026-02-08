import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../config/api_constants.dart';
import '../models/user.dart';
import 'api_service.dart';

final authServiceProvider = Provider<AuthService>((ref) {
  return AuthService(ref.read(apiServiceProvider));
});

class AuthService {
  final ApiService _api;

  AuthService(this._api);

  Future<AuthResult> login(String email, String password) async {
    final response = await _api.post(ApiConstants.login, data: {
      'email': email,
      'password': password,
    });
    final token = response.data['key'];
    await _api.setToken(token);
    return AuthResult(token: token);
  }

  Future<AuthResult> register(String email, String password, String password2) async {
    final response = await _api.post(ApiConstants.register, data: {
      'email': email,
      'password1': password,
      'password2': password2,
    });
    final token = response.data['key'];
    await _api.setToken(token);
    return AuthResult(token: token);
  }

  Future<void> logout() async {
    try {
      await _api.post(ApiConstants.logout);
    } finally {
      await _api.clearToken();
    }
  }

  Future<User> getUser() async {
    final response = await _api.get(ApiConstants.user);
    return User.fromJson(response.data);
  }

  Future<User> getUserProfile() async {
    final response = await _api.get(ApiConstants.userProfile);
    return User.fromJson(response.data);
  }

  Future<User> updateProfile(Map<String, dynamic> data) async {
    final response = await _api.patch(ApiConstants.userProfile, data: data);
    return User.fromJson(response.data);
  }

  Future<void> resetPassword(String email) async {
    await _api.post(ApiConstants.passwordReset, data: {
      'email': email,
    });
  }

  Future<void> changePassword(String oldPassword, String newPassword) async {
    await _api.post(ApiConstants.passwordChange, data: {
      'old_password': oldPassword,
      'new_password1': newPassword,
      'new_password2': newPassword,
    });
  }

  Future<bool> isLoggedIn() async {
    final token = await _api.getToken();
    return token != null;
  }
}

class AuthResult {
  final String token;

  AuthResult({required this.token});
}
