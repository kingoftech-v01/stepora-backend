import { rescueModeService } from '../services/rescueMode.service';
import { logger } from '../config/logger';

export function initializeRescueModeWorker() {
  // Run rescue mode check daily at 10 AM
  const runRescueCheck = async () => {
    try {
      logger.info('Running rescue mode check...');
      await rescueModeService.checkUsersForRescue();
    } catch (error) {
      logger.error('Rescue mode check failed:', { error });
    }
  };

  // Calculate time until next 10 AM
  const scheduleNextRun = () => {
    const now = new Date();
    const next10AM = new Date();
    next10AM.setHours(10, 0, 0, 0);

    if (now.getHours() >= 10) {
      next10AM.setDate(next10AM.getDate() + 1);
    }

    const timeUntilNext = next10AM.getTime() - now.getTime();

    setTimeout(() => {
      runRescueCheck();
      // Schedule daily runs
      setInterval(runRescueCheck, 24 * 60 * 60 * 1000);
    }, timeUntilNext);

    logger.info('Rescue mode worker scheduled:', {
      nextRun: next10AM.toISOString(),
    });
  };

  scheduleNextRun();

  logger.info('✅ Rescue mode worker initialized');
}
