import rateLimit from 'express-rate-limit';
import RedisStore from 'rate-limit-redis';
import { redis } from '../config/redis';
import { Request } from 'express';
import { AuthRequest } from './auth';

// Global rate limiter (100 requests per 15 minutes)
export const globalLimiter = rateLimit({
  windowMs: 15 * 60 * 1000, // 15 minutes
  max: 100,
  standardHeaders: true,
  legacyHeaders: false,
  store: new RedisStore({
    // @ts-expect-error - RedisStore types mismatch
    sendCommand: (...args: string[]) => redis.call(...args),
  }),
  message: 'Too many requests, please try again later',
});

// Auth endpoints rate limiter (5 attempts per hour)
export const authLimiter = rateLimit({
  windowMs: 60 * 60 * 1000, // 1 hour
  max: 5,
  skipSuccessfulRequests: true,
  standardHeaders: true,
  legacyHeaders: false,
  store: new RedisStore({
    // @ts-expect-error - RedisStore types mismatch
    sendCommand: (...args: string[]) => redis.call(...args),
    prefix: 'rl:auth:',
  }),
  message: 'Too many authentication attempts, please try again later',
});

// AI chat rate limiter (tier-based)
export const aiChatLimiter = rateLimit({
  windowMs: 60 * 60 * 1000, // 1 hour
  max: async (req: Request) => {
    const authReq = req as AuthRequest;
    const subscription = authReq.user?.subscription || 'free';

    const limits: Record<string, number> = {
      free: 10,
      premium: 100,
      pro: 1000,
    };

    return limits[subscription] || 10;
  },
  standardHeaders: true,
  legacyHeaders: false,
  store: new RedisStore({
    // @ts-expect-error - RedisStore types mismatch
    sendCommand: (...args: string[]) => redis.call(...args),
    prefix: 'rl:ai:',
  }),
  keyGenerator: (req: Request) => {
    const authReq = req as AuthRequest;
    return authReq.user?.id || req.ip;
  },
  message: 'AI chat limit reached. Please upgrade your subscription for more messages.',
});

// Plan generation rate limiter (5 per hour for free, 20 for premium)
export const planGenerationLimiter = rateLimit({
  windowMs: 60 * 60 * 1000, // 1 hour
  max: async (req: Request) => {
    const authReq = req as AuthRequest;
    const subscription = authReq.user?.subscription || 'free';

    return subscription === 'free' ? 5 : 20;
  },
  standardHeaders: true,
  legacyHeaders: false,
  store: new RedisStore({
    // @ts-expect-error - RedisStore types mismatch
    sendCommand: (...args: string[]) => redis.call(...args),
    prefix: 'rl:plan:',
  }),
  keyGenerator: (req: Request) => {
    const authReq = req as AuthRequest;
    return authReq.user?.id || req.ip;
  },
  message: 'Plan generation limit reached. Please try again later or upgrade your subscription.',
});
