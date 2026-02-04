import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { Dream, Goal, Task } from '../types';

interface DreamsState {
  dreams: Dream[];
  selectedDream: Dream | null;
  isLoading: boolean;
  error: string | null;

  // Stats
  totalCompleted: number;
  currentStreak: number;
  totalXP: number;
  level: number;

  // Actions
  setDreams: (dreams: Dream[]) => void;
  addDream: (dream: Dream) => void;
  updateDream: (id: string, updates: Partial<Dream>) => void;
  deleteDream: (id: string) => void;
  selectDream: (dream: Dream | null) => void;

  // Goal actions
  updateGoal: (dreamId: string, goalId: string, updates: Partial<Goal>) => void;
  completeTask: (dreamId: string, goalId: string, taskId: string) => void;

  // Stats actions
  incrementStreak: () => void;
  resetStreak: () => void;
  addXP: (amount: number) => void;

  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
}

const calculateLevel = (xp: number): number => {
  // Level thresholds: 0, 100, 300, 600, 1000, 1500, 2100, 2800, 3600, 4500...
  const thresholds = [0, 100, 300, 600, 1000, 1500, 2100, 2800, 3600, 4500, 5500, 6600, 7800, 9100, 10500];
  let level = 1;
  for (let i = 1; i < thresholds.length; i++) {
    if (xp >= thresholds[i]) {
      level = i + 1;
    } else {
      break;
    }
  }
  return level;
};

const calculateDreamProgress = (dream: Dream): number => {
  if (!dream.goals || dream.goals.length === 0) return 0;

  const totalTasks = dream.goals.reduce((sum, goal) => sum + (goal.tasks?.length || 0), 0);
  if (totalTasks === 0) return 0;

  const completedTasks = dream.goals.reduce(
    (sum, goal) => sum + (goal.tasks?.filter((t) => t.status === 'completed').length || 0),
    0
  );

  return Math.round((completedTasks / totalTasks) * 100);
};

export const useDreamsStore = create<DreamsState>()(
  persist(
    (set, get) => ({
      // Initial state
      dreams: [],
      selectedDream: null,
      isLoading: false,
      error: null,
      totalCompleted: 0,
      currentStreak: 0,
      totalXP: 0,
      level: 1,

      // Actions
      setDreams: (dreams) => set({ dreams }),

      addDream: (dream) =>
        set((state) => ({
          dreams: [...state.dreams, dream],
        })),

      updateDream: (id, updates) =>
        set((state) => ({
          dreams: state.dreams.map((d) =>
            d.id === id ? { ...d, ...updates, updatedAt: new Date() } : d
          ),
          selectedDream:
            state.selectedDream?.id === id
              ? { ...state.selectedDream, ...updates, updatedAt: new Date() }
              : state.selectedDream,
        })),

      deleteDream: (id) =>
        set((state) => ({
          dreams: state.dreams.filter((d) => d.id !== id),
          selectedDream: state.selectedDream?.id === id ? null : state.selectedDream,
        })),

      selectDream: (dream) => set({ selectedDream: dream }),

      updateGoal: (dreamId, goalId, updates) =>
        set((state) => ({
          dreams: state.dreams.map((dream) => {
            if (dream.id !== dreamId) return dream;

            const updatedGoals = dream.goals.map((goal) =>
              goal.id === goalId ? { ...goal, ...updates } : goal
            );

            const updatedDream = { ...dream, goals: updatedGoals };
            updatedDream.progress = calculateDreamProgress(updatedDream);

            return updatedDream;
          }),
        })),

      completeTask: (dreamId, goalId, taskId) =>
        set((state) => {
          const dreams = state.dreams.map((dream) => {
            if (dream.id !== dreamId) return dream;

            const updatedGoals = dream.goals.map((goal) => {
              if (goal.id !== goalId) return goal;

              const updatedTasks = goal.tasks.map((task) =>
                task.id === taskId
                  ? { ...task, status: 'completed' as const, completedAt: new Date() }
                  : task
              );

              const completedCount = updatedTasks.filter((t) => t.status === 'completed').length;
              const goalProgress = Math.round((completedCount / updatedTasks.length) * 100);

              return {
                ...goal,
                tasks: updatedTasks,
                progress: goalProgress,
                status: goalProgress === 100 ? ('completed' as const) : goal.status,
              };
            });

            const updatedDream = { ...dream, goals: updatedGoals };
            updatedDream.progress = calculateDreamProgress(updatedDream);

            // Check if dream is completed
            if (updatedDream.progress === 100) {
              updatedDream.status = 'completed';
            }

            return updatedDream;
          });

          // Calculate new XP
          const newXP = state.totalXP + 10; // 10 XP per task
          const newLevel = calculateLevel(newXP);

          return {
            dreams,
            totalCompleted: state.totalCompleted + 1,
            totalXP: newXP,
            level: newLevel,
          };
        }),

      incrementStreak: () =>
        set((state) => ({
          currentStreak: state.currentStreak + 1,
          totalXP: state.totalXP + state.currentStreak * 5, // Bonus XP for streak
          level: calculateLevel(state.totalXP + state.currentStreak * 5),
        })),

      resetStreak: () => set({ currentStreak: 0 }),

      addXP: (amount) =>
        set((state) => {
          const newXP = state.totalXP + amount;
          return {
            totalXP: newXP,
            level: calculateLevel(newXP),
          };
        }),

      setLoading: (loading) => set({ isLoading: loading }),
      setError: (error) => set({ error }),
    }),
    {
      name: 'dreamplanner-dreams',
      storage: createJSONStorage(() => AsyncStorage),
      partialize: (state) => ({
        dreams: state.dreams,
        totalCompleted: state.totalCompleted,
        currentStreak: state.currentStreak,
        totalXP: state.totalXP,
        level: state.level,
      }),
    }
  )
);
