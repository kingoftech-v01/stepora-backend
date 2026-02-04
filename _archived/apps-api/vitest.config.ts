import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    globals: true,
    environment: 'node',
    setupFiles: ['./src/__tests__/setup.ts'],
    include: ['src/__tests__/**/*.test.ts'],
    mockReset: true,
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json', 'html', 'lcov'],
      include: [
        'src/services/user.service.ts',
        'src/services/dream.service.ts',
        'src/services/goal.service.ts',
        'src/services/task.service.ts',
        'src/services/conversation.service.ts',
        'src/services/notification.service.ts',
        'src/services/calendar.service.ts',
        'src/middleware/auth.ts',
        'src/middleware/errorHandler.ts',
        'src/validators/index.ts',
        'src/workers/notificationWorker.ts',
      ],
    },
    testTimeout: 30000,
    hookTimeout: 30000,
  },
});
