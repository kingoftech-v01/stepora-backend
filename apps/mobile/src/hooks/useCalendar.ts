import { useQuery } from '@tanstack/react-query';
import { api } from '../services/api';

export function useCalendar(startDate: string, endDate: string) {
  return useQuery({
    queryKey: ['calendar', startDate, endDate],
    queryFn: () => api.calendar.get(startDate, endDate),
    enabled: !!startDate && !!endDate,
  });
}

export function useTodayTasks() {
  return useQuery({
    queryKey: ['calendar', 'today'],
    queryFn: () => api.calendar.getToday(),
  });
}

export function useWeekTasks() {
  return useQuery({
    queryKey: ['calendar', 'week'],
    queryFn: () => api.calendar.getWeek(),
  });
}
