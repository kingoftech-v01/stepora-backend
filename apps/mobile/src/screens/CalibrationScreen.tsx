/**
 * CalibrationScreen - AI-powered dream calibration questionnaire.
 * Presents a series of questions (7-15) to deeply understand the user's dream
 * before generating a personalized plan.
 *
 * Flow:
 * 1. Start calibration -> receives initial 7 questions
 * 2. User answers one question at a time with animated transitions
 * 3. After answering all, submit to backend
 * 4. Backend may return more questions or mark calibration complete
 * 5. On completion, auto-navigates back to DreamDetail
 */

import React, { useState, useCallback, useEffect, useRef } from 'react';
import {
  View,
  StyleSheet,
  ScrollView,
  Alert,
  KeyboardAvoidingView,
  Platform,
  Animated,
  Dimensions,
} from 'react-native';
import {
  Text,
  TextInput,
  Button,
  Surface,
  ProgressBar,
  IconButton,
  ActivityIndicator,
  useTheme,
} from 'react-native-paper';
import { SafeAreaView } from 'react-native-safe-area-context';
import Icon from 'react-native-vector-icons/MaterialCommunityIcons';
import { useMutation } from '@tanstack/react-query';
import { useNavigation, useRoute, RouteProp } from '@react-navigation/native';
import { api } from '../services/api';
import { AppTheme, spacing, borderRadius, colors, shadows, typography } from '../theme';
import { HomeStackParamList } from '../navigation/types';

type CalibrationRouteProp = RouteProp<HomeStackParamList, 'Calibration'>;

interface CalibrationQuestion {
  id: string;
  question: string;
  answer: string;
  question_number: number;
  category: string;
}

interface CalibrationResult {
  status: 'in_progress' | 'completed';
  questions?: CalibrationQuestion[];
  total_questions: number;
  answered: number;
  confidence_score?: number;
  missing_areas?: string[];
  message?: string;
}

const CATEGORY_ICONS: Record<string, string> = {
  experience: 'school',
  timeline: 'clock-outline',
  resources: 'toolbox',
  motivation: 'heart',
  constraints: 'alert-circle-outline',
  specifics: 'target',
  lifestyle: 'home-heart',
  preferences: 'tune-variant',
};

const CATEGORY_COLORS: Record<string, string> = {
  experience: colors.info,
  timeline: colors.primary[600],
  resources: colors.success,
  motivation: colors.error,
  constraints: colors.warning,
  specifics: colors.primary[400],
  lifestyle: colors.secondary[500],
  preferences: colors.secondary[400],
};

const { width: SCREEN_WIDTH } = Dimensions.get('window');

export const CalibrationScreen: React.FC = () => {
  const theme = useTheme() as AppTheme;
  const navigation = useNavigation<any>();
  const route = useRoute<CalibrationRouteProp>();
  const { dreamId, dreamTitle } = route.params;

  const [questions, setQuestions] = useState<CalibrationQuestion[]>([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [currentAnswer, setCurrentAnswer] = useState('');
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [totalQuestions, setTotalQuestions] = useState(7);
  const [isComplete, setIsComplete] = useState(false);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const slideAnim = useRef(new Animated.Value(0)).current;
  const fadeAnim = useRef(new Animated.Value(1)).current;

  // Start calibration
  const startMutation = useMutation({
    mutationFn: () => api.dreams.startCalibration(dreamId),
    onSuccess: (data: any) => {
      const result = data as CalibrationResult;
      setQuestions(result.questions || []);
      setTotalQuestions(result.total_questions);
      setCurrentIndex(0);
    },
    onError: (err: any) => {
      Alert.alert('Error', err.message || 'Failed to start calibration');
      navigation.goBack();
    },
  });

  // Submit answers
  const answerMutation = useMutation({
    mutationFn: (answersPayload: Array<{ question_id: string; answer: string }>) =>
      api.dreams.answerCalibration(dreamId, answersPayload),
    onSuccess: (data: any) => {
      const result = data as CalibrationResult;
      if (result.status === 'completed') {
        setIsComplete(true);
        setIsLoadingMore(false);
        // Auto-navigate back after delay
        setTimeout(() => {
          navigation.goBack();
        }, 2000);
      } else {
        // More questions arrived
        const newQuestions = result.questions || [];
        setQuestions((prev) => [...prev, ...newQuestions]);
        setTotalQuestions(result.total_questions);
        setCurrentIndex(Object.keys(answers).length);
        setIsLoadingMore(false);
      }
    },
    onError: (err: any) => {
      setIsLoadingMore(false);
      Alert.alert('Error', err.message || 'Failed to submit answers');
    },
  });

  // Skip calibration
  const skipMutation = useMutation({
    mutationFn: () => api.dreams.skipCalibration(dreamId),
    onSuccess: () => {
      navigation.goBack();
    },
  });

  useEffect(() => {
    startMutation.mutate();
  }, []);

  const animateTransition = useCallback(
    (direction: 'next' | 'back') => {
      const toValue = direction === 'next' ? -SCREEN_WIDTH : SCREEN_WIDTH;

      Animated.parallel([
        Animated.timing(slideAnim, {
          toValue,
          duration: 200,
          useNativeDriver: true,
        }),
        Animated.timing(fadeAnim, {
          toValue: 0,
          duration: 150,
          useNativeDriver: true,
        }),
      ]).start(() => {
        slideAnim.setValue(direction === 'next' ? SCREEN_WIDTH : -SCREEN_WIDTH);

        Animated.parallel([
          Animated.timing(slideAnim, {
            toValue: 0,
            duration: 250,
            useNativeDriver: true,
          }),
          Animated.timing(fadeAnim, {
            toValue: 1,
            duration: 200,
            useNativeDriver: true,
          }),
        ]).start();
      });
    },
    [slideAnim, fadeAnim],
  );

  const handleNext = useCallback(() => {
    if (!currentAnswer.trim()) return;

    const currentQuestion = questions[currentIndex];
    const updatedAnswers = {
      ...answers,
      [currentQuestion.id]: currentAnswer.trim(),
    };
    setAnswers(updatedAnswers);

    if (currentIndex < questions.length - 1) {
      // Go to next existing question
      animateTransition('next');
      setTimeout(() => {
        setCurrentIndex((prev) => prev + 1);
        setCurrentAnswer(answers[questions[currentIndex + 1]?.id] || '');
      }, 200);
    } else {
      // Submit all unanswered questions to backend
      setIsLoadingMore(true);
      const answersPayload = Object.entries(updatedAnswers).map(([qId, ans]) => ({
        question_id: qId,
        answer: ans,
      }));
      answerMutation.mutate(answersPayload);
    }
  }, [currentAnswer, currentIndex, questions, answers, animateTransition, answerMutation]);

  const handleBack = useCallback(() => {
    if (currentIndex > 0) {
      animateTransition('back');
      setTimeout(() => {
        const prevQuestion = questions[currentIndex - 1];
        setCurrentIndex((prev) => prev - 1);
        setCurrentAnswer(answers[prevQuestion.id] || '');
      }, 200);
    }
  }, [currentIndex, questions, answers, animateTransition]);

  const handleSkip = useCallback(() => {
    Alert.alert(
      'Skip Calibration?',
      'Skipping calibration means the AI will generate a plan with limited information. The plan may be less personalized.\n\nAre you sure?',
      [
        { text: 'Continue Calibrating', style: 'cancel' },
        {
          text: 'Skip',
          style: 'destructive',
          onPress: () => skipMutation.mutate(),
        },
      ],
    );
  }, [skipMutation]);

  // Loading state
  if (startMutation.isPending) {
    return (
      <SafeAreaView style={[styles.container, { backgroundColor: theme.colors.background }]}>
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color={theme.colors.primary} />
          <Text
            style={[
              typography.body,
              { color: theme.custom.colors.textSecondary, marginTop: spacing.md },
            ]}
          >
            Preparing your calibration questions...
          </Text>
        </View>
      </SafeAreaView>
    );
  }

  // Complete state
  if (isComplete) {
    return (
      <SafeAreaView style={[styles.container, { backgroundColor: theme.colors.background }]}>
        <View style={styles.completeContainer}>
          <View style={[styles.completeIcon, { backgroundColor: colors.success + '20' }]}>
            <Icon name="check-circle" size={64} color={colors.success} />
          </View>
          <Text
            style={[
              typography.h2,
              {
                color: theme.custom.colors.textPrimary,
                marginTop: spacing.lg,
                textAlign: 'center',
              },
            ]}
          >
            Calibration Complete!
          </Text>
          <Text
            style={[
              typography.body,
              {
                color: theme.custom.colors.textSecondary,
                marginTop: spacing.sm,
                textAlign: 'center',
                paddingHorizontal: spacing.xl,
              },
            ]}
          >
            The AI now has a deep understanding of your dream. Your personalized plan will be much
            more accurate.
          </Text>
        </View>
      </SafeAreaView>
    );
  }

  // Loading more questions
  if (isLoadingMore) {
    return (
      <SafeAreaView style={[styles.container, { backgroundColor: theme.colors.background }]}>
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color={theme.colors.primary} />
          <Text
            style={[
              typography.body,
              {
                color: theme.custom.colors.textSecondary,
                marginTop: spacing.md,
                textAlign: 'center',
                paddingHorizontal: spacing.xl,
              },
            ]}
          >
            Analyzing your answers...{'\n'}Checking if we need more details.
          </Text>
        </View>
      </SafeAreaView>
    );
  }

  const currentQuestion = questions[currentIndex];
  if (!currentQuestion) return null;

  const progress = (currentIndex + 1) / totalQuestions;
  const answeredCount = Object.keys(answers).length;
  const categoryIcon = CATEGORY_ICONS[currentQuestion.category] || 'help-circle-outline';
  const categoryColor = CATEGORY_COLORS[currentQuestion.category] || colors.primary[500];

  return (
    <SafeAreaView
      style={[styles.container, { backgroundColor: theme.colors.background }]}
      edges={['top']}
    >
      {/* Header */}
      <View
        style={[
          styles.header,
          {
            backgroundColor: theme.colors.surface,
            borderBottomColor: theme.custom.colors.border,
          },
        ]}
      >
        <IconButton
          icon="arrow-left"
          size={24}
          onPress={() => {
            Alert.alert(
              'Leave Calibration?',
              'Your progress will be saved. You can continue later.',
              [
                { text: 'Stay', style: 'cancel' },
                { text: 'Leave', onPress: () => navigation.goBack() },
              ],
            );
          }}
          style={styles.headerBackButton}
        />
        <View style={styles.headerTitleContainer}>
          <Text
            style={[typography.bodySmall, { color: theme.custom.colors.textSecondary }]}
            numberOfLines={1}
          >
            {dreamTitle}
          </Text>
          <Text style={[typography.h4, { color: theme.custom.colors.textPrimary }]}>
            Calibration
          </Text>
        </View>
        <Button
          mode="text"
          onPress={handleSkip}
          labelStyle={[typography.caption, { color: theme.custom.colors.textMuted }]}
          compact
        >
          Skip
        </Button>
      </View>

      {/* Progress */}
      <View style={styles.progressContainer}>
        <ProgressBar
          progress={progress}
          color={theme.colors.primary}
          style={[styles.progressBar, { backgroundColor: theme.custom.colors.border }]}
        />
        <Text
          style={[
            typography.caption,
            {
              color: theme.custom.colors.textMuted,
              marginTop: spacing.xs,
              textAlign: 'center',
            },
          ]}
        >
          Question {currentIndex + 1} of {totalQuestions}
        </Text>
      </View>

      <KeyboardAvoidingView
        style={styles.keyboardView}
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
        keyboardVerticalOffset={100}
      >
        <ScrollView
          style={styles.scrollView}
          contentContainerStyle={styles.scrollContent}
          keyboardShouldPersistTaps="handled"
        >
          {/* Question Card */}
          <Animated.View
            style={[{ transform: [{ translateX: slideAnim }], opacity: fadeAnim }]}
          >
            <Surface style={[styles.questionCard, shadows.md]} elevation={2}>
              {/* Category badge */}
              <View style={[styles.categoryBadge, { backgroundColor: categoryColor + '15' }]}>
                <Icon name={categoryIcon} size={16} color={categoryColor} />
                <Text
                  style={[
                    typography.caption,
                    {
                      color: categoryColor,
                      marginLeft: spacing.xs,
                      textTransform: 'capitalize',
                    },
                  ]}
                >
                  {currentQuestion.category || 'General'}
                </Text>
              </View>

              {/* Question */}
              <Text
                style={[
                  typography.h3,
                  {
                    color: theme.custom.colors.textPrimary,
                    marginTop: spacing.md,
                    lineHeight: 28,
                  },
                ]}
              >
                {currentQuestion.question}
              </Text>
            </Surface>

            {/* Answer Input */}
            <Surface style={[styles.answerCard, shadows.sm]} elevation={1}>
              <TextInput
                mode="outlined"
                placeholder="Type your answer here..."
                value={currentAnswer}
                onChangeText={setCurrentAnswer}
                multiline
                numberOfLines={4}
                style={styles.answerInput}
                outlineColor={theme.custom.colors.border}
                activeOutlineColor={theme.colors.primary}
                placeholderTextColor={theme.custom.colors.textMuted}
              />
              <Text
                style={[
                  typography.caption,
                  { color: theme.custom.colors.textMuted, marginTop: spacing.xs },
                ]}
              >
                Be as specific as possible - the more detail, the better your plan.
              </Text>
            </Surface>
          </Animated.View>
        </ScrollView>

        {/* Bottom Navigation */}
        <View
          style={[
            styles.bottomNav,
            {
              backgroundColor: theme.colors.surface,
              borderTopColor: theme.custom.colors.border,
            },
          ]}
        >
          <Button
            mode="outlined"
            onPress={handleBack}
            disabled={currentIndex === 0}
            style={[styles.navButton, currentIndex === 0 && styles.navButtonDisabled]}
            icon="arrow-left"
          >
            Back
          </Button>

          <View style={styles.navCenter}>
            <Text style={[typography.caption, { color: theme.custom.colors.textMuted }]}>
              {answeredCount} answered
            </Text>
          </View>

          <Button
            mode="contained"
            onPress={handleNext}
            disabled={!currentAnswer.trim()}
            style={[styles.navButton, !currentAnswer.trim() && styles.navButtonDisabled]}
            icon={currentIndex === questions.length - 1 ? 'check' : 'arrow-right'}
            contentStyle={{ flexDirection: 'row-reverse' }}
          >
            {currentIndex === questions.length - 1 ? 'Submit' : 'Next'}
          </Button>
        </View>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: spacing.xl,
  },
  completeContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: spacing.xl,
  },
  completeIcon: {
    width: 120,
    height: 120,
    borderRadius: 60,
    justifyContent: 'center',
    alignItems: 'center',
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingRight: spacing.xs,
    paddingVertical: spacing.xs,
    borderBottomWidth: 1,
  },
  headerBackButton: {
    marginLeft: spacing.xs,
  },
  headerTitleContainer: {
    flex: 1,
  },
  progressContainer: {
    paddingHorizontal: spacing.md,
    paddingTop: spacing.md,
    paddingBottom: spacing.sm,
  },
  progressBar: {
    height: 6,
    borderRadius: 3,
  },
  keyboardView: {
    flex: 1,
  },
  scrollView: {
    flex: 1,
  },
  scrollContent: {
    padding: spacing.md,
  },
  questionCard: {
    borderRadius: borderRadius.lg,
    padding: spacing.lg,
    marginBottom: spacing.md,
  },
  categoryBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    alignSelf: 'flex-start',
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.xs,
    borderRadius: borderRadius.full,
  },
  answerCard: {
    borderRadius: borderRadius.lg,
    padding: spacing.md,
    marginBottom: spacing.md,
  },
  answerInput: {
    backgroundColor: 'transparent',
    minHeight: 100,
  },
  bottomNav: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderTopWidth: 1,
  },
  navButton: {
    minWidth: 100,
  },
  navButtonDisabled: {
    opacity: 0.5,
  },
  navCenter: {
    flex: 1,
    alignItems: 'center',
  },
});
