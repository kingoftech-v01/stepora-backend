import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { initializeNotificationWorker, stopNotificationWorker } from '../../workers/notificationWorker';
import { notificationService } from '../../services/notification.service';

vi.mock('../../services/notification.service', () => ({
  notificationService: {
    processPendingNotifications: vi.fn(),
  },
}));

describe('NotificationWorker', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.useFakeTimers();
    process.env.NODE_ENV = 'production';
  });

  afterEach(() => {
    stopNotificationWorker();
    vi.useRealTimers();
    process.env.NODE_ENV = 'test';
  });

  it('should not initialize in test environment', () => {
    process.env.NODE_ENV = 'test';
    initializeNotificationWorker();

    // Should not set up interval in test
    vi.advanceTimersByTime(60000);
    expect(notificationService.processPendingNotifications).not.toHaveBeenCalled();
  });

  it('should process notifications on interval', () => {
    const mockProcess = vi.mocked(notificationService.processPendingNotifications);
    mockProcess.mockResolvedValue(2);

    initializeNotificationWorker();

    // Advance timer by 1 minute
    vi.advanceTimersByTime(60000);

    expect(mockProcess).toHaveBeenCalledTimes(1);
  });

  it('should stop worker when stopNotificationWorker is called', () => {
    const mockProcess = vi.mocked(notificationService.processPendingNotifications);
    mockProcess.mockResolvedValue(0);

    initializeNotificationWorker();
    stopNotificationWorker();

    vi.advanceTimersByTime(120000);
    expect(mockProcess).not.toHaveBeenCalled();
  });

  it('should handle errors gracefully', () => {
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
    const mockProcess = vi.mocked(notificationService.processPendingNotifications);
    mockProcess.mockRejectedValue(new Error('DB connection error'));

    initializeNotificationWorker();
    vi.advanceTimersByTime(60000);

    // Should not crash
    expect(mockProcess).toHaveBeenCalledTimes(1);
    consoleSpy.mockRestore();
  });
});
