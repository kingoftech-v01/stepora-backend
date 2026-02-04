import { Router, Response, NextFunction } from 'express';
import { dreamService } from '../services/dream.service';
import { userService } from '../services/user.service';
import { createDreamSchema, updateDreamSchema } from '../validators';
import { AuthenticatedRequest } from '../middleware/auth';
import { AppError } from '../middleware/errorHandler';

export const dreamsRouter = Router();

// GET /api/dreams - Get all dreams for current user
dreamsRouter.get(
  '/',
  async (req: AuthenticatedRequest, res: Response, next: NextFunction) => {
    try {
      const { status, category, limit, offset } = req.query;

      const result = await dreamService.findAllByUser(req.userId!, {
        status: status as string,
        category: category as string,
        limit: limit ? parseInt(limit as string, 10) : undefined,
        offset: offset ? parseInt(offset as string, 10) : undefined,
      });

      res.json({
        success: true,
        data: {
          dreams: result.dreams,
          total: result.total,
        },
      });
    } catch (error) {
      next(error);
    }
  }
);

// GET /api/dreams/:id - Get a specific dream
dreamsRouter.get(
  '/:id',
  async (req: AuthenticatedRequest, res: Response, next: NextFunction) => {
    try {
      const dream = await dreamService.findById(req.params.id, req.userId!);

      if (!dream) {
        throw new AppError('Dream not found', 404);
      }

      const progress = await dreamService.getProgress(dream.id, req.userId!);

      res.json({
        success: true,
        data: {
          dream,
          progress,
        },
      });
    } catch (error) {
      next(error);
    }
  }
);

// POST /api/dreams - Create a new dream
dreamsRouter.post(
  '/',
  async (req: AuthenticatedRequest, res: Response, next: NextFunction) => {
    try {
      const data = createDreamSchema.parse(req.body);

      const dream = await dreamService.create(req.userId!, {
        title: data.title,
        description: data.description,
        category: data.category,
        targetDate: data.targetDate ? new Date(data.targetDate) : undefined,
        priority: data.priority,
      });

      res.status(201).json({
        success: true,
        data: { dream },
      });
    } catch (error) {
      next(error);
    }
  }
);

// PATCH /api/dreams/:id - Update a dream
dreamsRouter.patch(
  '/:id',
  async (req: AuthenticatedRequest, res: Response, next: NextFunction) => {
    try {
      const data = updateDreamSchema.parse(req.body);

      const dream = await dreamService.update(req.params.id, req.userId!, {
        title: data.title,
        description: data.description,
        category: data.category,
        targetDate: data.targetDate ? new Date(data.targetDate) : undefined,
        priority: data.priority,
        status: data.status,
      });

      res.json({
        success: true,
        data: { dream },
      });
    } catch (error) {
      next(error);
    }
  }
);

// DELETE /api/dreams/:id - Delete a dream
dreamsRouter.delete(
  '/:id',
  async (req: AuthenticatedRequest, res: Response, next: NextFunction) => {
    try {
      await dreamService.delete(req.params.id, req.userId!);

      res.json({
        success: true,
        message: 'Dream deleted successfully',
      });
    } catch (error) {
      next(error);
    }
  }
);

// POST /api/dreams/:id/generate-plan - Generate AI plan for a dream
dreamsRouter.post(
  '/:id/generate-plan',
  async (req: AuthenticatedRequest, res: Response, next: NextFunction) => {
    try {
      const user = await userService.findById(req.userId!);

      if (!user) {
        throw new AppError('User not found', 404);
      }

      const workSchedule = user.workSchedule as {
        workDays: number[];
        startTime: string;
        endTime: string;
      } | null;

      const dream = await dreamService.generatePlan(
        req.params.id,
        req.userId!,
        {
          userName: user.displayName || 'Utilisateur',
          timezone: user.timezone,
          workSchedule: workSchedule || undefined,
          availableHoursPerWeek: req.body.availableHoursPerWeek,
        }
      );

      const progress = await dreamService.getProgress(dream.id, req.userId!);

      res.json({
        success: true,
        data: {
          dream,
          progress,
        },
      });
    } catch (error) {
      next(error);
    }
  }
);

// GET /api/dreams/:id/progress - Get dream progress
dreamsRouter.get(
  '/:id/progress',
  async (req: AuthenticatedRequest, res: Response, next: NextFunction) => {
    try {
      const progress = await dreamService.getProgress(req.params.id, req.userId!);

      res.json({
        success: true,
        data: progress,
      });
    } catch (error) {
      next(error);
    }
  }
);
