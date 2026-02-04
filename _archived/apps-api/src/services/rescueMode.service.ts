import { prisma } from '../utils/prisma';
import { notificationService } from './notification.service';
import { aiService } from './ai.service';
import { logger } from '../config/logger';

interface AbandonmentSignals {
  daysSinceLastActivity: number;
  missedTasksStreak: number;
  appOpenWithoutAction: number;
  previousAbandonPatterns: boolean;
}

class RescueModeService {
  shouldTriggerRescue(signals: AbandonmentSignals): boolean {
    return (
      signals.daysSinceLastActivity >= 3 ||
      signals.missedTasksStreak >= 5 ||
      (signals.appOpenWithoutAction >= 3 && signals.previousAbandonPatterns)
    );
  }

  async checkUsersForRescue(): Promise<void> {
    try {
      const threeDaysAgo = new Date();
      threeDaysAgo.setDate(threeDaysAgo.getDate() - 3);

      // Find users with no completed tasks in last 3 days
      const inactiveUsers = await prisma.user.findMany({
        where: {
          dreams: {
            some: {
              status: 'active',
              goals: {
                some: {
                  tasks: {
                    some: {
                      status: 'pending',
                    },
                  },
                },
              },
            },
          },
        },
        include: {
          dreams: {
            where: { status: 'active' },
            include: {
              goals: {
                include: {
                  tasks: {
                    where: {
                      status: { in: ['completed', 'skipped'] },
                      completedAt: { gte: threeDaysAgo },
                    },
                    take: 1,
                  },
                },
              },
            },
          },
        },
      });

      for (const user of inactiveUsers) {
        const hasRecentActivity = user.dreams.some((dream) =>
          dream.goals.some((goal) => goal.tasks.length > 0)
        );

        if (!hasRecentActivity) {
          await this.triggerRescueMode(user.id);
        }
      }

      logger.info('Rescue mode check completed:', {
        totalUsers: inactiveUsers.length,
        triggered: inactiveUsers.filter(
          (u) =>
            !u.dreams.some((d) => d.goals.some((g) => g.tasks.length > 0))
        ).length,
      });
    } catch (error) {
      logger.error('Failed to check users for rescue:', { error });
    }
  }

  async triggerRescueMode(userId: string): Promise<void> {
    try {
      // Send empathetic notification
      await notificationService.sendNotification(userId, {
        title: 'On est là pour toi 💜',
        body: "On a remarqué que tu n'as pas coché de tâches ces derniers jours. Tout va bien ?",
        type: 'rescue_mode',
        data: {
          action: 'open_questionnaire',
        },
      });

      logger.info('Rescue mode triggered:', { userId });
    } catch (error) {
      logger.error('Failed to trigger rescue mode:', { error, userId });
    }
  }

  async handleRescueResponse(
    userId: string,
    response: 'too_busy' | 'lost_motivation' | 'unclear_steps' | 'other',
    otherReason?: string
  ): Promise<string> {
    try {
      // Get user's active dreams
      const dreams = await prisma.dream.findMany({
        where: { userId, status: 'active' },
        include: {
          goals: {
            include: { tasks: true },
            take: 1,
          },
        },
        take: 1,
      });

      if (dreams.length === 0) {
        return "Pas de problème ! Prends ton temps. On est là quand tu es prêt.";
      }

      const dream = dreams[0];

      // Generate AI response based on the reason
      let adaptedMessage: string;

      switch (response) {
        case 'too_busy':
          adaptedMessage = await this.generateBusyResponse(dream.title);
          // Automatically adjust schedule - reduce task frequency
          await this.adjustScheduleForBusy(userId, dream.id);
          break;

        case 'lost_motivation':
          adaptedMessage = await this.generateMotivationResponse(dream.title);
          break;

        case 'unclear_steps':
          adaptedMessage = await this.generateClarityResponse(dream.title);
          // Offer to regenerate plan with simpler steps
          await this.simplifyPlan(dream.id);
          break;

        case 'other':
          adaptedMessage = `Je comprends. ${otherReason || 'Chaque parcours est unique.'}

L'important c'est de ne pas abandonner complètement. Que dirais-tu de faire juste UNE petite chose aujourd'hui ? Même 2 minutes, c'est déjà une victoire.`;
          break;

        default:
          adaptedMessage = "Merci d'avoir partagé. On va trouver une solution ensemble.";
      }

      return adaptedMessage;
    } catch (error) {
      logger.error('Failed to handle rescue response:', { error, userId, response });
      return "Merci d'avoir partagé. Continue à ton rythme, on est là pour toi.";
    }
  }

  private async generateBusyResponse(dreamTitle: string): Promise<string> {
    return `Je comprends, la vie est chargée ! Pour "${dreamTitle}", que dirais-tu de:

1. Réduire à 10 minutes par jour seulement
2. Choisir 1 jour de la semaine où tu as plus de temps
3. Transformer les trajets/pauses en mini-sessions

J'ai ajusté ton calendrier. Qu'en penses-tu ?`;
  }

  private async generateMotivationResponse(dreamTitle: string): Promise<string> {
    return `C'est normal de perdre de la motivation parfois. Rappelle-toi pourquoi "${dreamTitle}" est important pour toi.

Voici ce qui aide :
- Visualise le résultat final 5 minutes
- Partage ton objectif avec quelqu'un
- Commence juste 2 minutes (c'est tout !)

Tu veux essayer ?`;
  }

  private async generateClarityResponse(dreamTitle: string): Promise<string> {
    return `Pas de souci ! Parfois les étapes ne sont pas assez claires. Pour "${dreamTitle}", j'ai simplifié le plan:

Au lieu de grandes tâches vagues, tu as maintenant des actions précises et courtes.

Jette un œil et dis-moi si c'est plus clair !`;
  }

  private async adjustScheduleForBusy(userId: string, dreamId: string): Promise<void> {
    // Reschedule tasks to be less frequent
    const tasks = await prisma.task.findMany({
      where: {
        goal: { dreamId },
        status: 'pending',
        scheduledDate: { gte: new Date() },
      },
      orderBy: { scheduledDate: 'asc' },
    });

    // Space out tasks - one every 3 days instead of daily
    for (let i = 0; i < tasks.length; i++) {
      const newDate = new Date();
      newDate.setDate(newDate.getDate() + i * 3);

      await prisma.task.update({
        where: { id: tasks[i].id },
        data: {
          scheduledDate: newDate,
          estimatedMinutes: Math.min(tasks[i].estimatedMinutes || 30, 10), // Max 10 min
        },
      });
    }

    logger.info('Schedule adjusted for busy user:', { userId, dreamId, tasksCount: tasks.length });
  }

  private async simplifyPlan(dreamId: string): Promise<void> {
    // Break down existing tasks into smaller, clearer steps
    const goals = await prisma.goal.findMany({
      where: { dreamId },
      include: { tasks: { where: { status: 'pending' } } },
    });

    for (const goal of goals) {
      for (const task of goal.tasks) {
        // Make task titles more actionable
        if (task.title.length > 50) {
          await prisma.task.update({
            where: { id: task.id },
            data: {
              title: task.title.substring(0, 50) + '...',
              description: `Action précise: ${task.title}\n\n${task.description || ''}`,
              estimatedMinutes: Math.min(task.estimatedMinutes || 30, 15),
            },
          });
        }
      }
    }

    logger.info('Plan simplified:', { dreamId });
  }
}

export const rescueModeService = new RescueModeService();
