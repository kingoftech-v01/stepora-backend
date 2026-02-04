import { Router, Response, NextFunction } from 'express';
import { goalService } from '../services/goal.service';
import { createGoalSchema, updateGoalSchema } from '../validators';
import { AuthenticatedRequest } from '../middleware/auth';
import { AppError } from '../middleware/errorHandler';

export const goalsRouter = Router();

// GET /api/goals - Get goals by dream
goalsRouter.get(
  '/',
  async (req: AuthenticatedRequest, res: Response, next: NextFunction) => {
    try {
      const { dreamId } = req.query;

      if (!dreamId) {
        throw new AppError('dreamId query parameter is required', 400);
      }

      const goals = await goalService.findByDream(dreamId as string, req.userId!);

      res.json({
        success: true,
        data: { goals },
      });
    } catch (error) {
      next(error);
    }
  }
);

// GET /api/goals/:id - Get a specific goal
goalsRouter.get(
  '/:id',
  async (req: AuthenticatedRequest, res: Response, next: NextFunction) => {
    try {
      const goal = await goalService.findById(req.params.id, req.userId!);

      if (!goal) {
        throw new AppError('Goal not found', 404);
      }

      const progress = await goalService.getProgress(goal.id, req.userId!);

      res.json({
        success: true,
        data: {
          goal,
          progress,
        },
      });
    } catch (error) {
      next(error);
    }
  }
);

// POST /api/goals - Create a new goal
goalsRouter.post(
  '/',
  async (req: AuthenticatedRequest, res: Response, next: NextFunction) => {
    try {
      const data = createGoalSchema.parse(req.body);

      const goal = await goalService.create(data.dreamId, req.userId!, {
        title: data.title,
        description: data.description,
        estimatedMinutes: data.estimatedMinutes,
        scheduledStart: data.scheduledStart ? new Date(data.scheduledStart) : undefined,
        scheduledEnd: data.scheduledEnd ? new Date(data.scheduledEnd) : undefined,
        reminderEnabled: data.reminderEnabled,
        reminderTime: data.reminderTime ? new Date(data.reminderTime) : undefined,
      });

      res.status(201).json({
        success: true,
        data: { goal },
      });
    } catch (error) {
      next(error);
    }
  }
);

// PATCH /api/goals/:id - Update a goal
goalsRouter.patch(
  '/:id',
  async (req: AuthenticatedRequest, res: Response, next: NextFunction) => {
    try {
      const data = updateGoalSchema.parse(req.body);

      const goal = await goalService.update(req.params.id, req.userId!, {
        title: data.title,
        description: data.description,
        estimatedMinutes: data.estimatedMinutes,
        scheduledStart: data.scheduledStart ? new Date(data.scheduledStart) : undefined,
        scheduledEnd: data.scheduledEnd ? new Date(data.scheduledEnd) : undefined,
        status: data.status,
        reminderEnabled: data.reminderEnabled,
        reminderTime: data.reminderTime ? new Date(data.reminderTime) : undefined,
      });

      res.json({
        success: true,
        data: { goal },
      });
    } catch (error) {
      next(error);
    }
  }
);

// DELETE /api/goals/:id - Delete a goal
goalsRouter.delete(
  '/:id',
  async (req: AuthenticatedRequest, res: Response, next: NextFunction) => {
    try {
      await goalService.delete(req.params.id, req.userId!);

      res.json({
        success: true,
        message: 'Goal deleted successfully',
      });
    } catch (error) {
      next(error);
    }
  }
);

// POST /api/goals/reorder - Reorder goals within a dream
goalsRouter.post(
  '/reorder',
  async (req: AuthenticatedRequest, res: Response, next: NextFunction) => {
    try {
      const { dreamId, goalIds } = req.body;

      if (!dreamId || !goalIds || !Array.isArray(goalIds)) {
        throw new AppError('dreamId and goalIds array are required', 400);
      }

      await goalService.reorder(dreamId, req.userId!, goalIds);

      res.json({
        success: true,
        message: 'Goals reordered successfully',
      });
    } catch (error) {
      next(error);
    }
  }
);

// GET /api/goals/:id/progress - Get goal progress
goalsRouter.get(
  '/:id/progress',
  async (req: AuthenticatedRequest, res: Response, next: NextFunction) => {
    try {
      const progress = await goalService.getProgress(req.params.id, req.userId!);

      res.json({
        success: true,
        data: progress,
      });
    } catch (error) {
      next(error);
    }
  }
);
