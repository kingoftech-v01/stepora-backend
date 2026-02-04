import axios, { AxiosInstance, AxiosError } from 'axios';
import { Dream, Message, Conversation, PlanningResult, User, Task, ApiResponse } from '../types';

// Configuration
const API_BASE_URL = __DEV__
  ? 'http://localhost:3000/api'
  : 'https://api.dreamplanner.app/api';

// Create axios instance
const apiClient: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Token management
let authToken: string | null = null;

export const setAuthToken = (token: string | null) => {
  authToken = token;
  if (token) {
    apiClient.defaults.headers.common['Authorization'] = `Bearer ${token}`;
  } else {
    delete apiClient.defaults.headers.common['Authorization'];
  }
};

export const getAuthToken = () => authToken;

// Response interceptor to extract data
apiClient.interceptors.response.use(
  (response) => {
    // Backend wraps responses in { success, data }
    if (response.data?.success && response.data?.data !== undefined) {
      response.data = response.data.data;
    }
    return response;
  },
  (error) => Promise.reject(error)
);

// Error handler
const handleError = (error: AxiosError): never => {
  if (error.response) {
    const responseData = error.response.data as any;
    const message = responseData?.error?.message || responseData?.message || 'Une erreur est survenue';
    throw new Error(message);
  } else if (error.request) {
    throw new Error('Impossible de contacter le serveur');
  } else {
    throw new Error(error.message);
  }
};

// ============================================
// AUTH API
// ============================================

export const authApi = {
  register: async (
    idToken: string,
    email: string,
    displayName?: string,
    timezone?: string,
    fcmToken?: string,
    platform?: 'ios' | 'android'
  ): Promise<{ user: User; stats: any }> => {
    try {
      const response = await apiClient.post('/auth/register', {
        idToken,
        email,
        displayName,
        timezone,
        fcmToken,
        platform,
      });
      return response.data;
    } catch (error) {
      throw handleError(error as AxiosError);
    }
  },

  login: async (
    idToken: string,
    fcmToken?: string,
    platform?: 'ios' | 'android'
  ): Promise<{ user: User; stats: any }> => {
    try {
      const response = await apiClient.post('/auth/login', {
        idToken,
        fcmToken,
        platform,
      });
      return response.data;
    } catch (error) {
      throw handleError(error as AxiosError);
    }
  },

  logout: async (fcmToken?: string): Promise<void> => {
    try {
      await apiClient.post('/auth/logout', { fcmToken });
    } catch (error) {
      // Ignore logout errors
    }
  },

  refreshToken: async (idToken: string): Promise<{ valid: boolean; expiresAt: string }> => {
    try {
      const response = await apiClient.post('/auth/refresh-token', { idToken });
      return response.data;
    } catch (error) {
      throw handleError(error as AxiosError);
    }
  },
};

// ============================================
// USER API
// ============================================

export const userApi = {
  getProfile: async (): Promise<{ user: User; stats: any }> => {
    try {
      const response = await apiClient.get('/users/me');
      return response.data;
    } catch (error) {
      throw handleError(error as AxiosError);
    }
  },

  updateProfile: async (updates: {
    displayName?: string;
    timezone?: string;
    workSchedule?: any;
    notificationPrefs?: any;
    appPrefs?: any;
  }): Promise<{ user: User }> => {
    try {
      const response = await apiClient.patch('/users/me', updates);
      return response.data;
    } catch (error) {
      throw handleError(error as AxiosError);
    }
  },

  getStats: async (): Promise<any> => {
    try {
      const response = await apiClient.get('/users/me/stats');
      return response.data;
    } catch (error) {
      throw handleError(error as AxiosError);
    }
  },

  deleteAccount: async (): Promise<void> => {
    try {
      await apiClient.delete('/users/me');
    } catch (error) {
      throw handleError(error as AxiosError);
    }
  },

  registerFcmToken: async (token: string, platform: 'ios' | 'android'): Promise<void> => {
    try {
      await apiClient.post('/users/me/fcm-token', { token, platform });
    } catch (error) {
      throw handleError(error as AxiosError);
    }
  },
};

// ============================================
// CHAT API
// ============================================

export const chatApi = {
  sendMessage: async (
    conversationId: string,
    content: string
  ): Promise<{ userMessage: Message; assistantMessage: Message }> => {
    try {
      const response = await apiClient.post(
        `/conversations/${conversationId}/messages`,
        { content }
      );
      return response.data;
    } catch (error) {
      throw handleError(error as AxiosError);
    }
  },

  getConversation: async (conversationId: string): Promise<{ conversation: Conversation }> => {
    try {
      const response = await apiClient.get(`/conversations/${conversationId}`);
      return response.data;
    } catch (error) {
      throw handleError(error as AxiosError);
    }
  },

  getConversations: async (options?: {
    type?: string;
    dreamId?: string;
    limit?: number;
  }): Promise<{ conversations: Conversation[]; total: number }> => {
    try {
      const params = new URLSearchParams();
      if (options?.type) params.set('type', options.type);
      if (options?.dreamId) params.set('dreamId', options.dreamId);
      if (options?.limit) params.set('limit', options.limit.toString());

      const response = await apiClient.get(`/conversations?${params.toString()}`);
      return response.data;
    } catch (error) {
      throw handleError(error as AxiosError);
    }
  },

  createConversation: async (
    type: Conversation['type'],
    dreamId?: string
  ): Promise<{ conversation: Conversation }> => {
    try {
      const response = await apiClient.post('/conversations', { type, dreamId });
      return response.data;
    } catch (error) {
      throw handleError(error as AxiosError);
    }
  },

  deleteConversation: async (conversationId: string): Promise<void> => {
    try {
      await apiClient.delete(`/conversations/${conversationId}`);
    } catch (error) {
      throw handleError(error as AxiosError);
    }
  },
};

// ============================================
// DREAMS API
// ============================================

export const dreamsApi = {
  getDreams: async (options?: {
    status?: string;
    category?: string;
    limit?: number;
    offset?: number;
  }): Promise<{ dreams: Dream[]; total: number }> => {
    try {
      const params = new URLSearchParams();
      if (options?.status) params.set('status', options.status);
      if (options?.category) params.set('category', options.category);
      if (options?.limit) params.set('limit', options.limit.toString());
      if (options?.offset) params.set('offset', options.offset.toString());

      const response = await apiClient.get(`/dreams?${params.toString()}`);
      return response.data;
    } catch (error) {
      throw handleError(error as AxiosError);
    }
  },

  getDream: async (id: string): Promise<{ dream: Dream; progress: any }> => {
    try {
      const response = await apiClient.get(`/dreams/${id}`);
      return response.data;
    } catch (error) {
      throw handleError(error as AxiosError);
    }
  },

  createDream: async (data: {
    title: string;
    description: string;
    category?: string;
    targetDate?: string;
    priority?: number;
  }): Promise<{ dream: Dream }> => {
    try {
      const response = await apiClient.post('/dreams', data);
      return response.data;
    } catch (error) {
      throw handleError(error as AxiosError);
    }
  },

  updateDream: async (id: string, updates: Partial<Dream>): Promise<{ dream: Dream }> => {
    try {
      const response = await apiClient.patch(`/dreams/${id}`, updates);
      return response.data;
    } catch (error) {
      throw handleError(error as AxiosError);
    }
  },

  deleteDream: async (id: string): Promise<void> => {
    try {
      await apiClient.delete(`/dreams/${id}`);
    } catch (error) {
      throw handleError(error as AxiosError);
    }
  },

  generatePlan: async (dreamId: string, availableHoursPerWeek?: number): Promise<{ dream: Dream; progress: any }> => {
    try {
      const response = await apiClient.post(`/dreams/${dreamId}/generate-plan`, {
        availableHoursPerWeek,
      });
      return response.data;
    } catch (error) {
      throw handleError(error as AxiosError);
    }
  },

  getProgress: async (dreamId: string): Promise<any> => {
    try {
      const response = await apiClient.get(`/dreams/${dreamId}/progress`);
      return response.data;
    } catch (error) {
      throw handleError(error as AxiosError);
    }
  },
};

// ============================================
// TASKS API
// ============================================

export const tasksApi = {
  getTodayTasks: async (): Promise<{ tasks: Task[] }> => {
    try {
      const response = await apiClient.get('/tasks?today=true');
      return response.data;
    } catch (error) {
      throw handleError(error as AxiosError);
    }
  },

  getUpcomingTasks: async (limit?: number): Promise<{ tasks: Task[] }> => {
    try {
      const response = await apiClient.get(`/tasks?upcoming=true&limit=${limit || 10}`);
      return response.data;
    } catch (error) {
      throw handleError(error as AxiosError);
    }
  },

  getOverdueTasks: async (): Promise<{ tasks: Task[] }> => {
    try {
      const response = await apiClient.get('/tasks?overdue=true');
      return response.data;
    } catch (error) {
      throw handleError(error as AxiosError);
    }
  },

  getTasksByDateRange: async (startDate: string, endDate: string): Promise<{ tasks: Task[] }> => {
    try {
      const response = await apiClient.get(
        `/tasks?startDate=${startDate}&endDate=${endDate}`
      );
      return response.data;
    } catch (error) {
      throw handleError(error as AxiosError);
    }
  },

  completeTask: async (taskId: string): Promise<{ task: Task }> => {
    try {
      const response = await apiClient.post(`/tasks/${taskId}/complete`);
      return response.data;
    } catch (error) {
      throw handleError(error as AxiosError);
    }
  },

  skipTask: async (taskId: string): Promise<{ task: Task }> => {
    try {
      const response = await apiClient.post(`/tasks/${taskId}/skip`);
      return response.data;
    } catch (error) {
      throw handleError(error as AxiosError);
    }
  },

  updateTask: async (taskId: string, updates: Partial<Task>): Promise<{ task: Task }> => {
    try {
      const response = await apiClient.patch(`/tasks/${taskId}`, updates);
      return response.data;
    } catch (error) {
      throw handleError(error as AxiosError);
    }
  },
};

// ============================================
// CALENDAR API
// ============================================

export const calendarApi = {
  getMonthView: async (year: number, month: number): Promise<any> => {
    try {
      const response = await apiClient.get(
        `/calendar/month?year=${year}&month=${month}`
      );
      return response.data;
    } catch (error) {
      throw handleError(error as AxiosError);
    }
  },

  getDayView: async (date: string): Promise<any> => {
    try {
      const response = await apiClient.get(`/calendar/day?date=${date}`);
      return response.data;
    } catch (error) {
      throw handleError(error as AxiosError);
    }
  },
};

// ============================================
// NOTIFICATIONS API
// ============================================

export const notificationsApi = {
  getNotifications: async (options?: {
    limit?: number;
    offset?: number;
  }): Promise<{ notifications: any[]; total: number }> => {
    try {
      const params = new URLSearchParams();
      if (options?.limit) params.set('limit', options.limit.toString());
      if (options?.offset) params.set('offset', options.offset.toString());

      const response = await apiClient.get(`/notifications?${params.toString()}`);
      return response.data;
    } catch (error) {
      throw handleError(error as AxiosError);
    }
  },

  getUnreadCount: async (): Promise<{ count: number }> => {
    try {
      const response = await apiClient.get('/notifications/unread-count');
      return response.data;
    } catch (error) {
      throw handleError(error as AxiosError);
    }
  },

  markAsRead: async (id: string): Promise<void> => {
    try {
      await apiClient.patch(`/notifications/${id}/read`);
    } catch (error) {
      throw handleError(error as AxiosError);
    }
  },

  markAllAsRead: async (): Promise<void> => {
    try {
      await apiClient.post('/notifications/read-all');
    } catch (error) {
      throw handleError(error as AxiosError);
    }
  },
};

// Export API object
export default {
  auth: authApi,
  user: userApi,
  chat: chatApi,
  dreams: dreamsApi,
  tasks: tasksApi,
  calendar: calendarApi,
  notifications: notificationsApi,
  setAuthToken,
  getAuthToken,
};
