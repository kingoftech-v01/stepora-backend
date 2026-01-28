import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Alert } from 'react-native';
import { api, ApiError } from '../services/api';

// Helper to show error alerts
const showError = (error: unknown, defaultMessage: string) => {
  const apiError = error as ApiError;
  Alert.alert('Erreur', apiError?.message || defaultMessage);
};

export function useDreams(filters?: Record<string, unknown>) {
  return useQuery({
    queryKey: ['dreams', filters],
    queryFn: () => api.dreams.list(filters),
  });
}

export function useDream(id: string) {
  return useQuery({
    queryKey: ['dreams', id],
    queryFn: () => api.dreams.get(id),
    enabled: !!id,
  });
}

export function useCreateDream() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: api.dreams.create,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['dreams'] });
    },
    onError: (error) => {
      showError(error, 'Impossible de créer le rêve. Veuillez réessayer.');
    },
  });
}

export function useUpdateDream() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: Record<string, unknown> }) =>
      api.dreams.update(id, data),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['dreams'] });
      queryClient.invalidateQueries({ queryKey: ['dreams', variables.id] });
    },
    onError: (error) => {
      showError(error, 'Impossible de mettre à jour le rêve. Veuillez réessayer.');
    },
  });
}

export function useDeleteDream() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.dreams.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['dreams'] });
    },
    onError: (error) => {
      showError(error, 'Impossible de supprimer le rêve. Veuillez réessayer.');
    },
  });
}

export function useGeneratePlan() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data?: Record<string, unknown> }) =>
      api.dreams.generatePlan(id, data),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['dreams', variables.id] });
      queryClient.invalidateQueries({ queryKey: ['goals'] });
      queryClient.invalidateQueries({ queryKey: ['tasks'] });
    },
    onError: (error) => {
      showError(error, 'Impossible de générer le plan. Veuillez réessayer.');
    },
  });
}

export function useCompleteDream() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.dreams.complete(id),
    onSuccess: (_, id) => {
      queryClient.invalidateQueries({ queryKey: ['dreams'] });
      queryClient.invalidateQueries({ queryKey: ['dreams', id] });
    },
    onError: (error) => {
      showError(error, 'Impossible de compléter le rêve. Veuillez réessayer.');
    },
  });
}
