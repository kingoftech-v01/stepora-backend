import OpenAI from 'openai';
import { Message, User, Dream } from '@prisma/client';

const openai = new OpenAI({
  apiKey: process.env.OPENAI_API_KEY,
});

// System prompts
const SYSTEM_PROMPTS = {
  dreamCreation: `Tu es DreamPlanner, un assistant personnel bienveillant spécialisé dans l'aide à la réalisation des rêves et objectifs.

TON RÔLE:
1. Écouter attentivement les rêves et objectifs de l'utilisateur
2. Poser des questions pertinentes pour bien comprendre le contexte
3. Être encourageant tout en restant réaliste
4. Extraire les informations clés: objectif, date cible, ressources disponibles

STYLE DE COMMUNICATION:
- Chaleureux et motivant
- Questions ouvertes pour approfondir
- Reformuler pour confirmer la compréhension
- Éviter le jargon technique

À CHAQUE RÉPONSE:
- Pose maximum 2-3 questions à la fois
- Montre que tu as bien compris ce qui a été dit
- Guide vers la clarification de l'objectif`,

  planning: `Tu es DreamPlanner, un expert en planification et décomposition d'objectifs.

TON RÔLE:
1. Analyser l'objectif de l'utilisateur
2. Décomposer en étapes réalisables et mesurables
3. Créer un planning réaliste tenant compte des contraintes
4. Anticiper les obstacles potentiels

RÈGLES DE PLANIFICATION:
- Étapes de 1-2 semaines maximum
- Tâches quotidiennes de 15-60 minutes
- Intégrer des jours de repos
- Progression graduelle en difficulté
- Tenir compte du temps de travail de l'utilisateur

FORMAT DE SORTIE (JSON):
{
  "analysis": "Brève analyse de l'objectif",
  "feasibility": "high|medium|low",
  "estimatedDuration": "X semaines/mois",
  "weeklyTimeRequired": "Xh",
  "goals": [
    {
      "title": "Titre de l'étape",
      "description": "Description détaillée",
      "durationWeeks": 2,
      "tasks": [
        {
          "title": "Tâche spécifique",
          "durationMins": 30,
          "frequency": "daily|weekly|once",
          "days": [1,2,3,4,5]
        }
      ]
    }
  ],
  "tips": ["Conseil pratique 1", "Conseil pratique 2"],
  "potentialObstacles": ["Obstacle 1 avec solution", "Obstacle 2 avec solution"]
}`,

  motivation: `Tu génères des messages de motivation courts, personnalisés et authentiques.
- Maximum 100 caractères
- Ton encourageant mais pas excessif
- Référence à la progression actuelle
- Adapté à l'heure de la journée si pertinent`,

  checkIn: `Tu es DreamPlanner et tu fais un check-in bienveillant avec l'utilisateur.
- Demande comment ça se passe sans être intrusif
- Propose de l'aide si des difficultés sont mentionnées
- Célèbre les petites victoires
- Propose des ajustements si nécessaire`,
};

interface UserContext {
  userName: string;
  timezone: string;
  workSchedule?: {
    workDays: number[];
    startTime: string;
    endTime: string;
  };
  availableHoursPerWeek?: number;
}

interface PlanningResult {
  analysis: string;
  feasibility: 'high' | 'medium' | 'low';
  estimatedDuration: string;
  weeklyTimeRequired: string;
  goals: GeneratedGoal[];
  tips: string[];
  potentialObstacles: string[];
}

interface GeneratedGoal {
  title: string;
  description: string;
  durationWeeks: number;
  tasks: GeneratedTask[];
}

interface GeneratedTask {
  title: string;
  durationMins: number;
  frequency: 'daily' | 'weekly' | 'once';
  days?: number[];
}

export class AIService {
  /**
   * Chat conversation for dream exploration
   */
  async chat(
    conversationHistory: Pick<Message, 'role' | 'content'>[],
    userMessage: string,
    context: UserContext,
    type: 'dreamCreation' | 'checkIn' = 'dreamCreation'
  ): Promise<{ content: string; tokensUsed: number }> {
    const systemPrompt = this.buildSystemPrompt(
      SYSTEM_PROMPTS[type],
      context
    );

    const messages: OpenAI.Chat.ChatCompletionMessageParam[] = [
      { role: 'system', content: systemPrompt },
      ...conversationHistory.map((m) => ({
        role: m.role as 'user' | 'assistant',
        content: m.content,
      })),
      { role: 'user', content: userMessage },
    ];

    const response = await openai.chat.completions.create({
      model: 'gpt-4-turbo-preview',
      messages,
      temperature: 0.7,
      max_tokens: 1000,
    });

    return {
      content: response.choices[0].message.content || '',
      tokensUsed: response.usage?.total_tokens || 0,
    };
  }

  /**
   * Stream chat response for real-time display
   */
  async *chatStream(
    conversationHistory: Pick<Message, 'role' | 'content'>[],
    userMessage: string,
    context: UserContext
  ): AsyncGenerator<string> {
    const systemPrompt = this.buildSystemPrompt(
      SYSTEM_PROMPTS.dreamCreation,
      context
    );

    const messages: OpenAI.Chat.ChatCompletionMessageParam[] = [
      { role: 'system', content: systemPrompt },
      ...conversationHistory.map((m) => ({
        role: m.role as 'user' | 'assistant',
        content: m.content,
      })),
      { role: 'user', content: userMessage },
    ];

    const stream = await openai.chat.completions.create({
      model: 'gpt-4-turbo-preview',
      messages,
      temperature: 0.7,
      max_tokens: 1000,
      stream: true,
    });

    for await (const chunk of stream) {
      const content = chunk.choices[0]?.delta?.content;
      if (content) {
        yield content;
      }
    }
  }

  /**
   * Generate a complete plan for a dream
   */
  async generatePlan(
    dream: Pick<Dream, 'title' | 'description' | 'targetDate' | 'category'>,
    context: UserContext
  ): Promise<PlanningResult> {
    const prompt = `
Génère un plan détaillé pour atteindre cet objectif:

RÊVE/OBJECTIF: ${dream.title}
DESCRIPTION: ${dream.description}
DATE CIBLE: ${dream.targetDate?.toISOString() || 'Non spécifiée - propose une durée raisonnable'}
CATÉGORIE: ${dream.category || 'Non spécifiée'}

CONTEXTE UTILISATEUR:
- Nom: ${context.userName}
- Fuseau horaire: ${context.timezone}
- Horaires de travail: ${
      context.workSchedule
        ? `${context.workSchedule.workDays.map((d) => ['Dim', 'Lun', 'Mar', 'Mer', 'Jeu', 'Ven', 'Sam'][d]).join(', ')} de ${context.workSchedule.startTime} à ${context.workSchedule.endTime}`
        : 'Non spécifiés'
    }
- Heures disponibles par semaine: ${context.availableHoursPerWeek || 'À déterminer'}h

IMPORTANT:
- Crée des étapes progressives et réalisables
- Tiens compte du temps de travail pour planifier les tâches
- Inclus des jours de repos
- Sois réaliste sur les durées

Réponds UNIQUEMENT avec le JSON du plan, sans texte avant ou après.
`;

    const response = await openai.chat.completions.create({
      model: 'gpt-4-turbo-preview',
      messages: [
        { role: 'system', content: SYSTEM_PROMPTS.planning },
        { role: 'user', content: prompt },
      ],
      temperature: 0.5,
      max_tokens: 3000,
      response_format: { type: 'json_object' },
    });

    const content = response.choices[0].message.content;
    if (!content) {
      throw new Error('No response from AI');
    }

    return JSON.parse(content) as PlanningResult;
  }

  /**
   * Generate a motivational message
   */
  async generateMotivationalMessage(
    progress: number,
    streak: number,
    goalTitle: string,
    userName: string
  ): Promise<string> {
    const response = await openai.chat.completions.create({
      model: 'gpt-3.5-turbo',
      messages: [
        { role: 'system', content: SYSTEM_PROMPTS.motivation },
        {
          role: 'user',
          content: `Utilisateur: ${userName}
Objectif: "${goalTitle}"
Progression: ${progress}%
Série actuelle: ${streak} jours consécutifs
Génère un message de motivation court et personnalisé.`,
        },
      ],
      temperature: 0.8,
      max_tokens: 60,
    });

    return response.choices[0].message.content || 'Continue comme ça ! 💪';
  }

  /**
   * Analyze a dream description to extract key information
   */
  async analyzeDream(description: string): Promise<{
    suggestedTitle: string;
    suggestedCategory: string;
    estimatedDuration: string;
    clarifyingQuestions: string[];
  }> {
    const response = await openai.chat.completions.create({
      model: 'gpt-3.5-turbo',
      messages: [
        {
          role: 'system',
          content: `Analyse cette description d'objectif et extrait les informations clés.
Réponds en JSON avec ce format:
{
  "suggestedTitle": "Titre court et clair",
  "suggestedCategory": "career|health|education|personal|finance|travel|creativity|wellness",
  "estimatedDuration": "X semaines/mois",
  "clarifyingQuestions": ["Question 1", "Question 2"]
}`,
        },
        { role: 'user', content: description },
      ],
      temperature: 0.3,
      response_format: { type: 'json_object' },
    });

    return JSON.parse(response.choices[0].message.content || '{}');
  }

  /**
   * Build system prompt with user context
   */
  private buildSystemPrompt(basePrompt: string, context: UserContext): string {
    return `${basePrompt}

INFORMATIONS SUR L'UTILISATEUR:
- Nom: ${context.userName}
- Fuseau horaire: ${context.timezone}
${
  context.workSchedule
    ? `- Travaille: ${context.workSchedule.workDays.map((d) => ['Dimanche', 'Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi'][d]).join(', ')}
- Horaires: ${context.workSchedule.startTime} - ${context.workSchedule.endTime}`
    : '- Horaires de travail: Non spécifiés'
}

Adapte tes réponses à ce contexte.`;
  }
}

export const aiService = new AIService();
