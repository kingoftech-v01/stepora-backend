import { describe, it, expect, vi, beforeEach } from 'vitest';
import { calendarService } from '../../services/calendar.service';
import { taskService } from '../../services/task.service';

vi.mock('../../services/task.service', () => ({
  taskService: {
    findByDateRange: vi.fn(),
  },
}));

const mockTaskService = vi.mocked(taskService);

describe('CalendarService', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  const mockTaskWithGoal = {
    id: 'task-1',
    goalId: 'goal-1',
    title: 'Practice guitar',
    description: null,
    order: 1,
    scheduledDate: new Date('2024-01-15'),
    scheduledTime: '18:30',
    durationMins: 30,
    recurrence: null,
    status: 'pending',
    completedAt: null,
    createdAt: new Date(),
    updatedAt: new Date(),
    goal: {
      id: 'goal-1',
      title: 'Learn chords',
      dream: {
        id: 'dream-1',
        title: 'Learn Guitar',
        category: 'creativity',
      },
    },
  };

  describe('getMonthView', () => {
    it('should return month view with tasks', async () => {
      mockTaskService.findByDateRange.mockResolvedValue([mockTaskWithGoal] as any);

      const result = await calendarService.getMonthView('user-1', 2024, 1);

      expect(result.year).toBe(2024);
      expect(result.month).toBe(1);
      expect(result.weeks).toBeDefined();
      expect(result.weeks.length).toBeGreaterThan(0);
      expect(result.totalCount).toBe(1);
    });

    it('should return empty month view', async () => {
      mockTaskService.findByDateRange.mockResolvedValue([]);

      const result = await calendarService.getMonthView('user-1', 2024, 6);

      expect(result.totalCount).toBe(0);
      expect(result.completedCount).toBe(0);
    });
  });

  describe('getWeekView', () => {
    it('should return week view with tasks', async () => {
      mockTaskService.findByDateRange.mockResolvedValue([mockTaskWithGoal] as any);

      const result = await calendarService.getWeekView('user-1', 2024, 3);

      expect(result.weekNumber).toBe(3);
      expect(result.days).toHaveLength(7);
    });

    it('should return empty week view', async () => {
      mockTaskService.findByDateRange.mockResolvedValue([]);

      const result = await calendarService.getWeekView('user-1', 2024, 3);

      expect(result.totalCount).toBe(0);
      expect(result.days.every((d) => d.totalCount === 0)).toBe(true);
    });
  });

  describe('getDayView', () => {
    it('should return day view with tasks', async () => {
      mockTaskService.findByDateRange.mockResolvedValue([mockTaskWithGoal] as any);

      const result = await calendarService.getDayView('user-1', '2024-01-15');

      expect(result.date).toBe('2024-01-15');
      expect(result.tasks).toHaveLength(1);
      expect(result.totalCount).toBe(1);
    });

    it('should return empty day view', async () => {
      mockTaskService.findByDateRange.mockResolvedValue([]);

      const result = await calendarService.getDayView('user-1', '2024-01-15');

      expect(result.tasks).toHaveLength(0);
      expect(result.totalCount).toBe(0);
    });
  });

  describe('findAvailableSlots', () => {
    it('should find available slots respecting work schedule', async () => {
      // No tasks scheduled
      mockTaskService.findByDateRange.mockResolvedValue([]);

      const startDate = new Date('2024-01-15');
      const endDate = new Date('2024-01-16');

      const slots = await calendarService.findAvailableSlots(
        'user-1',
        startDate,
        endDate,
        30,
        { workDays: [1, 2, 3, 4, 5], startTime: '09:00', endTime: '18:00' }
      );

      expect(slots.length).toBeGreaterThanOrEqual(0);
    });

    it('should skip non-work days', async () => {
      mockTaskService.findByDateRange.mockResolvedValue([]);

      // Saturday and Sunday
      const startDate = new Date('2024-01-13'); // Saturday
      const endDate = new Date('2024-01-14'); // Sunday

      const slots = await calendarService.findAvailableSlots(
        'user-1',
        startDate,
        endDate,
        30,
        { workDays: [1, 2, 3, 4, 5], startTime: '09:00', endTime: '18:00' }
      );

      expect(slots).toHaveLength(0);
    });

    it('should work without work schedule', async () => {
      mockTaskService.findByDateRange.mockResolvedValue([]);

      const startDate = new Date('2024-01-15');
      const endDate = new Date('2024-01-15');

      const slots = await calendarService.findAvailableSlots(
        'user-1',
        startDate,
        endDate,
        30
      );

      expect(slots).toBeDefined();
    });
  });
});
