import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:table_calendar/table_calendar.dart';
import '../../core/theme/app_theme.dart';
import '../../models/calendar_event.dart';
import '../../providers/calendar_provider.dart';
import '../../providers/tasks_provider.dart';
import '../../widgets/task_tile.dart';

class CalendarScreen extends ConsumerStatefulWidget {
  const CalendarScreen({super.key});

  @override
  ConsumerState<CalendarScreen> createState() => _CalendarScreenState();
}

class _CalendarScreenState extends ConsumerState<CalendarScreen> {
  CalendarFormat _calendarFormat = CalendarFormat.month;

  @override
  void initState() {
    super.initState();
    Future.microtask(() {
      final now = DateTime.now();
      ref.read(calendarProvider.notifier).fetchEvents(
        DateTime(now.year, now.month, 1),
        DateTime(now.year, now.month + 1, 0),
      );
      ref.read(tasksProvider.notifier).fetchTasks(
        date: now.toIso8601String().split('T').first,
      );
    });
  }

  @override
  Widget build(BuildContext context) {
    final calState = ref.watch(calendarProvider);
    final tasksState = ref.watch(tasksProvider);

    return Scaffold(
      appBar: AppBar(title: const Text('Calendar')),
      body: Column(
        children: [
          TableCalendar<CalendarEvent>(
            firstDay: DateTime(2020),
            lastDay: DateTime(2030),
            focusedDay: calState.focusedDay,
            selectedDayPredicate: (day) => isSameDay(calState.selectedDay, day),
            calendarFormat: _calendarFormat,
            eventLoader: (day) => calState.eventsForDay(day),
            onDaySelected: (selected, focused) {
              ref.read(calendarProvider.notifier).selectDay(selected);
              ref.read(calendarProvider.notifier).changeFocusedDay(focused);
              ref.read(tasksProvider.notifier).fetchTasks(
                date: selected.toIso8601String().split('T').first,
              );
            },
            onFormatChanged: (format) {
              setState(() => _calendarFormat = format);
            },
            onPageChanged: (focusedDay) {
              ref.read(calendarProvider.notifier).changeFocusedDay(focusedDay);
              ref.read(calendarProvider.notifier).fetchEvents(
                DateTime(focusedDay.year, focusedDay.month, 1),
                DateTime(focusedDay.year, focusedDay.month + 1, 0),
              );
            },
            calendarStyle: CalendarStyle(
              todayDecoration: BoxDecoration(
                color: AppTheme.primaryPurple.withOpacity(0.3),
                shape: BoxShape.circle,
              ),
              selectedDecoration: const BoxDecoration(
                color: AppTheme.primaryPurple,
                shape: BoxShape.circle,
              ),
              markerDecoration: const BoxDecoration(
                color: AppTheme.accent,
                shape: BoxShape.circle,
              ),
              markerSize: 6,
              markersMaxCount: 3,
            ),
            headerStyle: const HeaderStyle(
              formatButtonVisible: true,
              titleCentered: true,
            ),
          ),
          const Divider(height: 1),
          Padding(
            padding: const EdgeInsets.all(16),
            child: Row(
              children: [
                Text(
                  'Tasks for ${_formatDate(calState.selectedDay)}',
                  style: Theme.of(context).textTheme.titleMedium?.copyWith(
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ],
            ),
          ),
          Expanded(
            child: tasksState.isLoading
                ? const Center(child: CircularProgressIndicator())
                : tasksState.tasks.isEmpty
                    ? Center(
                        child: Column(
                          mainAxisAlignment: MainAxisAlignment.center,
                          children: [
                            Icon(Icons.event_available, size: 48, color: Colors.grey[300]),
                            const SizedBox(height: 8),
                            Text('No tasks for this day',
                                style: TextStyle(color: Colors.grey[500])),
                          ],
                        ),
                      )
                    : ListView.builder(
                        padding: const EdgeInsets.symmetric(horizontal: 16),
                        itemCount: tasksState.tasks.length,
                        itemBuilder: (context, index) {
                          final task = tasksState.tasks[index];
                          return TaskTile(
                            task: task,
                            onComplete: () async {
                              await ref.read(tasksProvider.notifier).completeTask(task.id);
                            },
                          );
                        },
                      ),
          ),
        ],
      ),
    );
  }

  String _formatDate(DateTime date) {
    final months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                     'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    return '${months[date.month - 1]} ${date.day}, ${date.year}';
  }
}
