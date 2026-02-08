import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../config/api_constants.dart';
import '../models/dream.dart';
import '../models/goal.dart';
import '../models/task.dart';
import '../services/api_service.dart';

class DreamsState {
  final List<Dream> dreams;
  final bool isLoading;
  final String? error;

  const DreamsState({
    this.dreams = const [],
    this.isLoading = false,
    this.error,
  });

  DreamsState copyWith({
    List<Dream>? dreams,
    bool? isLoading,
    String? error,
    bool clearError = false,
  }) {
    return DreamsState(
      dreams: dreams ?? this.dreams,
      isLoading: isLoading ?? this.isLoading,
      error: clearError ? null : (error ?? this.error),
    );
  }
}

class DreamsNotifier extends StateNotifier<DreamsState> {
  final ApiService _api;

  DreamsNotifier(this._api) : super(const DreamsState());

  Future<void> fetchDreams() async {
    state = state.copyWith(isLoading: true, clearError: true);
    try {
      final response = await _api.get(ApiConstants.dreams);
      final results = response.data['results'] as List? ?? response.data as List;
      final dreams = results.map((d) => Dream.fromJson(d)).toList();
      state = state.copyWith(dreams: dreams, isLoading: false);
    } catch (e) {
      state = state.copyWith(isLoading: false, error: e.toString());
    }
  }

  Future<Dream> createDream(Map<String, dynamic> data) async {
    final response = await _api.post(ApiConstants.dreams, data: data);
    final dream = Dream.fromJson(response.data);
    state = state.copyWith(dreams: [...state.dreams, dream]);
    return dream;
  }

  Future<Dream> getDreamDetail(String id) async {
    final response = await _api.get(ApiConstants.dreamDetail(id));
    return Dream.fromJson(response.data);
  }

  Future<void> generatePlan(String dreamId) async {
    await _api.post(ApiConstants.dreamGeneratePlan(dreamId));
  }

  Future<String?> generateVisionBoard(String dreamId) async {
    final response = await _api.post(ApiConstants.dreamVisionBoard(dreamId));
    return response.data['vision_board_url'];
  }

  Future<List<Goal>> getGoals(String dreamId) async {
    final response = await _api.get(ApiConstants.dreamGoals(dreamId));
    final results = response.data['results'] as List? ?? response.data as List;
    return results.map((g) => Goal.fromJson(g)).toList();
  }

  Future<List<Task>> getTasks(String goalId) async {
    final response = await _api.get(ApiConstants.goalTasks(goalId));
    final results = response.data['results'] as List? ?? response.data as List;
    return results.map((t) => Task.fromJson(t)).toList();
  }

  Future<void> completeTask(String taskId) async {
    await _api.post(ApiConstants.taskComplete(taskId));
  }

  Future<Map<String, dynamic>> startMicroStart(String taskId) async {
    final response = await _api.post(ApiConstants.taskMicroStart(taskId));
    return response.data;
  }

  Future<void> deleteDream(String id) async {
    await _api.delete(ApiConstants.dreamDetail(id));
    state = state.copyWith(
      dreams: state.dreams.where((d) => d.id != id).toList(),
    );
  }
}

final dreamsProvider = StateNotifierProvider<DreamsNotifier, DreamsState>((ref) {
  return DreamsNotifier(ref.read(apiServiceProvider));
});
