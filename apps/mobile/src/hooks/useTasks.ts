import { useMutation, useQueryClient } from '@tanstack/react-query';
import { Alert } from 'react-native';
import { api, ApiError } from '../services/api';

// Helper to show error alerts
const showError = (error: unknown, defaultMessage: string) => {
  const apiError = error as ApiError;
  Alert.alert('Error', apiError?.message || defaultMessage);
};

export function useUpdateTask() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: Record<string, unknown> }) =>
      api.tasks.update(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tasks'] });
      queryClient.invalidateQueries({ queryKey: ['calendar'] });
      queryClient.invalidateQueries({ queryKey: ['goals'] });
    },
    onError: (error) => {
      showError(error, 'Unable to update task. Please try again.');
    },
  });
}

export function useCompleteTask() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.tasks.complete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tasks'] });
      queryClient.invalidateQueries({ queryKey: ['calendar'] });
      queryClient.invalidateQueries({ queryKey: ['goals'] });
      queryClient.invalidateQueries({ queryKey: ['dreams'] });
    },
    onError: (error) => {
      showError(error, 'Unable to complete task. Please try again.');
    },
  });
}

export function useSkipTask() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.tasks.skip(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tasks'] });
      queryClient.invalidateQueries({ queryKey: ['calendar'] });
    },
    onError: (error) => {
      showError(error, 'Unable to skip task. Please try again.');
    },
  });
}
