import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:table_calendar/table_calendar.dart';
import '../../core/theme/app_theme.dart';
import '../../models/calendar_event.dart';
import '../../providers/calendar_provider.dart';
import '../../providers/tasks_provider.dart';
import '../../services/api_service.dart';
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

  void _showCreateEventDialog() {
    final titleController = TextEditingController();
    final descController = TextEditingController();
    final calState = ref.read(calendarProvider);
    DateTime selectedDate = calState.selectedDay;
    TimeOfDay startTime = const TimeOfDay(hour: 9, minute: 0);
    TimeOfDay endTime = const TimeOfDay(hour: 10, minute: 0);

    showDialog(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setDialogState) => AlertDialog(
          title: const Text('New Event'),
          content: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                TextField(
                  controller: titleController,
                  decoration: const InputDecoration(labelText: 'Title', border: OutlineInputBorder()),
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: descController,
                  decoration: const InputDecoration(labelText: 'Description', border: OutlineInputBorder()),
                  maxLines: 2,
                ),
                const SizedBox(height: 12),
                ListTile(
                  contentPadding: EdgeInsets.zero,
                  title: const Text('Date'),
                  subtitle: Text(
                    '${selectedDate.year}-${selectedDate.month.toString().padLeft(2, '0')}-${selectedDate.day.toString().padLeft(2, '0')}',
                  ),
                  trailing: const Icon(Icons.calendar_today),
                  onTap: () async {
                    final picked = await showDatePicker(
                      context: ctx,
                      initialDate: selectedDate,
                      firstDate: DateTime.now(),
                      lastDate: DateTime(2030),
                    );
                    if (picked != null) setDialogState(() => selectedDate = picked);
                  },
                ),
                ListTile(
                  contentPadding: EdgeInsets.zero,
                  title: const Text('Start Time'),
                  subtitle: Text(startTime.format(ctx)),
                  trailing: const Icon(Icons.access_time),
                  onTap: () async {
                    final picked = await showTimePicker(context: ctx, initialTime: startTime);
                    if (picked != null) setDialogState(() => startTime = picked);
                  },
                ),
                ListTile(
                  contentPadding: EdgeInsets.zero,
                  title: const Text('End Time'),
                  subtitle: Text(endTime.format(ctx)),
                  trailing: const Icon(Icons.access_time),
                  onTap: () async {
                    final picked = await showTimePicker(context: ctx, initialTime: endTime);
                    if (picked != null) setDialogState(() => endTime = picked);
                  },
                ),
              ],
            ),
          ),
          actions: [
            TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Cancel')),
            FilledButton(
              onPressed: () async {
                if (titleController.text.trim().isEmpty) return;
                final startDateTime = DateTime(
                  selectedDate.year, selectedDate.month, selectedDate.day,
                  startTime.hour, startTime.minute,
                );
                final endDateTime = DateTime(
                  selectedDate.year, selectedDate.month, selectedDate.day,
                  endTime.hour, endTime.minute,
                );
                try {
                  final api = ref.read(apiServiceProvider);
                  await api.post('/calendar/', data: {
                    'title': titleController.text.trim(),
                    'description': descController.text.trim(),
                    'start_time': startDateTime.toIso8601String(),
                    'end_time': endDateTime.toIso8601String(),
                  });
                  if (ctx.mounted) Navigator.pop(ctx);
                  final focusedDay = ref.read(calendarProvider).focusedDay;
                  ref.read(calendarProvider.notifier).fetchEvents(
                    DateTime(focusedDay.year, focusedDay.month, 1),
                    DateTime(focusedDay.year, focusedDay.month + 1, 0),
                  );
                  ref.read(tasksProvider.notifier).fetchTasks(
                    date: selectedDate.toIso8601String().split('T').first,
                  );
                } catch (e) {
                  if (ctx.mounted) {
                    ScaffoldMessenger.of(context).showSnackBar(
                      SnackBar(content: Text('Error: $e')),
                    );
                  }
                }
              },
              style: FilledButton.styleFrom(backgroundColor: AppTheme.primaryPurple),
              child: const Text('Create'),
            ),
          ],
        ),
      ),
    );
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
                color: AppTheme.primaryPurple.withValues(alpha: 0.3),
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
      floatingActionButton: FloatingActionButton(
        onPressed: _showCreateEventDialog,
        backgroundColor: AppTheme.primaryPurple,
        foregroundColor: Colors.white,
        child: const Icon(Icons.add),
      ),
    );
  }

  String _formatDate(DateTime date) {
    final months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                     'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    return '${months[date.month - 1]} ${date.day}, ${date.year}';
  }
}
