import { MD3LightTheme, MD3DarkTheme } from 'react-native-paper';

// Color palette
export const colors = {
  // Primary - Purple Dream
  primary: {
    50: '#F3E8FF',
    100: '#E9D5FF',
    200: '#D8B4FE',
    300: '#C084FC',
    400: '#A855F7',
    500: '#8B5CF6', // Main primary
    600: '#7C3AED',
    700: '#6D28D9',
    800: '#5B21B6',
    900: '#4C1D95',
  },

  // Secondary - Teal Success
  secondary: {
    50: '#F0FDFA',
    100: '#CCFBF1',
    200: '#99F6E4',
    300: '#5EEAD4',
    400: '#2DD4BF',
    500: '#14B8A6', // Main secondary
    600: '#0D9488',
    700: '#0F766E',
    800: '#115E59',
    900: '#134E4A',
  },

  // Semantic
  success: '#10B981',
  warning: '#F59E0B',
  error: '#EF4444',
  info: '#3B82F6',

  // Neutral
  gray: {
    50: '#F9FAFB',
    100: '#F3F4F6',
    200: '#E5E7EB',
    300: '#D1D5DB',
    400: '#9CA3AF',
    500: '#6B7280',
    600: '#4B5563',
    700: '#374151',
    800: '#1F2937',
    900: '#111827',
  },

  // Dark mode specific
  dark: {
    surface: '#0F0F23',
    card: '#1A1A2E',
    elevated: '#25253A',
  },
};

// Light theme
const lightTheme = {
  ...MD3LightTheme,
  colors: {
    ...MD3LightTheme.colors,
    primary: colors.primary[500],
    primaryContainer: colors.primary[100],
    secondary: colors.secondary[500],
    secondaryContainer: colors.secondary[100],
    background: colors.gray[50],
    surface: '#FFFFFF',
    surfaceVariant: colors.gray[100],
    error: colors.error,
    onPrimary: '#FFFFFF',
    onSecondary: '#FFFFFF',
    onBackground: colors.gray[800],
    onSurface: colors.gray[800],
    onSurfaceVariant: colors.gray[600],
    outline: colors.gray[300],
    elevation: {
      level0: 'transparent',
      level1: '#FFFFFF',
      level2: colors.gray[50],
      level3: colors.gray[100],
      level4: colors.gray[100],
      level5: colors.gray[200],
    },
  },
};

// Dark theme
const darkTheme = {
  ...MD3DarkTheme,
  colors: {
    ...MD3DarkTheme.colors,
    primary: colors.primary[400],
    primaryContainer: colors.primary[900],
    secondary: colors.secondary[400],
    secondaryContainer: colors.secondary[900],
    background: colors.dark.surface,
    surface: colors.dark.card,
    surfaceVariant: colors.dark.elevated,
    error: colors.error,
    onPrimary: '#FFFFFF',
    onSecondary: '#FFFFFF',
    onBackground: colors.gray[50],
    onSurface: colors.gray[50],
    onSurfaceVariant: colors.gray[400],
    outline: colors.gray[700],
    elevation: {
      level0: 'transparent',
      level1: colors.dark.card,
      level2: colors.dark.elevated,
      level3: colors.dark.elevated,
      level4: colors.dark.elevated,
      level5: colors.dark.elevated,
    },
  },
};

// Theme export
export const theme = {
  light: lightTheme,
  dark: darkTheme,
  colors: {
    ...colors,
    primary: colors.primary[500],
    secondary: colors.secondary[500],
    background: colors.gray[50],
    surface: '#FFFFFF',
    text: colors.gray[800],
    textSecondary: colors.gray[500],
    border: colors.gray[200],
    disabled: colors.gray[400],
  },
};

// Spacing scale (base 4px)
export const spacing = {
  xs: 4,
  sm: 8,
  md: 16,
  lg: 24,
  xl: 32,
  '2xl': 48,
  '3xl': 64,
};

// Typography
export const typography = {
  h1: {
    fontSize: 32,
    fontWeight: '700' as const,
    lineHeight: 38,
  },
  h2: {
    fontSize: 24,
    fontWeight: '600' as const,
    lineHeight: 31,
  },
  h3: {
    fontSize: 20,
    fontWeight: '600' as const,
    lineHeight: 28,
  },
  h4: {
    fontSize: 18,
    fontWeight: '500' as const,
    lineHeight: 25,
  },
  bodyLarge: {
    fontSize: 18,
    fontWeight: '400' as const,
    lineHeight: 29,
  },
  body: {
    fontSize: 16,
    fontWeight: '400' as const,
    lineHeight: 24,
  },
  bodySmall: {
    fontSize: 14,
    fontWeight: '400' as const,
    lineHeight: 21,
  },
  caption: {
    fontSize: 12,
    fontWeight: '400' as const,
    lineHeight: 17,
  },
};

// Border radius
export const borderRadius = {
  sm: 8,
  md: 12,
  lg: 16,
  xl: 24,
  full: 9999,
};

// Shadows
export const shadows = {
  sm: {
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.05,
    shadowRadius: 2,
    elevation: 1,
  },
  md: {
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.08,
    shadowRadius: 8,
    elevation: 3,
  },
  lg: {
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.1,
    shadowRadius: 16,
    elevation: 5,
  },
};
