import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../config/api_constants.dart';
import '../models/task.dart';
import '../services/api_service.dart';

class TasksState {
  final List<Task> tasks;
  final bool isLoading;

  const TasksState({this.tasks = const [], this.isLoading = false});

  TasksState copyWith({List<Task>? tasks, bool? isLoading}) {
    return TasksState(
      tasks: tasks ?? this.tasks,
      isLoading: isLoading ?? this.isLoading,
    );
  }
}

class TasksNotifier extends Notifier<TasksState> {
  late ApiService _api;

  @override
  TasksState build() {
    _api = ref.read(apiServiceProvider);
    return const TasksState();
  }

  Future<void> fetchTasks({String? date}) async {
    state = state.copyWith(isLoading: true);
    try {
      final response = await _api.get(
        ApiConstants.tasks,
        queryParams: date != null ? {'scheduled_date': date} : null,
      );
      final results = response.data['results'] as List? ?? response.data as List;
      final tasks = results.map((t) => Task.fromJson(t)).toList();
      state = state.copyWith(tasks: tasks, isLoading: false);
    } catch (_) {
      state = state.copyWith(isLoading: false);
    }
  }

  Future<void> completeTask(String taskId) async {
    await _api.post(ApiConstants.taskComplete(taskId));
    state = state.copyWith(
      tasks: state.tasks.map((t) {
        if (t.id == taskId) {
          return Task(
            id: t.id,
            goalId: t.goalId,
            title: t.title,
            description: t.description,
            priority: t.priority,
            estimatedMinutes: t.estimatedMinutes,
            isCompleted: true,
            completedAt: DateTime.now(),
            scheduledDate: t.scheduledDate,
            scheduledTime: t.scheduledTime,
            twoMinuteAction: t.twoMinuteAction,
            xpReward: t.xpReward,
            createdAt: t.createdAt,
          );
        }
        return t;
      }).toList(),
    );
  }

  Future<Task> createTask(Map<String, dynamic> data) async {
    final response = await _api.post(ApiConstants.tasks, data: data);
    final task = Task.fromJson(response.data);
    state = state.copyWith(tasks: [...state.tasks, task]);
    return task;
  }
}

final tasksProvider = NotifierProvider<TasksNotifier, TasksState>(TasksNotifier.new);
