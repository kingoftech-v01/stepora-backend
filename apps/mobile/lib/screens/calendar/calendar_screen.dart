import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:table_calendar/table_calendar.dart';
import '../../core/theme/app_theme.dart';
import '../../config/api_constants.dart';
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

  void _goToToday() {
    final now = DateTime.now();
    ref.read(calendarProvider.notifier).selectDay(now);
    ref.read(calendarProvider.notifier).changeFocusedDay(now);
    ref.read(calendarProvider.notifier).fetchEvents(
      DateTime(now.year, now.month, 1),
      DateTime(now.year, now.month + 1, 0),
    );
    ref.read(tasksProvider.notifier).fetchTasks(
      date: now.toIso8601String().split('T').first,
    );
  }

  void _showCreateEventDialog() {
    _showEventDialog(null);
  }

  void _showEditEventDialog(CalendarEvent event) {
    _showEventDialog(event);
  }

  void _showEventDialog(CalendarEvent? existingEvent) {
    final titleController = TextEditingController(text: existingEvent?.title ?? '');
    final descController = TextEditingController(text: existingEvent?.description ?? '');
    final calState = ref.read(calendarProvider);
    DateTime selectedDate = existingEvent?.startTime ?? calState.selectedDay;
    TimeOfDay startTime = existingEvent != null
        ? TimeOfDay(hour: existingEvent.startTime.hour, minute: existingEvent.startTime.minute)
        : const TimeOfDay(hour: 9, minute: 0);
    TimeOfDay endTime = existingEvent != null
        ? TimeOfDay(hour: existingEvent.endTime.hour, minute: existingEvent.endTime.minute)
        : const TimeOfDay(hour: 10, minute: 0);

    final isEditing = existingEvent != null;

    showDialog(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setDialogState) => AlertDialog(
          title: Text(isEditing ? 'Edit Event' : 'New Event'),
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
                      firstDate: DateTime(2020),
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
                  if (isEditing) {
                    await ref.read(calendarProvider.notifier).updateEvent(
                      existingEvent.id,
                      {
                        'title': titleController.text.trim(),
                        'description': descController.text.trim(),
                        'start_time': startDateTime.toIso8601String(),
                        'end_time': endDateTime.toIso8601String(),
                      },
                    );
                  } else {
                    final api = ref.read(apiServiceProvider);
                    await api.post(ApiConstants.calendarEvents, data: {
                      'title': titleController.text.trim(),
                      'description': descController.text.trim(),
                      'start_time': startDateTime.toIso8601String(),
                      'end_time': endDateTime.toIso8601String(),
                    });
                  }
                  if (ctx.mounted) Navigator.pop(ctx);
                  _refreshEvents();
                } catch (e) {
                  if (ctx.mounted) {
                    ScaffoldMessenger.of(context).showSnackBar(
                      SnackBar(content: Text('Error: $e')),
                    );
                  }
                }
              },
              style: FilledButton.styleFrom(backgroundColor: AppTheme.primaryPurple),
              child: Text(isEditing ? 'Save' : 'Create'),
            ),
          ],
        ),
      ),
    );
  }

  Future<void> _deleteEvent(CalendarEvent event) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Delete Event?'),
        content: Text('Delete "${event.title}"?'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancel')),
          TextButton(
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('Delete', style: TextStyle(color: Colors.red)),
          ),
        ],
      ),
    );
    if (confirmed != true) return;
    try {
      await ref.read(calendarProvider.notifier).deleteEvent(event.id);
      _refreshEvents();
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Event deleted')),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error: $e')),
        );
      }
    }
  }

  void _showTimeBlocksSheet() {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (ctx) => DraggableScrollableSheet(
        initialChildSize: 0.6,
        minChildSize: 0.3,
        maxChildSize: 0.9,
        expand: false,
        builder: (ctx, scrollController) => _TimeBlocksSheet(
          scrollController: scrollController,
          calendarNotifier: ref.read(calendarProvider.notifier),
        ),
      ),
    );
  }

  void _refreshEvents() {
    final focusedDay = ref.read(calendarProvider).focusedDay;
    ref.read(calendarProvider.notifier).fetchEvents(
      DateTime(focusedDay.year, focusedDay.month, 1),
      DateTime(focusedDay.year, focusedDay.month + 1, 0),
    );
    final selectedDay = ref.read(calendarProvider).selectedDay;
    ref.read(tasksProvider.notifier).fetchTasks(
      date: selectedDay.toIso8601String().split('T').first,
    );
  }

  @override
  Widget build(BuildContext context) {
    final calState = ref.watch(calendarProvider);
    final tasksState = ref.watch(tasksProvider);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Calendar'),
        actions: [
          IconButton(
            icon: const Icon(Icons.today),
            tooltip: 'Today',
            onPressed: _goToToday,
          ),
          IconButton(
            icon: const Icon(Icons.auto_fix_high),
            tooltip: 'Auto-Schedule',
            onPressed: () async {
              try {
                await ref.read(calendarProvider.notifier).autoSchedule();
                _refreshEvents();
                if (mounted) {
                  ScaffoldMessenger.of(context).showSnackBar(
                    const SnackBar(content: Text('Tasks auto-scheduled!')),
                  );
                }
              } catch (e) {
                if (mounted) {
                  ScaffoldMessenger.of(context).showSnackBar(
                    SnackBar(content: Text('Error: $e')),
                  );
                }
              }
            },
          ),
          IconButton(
            icon: const Icon(Icons.settings),
            tooltip: 'Time Blocks',
            onPressed: _showTimeBlocksSheet,
          ),
        ],
      ),
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

          // Events for selected day
          if (calState.eventsForDay(calState.selectedDay).isNotEmpty) ...[
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 12, 16, 4),
              child: Align(
                alignment: Alignment.centerLeft,
                child: Text(
                  'Events',
                  style: Theme.of(context).textTheme.titleSmall?.copyWith(fontWeight: FontWeight.bold),
                ),
              ),
            ),
            SizedBox(
              height: 70,
              child: ListView.builder(
                scrollDirection: Axis.horizontal,
                padding: const EdgeInsets.symmetric(horizontal: 12),
                itemCount: calState.eventsForDay(calState.selectedDay).length,
                itemBuilder: (context, index) {
                  final event = calState.eventsForDay(calState.selectedDay)[index];
                  return GestureDetector(
                    onTap: () => _showEditEventDialog(event),
                    onLongPress: () => _deleteEvent(event),
                    child: Container(
                      width: 180,
                      margin: const EdgeInsets.symmetric(horizontal: 4, vertical: 4),
                      padding: const EdgeInsets.all(10),
                      decoration: BoxDecoration(
                        color: AppTheme.primaryPurple.withValues(alpha: 0.08),
                        borderRadius: BorderRadius.circular(10),
                        border: Border.all(color: AppTheme.primaryPurple.withValues(alpha: 0.2)),
                      ),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Text(
                            event.title,
                            style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 13),
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                          ),
                          const SizedBox(height: 4),
                          Text(
                            '${_formatTime(event.startTime)} - ${_formatTime(event.endTime)}',
                            style: TextStyle(fontSize: 11, color: Colors.grey[600]),
                          ),
                        ],
                      ),
                    ),
                  );
                },
              ),
            ),
          ],

          Padding(
            padding: const EdgeInsets.fromLTRB(16, 12, 16, 4),
            child: Align(
              alignment: Alignment.centerLeft,
              child: Text(
                'Tasks for ${_formatDate(calState.selectedDay)}',
                style: Theme.of(context).textTheme.titleMedium?.copyWith(
                  fontWeight: FontWeight.bold,
                ),
              ),
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

  String _formatTime(DateTime dt) {
    return '${dt.hour.toString().padLeft(2, '0')}:${dt.minute.toString().padLeft(2, '0')}';
  }

  String _formatDate(DateTime date) {
    final months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                     'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    return '${months[date.month - 1]} ${date.day}, ${date.year}';
  }
}

class _TimeBlocksSheet extends StatefulWidget {
  final ScrollController scrollController;
  final CalendarNotifier calendarNotifier;

  const _TimeBlocksSheet({required this.scrollController, required this.calendarNotifier});

  @override
  State<_TimeBlocksSheet> createState() => _TimeBlocksSheetState();
}

class _TimeBlocksSheetState extends State<_TimeBlocksSheet> {
  List<Map<String, dynamic>> _blocks = [];
  bool _isLoading = true;

  @override
  void initState() {
    super.initState();
    _loadBlocks();
  }

  Future<void> _loadBlocks() async {
    setState(() => _isLoading = true);
    try {
      _blocks = await widget.calendarNotifier.fetchTimeBlocks();
    } catch (_) {}
    setState(() => _isLoading = false);
  }

  void _showAddBlockDialog() {
    final labelC = TextEditingController();
    TimeOfDay start = const TimeOfDay(hour: 9, minute: 0);
    TimeOfDay end = const TimeOfDay(hour: 17, minute: 0);

    showDialog(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setDialogState) => AlertDialog(
          title: const Text('Add Time Block'),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              TextField(controller: labelC, decoration: const InputDecoration(labelText: 'Label', border: OutlineInputBorder())),
              const SizedBox(height: 12),
              ListTile(
                contentPadding: EdgeInsets.zero,
                title: const Text('Start'),
                subtitle: Text(start.format(ctx)),
                trailing: const Icon(Icons.access_time),
                onTap: () async {
                  final picked = await showTimePicker(context: ctx, initialTime: start);
                  if (picked != null) setDialogState(() => start = picked);
                },
              ),
              ListTile(
                contentPadding: EdgeInsets.zero,
                title: const Text('End'),
                subtitle: Text(end.format(ctx)),
                trailing: const Icon(Icons.access_time),
                onTap: () async {
                  final picked = await showTimePicker(context: ctx, initialTime: end);
                  if (picked != null) setDialogState(() => end = picked);
                },
              ),
            ],
          ),
          actions: [
            TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Cancel')),
            FilledButton(
              onPressed: () async {
                if (labelC.text.trim().isEmpty) return;
                Navigator.pop(ctx);
                await widget.calendarNotifier.createTimeBlock({
                  'label': labelC.text.trim(),
                  'start_time': '${start.hour.toString().padLeft(2, '0')}:${start.minute.toString().padLeft(2, '0')}',
                  'end_time': '${end.hour.toString().padLeft(2, '0')}:${end.minute.toString().padLeft(2, '0')}',
                });
                _loadBlocks();
              },
              style: FilledButton.styleFrom(backgroundColor: AppTheme.primaryPurple),
              child: const Text('Add'),
            ),
          ],
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 16, 16, 8),
          child: Row(
            children: [
              const Text('Time Blocks', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
              const Spacer(),
              IconButton(onPressed: _showAddBlockDialog, icon: const Icon(Icons.add)),
            ],
          ),
        ),
        const Divider(height: 1),
        Expanded(
          child: _isLoading
              ? const Center(child: CircularProgressIndicator())
              : _blocks.isEmpty
                  ? Center(
                      child: Column(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          Icon(Icons.schedule, size: 48, color: Colors.grey[300]),
                          const SizedBox(height: 8),
                          Text('No time blocks defined', style: TextStyle(color: Colors.grey[500])),
                        ],
                      ),
                    )
                  : ListView.builder(
                      controller: widget.scrollController,
                      itemCount: _blocks.length,
                      itemBuilder: (context, index) {
                        final block = _blocks[index];
                        return ListTile(
                          leading: const Icon(Icons.access_time),
                          title: Text(block['label'] ?? 'Block'),
                          subtitle: Text('${block['start_time']} - ${block['end_time']}'),
                          trailing: IconButton(
                            icon: const Icon(Icons.delete_outline, color: Colors.red),
                            onPressed: () async {
                              await widget.calendarNotifier.deleteTimeBlock(block['id'].toString());
                              _loadBlocks();
                            },
                          ),
                        );
                      },
                    ),
        ),
      ],
    );
  }
}
