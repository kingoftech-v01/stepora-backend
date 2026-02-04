import { notificationService } from '../services/notification.service';

let intervalId: NodeJS.Timeout | null = null;

const POLL_INTERVAL = 60 * 1000; // 1 minute

export function initializeNotificationWorker(): void {
  if (process.env.NODE_ENV === 'test') {
    return;
  }

  console.log('🔔 Notification worker initialized');

  // Process pending notifications every minute
  intervalId = setInterval(async () => {
    try {
      const sentCount = await notificationService.processPendingNotifications();
      if (sentCount > 0) {
        console.log(`📨 Sent ${sentCount} notifications`);
      }
    } catch (error) {
      console.error('Notification worker error:', error);
    }
  }, POLL_INTERVAL);
}

export function stopNotificationWorker(): void {
  if (intervalId) {
    clearInterval(intervalId);
    intervalId = null;
    console.log('🔔 Notification worker stopped');
  }
}
