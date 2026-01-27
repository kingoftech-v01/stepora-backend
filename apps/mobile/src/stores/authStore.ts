import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';
import { MMKV } from 'react-native-mmkv';

// MMKV storage instance
const storage = new MMKV();

// Zustand storage adapter for MMKV
const zustandStorage = {
  getItem: (name: string) => {
    const value = storage.getString(name);
    return value ?? null;
  },
  setItem: (name: string, value: string) => {
    storage.set(name, value);
  },
  removeItem: (name: string) => {
    storage.delete(name);
  },
};

interface User {
  id: string;
  email: string;
  displayName: string | null;
  avatarUrl: string | null;
  timezone: string;
  subscription: 'free' | 'premium' | 'pro';
}

interface WorkSchedule {
  workDays: number[]; // 0-6, 0 = Sunday
  startTime: string; // "HH:mm"
  endTime: string; // "HH:mm"
}

interface NotificationPrefs {
  reminders: boolean;
  reminderMinutesBefore: number;
  motivation: boolean;
  motivationTime: string;
  weeklyReport: boolean;
  weeklyReportDay: number;
  dndEnabled: boolean;
  dndStart: number; // hour (0-23)
  dndEnd: number; // hour (0-23)
}

interface AppPreferences {
  theme: 'light' | 'dark' | 'system';
  language: 'fr' | 'en';
}

interface AuthState {
  // Auth state
  user: User | null;
  accessToken: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;

  // User preferences
  workSchedule: WorkSchedule | null;
  notificationPrefs: NotificationPrefs | null;
  preferences: AppPreferences | null;

  // Onboarding
  hasCompletedOnboarding: boolean;

  // Actions
  setUser: (user: User | null) => void;
  setAccessToken: (token: string | null) => void;
  setWorkSchedule: (schedule: WorkSchedule) => void;
  setNotificationPrefs: (prefs: NotificationPrefs) => void;
  setPreferences: (prefs: AppPreferences) => void;
  setOnboardingComplete: () => void;
  logout: () => void;
}

const defaultNotificationPrefs: NotificationPrefs = {
  reminders: true,
  reminderMinutesBefore: 15,
  motivation: true,
  motivationTime: '08:00',
  weeklyReport: true,
  weeklyReportDay: 0, // Sunday
  dndEnabled: true,
  dndStart: 22,
  dndEnd: 7,
};

const defaultAppPreferences: AppPreferences = {
  theme: 'system',
  language: 'fr',
};

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      // Initial state
      user: null,
      accessToken: null,
      isAuthenticated: false,
      isLoading: true,
      workSchedule: null,
      notificationPrefs: defaultNotificationPrefs,
      preferences: defaultAppPreferences,
      hasCompletedOnboarding: false,

      // Actions
      setUser: (user) =>
        set({
          user,
          isAuthenticated: !!user,
          isLoading: false,
        }),

      setAccessToken: (token) =>
        set({
          accessToken: token,
        }),

      setWorkSchedule: (schedule) =>
        set({
          workSchedule: schedule,
        }),

      setNotificationPrefs: (prefs) =>
        set({
          notificationPrefs: prefs,
        }),

      setPreferences: (prefs) =>
        set({
          preferences: prefs,
        }),

      setOnboardingComplete: () =>
        set({
          hasCompletedOnboarding: true,
        }),

      logout: () =>
        set({
          user: null,
          accessToken: null,
          isAuthenticated: false,
          workSchedule: null,
          notificationPrefs: defaultNotificationPrefs,
          preferences: defaultAppPreferences,
          hasCompletedOnboarding: false,
        }),
    }),
    {
      name: 'dreamplanner-auth',
      storage: createJSONStorage(() => zustandStorage),
      partialize: (state) => ({
        user: state.user,
        accessToken: state.accessToken,
        isAuthenticated: state.isAuthenticated,
        workSchedule: state.workSchedule,
        notificationPrefs: state.notificationPrefs,
        preferences: state.preferences,
        hasCompletedOnboarding: state.hasCompletedOnboarding,
      }),
    }
  )
);
