import React, { useState } from 'react';
import { View, ScrollView, StyleSheet } from 'react-native';
import {
  Text,
  Card,
  Avatar,
  Button,
  ProgressBar,
  Surface,
  TextInput,
  Dialog,
  Portal,
} from 'react-native-paper';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../services/api';

export const DreamBuddyScreen = () => {
  const queryClient = useQueryClient();
  const [encourageDialogVisible, setEncourageDialogVisible] = useState(false);
  const [message, setMessage] = useState('');

  const { data: buddy, isLoading } = useQuery({
    queryKey: ['currentBuddy'],
    queryFn: async () => {
      const response = await api.get('/buddies/current');
      return response.data.buddy;
    },
  });

  const { data: progress } = useQuery({
    queryKey: ['buddyProgress', buddy?.id],
    queryFn: async () => {
      const response = await api.get(`/buddies/${buddy?.id}/progress`);
      return response.data.progress;
    },
    enabled: !!buddy?.id,
  });

  const findMatchMutation = useMutation({
    mutationFn: async () => {
      const response = await api.post('/buddies/find-match', {});
      return response.data.match;
    },
    onSuccess: (match) => {
      if (match) {
        pairMutation.mutate(match.userId);
      }
    },
  });

  const pairMutation = useMutation({
    mutationFn: async (partnerId: string) => {
      await api.post('/buddies/pair', { partnerId });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['currentBuddy'] });
    },
  });

  const encourageMutation = useMutation({
    mutationFn: async () => {
      await api.post(`/buddies/${buddy.id}/encourage`, { message });
    },
    onSuccess: () => {
      setEncourageDialogVisible(false);
      setMessage('');
    },
  });

  const endPairingMutation = useMutation({
    mutationFn: async () => {
      await api.delete(`/buddies/${buddy.id}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['currentBuddy'] });
    },
  });

  if (isLoading) {
    return (
      <View style={styles.container}>
        <Text>Chargement...</Text>
      </View>
    );
  }

  if (!buddy) {
    return (
      <View style={styles.container}>
        <ScrollView contentContainerStyle={styles.emptyState}>
          <Text variant="headlineMedium" style={styles.emptyTitle}>
            Trouve ton Dream Buddy! 🤝
          </Text>
          <Text variant="bodyLarge" style={styles.emptyDescription}>
            Un partenaire pour t'aider à rester motivé et atteindre tes objectifs ensemble.
          </Text>
          <Button
            mode="contained"
            onPress={() => findMatchMutation.mutate()}
            loading={findMatchMutation.isPending}
            style={styles.findButton}
          >
            Trouver un Buddy
          </Button>
        </ScrollView>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <ScrollView>
        {/* Buddy Header */}
        <Card style={styles.buddyCard}>
          <Card.Content>
            <View style={styles.buddyHeader}>
              <Avatar.Image size={80} source={{ uri: buddy.partner.avatar }} />
              <View style={styles.buddyInfo}>
                <Text variant="headlineSmall">{buddy.partner.username}</Text>
                <Text variant="bodyMedium" style={styles.buddyTitle}>
                  {buddy.partner.title}
                </Text>
                <View style={styles.buddyStats}>
                  <Text variant="bodySmall">Niveau {buddy.partner.currentLevel}</Text>
                  <Text variant="bodySmall"> • </Text>
                  <Text variant="bodySmall">{buddy.partner.influenceScore} Influence</Text>
                </View>
              </View>
            </View>

            <View style={styles.streakContainer}>
              <Surface style={styles.streakBadge} elevation={1}>
                <Text variant="headlineMedium">🔥 {buddy.partner.currentStreak}</Text>
                <Text variant="bodySmall">Série actuelle</Text>
              </Surface>
              <Surface style={styles.streakBadge} elevation={1}>
                <Text variant="headlineMedium">📅 {buddy.recentActivity}</Text>
                <Text variant="bodySmall">Tâches cette semaine</Text>
              </Surface>
            </View>

            <View style={styles.actionButtons}>
              <Button
                mode="contained"
                icon="hand-heart"
                onPress={() => setEncourageDialogVisible(true)}
                style={styles.actionButton}
              >
                Encourager
              </Button>
              <Button
                mode="outlined"
                icon="close"
                onPress={() => endPairingMutation.mutate()}
                style={styles.actionButton}
              >
                Terminer
              </Button>
            </View>
          </Card.Content>
        </Card>

        {/* Progress Comparison */}
        {progress && (
          <Card style={styles.progressCard}>
            <Card.Content>
              <Text variant="titleLarge" style={styles.sectionTitle}>
                Comparaison des progrès
              </Text>

              <View style={styles.progressItem}>
                <Text variant="bodyMedium" style={styles.progressLabel}>
                  Série actuelle
                </Text>
                <View style={styles.progressBars}>
                  <View style={styles.progressRow}>
                    <Text style={styles.progressName}>Toi</Text>
                    <ProgressBar
                      progress={progress.user.currentStreak / 100}
                      style={styles.progressBar}
                    />
                    <Text style={styles.progressValue}>{progress.user.currentStreak}</Text>
                  </View>
                  <View style={styles.progressRow}>
                    <Text style={styles.progressName}>{buddy.partner.username}</Text>
                    <ProgressBar
                      progress={progress.partner.currentStreak / 100}
                      style={styles.progressBar}
                    />
                    <Text style={styles.progressValue}>{progress.partner.currentStreak}</Text>
                  </View>
                </View>
              </View>

              <View style={styles.progressItem}>
                <Text variant="bodyMedium" style={styles.progressLabel}>
                  Tâches cette semaine
                </Text>
                <View style={styles.progressBars}>
                  <View style={styles.progressRow}>
                    <Text style={styles.progressName}>Toi</Text>
                    <ProgressBar
                      progress={progress.user.tasksThisWeek / 20}
                      style={styles.progressBar}
                    />
                    <Text style={styles.progressValue}>{progress.user.tasksThisWeek}</Text>
                  </View>
                  <View style={styles.progressRow}>
                    <Text style={styles.progressName}>{buddy.partner.username}</Text>
                    <ProgressBar
                      progress={progress.partner.tasksThisWeek / 20}
                      style={styles.progressBar}
                    />
                    <Text style={styles.progressValue}>{progress.partner.tasksThisWeek}</Text>
                  </View>
                </View>
              </View>

              <View style={styles.progressItem}>
                <Text variant="bodyMedium" style={styles.progressLabel}>
                  Influence Score
                </Text>
                <View style={styles.progressBars}>
                  <View style={styles.progressRow}>
                    <Text style={styles.progressName}>Toi</Text>
                    <ProgressBar
                      progress={progress.user.influenceScore / 10000}
                      style={styles.progressBar}
                    />
                    <Text style={styles.progressValue}>{progress.user.influenceScore}</Text>
                  </View>
                  <View style={styles.progressRow}>
                    <Text style={styles.progressName}>{buddy.partner.username}</Text>
                    <ProgressBar
                      progress={progress.partner.influenceScore / 10000}
                      style={styles.progressBar}
                    />
                    <Text style={styles.progressValue}>{progress.partner.influenceScore}</Text>
                  </View>
                </View>
              </View>
            </Card.Content>
          </Card>
        )}
      </ScrollView>

      {/* Encourage Dialog */}
      <Portal>
        <Dialog
          visible={encourageDialogVisible}
          onDismiss={() => setEncourageDialogVisible(false)}
        >
          <Dialog.Title>Envoyer un message d'encouragement</Dialog.Title>
          <Dialog.Content>
            <TextInput
              label="Message (optionnel)"
              value={message}
              onChangeText={setMessage}
              multiline
              numberOfLines={3}
            />
          </Dialog.Content>
          <Dialog.Actions>
            <Button onPress={() => setEncourageDialogVisible(false)}>Annuler</Button>
            <Button
              onPress={() => encourageMutation.mutate()}
              loading={encourageMutation.isPending}
            >
              Envoyer
            </Button>
          </Dialog.Actions>
        </Dialog>
      </Portal>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#f5f5f5',
  },
  emptyState: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: 40,
  },
  emptyTitle: {
    textAlign: 'center',
    marginBottom: 16,
  },
  emptyDescription: {
    textAlign: 'center',
    color: '#666',
    marginBottom: 32,
  },
  findButton: {
    minWidth: 200,
  },
  buddyCard: {
    margin: 16,
  },
  buddyHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 20,
  },
  buddyInfo: {
    marginLeft: 16,
    flex: 1,
  },
  buddyTitle: {
    color: '#666',
    marginTop: 4,
  },
  buddyStats: {
    flexDirection: 'row',
    marginTop: 8,
  },
  streakContainer: {
    flexDirection: 'row',
    gap: 12,
    marginBottom: 20,
  },
  streakBadge: {
    flex: 1,
    padding: 16,
    borderRadius: 12,
    alignItems: 'center',
  },
  actionButtons: {
    flexDirection: 'row',
    gap: 12,
  },
  actionButton: {
    flex: 1,
  },
  progressCard: {
    margin: 16,
    marginTop: 0,
  },
  sectionTitle: {
    fontWeight: 'bold',
    marginBottom: 20,
  },
  progressItem: {
    marginBottom: 24,
  },
  progressLabel: {
    fontWeight: '600',
    marginBottom: 12,
  },
  progressBars: {
    gap: 12,
  },
  progressRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  progressName: {
    width: 60,
    fontSize: 12,
  },
  progressBar: {
    flex: 1,
    height: 8,
    borderRadius: 4,
  },
  progressValue: {
    width: 40,
    fontSize: 12,
    textAlign: 'right',
    fontWeight: '600',
  },
});
