import { prisma } from '../config/database';
import { taskService, TaskWithGoalAndDream } from './task.service';

export interface CalendarDay {
  date: string; // YYYY-MM-DD
  tasks: TaskWithGoalAndDream[];
  completedCount: number;
  totalCount: number;
}

export interface CalendarWeek {
  weekNumber: number;
  startDate: string;
  endDate: string;
  days: CalendarDay[];
  completedCount: number;
  totalCount: number;
}

export interface CalendarMonth {
  year: number;
  month: number;
  weeks: CalendarWeek[];
  completedCount: number;
  totalCount: number;
}

export interface WorkSchedule {
  workDays: number[];
  startTime: string;
  endTime: string;
}

export interface AvailableSlot {
  date: string;
  startTime: string;
  endTime: string;
  durationMins: number;
}

export class CalendarService {
  async getMonthView(
    userId: string,
    year: number,
    month: number
  ): Promise<CalendarMonth> {
    const startDate = new Date(year, month - 1, 1);
    const endDate = new Date(year, month, 0);

    const tasks = await taskService.findByDateRange(userId, startDate, endDate);

    const tasksByDate = tasks.reduce((acc, task) => {
      if (task.scheduledDate) {
        const dateKey = task.scheduledDate.toISOString().split('T')[0];
        if (!acc[dateKey]) acc[dateKey] = [];
        acc[dateKey].push(task);
      }
      return acc;
    }, {} as Record<string, TaskWithGoalAndDream[]>);

    const weeks: CalendarWeek[] = [];
    let currentDate = new Date(startDate);

    // Adjust to start of week (Monday)
    const dayOfWeek = currentDate.getDay();
    const diff = dayOfWeek === 0 ? -6 : 1 - dayOfWeek;
    currentDate.setDate(currentDate.getDate() + diff);

    while (currentDate <= endDate || currentDate.getDay() !== 1) {
      const weekDays: CalendarDay[] = [];
      const weekStart = new Date(currentDate);

      for (let i = 0; i < 7; i++) {
        const dateKey = currentDate.toISOString().split('T')[0];
        const dayTasks = tasksByDate[dateKey] || [];

        weekDays.push({
          date: dateKey,
          tasks: dayTasks,
          completedCount: dayTasks.filter((t) => t.status === 'completed').length,
          totalCount: dayTasks.length,
        });

        currentDate.setDate(currentDate.getDate() + 1);
      }

      const weekEnd = new Date(currentDate);
      weekEnd.setDate(weekEnd.getDate() - 1);

      weeks.push({
        weekNumber: this.getWeekNumber(weekStart),
        startDate: weekStart.toISOString().split('T')[0],
        endDate: weekEnd.toISOString().split('T')[0],
        days: weekDays,
        completedCount: weekDays.reduce((sum, d) => sum + d.completedCount, 0),
        totalCount: weekDays.reduce((sum, d) => sum + d.totalCount, 0),
      });

      if (currentDate.getMonth() !== month - 1 && currentDate.getDay() === 1) {
        break;
      }
    }

    return {
      year,
      month,
      weeks,
      completedCount: weeks.reduce((sum, w) => sum + w.completedCount, 0),
      totalCount: weeks.reduce((sum, w) => sum + w.totalCount, 0),
    };
  }

  async getWeekView(
    userId: string,
    year: number,
    weekNumber: number
  ): Promise<CalendarWeek> {
    const startDate = this.getDateOfWeek(year, weekNumber);
    const endDate = new Date(startDate);
    endDate.setDate(endDate.getDate() + 6);

    const tasks = await taskService.findByDateRange(userId, startDate, endDate);

    const tasksByDate = tasks.reduce((acc, task) => {
      if (task.scheduledDate) {
        const dateKey = task.scheduledDate.toISOString().split('T')[0];
        if (!acc[dateKey]) acc[dateKey] = [];
        acc[dateKey].push(task);
      }
      return acc;
    }, {} as Record<string, TaskWithGoalAndDream[]>);

    const days: CalendarDay[] = [];
    const currentDate = new Date(startDate);

    for (let i = 0; i < 7; i++) {
      const dateKey = currentDate.toISOString().split('T')[0];
      const dayTasks = tasksByDate[dateKey] || [];

      days.push({
        date: dateKey,
        tasks: dayTasks,
        completedCount: dayTasks.filter((t) => t.status === 'completed').length,
        totalCount: dayTasks.length,
      });

      currentDate.setDate(currentDate.getDate() + 1);
    }

    return {
      weekNumber,
      startDate: startDate.toISOString().split('T')[0],
      endDate: endDate.toISOString().split('T')[0],
      days,
      completedCount: days.reduce((sum, d) => sum + d.completedCount, 0),
      totalCount: days.reduce((sum, d) => sum + d.totalCount, 0),
    };
  }

  async getDayView(userId: string, date: string): Promise<CalendarDay> {
    const targetDate = new Date(date);
    const nextDate = new Date(targetDate);
    nextDate.setDate(nextDate.getDate() + 1);

    const tasks = await taskService.findByDateRange(userId, targetDate, nextDate);

    return {
      date,
      tasks,
      completedCount: tasks.filter((t) => t.status === 'completed').length,
      totalCount: tasks.length,
    };
  }

  async findAvailableSlots(
    userId: string,
    startDate: Date,
    endDate: Date,
    durationMins: number,
    workSchedule?: WorkSchedule
  ): Promise<AvailableSlot[]> {
    const tasks = await taskService.findByDateRange(userId, startDate, endDate);

    const slots: AvailableSlot[] = [];
    const currentDate = new Date(startDate);

    while (currentDate <= endDate) {
      const dayOfWeek = currentDate.getDay();
      const dateKey = currentDate.toISOString().split('T')[0];

      // Check if it's a work day
      if (workSchedule && !workSchedule.workDays.includes(dayOfWeek)) {
        currentDate.setDate(currentDate.getDate() + 1);
        continue;
      }

      // Get tasks for this day
      const dayTasks = tasks
        .filter(
          (t) =>
            t.scheduledDate &&
            t.scheduledDate.toISOString().split('T')[0] === dateKey &&
            t.scheduledTime
        )
        .sort((a, b) => (a.scheduledTime! < b.scheduledTime! ? -1 : 1));

      // Define available time range
      const dayStart = workSchedule?.endTime || '18:00'; // After work
      const dayEnd = '22:00'; // Evening limit

      // Find gaps between tasks
      let currentTime = dayStart;

      for (const task of dayTasks) {
        if (task.scheduledTime && task.scheduledTime > currentTime) {
          const gapMins = this.getTimeDiffMins(currentTime, task.scheduledTime);
          if (gapMins >= durationMins) {
            slots.push({
              date: dateKey,
              startTime: currentTime,
              endTime: task.scheduledTime,
              durationMins: gapMins,
            });
          }
        }

        if (task.scheduledTime && task.durationMins) {
          currentTime = this.addMinutesToTime(task.scheduledTime, task.durationMins);
        }
      }

      // Add remaining time
      if (currentTime < dayEnd) {
        const gapMins = this.getTimeDiffMins(currentTime, dayEnd);
        if (gapMins >= durationMins) {
          slots.push({
            date: dateKey,
            startTime: currentTime,
            endTime: dayEnd,
            durationMins: gapMins,
          });
        }
      }

      currentDate.setDate(currentDate.getDate() + 1);
    }

    return slots;
  }

  private getWeekNumber(date: Date): number {
    const d = new Date(Date.UTC(date.getFullYear(), date.getMonth(), date.getDate()));
    const dayNum = d.getUTCDay() || 7;
    d.setUTCDate(d.getUTCDate() + 4 - dayNum);
    const yearStart = new Date(Date.UTC(d.getUTCFullYear(), 0, 1));
    return Math.ceil(((d.getTime() - yearStart.getTime()) / 86400000 + 1) / 7);
  }

  private getDateOfWeek(year: number, week: number): Date {
    const jan1 = new Date(year, 0, 1);
    const days = (week - 1) * 7;
    const dayOfWeek = jan1.getDay();
    const diff = dayOfWeek <= 4 ? dayOfWeek - 1 : dayOfWeek - 8;
    jan1.setDate(jan1.getDate() - diff + days);
    return jan1;
  }

  private getTimeDiffMins(start: string, end: string): number {
    const [startH, startM] = start.split(':').map(Number);
    const [endH, endM] = end.split(':').map(Number);
    return (endH * 60 + endM) - (startH * 60 + startM);
  }

  private addMinutesToTime(time: string, mins: number): string {
    const [h, m] = time.split(':').map(Number);
    const totalMins = h * 60 + m + mins;
    const newH = Math.floor(totalMins / 60);
    const newM = totalMins % 60;
    return `${newH.toString().padStart(2, '0')}:${newM.toString().padStart(2, '0')}`;
  }
}

export const calendarService = new CalendarService();
