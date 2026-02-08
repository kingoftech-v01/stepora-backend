import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../config/api_constants.dart';
import '../models/calendar_event.dart';
import '../services/api_service.dart';

class CalendarState {
  final Map<DateTime, List<CalendarEvent>> events;
  final DateTime selectedDay;
  final DateTime focusedDay;
  final bool isLoading;

  CalendarState({
    this.events = const {},
    DateTime? selectedDay,
    DateTime? focusedDay,
    this.isLoading = false,
  })  : selectedDay = selectedDay ?? DateTime.now(),
        focusedDay = focusedDay ?? DateTime.now();

  CalendarState copyWith({
    Map<DateTime, List<CalendarEvent>>? events,
    DateTime? selectedDay,
    DateTime? focusedDay,
    bool? isLoading,
  }) {
    return CalendarState(
      events: events ?? this.events,
      selectedDay: selectedDay ?? this.selectedDay,
      focusedDay: focusedDay ?? this.focusedDay,
      isLoading: isLoading ?? this.isLoading,
    );
  }

  List<CalendarEvent> eventsForDay(DateTime day) {
    final key = DateTime(day.year, day.month, day.day);
    return events[key] ?? [];
  }
}

class CalendarNotifier extends StateNotifier<CalendarState> {
  final ApiService _api;

  CalendarNotifier(this._api) : super(CalendarState());

  Future<void> fetchEvents(DateTime start, DateTime end) async {
    state = state.copyWith(isLoading: true);
    try {
      final response = await _api.get(ApiConstants.calendarEvents, queryParams: {
        'start_date': start.toIso8601String().split('T').first,
        'end_date': end.toIso8601String().split('T').first,
      });
      final results = response.data['results'] as List? ?? response.data as List;
      final allEvents = results.map((e) => CalendarEvent.fromJson(e)).toList();

      final eventMap = <DateTime, List<CalendarEvent>>{};
      for (final event in allEvents) {
        final key = DateTime(event.startTime.year, event.startTime.month, event.startTime.day);
        eventMap.putIfAbsent(key, () => []).add(event);
      }

      state = state.copyWith(events: eventMap, isLoading: false);
    } catch (_) {
      state = state.copyWith(isLoading: false);
    }
  }

  void selectDay(DateTime day) {
    state = state.copyWith(selectedDay: day);
  }

  void changeFocusedDay(DateTime day) {
    state = state.copyWith(focusedDay: day);
  }

  Future<void> createEvent(Map<String, dynamic> data) async {
    await _api.post(ApiConstants.calendarEvents, data: data);
    await fetchEvents(
      DateTime(state.focusedDay.year, state.focusedDay.month, 1),
      DateTime(state.focusedDay.year, state.focusedDay.month + 1, 0),
    );
  }
}

final calendarProvider = StateNotifierProvider<CalendarNotifier, CalendarState>((ref) {
  return CalendarNotifier(ref.read(apiServiceProvider));
});
