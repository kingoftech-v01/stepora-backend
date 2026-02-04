import { act } from 'react-test-renderer';
import { useAuthStore } from '../../stores/authStore';

// Reset store state before each test
beforeEach(() => {
  const { logout } = useAuthStore.getState();
  act(() => {
    logout();
  });
});

describe('AuthStore', () => {
  describe('Initial state', () => {
    it('should have correct initial state', () => {
      const state = useAuthStore.getState();

      expect(state.user).toBeNull();
      expect(state.accessToken).toBeNull();
      expect(state.isAuthenticated).toBe(false);
      expect(state.hasCompletedOnboarding).toBe(false);
    });

    it('should have default notification preferences', () => {
      const state = useAuthStore.getState();

      expect(state.notificationPrefs).toEqual({
        reminders: true,
        reminderMinutesBefore: 15,
        motivation: true,
        motivationTime: '08:00',
        weeklyReport: true,
        weeklyReportDay: 0,
        dndEnabled: true,
        dndStart: 22,
        dndEnd: 7,
      });
    });

    it('should have default app preferences', () => {
      const state = useAuthStore.getState();

      expect(state.preferences).toEqual({
        theme: 'system',
        language: 'fr',
      });
    });
  });

  describe('setUser', () => {
    it('should set user and mark as authenticated', () => {
      const mockUser = {
        id: 'user-1',
        email: 'test@example.com',
        displayName: 'Test User',
        avatarUrl: null,
        timezone: 'Europe/Paris',
        subscription: 'free' as const,
      };

      act(() => {
        useAuthStore.getState().setUser(mockUser);
      });

      const state = useAuthStore.getState();
      expect(state.user).toEqual(mockUser);
      expect(state.isAuthenticated).toBe(true);
      expect(state.isLoading).toBe(false);
    });

    it('should set user to null and mark as not authenticated', () => {
      act(() => {
        useAuthStore.getState().setUser({
          id: '1',
          email: 'test@test.com',
          displayName: 'Test',
          avatarUrl: null,
          timezone: 'UTC',
          subscription: 'free',
        });
      });

      act(() => {
        useAuthStore.getState().setUser(null);
      });

      const state = useAuthStore.getState();
      expect(state.user).toBeNull();
      expect(state.isAuthenticated).toBe(false);
    });
  });

  describe('setAccessToken', () => {
    it('should set access token', () => {
      act(() => {
        useAuthStore.getState().setAccessToken('my-token-123');
      });

      expect(useAuthStore.getState().accessToken).toBe('my-token-123');
    });

    it('should clear access token', () => {
      act(() => {
        useAuthStore.getState().setAccessToken('token');
      });

      act(() => {
        useAuthStore.getState().setAccessToken(null);
      });

      expect(useAuthStore.getState().accessToken).toBeNull();
    });
  });

  describe('setWorkSchedule', () => {
    it('should set work schedule', () => {
      const schedule = {
        workDays: [1, 2, 3, 4, 5],
        startTime: '09:00',
        endTime: '18:00',
      };

      act(() => {
        useAuthStore.getState().setWorkSchedule(schedule);
      });

      expect(useAuthStore.getState().workSchedule).toEqual(schedule);
    });
  });

  describe('setNotificationPrefs', () => {
    it('should set notification preferences', () => {
      const prefs = {
        reminders: false,
        reminderMinutesBefore: 30,
        motivation: false,
        motivationTime: '09:00',
        weeklyReport: false,
        weeklyReportDay: 1,
        dndEnabled: false,
        dndStart: 23,
        dndEnd: 8,
      };

      act(() => {
        useAuthStore.getState().setNotificationPrefs(prefs);
      });

      expect(useAuthStore.getState().notificationPrefs).toEqual(prefs);
    });
  });

  describe('setPreferences', () => {
    it('should set app preferences', () => {
      const prefs = { theme: 'dark' as const, language: 'en' as const };

      act(() => {
        useAuthStore.getState().setPreferences(prefs);
      });

      expect(useAuthStore.getState().preferences).toEqual(prefs);
    });
  });

  describe('setOnboardingComplete', () => {
    it('should mark onboarding as complete', () => {
      act(() => {
        useAuthStore.getState().setOnboardingComplete();
      });

      expect(useAuthStore.getState().hasCompletedOnboarding).toBe(true);
    });
  });

  describe('logout', () => {
    it('should reset all state', () => {
      // Set some state first
      act(() => {
        useAuthStore.getState().setUser({
          id: '1',
          email: 'test@test.com',
          displayName: 'Test',
          avatarUrl: null,
          timezone: 'UTC',
          subscription: 'premium',
        });
        useAuthStore.getState().setAccessToken('token');
        useAuthStore.getState().setOnboardingComplete();
      });

      // Logout
      act(() => {
        useAuthStore.getState().logout();
      });

      const state = useAuthStore.getState();
      expect(state.user).toBeNull();
      expect(state.accessToken).toBeNull();
      expect(state.isAuthenticated).toBe(false);
      expect(state.hasCompletedOnboarding).toBe(false);
      expect(state.workSchedule).toBeNull();
    });
  });
});
