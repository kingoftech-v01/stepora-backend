import { Router, Response, NextFunction } from 'express';
import { calendarService } from '../services/calendar.service';
import { userService } from '../services/user.service';
import { AuthenticatedRequest } from '../middleware/auth';
import { AppError } from '../middleware/errorHandler';

export const calendarRouter = Router();

// GET /api/calendar/month - Get month view
calendarRouter.get(
  '/month',
  async (req: AuthenticatedRequest, res: Response, next: NextFunction) => {
    try {
      const { year, month } = req.query;

      const now = new Date();
      const y = year ? parseInt(year as string, 10) : now.getFullYear();
      const m = month ? parseInt(month as string, 10) : now.getMonth() + 1;

      if (m < 1 || m > 12) {
        throw new AppError('Month must be between 1 and 12', 400);
      }

      const monthView = await calendarService.getMonthView(req.userId!, y, m);

      res.json({
        success: true,
        data: monthView,
      });
    } catch (error) {
      next(error);
    }
  }
);

// GET /api/calendar/week - Get week view
calendarRouter.get(
  '/week',
  async (req: AuthenticatedRequest, res: Response, next: NextFunction) => {
    try {
      const { year, week } = req.query;

      if (!year || !week) {
        throw new AppError('year and week query parameters are required', 400);
      }

      const y = parseInt(year as string, 10);
      const w = parseInt(week as string, 10);

      if (w < 1 || w > 53) {
        throw new AppError('Week must be between 1 and 53', 400);
      }

      const weekView = await calendarService.getWeekView(req.userId!, y, w);

      res.json({
        success: true,
        data: weekView,
      });
    } catch (error) {
      next(error);
    }
  }
);

// GET /api/calendar/day - Get day view
calendarRouter.get(
  '/day',
  async (req: AuthenticatedRequest, res: Response, next: NextFunction) => {
    try {
      const { date } = req.query;

      const targetDate = date
        ? (date as string)
        : new Date().toISOString().split('T')[0];

      const dayView = await calendarService.getDayView(req.userId!, targetDate);

      res.json({
        success: true,
        data: dayView,
      });
    } catch (error) {
      next(error);
    }
  }
);

// GET /api/calendar/available-slots - Find available time slots
calendarRouter.get(
  '/available-slots',
  async (req: AuthenticatedRequest, res: Response, next: NextFunction) => {
    try {
      const { startDate, endDate, durationMins } = req.query;

      if (!startDate || !endDate || !durationMins) {
        throw new AppError(
          'startDate, endDate, and durationMins query parameters are required',
          400
        );
      }

      const user = await userService.findById(req.userId!);

      if (!user) {
        throw new AppError('User not found', 404);
      }

      const workSchedule = user.workSchedule as {
        workDays: number[];
        startTime: string;
        endTime: string;
      } | null;

      const slots = await calendarService.findAvailableSlots(
        req.userId!,
        new Date(startDate as string),
        new Date(endDate as string),
        parseInt(durationMins as string, 10),
        workSchedule || undefined
      );

      res.json({
        success: true,
        data: { slots },
      });
    } catch (error) {
      next(error);
    }
  }
);
