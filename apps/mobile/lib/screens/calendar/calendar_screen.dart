import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:table_calendar/table_calendar.dart';
import '../../core/theme/app_theme.dart';
import '../../config/api_constants.dart';
import '../../models/calendar_event.dart';
import '../../providers/calendar_provider.dart';
import '../../providers/tasks_provider.dart';
import '../../services/api_service.dart';
import '../../widgets/gradient_background.dart';
import '../../widgets/glass_container.dart';
import '../../widgets/glass_app_bar.dart';
import '../../widgets/glass_button.dart';
import '../../widgets/glass_text_field.dart';
import '../../widgets/animated_list_item.dart';
import '../../widgets/loading_shimmer.dart';
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

  void _showCreateEventDialog() => _showEventDialog(null);

  void _showEditEventDialog(CalendarEvent event) => _showEventDialog(event);

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
    final isDark = Theme.of(context).brightness == Brightness.dark;

    showDialog(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setDialogState) => AlertDialog(
          backgroundColor: isDark ? const Color(0xFF1E1B4B) : Colors.white,
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
          title: Text(isEditing ? 'Edit Event' : 'New Event', style: TextStyle(color: isDark ? Colors.white : const Color(0xFF1E1B4B))),
          content: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                GlassTextField(controller: titleController, label: 'Title', textInputAction: TextInputAction.next),
                const SizedBox(height: 12),
                GlassTextField(controller: descController, label: 'Description', maxLines: 2),
                const SizedBox(height: 12),
                _buildDateTimeTile(ctx, isDark, 'Date',
                  '${selectedDate.year}-${selectedDate.month.toString().padLeft(2, '0')}-${selectedDate.day.toString().padLeft(2, '0')}',
                  Icons.calendar_today, () async {
                    final picked = await showDatePicker(context: ctx, initialDate: selectedDate, firstDate: DateTime(2020), lastDate: DateTime(2030));
                    if (picked != null) setDialogState(() => selectedDate = picked);
                  },
                ),
                _buildDateTimeTile(ctx, isDark, 'Start Time', startTime.format(ctx), Icons.access_time, () async {
                  final picked = await showTimePicker(context: ctx, initialTime: startTime);
                  if (picked != null) setDialogState(() => startTime = picked);
                }),
                _buildDateTimeTile(ctx, isDark, 'End Time', endTime.format(ctx), Icons.access_time, () async {
                  final picked = await showTimePicker(context: ctx, initialTime: endTime);
                  if (picked != null) setDialogState(() => endTime = picked);
                }),
              ],
            ),
          ),
          actions: [
            TextButton(onPressed: () => Navigator.pop(ctx), child: Text('Cancel', style: TextStyle(color: isDark ? Colors.white54 : Colors.grey))),
            GlassButton(
              label: isEditing ? 'Save' : 'Create',
              onPressed: () async {
                if (titleController.text.trim().isEmpty) return;
                final startDateTime = DateTime(selectedDate.year, selectedDate.month, selectedDate.day, startTime.hour, startTime.minute);
                final endDateTime = DateTime(selectedDate.year, selectedDate.month, selectedDate.day, endTime.hour, endTime.minute);
                try {
                  if (isEditing) {
                    await ref.read(calendarProvider.notifier).updateEvent(existingEvent.id, {
                      'title': titleController.text.trim(), 'description': descController.text.trim(),
                      'start_time': startDateTime.toIso8601String(), 'end_time': endDateTime.toIso8601String(),
                    });
                  } else {
                    final api = ref.read(apiServiceProvider);
                    await api.post(ApiConstants.calendarEvents, data: {
                      'title': titleController.text.trim(), 'description': descController.text.trim(),
                      'start_time': startDateTime.toIso8601String(), 'end_time': endDateTime.toIso8601String(),
                    });
                  }
                  if (ctx.mounted) Navigator.pop(ctx);
                  _refreshEvents();
                } catch (e) {
                  if (ctx.mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Error: $e')));
                }
              },
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildDateTimeTile(BuildContext ctx, bool isDark, String title, String value, IconData icon, VoidCallback onTap) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        margin: const EdgeInsets.only(bottom: 8),
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
        decoration: BoxDecoration(
          color: isDark ? Colors.white.withValues(alpha: 0.06) : Colors.grey.withValues(alpha: 0.08),
          borderRadius: BorderRadius.circular(10),
          border: Border.all(color: isDark ? Colors.white.withValues(alpha: 0.1) : Colors.grey.withValues(alpha: 0.2)),
        ),
        child: Row(children: [
          Icon(icon, size: 18, color: AppTheme.primaryPurple),
          const SizedBox(width: 10),
          Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(title, style: TextStyle(fontSize: 11, color: isDark ? Colors.white38 : Colors.grey)),
            Text(value, style: TextStyle(fontSize: 14, fontWeight: FontWeight.w500, color: isDark ? Colors.white : const Color(0xFF1E1B4B))),
          ])),
          Icon(Icons.chevron_right, size: 18, color: isDark ? Colors.white24 : Colors.grey[600]),
        ]),
      ),
    );
  }

  Future<void> _deleteEvent(CalendarEvent event) async {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: isDark ? const Color(0xFF1E1B4B) : Colors.white,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
        title: Text('Delete Event?', style: TextStyle(color: isDark ? Colors.white : const Color(0xFF1E1B4B))),
        content: Text('Delete "${event.title}"?', style: TextStyle(color: isDark ? Colors.white70 : Colors.grey[700])),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: Text('Cancel', style: TextStyle(color: isDark ? Colors.white54 : Colors.grey))),
          TextButton(onPressed: () => Navigator.pop(ctx, true), child: const Text('Delete', style: TextStyle(color: Colors.red))),
        ],
      ),
    );
    if (confirmed != true) return;
    try {
      await ref.read(calendarProvider.notifier).deleteEvent(event.id);
      _refreshEvents();
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Event deleted')));
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Error: $e')));
    }
  }

  void _showTimeBlocksSheet() {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (ctx) => DraggableScrollableSheet(
        initialChildSize: 0.6,
        minChildSize: 0.3,
        maxChildSize: 0.9,
        expand: false,
        builder: (ctx, scrollController) => Container(
          decoration: BoxDecoration(
            color: isDark ? const Color(0xFF1E1B4B).withValues(alpha: 0.95) : Colors.white.withValues(alpha: 0.97),
            borderRadius: const BorderRadius.vertical(top: Radius.circular(24)),
          ),
          child: _TimeBlocksSheet(
            scrollController: scrollController,
            calendarNotifier: ref.read(calendarProvider.notifier),
            isDark: isDark,
          ),
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
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final events = calState.eventsForDay(calState.selectedDay);

    return GradientBackground(
      colors: isDark ? AppTheme.gradientCalendar : AppTheme.gradientCalendarLight,
      child: Scaffold(
        backgroundColor: Colors.transparent,
        extendBodyBehindAppBar: true,
        appBar: GlassAppBar(
          title: 'Calendar',
          actions: [
            IconButton(
              icon: Icon(Icons.today, color: isDark ? Colors.white70 : const Color(0xFF1E1B4B)),
              tooltip: 'Today',
              onPressed: _goToToday,
            ),
            IconButton(
              icon: Icon(Icons.auto_fix_high, color: isDark ? Colors.white70 : const Color(0xFF1E1B4B)),
              tooltip: 'Auto-Schedule',
              onPressed: () async {
                try {
                  await ref.read(calendarProvider.notifier).autoSchedule();
                  _refreshEvents();
                  if (mounted) ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Tasks auto-scheduled!')));
                } catch (e) {
                  if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Error: $e')));
                }
              },
            ),
            IconButton(
              icon: Icon(Icons.view_timeline_outlined, color: isDark ? Colors.white70 : const Color(0xFF1E1B4B)),
              tooltip: 'Time Blocks',
              onPressed: _showTimeBlocksSheet,
            ),
          ],
        ),
        body: SafeArea(
          child: Column(
            children: [
              // Glass calendar card
              GlassContainer(
                margin: const EdgeInsets.fromLTRB(12, 8, 12, 0),
                padding: const EdgeInsets.only(bottom: 8),
                opacity: isDark ? 0.12 : 0.25,
                child: TableCalendar<CalendarEvent>(
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
                  onFormatChanged: (format) => setState(() => _calendarFormat = format),
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
                    selectedDecoration: BoxDecoration(
                      gradient: LinearGradient(colors: [AppTheme.primaryPurple, AppTheme.primaryPurple.withValues(alpha: 0.7)]),
                      shape: BoxShape.circle,
                      boxShadow: [BoxShadow(color: AppTheme.primaryPurple.withValues(alpha: 0.4), blurRadius: 8)],
                    ),
                    markerDecoration: BoxDecoration(
                      color: AppTheme.accent,
                      shape: BoxShape.circle,
                      boxShadow: [BoxShadow(color: AppTheme.accent.withValues(alpha: 0.4), blurRadius: 4)],
                    ),
                    markerSize: 6,
                    markersMaxCount: 3,
                    defaultTextStyle: TextStyle(color: isDark ? Colors.white : const Color(0xFF1E1B4B)),
                    weekendTextStyle: TextStyle(color: isDark ? Colors.white60 : Colors.grey[600]!),
                    outsideTextStyle: TextStyle(color: isDark ? Colors.white24 : Colors.grey[600]!),
                    todayTextStyle: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold),
                    selectedTextStyle: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold),
                  ),
                  headerStyle: HeaderStyle(
                    formatButtonVisible: true,
                    titleCentered: true,
                    titleTextStyle: TextStyle(fontSize: 17, fontWeight: FontWeight.w600, color: isDark ? Colors.white : const Color(0xFF1E1B4B)),
                    leftChevronIcon: Icon(Icons.chevron_left, color: isDark ? Colors.white70 : const Color(0xFF1E1B4B)),
                    rightChevronIcon: Icon(Icons.chevron_right, color: isDark ? Colors.white70 : const Color(0xFF1E1B4B)),
                    formatButtonDecoration: BoxDecoration(
                      border: Border.all(color: AppTheme.primaryPurple.withValues(alpha: 0.5)),
                      borderRadius: BorderRadius.circular(8),
                    ),
                    formatButtonTextStyle: TextStyle(color: AppTheme.primaryPurple, fontSize: 12),
                  ),
                  daysOfWeekStyle: DaysOfWeekStyle(
                    weekdayStyle: TextStyle(color: isDark ? Colors.white54 : Colors.grey[600]!, fontSize: 12, fontWeight: FontWeight.w600),
                    weekendStyle: TextStyle(color: isDark ? Colors.white38 : Colors.grey[700]!, fontSize: 12, fontWeight: FontWeight.w600),
                  ),
                ),
              ).animate().fadeIn(duration: 500.ms).slideY(begin: -0.05, end: 0),

              // Events horizontal list
              if (events.isNotEmpty) ...[
                Padding(
                  padding: const EdgeInsets.fromLTRB(20, 14, 20, 6),
                  child: Align(
                    alignment: Alignment.centerLeft,
                    child: Text('Events', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 15, color: isDark ? Colors.white : const Color(0xFF1E1B4B))),
                  ),
                ),
                SizedBox(
                  height: 76,
                  child: ListView.builder(
                    scrollDirection: Axis.horizontal,
                    padding: const EdgeInsets.symmetric(horizontal: 12),
                    itemCount: events.length,
                    itemBuilder: (context, index) {
                      final event = events[index];
                      return AnimatedListItem(
                        index: index,
                        child: GestureDetector(
                          onTap: () => _showEditEventDialog(event),
                          onLongPress: () => _deleteEvent(event),
                          child: GlassContainer(
                            width: 180,
                            margin: const EdgeInsets.symmetric(horizontal: 4, vertical: 4),
                            padding: const EdgeInsets.all(12),
                            opacity: isDark ? 0.15 : 0.3,
                            border: Border(left: BorderSide(color: AppTheme.primaryPurple, width: 3)),
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              mainAxisSize: MainAxisSize.min,
                              children: [
                                Text(event.title, style: TextStyle(fontWeight: FontWeight.w600, fontSize: 13, color: isDark ? Colors.white : const Color(0xFF1E1B4B)), maxLines: 1, overflow: TextOverflow.ellipsis),
                                const SizedBox(height: 6),
                                Row(children: [
                                  Icon(Icons.access_time, size: 12, color: isDark ? Colors.white38 : Colors.grey),
                                  const SizedBox(width: 4),
                                  Text('${_formatTime(event.startTime)} - ${_formatTime(event.endTime)}', style: TextStyle(fontSize: 11, color: isDark ? Colors.white54 : Colors.grey[600])),
                                ]),
                              ],
                            ),
                          ),
                        ),
                      );
                    },
                  ),
                ),
              ],

              // Tasks header
              Padding(
                padding: const EdgeInsets.fromLTRB(20, 14, 20, 6),
                child: Align(
                  alignment: Alignment.centerLeft,
                  child: Text('Tasks for ${_formatDate(calState.selectedDay)}',
                    style: TextStyle(fontWeight: FontWeight.bold, fontSize: 15, color: isDark ? Colors.white : const Color(0xFF1E1B4B)),
                  ),
                ),
              ).animate().fadeIn(duration: 300.ms),

              // Tasks list
              Expanded(
                child: tasksState.isLoading
                    ? const Center(child: LoadingShimmer())
                    : tasksState.tasks.isEmpty
                        ? Center(
                            child: Column(
                              mainAxisAlignment: MainAxisAlignment.center,
                              children: [
                                Icon(Icons.event_available, size: 48, color: isDark ? Colors.white24 : Colors.grey[600]),
                                const SizedBox(height: 8),
                                Text('No tasks for this day', style: TextStyle(color: isDark ? Colors.white54 : Colors.grey[700])),
                              ],
                            ),
                          )
                        : ListView.builder(
                            padding: const EdgeInsets.symmetric(horizontal: 16),
                            itemCount: tasksState.tasks.length,
                            itemBuilder: (context, index) {
                              final task = tasksState.tasks[index];
                              return AnimatedListItem(
                                index: index,
                                child: TaskTile(
                                  task: task,
                                  onComplete: () async {
                                    await ref.read(tasksProvider.notifier).completeTask(task.id);
                                  },
                                ),
                              );
                            },
                          ),
              ),
            ],
          ),
        ),
        floatingActionButton: Container(
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            boxShadow: [BoxShadow(color: AppTheme.primaryPurple.withValues(alpha: 0.4), blurRadius: 16, spreadRadius: 2)],
          ),
          child: FloatingActionButton(
            onPressed: _showCreateEventDialog,
            backgroundColor: AppTheme.primaryPurple,
            foregroundColor: Colors.white,
            child: const Icon(Icons.add),
          ),
        ).animate().fadeIn(duration: 500.ms, delay: 300.ms).scale(begin: const Offset(0.8, 0.8), end: const Offset(1, 1)),
      ),
    );
  }

  String _formatTime(DateTime dt) {
    return '${dt.hour.toString().padLeft(2, '0')}:${dt.minute.toString().padLeft(2, '0')}';
  }

  String _formatDate(DateTime date) {
    final months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    return '${months[date.month - 1]} ${date.day}, ${date.year}';
  }
}

class _TimeBlocksSheet extends StatefulWidget {
  final ScrollController scrollController;
  final CalendarNotifier calendarNotifier;
  final bool isDark;

  const _TimeBlocksSheet({required this.scrollController, required this.calendarNotifier, required this.isDark});

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
    try { _blocks = await widget.calendarNotifier.fetchTimeBlocks(); } catch (_) {}
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
          backgroundColor: widget.isDark ? const Color(0xFF1E1B4B) : Colors.white,
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
          title: Text('Add Time Block', style: TextStyle(color: widget.isDark ? Colors.white : const Color(0xFF1E1B4B))),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              GlassTextField(controller: labelC, label: 'Label'),
              const SizedBox(height: 12),
              _buildTimeTile(ctx, 'Start', start.format(ctx), () async {
                final picked = await showTimePicker(context: ctx, initialTime: start);
                if (picked != null) setDialogState(() => start = picked);
              }),
              _buildTimeTile(ctx, 'End', end.format(ctx), () async {
                final picked = await showTimePicker(context: ctx, initialTime: end);
                if (picked != null) setDialogState(() => end = picked);
              }),
            ],
          ),
          actions: [
            TextButton(onPressed: () => Navigator.pop(ctx), child: Text('Cancel', style: TextStyle(color: widget.isDark ? Colors.white54 : Colors.grey))),
            GlassButton(
              label: 'Add',
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
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildTimeTile(BuildContext ctx, String label, String value, VoidCallback onTap) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        margin: const EdgeInsets.only(bottom: 8),
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
        decoration: BoxDecoration(
          color: widget.isDark ? Colors.white.withValues(alpha: 0.06) : Colors.grey.withValues(alpha: 0.08),
          borderRadius: BorderRadius.circular(10),
        ),
        child: Row(children: [
          Icon(Icons.access_time, size: 18, color: AppTheme.primaryPurple),
          const SizedBox(width: 10),
          Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(label, style: TextStyle(fontSize: 11, color: widget.isDark ? Colors.white38 : Colors.grey)),
            Text(value, style: TextStyle(fontSize: 14, fontWeight: FontWeight.w500, color: widget.isDark ? Colors.white : const Color(0xFF1E1B4B))),
          ]),
          const Spacer(),
          Icon(Icons.chevron_right, size: 18, color: widget.isDark ? Colors.white24 : Colors.grey[600]),
        ]),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        // Handle bar
        Container(
          margin: const EdgeInsets.only(top: 12),
          width: 40,
          height: 4,
          decoration: BoxDecoration(color: widget.isDark ? Colors.white24 : Colors.grey[600], borderRadius: BorderRadius.circular(2)),
        ),
        Padding(
          padding: const EdgeInsets.fromLTRB(20, 16, 12, 8),
          child: Row(
            children: [
              Text('Time Blocks', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: widget.isDark ? Colors.white : const Color(0xFF1E1B4B))),
              const Spacer(),
              IconButton(
                onPressed: _showAddBlockDialog,
                icon: Container(
                  padding: const EdgeInsets.all(6),
                  decoration: BoxDecoration(
                    color: AppTheme.primaryPurple.withValues(alpha: 0.15),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: Icon(Icons.add, color: AppTheme.primaryPurple, size: 20),
                ),
              ),
            ],
          ),
        ),
        Divider(height: 1, color: widget.isDark ? Colors.white12 : Colors.grey.withValues(alpha: 0.15)),
        Expanded(
          child: _isLoading
              ? const Center(child: LoadingShimmer())
              : _blocks.isEmpty
                  ? Center(
                      child: Column(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          Icon(Icons.schedule, size: 48, color: widget.isDark ? Colors.white24 : Colors.grey[600]),
                          const SizedBox(height: 8),
                          Text('No time blocks defined', style: TextStyle(color: widget.isDark ? Colors.white54 : Colors.grey[700])),
                        ],
                      ),
                    )
                  : ListView.builder(
                      controller: widget.scrollController,
                      padding: const EdgeInsets.all(16),
                      itemCount: _blocks.length,
                      itemBuilder: (context, index) {
                        final block = _blocks[index];
                        return AnimatedListItem(
                          index: index,
                          child: GlassContainer(
                            margin: const EdgeInsets.only(bottom: 10),
                            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                            opacity: widget.isDark ? 0.1 : 0.2,
                            child: Row(children: [
                              Container(
                                padding: const EdgeInsets.all(8),
                                decoration: BoxDecoration(
                                  color: AppTheme.primaryPurple.withValues(alpha: 0.12),
                                  borderRadius: BorderRadius.circular(8),
                                ),
                                child: Icon(Icons.access_time, color: AppTheme.primaryPurple, size: 20),
                              ),
                              const SizedBox(width: 12),
                              Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                                Text(block['label'] ?? 'Block', style: TextStyle(fontWeight: FontWeight.w600, color: widget.isDark ? Colors.white : const Color(0xFF1E1B4B))),
                                const SizedBox(height: 2),
                                Text('${block['start_time']} - ${block['end_time']}', style: TextStyle(fontSize: 13, color: widget.isDark ? Colors.white54 : Colors.grey[600])),
                              ])),
                              IconButton(
                                icon: Icon(Icons.delete_outline, color: Colors.red.withValues(alpha: 0.7), size: 20),
                                onPressed: () async {
                                  await widget.calendarNotifier.deleteTimeBlock(block['id'].toString());
                                  _loadBlocks();
                                },
                              ),
                            ]),
                          ),
                        );
                      },
                    ),
        ),
      ],
    );
  }
}
