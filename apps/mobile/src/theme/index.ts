import { MD3LightTheme, MD3DarkTheme, configureFonts } from 'react-native-paper';
import { StyleSheet } from 'react-native';

// Color palette
export const colors = {
  // Primary - Purple Dream
  primary: {
    50: '#F3E8FF',
    100: '#E9D5FF',
    200: '#D8B4FE',
    300: '#C084FC',
    400: '#A855F7',
    500: '#8B5CF6',
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
    500: '#14B8A6',
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

  white: '#FFFFFF',
  black: '#000000',
};

// Light theme
export const lightTheme = {
  ...MD3LightTheme,
  colors: {
    ...MD3LightTheme.colors,
    primary: colors.primary[500],
    primaryContainer: colors.primary[100],
    secondary: colors.secondary[500],
    secondaryContainer: colors.secondary[100],
    background: colors.gray[50],
    surface: colors.white,
    surfaceVariant: colors.gray[100],
    error: colors.error,
    onPrimary: colors.white,
    onSecondary: colors.white,
    onBackground: colors.gray[800],
    onSurface: colors.gray[800],
    onSurfaceVariant: colors.gray[600],
    outline: colors.gray[300],
    outlineVariant: colors.gray[200],
  },
  custom: {
    colors: {
      textPrimary: colors.gray[800],
      textSecondary: colors.gray[500],
      textMuted: colors.gray[400],
      border: colors.gray[200],
      cardBackground: colors.white,
      inputBackground: colors.gray[50],
      success: colors.success,
      warning: colors.warning,
      error: colors.error,
      info: colors.info,
      aiBubble: colors.primary[50],
      userBubble: colors.primary[500],
    },
  },
};

// Dark theme
export const darkTheme = {
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
    onPrimary: colors.white,
    onSecondary: colors.white,
    onBackground: colors.gray[50],
    onSurface: colors.gray[50],
    onSurfaceVariant: colors.gray[400],
    outline: colors.gray[700],
    outlineVariant: colors.gray[800],
  },
  custom: {
    colors: {
      textPrimary: colors.gray[50],
      textSecondary: colors.gray[400],
      textMuted: colors.gray[500],
      border: colors.gray[700],
      cardBackground: colors.dark.card,
      inputBackground: colors.dark.elevated,
      success: colors.success,
      warning: colors.warning,
      error: colors.error,
      info: colors.info,
      aiBubble: colors.dark.elevated,
      userBubble: colors.primary[600],
    },
  },
};

// Spacing scale (base 4px)
export const spacing = {
  xs: 4,
  sm: 8,
  md: 16,
  lg: 24,
  xl: 32,
  xxl: 48,
};

// Border radius
export const borderRadius = {
  sm: 8,
  md: 12,
  lg: 16,
  xl: 24,
  full: 9999,
};

// Typography
export const typography = StyleSheet.create({
  h1: {
    fontSize: 32,
    fontWeight: '700',
    lineHeight: 40,
  },
  h2: {
    fontSize: 24,
    fontWeight: '600',
    lineHeight: 32,
  },
  h3: {
    fontSize: 20,
    fontWeight: '600',
    lineHeight: 28,
  },
  h4: {
    fontSize: 18,
    fontWeight: '500',
    lineHeight: 26,
  },
  body: {
    fontSize: 16,
    fontWeight: '400',
    lineHeight: 24,
  },
  bodySmall: {
    fontSize: 14,
    fontWeight: '400',
    lineHeight: 20,
  },
  caption: {
    fontSize: 12,
    fontWeight: '400',
    lineHeight: 16,
  },
});

// Shadows
export const shadows = StyleSheet.create({
  sm: {
    shadowColor: colors.black,
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.05,
    shadowRadius: 2,
    elevation: 1,
  },
  md: {
    shadowColor: colors.black,
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.08,
    shadowRadius: 8,
    elevation: 3,
  },
  lg: {
    shadowColor: colors.black,
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.12,
    shadowRadius: 16,
    elevation: 6,
  },
});

// Export theme type
export type AppTheme = typeof lightTheme;
