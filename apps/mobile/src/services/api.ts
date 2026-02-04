import axios, { AxiosInstance, AxiosError } from 'axios';
import { Dream, Message, Conversation, PlanningResult, User } from '../types';

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

// Error handler
const handleError = (error: AxiosError) => {
  if (error.response) {
    const message = (error.response.data as any)?.message || 'Une erreur est survenue';
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
  register: async (email: string, password: string, displayName: string): Promise<{ user: User; accessToken: string }> => {
    try {
      const response = await apiClient.post('/auth/register', {
        email,
        password,
        displayName,
      });
      return response.data;
    } catch (error) {
      throw handleError(error as AxiosError);
    }
  },

  login: async (email: string, password: string): Promise<{ user: User; accessToken: string }> => {
    try {
      const response = await apiClient.post('/auth/login', { email, password });
      return response.data;
    } catch (error) {
      throw handleError(error as AxiosError);
    }
  },

  logout: async (): Promise<void> => {
    try {
      await apiClient.post('/auth/logout');
    } catch (error) {
      // Ignore logout errors
    }
  },

  getProfile: async (): Promise<User> => {
    try {
      const response = await apiClient.get('/users/me');
      return response.data;
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
    message: string,
    conversationId?: string
  ): Promise<{ message: Message; conversationId: string }> => {
    try {
      const response = await apiClient.post('/conversations/message', {
        message,
        conversationId,
      });
      return response.data;
    } catch (error) {
      throw handleError(error as AxiosError);
    }
  },

  getConversation: async (conversationId: string): Promise<Conversation> => {
    try {
      const response = await apiClient.get(`/conversations/${conversationId}`);
      return response.data;
    } catch (error) {
      throw handleError(error as AxiosError);
    }
  },

  getConversations: async (): Promise<Conversation[]> => {
    try {
      const response = await apiClient.get('/conversations');
      return response.data;
    } catch (error) {
      throw handleError(error as AxiosError);
    }
  },

  startNewConversation: async (type: Conversation['type'] = 'general'): Promise<Conversation> => {
    try {
      const response = await apiClient.post('/conversations', { type });
      return response.data;
    } catch (error) {
      throw handleError(error as AxiosError);
    }
  },
};

// ============================================
// DREAMS API
// ============================================

export const dreamsApi = {
  getDreams: async (): Promise<Dream[]> => {
    try {
      const response = await apiClient.get('/dreams');
      return response.data;
    } catch (error) {
      throw handleError(error as AxiosError);
    }
  },

  getDream: async (id: string): Promise<Dream> => {
    try {
      const response = await apiClient.get(`/dreams/${id}`);
      return response.data;
    } catch (error) {
      throw handleError(error as AxiosError);
    }
  },

  createDream: async (dream: Partial<Dream>): Promise<Dream> => {
    try {
      const response = await apiClient.post('/dreams', dream);
      return response.data;
    } catch (error) {
      throw handleError(error as AxiosError);
    }
  },

  updateDream: async (id: string, updates: Partial<Dream>): Promise<Dream> => {
    try {
      const response = await apiClient.put(`/dreams/${id}`, updates);
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

  generatePlan: async (dreamId: string): Promise<PlanningResult> => {
    try {
      const response = await apiClient.post(`/dreams/${dreamId}/generate-plan`);
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
  getTodayTasks: async (): Promise<any[]> => {
    try {
      const response = await apiClient.get('/calendar/today');
      return response.data;
    } catch (error) {
      throw handleError(error as AxiosError);
    }
  },

  completeTask: async (taskId: string): Promise<void> => {
    try {
      await apiClient.post(`/tasks/${taskId}/complete`);
    } catch (error) {
      throw handleError(error as AxiosError);
    }
  },

  rescheduleTask: async (taskId: string, newDate: string): Promise<void> => {
    try {
      await apiClient.put(`/tasks/${taskId}`, { scheduledDate: newDate });
    } catch (error) {
      throw handleError(error as AxiosError);
    }
  },
};

// Export default API object
export default {
  auth: authApi,
  chat: chatApi,
  dreams: dreamsApi,
  tasks: tasksApi,
  setAuthToken,
};
