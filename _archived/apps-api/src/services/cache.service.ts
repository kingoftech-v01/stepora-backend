import { redisClient } from '../config/redis';
import { logger } from '../config/logger';

interface CacheOptions {
  ttl?: number; // Time to live in seconds
  prefix?: string;
}

class CacheService {
  private readonly DEFAULT_TTL = 300; // 5 minutes

  /**
   * Get value from cache
   */
  async get<T>(key: string): Promise<T | null> {
    try {
      const cached = await redisClient.get(key);
      if (!cached) return null;

      return JSON.parse(cached) as T;
    } catch (error) {
      logger.error('Cache get error:', { error, key });
      return null;
    }
  }

  /**
   * Set value in cache
   */
  async set(key: string, value: any, options?: CacheOptions): Promise<void> {
    try {
      const ttl = options?.ttl || this.DEFAULT_TTL;
      const fullKey = options?.prefix ? `${options.prefix}:${key}` : key;

      await redisClient.setEx(fullKey, ttl, JSON.stringify(value));
    } catch (error) {
      logger.error('Cache set error:', { error, key });
    }
  }

  /**
   * Delete value from cache
   */
  async del(key: string | string[]): Promise<void> {
    try {
      if (Array.isArray(key)) {
        await redisClient.del(key);
      } else {
        await redisClient.del(key);
      }
    } catch (error) {
      logger.error('Cache delete error:', { error, key });
    }
  }

  /**
   * Delete keys matching pattern
   */
  async delPattern(pattern: string): Promise<void> {
    try {
      const keys = await redisClient.keys(pattern);
      if (keys.length > 0) {
        await redisClient.del(keys);
      }
    } catch (error) {
      logger.error('Cache delete pattern error:', { error, pattern });
    }
  }

  /**
   * Check if key exists
   */
  async exists(key: string): Promise<boolean> {
    try {
      const result = await redisClient.exists(key);
      return result === 1;
    } catch (error) {
      logger.error('Cache exists error:', { error, key });
      return false;
    }
  }

  /**
   * Get or set value with a factory function
   */
  async getOrSet<T>(
    key: string,
    factory: () => Promise<T>,
    options?: CacheOptions
  ): Promise<T> {
    // Try to get from cache
    const cached = await this.get<T>(key);
    if (cached !== null) {
      return cached;
    }

    // Generate value
    const value = await factory();

    // Cache it
    await this.set(key, value, options);

    return value;
  }

  /**
   * Increment a counter
   */
  async increment(key: string, amount: number = 1): Promise<number> {
    try {
      return await redisClient.incrBy(key, amount);
    } catch (error) {
      logger.error('Cache increment error:', { error, key });
      return 0;
    }
  }

  /**
   * Set expiration on existing key
   */
  async expire(key: string, seconds: number): Promise<void> {
    try {
      await redisClient.expire(key, seconds);
    } catch (error) {
      logger.error('Cache expire error:', { error, key });
    }
  }

  /**
   * Cache keys generator functions
   */
  keys = {
    userProfile: (userId: string) => `profile:${userId}`,
    userStats: (userId: string) => `stats:${userId}`,
    dreamsList: (userId: string) => `dreams:${userId}`,
    calendarView: (userId: string, date: string) => `calendar:${userId}:${date}`,
    leaderboard: (type: string, filter?: string) => `leaderboard:${type}:${filter || 'all'}`,
    aiResponse: (hash: string) => `ai:response:${hash}`,
    userPreferences: (userId: string) => `prefs:${userId}`,
  };

  /**
   * TTL constants (in seconds)
   */
  ttl = {
    MINUTE: 60,
    FIVE_MINUTES: 300,
    TEN_MINUTES: 600,
    THIRTY_MINUTES: 1800,
    HOUR: 3600,
    SIX_HOURS: 21600,
    DAY: 86400,
    WEEK: 604800,
  };
}

export const cacheService = new CacheService();
