import { aiService } from './ai.service';
import { prisma } from '../utils/prisma';
import { logger } from '../config/logger';
import { gamificationService } from './gamification.service';

interface MicroStartTask {
  action: string;
  duration: '30s' | '1min' | '2min';
  why: string;
}

class MicroStartService {
  async generateMicroStart(dreamTitle: string, dreamDescription: string): Promise<MicroStartTask> {
    const prompt = `Pour cet objectif: ${dreamTitle}

Description: ${dreamDescription}

Génère UNE SEULE action qui:
1. Prend MAXIMUM 2 minutes
2. Ne nécessite aucune préparation
3. Peut être faite MAINTENANT
4. Crée un premier engagement

Réponds UNIQUEMENT avec un JSON au format:
{
  "action": "description de l'action",
  "duration": "30s" ou "1min" ou "2min",
  "why": "pourquoi cette action est importante"
}`;

    try {
      const response = await aiService.chat(
        [{ role: 'user', content: prompt }],
        'general'
      );

      // Parse JSON from response
      const jsonMatch = response.response.match(/\{[\s\S]*\}/);
      if (!jsonMatch) {
        throw new Error('Failed to parse micro-start task');
      }

      const microTask: MicroStartTask = JSON.parse(jsonMatch[0]);

      logger.info('Micro-start task generated:', { dreamTitle, microTask });

      return microTask;
    } catch (error) {
      logger.error('Failed to generate micro-start task:', { error, dreamTitle });

      // Fallback to default micro-start
      return {
        action: 'Écris une phrase décrivant pourquoi cet objectif est important pour toi',
        duration: '2min',
        why: 'Clarifier ta motivation renforce ton engagement',
      };
    }
  }

  async saveMicroStartCompletion(userId: string, dreamId: string): Promise<void> {
    // Create a micro-start completion record
    await prisma.dream.update({
      where: { id: dreamId },
      data: {
        aiAnalysis: {
          microStartCompleted: true,
          microStartCompletedAt: new Date().toISOString(),
        },
      },
    });

    // Award XP for completing micro-start (5 XP)
    try {
      await gamificationService.awardXP(
        userId,
        'micro_start_completed',
        5,
        dreamId,
        { discipline: 1 }
      );
    } catch (error) {
      logger.error('Failed to award micro-start XP:', { error, userId, dreamId });
    }

    logger.info('Micro-start completed:', { userId, dreamId });
  }
}

export const microStartService = new MicroStartService();
