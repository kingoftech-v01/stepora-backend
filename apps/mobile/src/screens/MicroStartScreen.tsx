import React, { useState, useEffect } from 'react';
import { View, StyleSheet, Animated } from 'react-native';
import { Text, Button, Card, ProgressBar } from 'react-native-paper';
import { SafeAreaView } from 'react-native-safe-area-context';
import { theme } from '../theme';
import { api } from '../services/api';

interface MicroStartScreenProps {
  route: {
    params: {
      dreamId: string;
      microTask: {
        action: string;
        duration: string;
        why: string;
      };
    };
  };
  navigation: any;
}

export function MicroStartScreen({ route, navigation }: MicroStartScreenProps) {
  const { dreamId, microTask } = route.params;
  const [timeLeft, setTimeLeft] = useState(120); // 2 minutes
  const [isRunning, setIsRunning] = useState(false);
  const [isCompleted, setIsCompleted] = useState(false);
  const [scaleAnim] = useState(new Animated.Value(1));

  const durationInSeconds = microTask.duration === '30s' ? 30 : microTask.duration === '1min' ? 60 : 120;

  useEffect(() => {
    let interval: NodeJS.Timeout;

    if (isRunning && timeLeft > 0) {
      interval = setInterval(() => {
        setTimeLeft((prev) => prev - 1);
      }, 1000);
    } else if (timeLeft === 0 && isRunning) {
      handleComplete();
    }

    return () => clearInterval(interval);
  }, [isRunning, timeLeft]);

  const handleStart = () => {
    setIsRunning(true);
    setTimeLeft(durationInSeconds);
  };

  const handleComplete = async () => {
    setIsCompleted(true);
    setIsRunning(false);

    // Celebration animation
    Animated.sequence([
      Animated.timing(scaleAnim, {
        toValue: 1.2,
        duration: 200,
        useNativeDriver: true,
      }),
      Animated.timing(scaleAnim, {
        toValue: 1,
        duration: 200,
        useNativeDriver: true,
      }),
    ]).start();

    try {
      await api.dreams.create({ dreamId, action: 'microstart_complete' });
    } catch (error) {
      console.error('Failed to save micro-start completion:', error);
    }
  };

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  const progress = 1 - timeLeft / durationInSeconds;

  if (isCompleted) {
    return (
      <SafeAreaView style={styles.container}>
        <View style={styles.content}>
          <Animated.View style={[styles.celebrationContainer, { transform: [{ scale: scaleAnim }] }]}>
            <Text variant="displayMedium" style={styles.celebrationEmoji}>
              🎉
            </Text>
            <Text variant="headlineLarge" style={styles.celebrationTitle}>
              Bravo !
            </Text>
            <Text variant="titleMedium" style={styles.celebrationText}>
              Premier pas accompli ! Le plus dur est fait.
            </Text>
            <Text variant="bodyMedium" style={styles.xpText}>
              +5 XP
            </Text>
          </Animated.View>

          <Button mode="contained" onPress={() => navigation.goBack()} style={styles.button}>
            Continuer
          </Button>
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.content}>
        <Text variant="headlineMedium" style={styles.title}>
          2-Minute Start
        </Text>

        <Card style={styles.card}>
          <Card.Content>
            <Text variant="titleLarge" style={styles.taskTitle}>
              {microTask.action}
            </Text>

            <View style={styles.durationBadge}>
              <Text variant="bodyMedium" style={styles.durationText}>
                ⏱️ {microTask.duration}
              </Text>
            </View>

            <Text variant="bodyMedium" style={styles.why}>
              Pourquoi: {microTask.why}
            </Text>
          </Card.Content>
        </Card>

        {isRunning ? (
          <View style={styles.timerContainer}>
            <Text variant="displayLarge" style={styles.timer}>
              {formatTime(timeLeft)}
            </Text>
            <ProgressBar progress={progress} color={theme.colors.primary} style={styles.progressBar} />
            <Button mode="outlined" onPress={handleComplete} style={styles.button}>
              J'ai terminé
            </Button>
          </View>
        ) : (
          <View style={styles.startContainer}>
            <Text variant="bodyLarge" style={styles.instruction}>
              Prêt à commencer ? Juste {microTask.duration}, c'est tout !
            </Text>
            <Button mode="contained" onPress={handleStart} style={styles.button}>
              Lancer le timer
            </Button>
            <Button mode="text" onPress={() => navigation.goBack()}>
              Plus tard
            </Button>
          </View>
        )}
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#f5f5f5',
  },
  content: {
    flex: 1,
    padding: 24,
    justifyContent: 'center',
  },
  title: {
    textAlign: 'center',
    marginBottom: 24,
    color: theme.colors.primary,
  },
  card: {
    marginBottom: 32,
    elevation: 4,
  },
  taskTitle: {
    marginBottom: 16,
    color: '#333',
  },
  durationBadge: {
    alignSelf: 'flex-start',
    backgroundColor: theme.colors.primaryContainer,
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 16,
    marginBottom: 16,
  },
  durationText: {
    color: theme.colors.primary,
    fontWeight: 'bold',
  },
  why: {
    color: '#666',
    fontStyle: 'italic',
  },
  timerContainer: {
    alignItems: 'center',
  },
  timer: {
    fontSize: 72,
    fontWeight: 'bold',
    color: theme.colors.primary,
    marginBottom: 16,
  },
  progressBar: {
    width: '100%',
    height: 8,
    borderRadius: 4,
    marginBottom: 32,
  },
  startContainer: {
    alignItems: 'center',
  },
  instruction: {
    textAlign: 'center',
    marginBottom: 24,
    color: '#666',
  },
  button: {
    marginTop: 16,
    minWidth: 200,
  },
  celebrationContainer: {
    alignItems: 'center',
    marginBottom: 48,
  },
  celebrationEmoji: {
    fontSize: 80,
    marginBottom: 16,
  },
  celebrationTitle: {
    fontWeight: 'bold',
    color: theme.colors.primary,
    marginBottom: 8,
  },
  celebrationText: {
    textAlign: 'center',
    color: '#666',
    marginBottom: 16,
  },
  xpText: {
    color: theme.colors.primary,
    fontWeight: 'bold',
    fontSize: 18,
  },
});
