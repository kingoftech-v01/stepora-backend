import { Router, Response, NextFunction } from 'express';
import { taskService } from '../services/task.service';
import { createTaskSchema, updateTaskSchema } from '../validators';
import { AuthenticatedRequest } from '../middleware/auth';
import { AppError } from '../middleware/errorHandler';

export const tasksRouter = Router();

// GET /api/tasks - Get tasks (by goal, by date range, or today)
tasksRouter.get(
  '/',
  async (req: AuthenticatedRequest, res: Response, next: NextFunction) => {
    try {
      const { goalId, startDate, endDate, today, upcoming, overdue, limit } = req.query;

      if (today === 'true') {
        const tasks = await taskService.getTodayTasks(req.userId!);
        return res.json({
          success: true,
          data: { tasks },
        });
      }

      if (overdue === 'true') {
        const tasks = await taskService.getOverdueTasks(req.userId!);
        return res.json({
          success: true,
          data: { tasks },
        });
      }

      if (upcoming === 'true') {
        const tasks = await taskService.findUpcoming(
          req.userId!,
          limit ? parseInt(limit as string, 10) : 10
        );
        return res.json({
          success: true,
          data: { tasks },
        });
      }

      if (goalId) {
        const tasks = await taskService.findByGoal(goalId as string, req.userId!);
        return res.json({
          success: true,
          data: { tasks },
        });
      }

      if (startDate && endDate) {
        const tasks = await taskService.findByDateRange(
          req.userId!,
          new Date(startDate as string),
          new Date(endDate as string)
        );
        return res.json({
          success: true,
          data: { tasks },
        });
      }

      // Default: return upcoming tasks
      const tasks = await taskService.findUpcoming(req.userId!, 20);
      res.json({
        success: true,
        data: { tasks },
      });
    } catch (error) {
      next(error);
    }
  }
);

// GET /api/tasks/:id - Get a specific task
tasksRouter.get(
  '/:id',
  async (req: AuthenticatedRequest, res: Response, next: NextFunction) => {
    try {
      const task = await taskService.findById(req.params.id, req.userId!);

      if (!task) {
        throw new AppError('Task not found', 404);
      }

      res.json({
        success: true,
        data: { task },
      });
    } catch (error) {
      next(error);
    }
  }
);

// POST /api/tasks - Create a new task
tasksRouter.post(
  '/',
  async (req: AuthenticatedRequest, res: Response, next: NextFunction) => {
    try {
      const data = createTaskSchema.parse(req.body);

      const task = await taskService.create(data.goalId, req.userId!, {
        title: data.title,
        description: data.description,
        scheduledDate: data.scheduledDate ? new Date(data.scheduledDate) : undefined,
        scheduledTime: data.scheduledTime,
        durationMins: data.durationMins,
        recurrence: data.recurrence,
      });

      res.status(201).json({
        success: true,
        data: { task },
      });
    } catch (error) {
      next(error);
    }
  }
);

// PATCH /api/tasks/:id - Update a task
tasksRouter.patch(
  '/:id',
  async (req: AuthenticatedRequest, res: Response, next: NextFunction) => {
    try {
      const data = updateTaskSchema.parse(req.body);

      const task = await taskService.update(req.params.id, req.userId!, {
        title: data.title,
        description: data.description,
        scheduledDate: data.scheduledDate ? new Date(data.scheduledDate) : undefined,
        scheduledTime: data.scheduledTime,
        durationMins: data.durationMins,
        status: data.status,
        recurrence: data.recurrence,
      });

      res.json({
        success: true,
        data: { task },
      });
    } catch (error) {
      next(error);
    }
  }
);

// POST /api/tasks/:id/complete - Complete a task
tasksRouter.post(
  '/:id/complete',
  async (req: AuthenticatedRequest, res: Response, next: NextFunction) => {
    try {
      const task = await taskService.complete(req.params.id, req.userId!);

      res.json({
        success: true,
        data: { task },
      });
    } catch (error) {
      next(error);
    }
  }
);

// POST /api/tasks/:id/skip - Skip a task
tasksRouter.post(
  '/:id/skip',
  async (req: AuthenticatedRequest, res: Response, next: NextFunction) => {
    try {
      const task = await taskService.skip(req.params.id, req.userId!);

      res.json({
        success: true,
        data: { task },
      });
    } catch (error) {
      next(error);
    }
  }
);

// DELETE /api/tasks/:id - Delete a task
tasksRouter.delete(
  '/:id',
  async (req: AuthenticatedRequest, res: Response, next: NextFunction) => {
    try {
      await taskService.delete(req.params.id, req.userId!);

      res.json({
        success: true,
        message: 'Task deleted successfully',
      });
    } catch (error) {
      next(error);
    }
  }
);

// POST /api/tasks/reorder - Reorder tasks within a goal
tasksRouter.post(
  '/reorder',
  async (req: AuthenticatedRequest, res: Response, next: NextFunction) => {
    try {
      const { goalId, taskIds } = req.body;

      if (!goalId || !taskIds || !Array.isArray(taskIds)) {
        throw new AppError('goalId and taskIds array are required', 400);
      }

      await taskService.reorder(goalId, req.userId!, taskIds);

      res.json({
        success: true,
        message: 'Tasks reordered successfully',
      });
    } catch (error) {
      next(error);
    }
  }
);
