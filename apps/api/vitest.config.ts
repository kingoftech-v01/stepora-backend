import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    globals: true,
    environment: 'node',
    coverage: {
      provider: 'v8',
      reporter: ['text', 'text-summary', 'lcov', 'json'],
      include: [
        'src/services/**/*.ts',
        'src/middleware/**/*.ts',
        'src/validators/**/*.ts',
        'src/workers/**/*.ts',
      ],
      exclude: [
        'src/**/*.test.ts',
        'src/**/*.spec.ts',
        'src/__tests__/**',
        'src/services/ai.service.ts',
      ],
      thresholds: {
        lines: 80,
        functions: 85,
        branches: 75,
        statements: 80,
      },
    },
    setupFiles: ['./src/__tests__/setup.ts'],
    mockReset: true,
  },
});
