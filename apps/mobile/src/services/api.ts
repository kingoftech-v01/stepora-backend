import axios, { AxiosInstance, AxiosRequestConfig } from 'axios';
import auth from '@react-native-firebase/auth';
import { ENV } from '../config/env';

// Types for API responses
export interface ApiError {
  message: string;
  code?: string;
  details?: Record<string, string[]>;
}

export interface PaginatedResponse<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

class ApiService {
  private client: AxiosInstance;

  constructor() {
    this.client = axios.create({
      baseURL: ENV.API_URL,
      timeout: 30000,
      headers: {
        'Content-Type': 'application/json',
      },
    });

    // Request interceptor: Add Firebase token
    this.client.interceptors.request.use(
      async (config) => {
        const user = auth().currentUser;
        if (user) {
          try {
            const token = await user.getIdToken();
            config.headers.Authorization = `Bearer ${token}`;
          } catch (error) {
            // Token retrieval failed - continue without auth
          }
        }
        return config;
      },
      (error) => Promise.reject(error)
    );

    // Response interceptor: Handle errors and unwrap data
    this.client.interceptors.response.use(
      (response) => response.data,
      async (error) => {
        if (error.response?.status === 401) {
          // Token expired or invalid
          try {
            const user = auth().currentUser;
            if (user) {
              await user.getIdToken(true); // Force refresh
              // Retry the request
              return this.client.request(error.config);
            }
          } catch (refreshError) {
            // If refresh fails, logout
            await auth().signOut();
          }
        }

        // Format error for consistent handling
        const apiError: ApiError = {
          message: error.response?.data?.detail ||
                   error.response?.data?.message ||
                   error.message ||
                   'An error occurred',
          code: error.response?.status?.toString(),
          details: error.response?.data?.errors,
        };

        return Promise.reject(apiError);
      }
    );
  }

  // Base HTTP methods for direct access
  get<T = unknown>(url: string, config?: AxiosRequestConfig): Promise<T> {
    return this.client.get(url, config);
  }

  post<T = unknown>(url: string, data?: unknown, config?: AxiosRequestConfig): Promise<T> {
    return this.client.post(url, data, config);
  }

  patch<T = unknown>(url: string, data?: unknown, config?: AxiosRequestConfig): Promise<T> {
    return this.client.patch(url, data, config);
  }

  put<T = unknown>(url: string, data?: unknown, config?: AxiosRequestConfig): Promise<T> {
    return this.client.put(url, data, config);
  }

  delete<T = unknown>(url: string, config?: AxiosRequestConfig): Promise<T> {
    return this.client.delete(url, config);
  }

  // Auth endpoints (Django REST Framework)
  auth = {
    register: (data: { email: string; password: string; username?: string }) =>
      this.client.post('/api/auth/register/', data),
    verify: () =>
      this.client.post('/api/auth/verify/'),
    login: (data: { email: string; password: string }) =>
      this.client.post('/api/auth/login/', data),
  };

  // Users endpoints
  users = {
    getMe: () =>
      this.client.get('/api/users/me/'),
    updateMe: (data: Record<string, unknown>) =>
      this.client.patch('/api/users/me/', data),
    registerFcmToken: (token: string, platform: string) =>
      this.client.post('/api/users/fcm-token/', { token, platform }),
  };

  // Dreams endpoints (Django DRF ViewSet)
  dreams = {
    list: (params?: Record<string, unknown>) =>
      this.client.get('/api/dreams/dreams/', { params }),
    create: (data: Record<string, unknown>) =>
      this.client.post('/api/dreams/dreams/', data),
    get: (id: string) =>
      this.client.get(`/api/dreams/dreams/${id}/`),
    update: (id: string, data: Record<string, unknown>) =>
      this.client.patch(`/api/dreams/dreams/${id}/`, data),
    delete: (id: string) =>
      this.client.delete(`/api/dreams/dreams/${id}/`),
    generatePlan: (id: string, data?: Record<string, unknown>) =>
      this.client.post(`/api/dreams/dreams/${id}/generate_plan/`, data),
    complete: (id: string) =>
      this.client.post(`/api/dreams/dreams/${id}/complete/`),
  };

  // Goals endpoints (Django DRF ViewSet)
  goals = {
    list: (params?: Record<string, unknown>) =>
      this.client.get('/api/dreams/goals/', { params }),
    get: (id: string) =>
      this.client.get(`/api/dreams/goals/${id}/`),
    update: (id: string, data: Record<string, unknown>) =>
      this.client.patch(`/api/dreams/goals/${id}/`, data),
    complete: (id: string) =>
      this.client.post(`/api/dreams/goals/${id}/complete/`),
  };

  // Tasks endpoints (Django DRF ViewSet)
  tasks = {
    list: (params?: Record<string, unknown>) =>
      this.client.get('/api/dreams/tasks/', { params }),
    update: (id: string, data: Record<string, unknown>) =>
      this.client.patch(`/api/dreams/tasks/${id}/`, data),
    complete: (id: string) =>
      this.client.post(`/api/dreams/tasks/${id}/complete/`),
    skip: (id: string) =>
      this.client.post(`/api/dreams/tasks/${id}/skip/`),
  };

  // Conversations endpoints
  conversations = {
    list: () =>
      this.client.get('/api/conversations/'),
    create: (data: Record<string, unknown>) =>
      this.client.post('/api/conversations/', data),
    get: (id: string) =>
      this.client.get(`/api/conversations/${id}/`),
    sendMessage: (id: string, content: string) =>
      this.client.post(`/api/conversations/${id}/messages/`, { content }),
  };

  // Calendar endpoints
  calendar = {
    get: (startDate: string, endDate: string) =>
      this.client.get('/api/calendar/', { params: { start_date: startDate, end_date: endDate } }),
    getToday: () =>
      this.client.get('/api/calendar/today/'),
    getWeek: () =>
      this.client.get('/api/calendar/week/'),
  };

  // Notifications endpoints
  notifications = {
    list: () =>
      this.client.get('/api/notifications/'),
    markRead: (id: string) =>
      this.client.patch(`/api/notifications/${id}/read/`),
    markAllRead: () =>
      this.client.patch('/api/notifications/read-all/'),
  };

  // Gamification endpoints
  gamification = {
    getProfile: () =>
      this.client.get('/api/gamification/profile/'),
    getLeaderboard: (type: string, params?: Record<string, unknown>) =>
      this.client.get(`/api/gamification/leaderboards/${type}/`, { params }),
  };

  // Social endpoints
  social = {
    getFeed: (type: 'friends' | 'global' = 'friends') =>
      this.client.get(`/api/social/feed/${type}/`),
    getFriends: () =>
      this.client.get('/api/social/friends/'),
    getFriendRequests: () =>
      this.client.get('/api/social/friend-requests/'),
    sendFriendRequest: (userId: string) =>
      this.client.post('/api/social/friend-requests/', { user_id: userId }),
    acceptFriendRequest: (requestId: string) =>
      this.client.post(`/api/social/friend-requests/${requestId}/accept/`),
    rejectFriendRequest: (requestId: string) =>
      this.client.post(`/api/social/friend-requests/${requestId}/reject/`),
  };

  // Buddy endpoints
  buddies = {
    getCurrent: () =>
      this.client.get('/api/buddies/current/'),
    findMatch: () =>
      this.client.post('/api/buddies/find-match/'),
    pair: (userId: string) =>
      this.client.post('/api/buddies/pair/', { user_id: userId }),
    getProgress: (buddyId: string) =>
      this.client.get(`/api/buddies/${buddyId}/progress/`),
    sendEncouragement: (buddyId: string, message: string) =>
      this.client.post(`/api/buddies/${buddyId}/encourage/`, { message }),
    endPairing: (buddyId: string) =>
      this.client.post(`/api/buddies/${buddyId}/end/`),
  };

  // Circles endpoints
  circles = {
    list: (filter?: string) =>
      this.client.get('/api/circles/', { params: filter ? { filter } : undefined }),
    get: (id: string) =>
      this.client.get(`/api/circles/${id}/`),
    create: (data: Record<string, unknown>) =>
      this.client.post('/api/circles/', data),
    join: (id: string) =>
      this.client.post(`/api/circles/${id}/join/`),
    leave: (id: string) =>
      this.client.post(`/api/circles/${id}/leave/`),
    getMembers: (id: string) =>
      this.client.get(`/api/circles/${id}/members/`),
    getChallenges: (id: string) =>
      this.client.get(`/api/circles/${id}/challenges/`),
    createChallenge: (id: string, data: Record<string, unknown>) =>
      this.client.post(`/api/circles/${id}/challenges/`, data),
  };
}

export const api = new ApiService();
