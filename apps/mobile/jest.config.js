module.exports = {
  testEnvironment: 'node',
  moduleFileExtensions: ['ts', 'tsx', 'js', 'jsx', 'json'],
  transform: {
    '^.+\\.(ts|tsx|js|jsx)$': ['ts-jest', {
      tsconfig: {
        jsx: 'react-jsx',
        esModuleInterop: true,
        allowJs: true,
        module: 'commonjs',
        target: 'es2020',
        strict: false,
        moduleResolution: 'node',
        types: ['jest', 'node'],
      },
      diagnostics: false,
    }],
  },
  transformIgnorePatterns: [
    'node_modules/(?!(react-native|@react-native|@react-navigation|react-native-paper|react-native-vector-icons|react-native-safe-area-context|react-native-screens|react-native-gesture-handler|react-native-reanimated|react-native-calendars|react-native-linear-gradient|react-native-mmkv|@react-native-async-storage|@notifee|@react-native-firebase)/)',
  ],
  setupFiles: ['./src/__tests__/setup.ts'],
  testPathIgnorePatterns: ['/node_modules/', 'setup.ts'],
  collectCoverageFrom: [
    'src/**/*.{ts,tsx}',
    '!src/**/*.test.{ts,tsx}',
    '!src/__tests__/**',
    '!src/types/**',
  ],
};
