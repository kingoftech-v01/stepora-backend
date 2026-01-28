import { Router, Request, Response } from 'express';
import { prisma } from '../utils/prisma';
import { redisClient } from '../config/redis';
import { asyncHandler } from '../middleware/errorHandler';

const router = Router();

interface HealthStatus {
  status: 'healthy' | 'degraded' | 'unhealthy';
  timestamp: string;
  uptime: number;
  services: {
    database: {
      status: 'up' | 'down';
      responseTime?: number;
    };
    redis: {
      status: 'up' | 'down';
      responseTime?: number;
    };
    memory: {
      used: number;
      total: number;
      percentage: number;
    };
  };
  version: string;
}

router.get(
  '/health',
  asyncHandler(async (req: Request, res: Response) => {
    const healthCheck: HealthStatus = {
      status: 'healthy',
      timestamp: new Date().toISOString(),
      uptime: process.uptime(),
      services: {
        database: { status: 'down' },
        redis: { status: 'down' },
        memory: {
          used: 0,
          total: 0,
          percentage: 0,
        },
      },
      version: process.env.npm_package_version || '1.0.0',
    };

    // Check database
    try {
      const dbStart = Date.now();
      await prisma.$queryRaw`SELECT 1`;
      const dbTime = Date.now() - dbStart;
      healthCheck.services.database = {
        status: 'up',
        responseTime: dbTime,
      };
    } catch (error) {
      healthCheck.status = 'unhealthy';
      healthCheck.services.database = { status: 'down' };
    }

    // Check Redis
    try {
      const redisStart = Date.now();
      await redisClient.ping();
      const redisTime = Date.now() - redisStart;
      healthCheck.services.redis = {
        status: 'up',
        responseTime: redisTime,
      };
    } catch (error) {
      healthCheck.status = 'degraded';
      healthCheck.services.redis = { status: 'down' };
    }

    // Memory usage
    const memUsage = process.memoryUsage();
    healthCheck.services.memory = {
      used: Math.round(memUsage.heapUsed / 1024 / 1024), // MB
      total: Math.round(memUsage.heapTotal / 1024 / 1024), // MB
      percentage: Math.round((memUsage.heapUsed / memUsage.heapTotal) * 100),
    };

    const statusCode = healthCheck.status === 'healthy' ? 200 : 503;
    res.status(statusCode).json(healthCheck);
  })
);

router.get(
  '/health/live',
  (req: Request, res: Response) => {
    // Liveness probe - just check if server is running
    res.status(200).json({ status: 'alive' });
  }
);

router.get(
  '/health/ready',
  asyncHandler(async (req: Request, res: Response) => {
    // Readiness probe - check if server can handle requests
    try {
      await prisma.$queryRaw`SELECT 1`;
      res.status(200).json({ status: 'ready' });
    } catch (error) {
      res.status(503).json({ status: 'not ready' });
    }
  })
);

router.get(
  '/metrics',
  asyncHandler(async (req: Request, res: Response) => {
    const metrics = {
      timestamp: new Date().toISOString(),
      uptime: process.uptime(),
      memory: {
        rss: Math.round(process.memoryUsage().rss / 1024 / 1024),
        heapTotal: Math.round(process.memoryUsage().heapTotal / 1024 / 1024),
        heapUsed: Math.round(process.memoryUsage().heapUsed / 1024 / 1024),
        external: Math.round(process.memoryUsage().external / 1024 / 1024),
      },
      cpu: process.cpuUsage(),
      environment: process.env.NODE_ENV,
      nodeVersion: process.version,
      platform: process.platform,
      pid: process.pid,
    };

    res.json(metrics);
  })
);

export { router as healthRouter };
