import { act } from 'react-test-renderer';
import { useDreamsStore } from '../../stores/dreamsStore';

const mockDream = {
  id: 'dream-1',
  title: 'Learn Guitar',
  description: 'Master guitar playing',
  category: 'creativity' as const,
  priority: 3,
  status: 'active' as const,
  progress: 0,
  createdAt: new Date(),
  updatedAt: new Date(),
  goals: [
    {
      id: 'goal-1',
      dreamId: 'dream-1',
      title: 'Learn basic chords',
      order: 1,
      status: 'in_progress' as const,
      progress: 50,
      tasks: [
        {
          id: 'task-1',
          goalId: 'goal-1',
          title: 'Practice C chord',
          status: 'completed' as const,
          completedAt: new Date(),
        },
        {
          id: 'task-2',
          goalId: 'goal-1',
          title: 'Practice G chord',
          status: 'pending' as const,
        },
      ],
    },
  ],
};

beforeEach(() => {
  act(() => {
    useDreamsStore.setState({
      dreams: [],
      selectedDream: null,
      isLoading: false,
      error: null,
      totalCompleted: 0,
      currentStreak: 0,
      totalXP: 0,
      level: 1,
    });
  });
});

describe('DreamsStore', () => {
  describe('Initial state', () => {
    it('should have correct initial state', () => {
      const state = useDreamsStore.getState();

      expect(state.dreams).toEqual([]);
      expect(state.selectedDream).toBeNull();
      expect(state.isLoading).toBe(false);
      expect(state.error).toBeNull();
      expect(state.totalXP).toBe(0);
      expect(state.level).toBe(1);
    });
  });

  describe('setDreams', () => {
    it('should set dreams list', () => {
      act(() => {
        useDreamsStore.getState().setDreams([mockDream]);
      });

      expect(useDreamsStore.getState().dreams).toHaveLength(1);
      expect(useDreamsStore.getState().dreams[0].title).toBe('Learn Guitar');
    });
  });

  describe('addDream', () => {
    it('should add a dream to the list', () => {
      act(() => {
        useDreamsStore.getState().addDream(mockDream);
      });

      expect(useDreamsStore.getState().dreams).toHaveLength(1);
    });

    it('should append to existing dreams', () => {
      act(() => {
        useDreamsStore.getState().addDream(mockDream);
        useDreamsStore.getState().addDream({
          ...mockDream,
          id: 'dream-2',
          title: 'Run Marathon',
        });
      });

      expect(useDreamsStore.getState().dreams).toHaveLength(2);
    });
  });

  describe('updateDream', () => {
    it('should update a dream by id', () => {
      act(() => {
        useDreamsStore.getState().setDreams([mockDream]);
      });

      act(() => {
        useDreamsStore.getState().updateDream('dream-1', { title: 'Updated Title' });
      });

      expect(useDreamsStore.getState().dreams[0].title).toBe('Updated Title');
    });

    it('should update selected dream if it matches', () => {
      act(() => {
        useDreamsStore.getState().setDreams([mockDream]);
        useDreamsStore.getState().selectDream(mockDream);
      });

      act(() => {
        useDreamsStore.getState().updateDream('dream-1', { title: 'Updated' });
      });

      expect(useDreamsStore.getState().selectedDream?.title).toBe('Updated');
    });

    it('should not update other dreams', () => {
      act(() => {
        useDreamsStore.getState().setDreams([
          mockDream,
          { ...mockDream, id: 'dream-2', title: 'Other Dream' },
        ]);
      });

      act(() => {
        useDreamsStore.getState().updateDream('dream-1', { title: 'Updated' });
      });

      expect(useDreamsStore.getState().dreams[1].title).toBe('Other Dream');
    });
  });

  describe('deleteDream', () => {
    it('should remove dream from list', () => {
      act(() => {
        useDreamsStore.getState().setDreams([mockDream]);
      });

      act(() => {
        useDreamsStore.getState().deleteDream('dream-1');
      });

      expect(useDreamsStore.getState().dreams).toHaveLength(0);
    });

    it('should clear selected dream if it was deleted', () => {
      act(() => {
        useDreamsStore.getState().setDreams([mockDream]);
        useDreamsStore.getState().selectDream(mockDream);
      });

      act(() => {
        useDreamsStore.getState().deleteDream('dream-1');
      });

      expect(useDreamsStore.getState().selectedDream).toBeNull();
    });
  });

  describe('selectDream', () => {
    it('should select a dream', () => {
      act(() => {
        useDreamsStore.getState().selectDream(mockDream);
      });

      expect(useDreamsStore.getState().selectedDream).toEqual(mockDream);
    });

    it('should deselect dream', () => {
      act(() => {
        useDreamsStore.getState().selectDream(mockDream);
        useDreamsStore.getState().selectDream(null);
      });

      expect(useDreamsStore.getState().selectedDream).toBeNull();
    });
  });

  describe('completeTask', () => {
    it('should mark task as completed', () => {
      act(() => {
        useDreamsStore.getState().setDreams([mockDream]);
      });

      act(() => {
        useDreamsStore.getState().completeTask('dream-1', 'goal-1', 'task-2');
      });

      const dream = useDreamsStore.getState().dreams[0];
      const task = dream.goals[0].tasks[1];
      expect(task.status).toBe('completed');
      expect(task.completedAt).toBeDefined();
    });

    it('should update goal progress when task completed', () => {
      act(() => {
        useDreamsStore.getState().setDreams([mockDream]);
      });

      act(() => {
        useDreamsStore.getState().completeTask('dream-1', 'goal-1', 'task-2');
      });

      const goal = useDreamsStore.getState().dreams[0].goals[0];
      expect(goal.progress).toBe(100);
      expect(goal.status).toBe('completed');
    });

    it('should increase XP when completing task', () => {
      act(() => {
        useDreamsStore.getState().setDreams([mockDream]);
      });

      const xpBefore = useDreamsStore.getState().totalXP;

      act(() => {
        useDreamsStore.getState().completeTask('dream-1', 'goal-1', 'task-2');
      });

      expect(useDreamsStore.getState().totalXP).toBe(xpBefore + 10);
    });

    it('should increment total completed', () => {
      act(() => {
        useDreamsStore.getState().setDreams([mockDream]);
      });

      act(() => {
        useDreamsStore.getState().completeTask('dream-1', 'goal-1', 'task-2');
      });

      expect(useDreamsStore.getState().totalCompleted).toBe(1);
    });
  });

  describe('updateGoal', () => {
    it('should update goal within dream', () => {
      act(() => {
        useDreamsStore.getState().setDreams([mockDream]);
      });

      act(() => {
        useDreamsStore.getState().updateGoal('dream-1', 'goal-1', {
          title: 'Updated Goal',
        });
      });

      expect(useDreamsStore.getState().dreams[0].goals[0].title).toBe('Updated Goal');
    });
  });

  describe('incrementStreak', () => {
    it('should increment streak', () => {
      act(() => {
        useDreamsStore.getState().incrementStreak();
      });

      expect(useDreamsStore.getState().currentStreak).toBe(1);
    });

    it('should give bonus XP for streak', () => {
      act(() => {
        useDreamsStore.getState().incrementStreak();
        useDreamsStore.getState().incrementStreak();
      });

      // Streak 1: 0 * 5 = 0 bonus, Streak 2: 1 * 5 = 5 bonus
      expect(useDreamsStore.getState().totalXP).toBe(5);
    });
  });

  describe('resetStreak', () => {
    it('should reset streak to 0', () => {
      act(() => {
        useDreamsStore.getState().incrementStreak();
        useDreamsStore.getState().incrementStreak();
        useDreamsStore.getState().resetStreak();
      });

      expect(useDreamsStore.getState().currentStreak).toBe(0);
    });
  });

  describe('addXP', () => {
    it('should add XP', () => {
      act(() => {
        useDreamsStore.getState().addXP(50);
      });

      expect(useDreamsStore.getState().totalXP).toBe(50);
    });

    it('should update level based on XP', () => {
      act(() => {
        useDreamsStore.getState().addXP(100);
      });

      expect(useDreamsStore.getState().level).toBe(2);
    });

    it('should calculate higher levels correctly', () => {
      act(() => {
        useDreamsStore.getState().addXP(1000);
      });

      expect(useDreamsStore.getState().level).toBe(5);
    });
  });

  describe('setLoading', () => {
    it('should set loading state', () => {
      act(() => {
        useDreamsStore.getState().setLoading(true);
      });

      expect(useDreamsStore.getState().isLoading).toBe(true);
    });
  });

  describe('setError', () => {
    it('should set error', () => {
      act(() => {
        useDreamsStore.getState().setError('Failed to load');
      });

      expect(useDreamsStore.getState().error).toBe('Failed to load');
    });
  });
});
