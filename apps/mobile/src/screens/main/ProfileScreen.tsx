import React from 'react';
import { View, ScrollView, StyleSheet, Alert } from 'react-native';
import { Text, List, Switch, Button, Avatar, Divider, ProgressBar, Card, Surface } from 'react-native-paper';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useAuthStore } from '../../stores/authStore';
import { useFirebaseAuth } from '../../hooks/useAuth';
import { useQuery } from '@tanstack/react-query';
import { api } from '../../services/api';
import { theme } from '../../theme';

export function ProfileScreen() {
  const user = useAuthStore((state) => state.user);
  const preferences = useAuthStore((state) => state.preferences);
  const notificationPrefs = useAuthStore((state) => state.notificationPrefs);
  const setPreferences = useAuthStore((state) => state.setPreferences);
  const setNotificationPrefs = useAuthStore((state) => state.setNotificationPrefs);

  const { signOut } = useFirebaseAuth();

  // Fetch gamification stats
  const { data: profile } = useQuery({
    queryKey: ['profile'],
    queryFn: async () => {
      const response = await api.get('/gamification/profile');
      return response.data.profile;
    },
  });

  const { data: stats } = useQuery({
    queryKey: ['stats'],
    queryFn: async () => {
      const response = await api.get('/gamification/stats');
      return response.data.stats;
    },
  });

  const handleLogout = () => {
    Alert.alert(
      'Déconnexion',
      'Êtes-vous sûr de vouloir vous déconnecter ?',
      [
        { text: 'Annuler', style: 'cancel' },
        {
          text: 'Déconnexion',
          style: 'destructive',
          onPress: signOut,
        },
      ]
    );
  };

  return (
    <SafeAreaView style={styles.container}>
      <ScrollView>
        <View style={styles.header}>
          <Avatar.Text
            size={80}
            label={(user?.displayName?.[0] || user?.email?.[0] || 'U').toUpperCase()}
            style={styles.avatar}
          />
          <Text variant="headlineSmall" style={styles.name}>
            {user?.displayName || 'Utilisateur'}
          </Text>
          <Text variant="bodyMedium" style={styles.email}>
            {user?.email}
          </Text>
          <Text variant="bodySmall" style={styles.title}>
            {profile?.title || 'Rêveur'}
          </Text>
        </View>

        {/* Gamification Stats */}
        {profile && (
          <View style={styles.statsSection}>
            <Card style={styles.statsCard}>
              <Card.Content>
                <Text variant="titleMedium" style={styles.sectionTitle}>
                  Niveau & XP
                </Text>
                <View style={styles.levelContainer}>
                  <Text variant="headlineLarge" style={styles.level}>
                    Niveau {profile.currentLevel}
                  </Text>
                  <Text variant="bodySmall" style={styles.xp}>
                    {profile.totalXp} XP
                  </Text>
                </View>
                <ProgressBar
                  progress={
                    1 - profile.xpToNextLevel / ((profile.currentLevel + 1) * 100)
                  }
                  style={styles.xpBar}
                  color={theme.colors.primary}
                />
                <Text variant="bodySmall" style={styles.xpLabel}>
                  {profile.xpToNextLevel} XP jusqu'au niveau suivant
                </Text>
              </Card.Content>
            </Card>

            <View style={styles.statsRow}>
              <Surface style={styles.statBox} elevation={1}>
                <Text variant="headlineSmall" style={styles.statValue}>
                  {profile.influenceScore}
                </Text>
                <Text variant="bodySmall" style={styles.statLabel}>
                  Influence
                </Text>
              </Surface>

              <Surface style={styles.statBox} elevation={1}>
                <Text variant="headlineSmall" style={styles.statValue}>
                  {profile.currentStreak} 🔥
                </Text>
                <Text variant="bodySmall" style={styles.statLabel}>
                  Série
                </Text>
              </Surface>

              <Surface style={styles.statBox} elevation={1}>
                <Text variant="headlineSmall" style={styles.statValue}>
                  {stats?.completedDreams || 0}
                </Text>
                <Text variant="bodySmall" style={styles.statLabel}>
                  Rêves
                </Text>
              </Surface>
            </View>

            <Card style={styles.statsCard}>
              <Card.Content>
                <Text variant="titleMedium" style={styles.sectionTitle}>
                  Attributs RPG
                </Text>
                {[
                  { name: 'Discipline', value: profile.attributeDiscipline },
                  { name: 'Apprentissage', value: profile.attributeLearning },
                  { name: 'Bien-être', value: profile.attributeWellbeing },
                  { name: 'Carrière', value: profile.attributeCareer },
                  { name: 'Créativité', value: profile.attributeCreativity },
                ].map((attr) => (
                  <View key={attr.name} style={styles.attributeRow}>
                    <Text style={styles.attributeName}>{attr.name}</Text>
                    <View style={styles.attributeBarContainer}>
                      <ProgressBar
                        progress={attr.value / 100}
                        style={styles.attributeBar}
                        color={theme.colors.secondary}
                      />
                      <Text style={styles.attributeValue}>{attr.value}</Text>
                    </View>
                  </View>
                ))}
              </Card.Content>
            </Card>
          </View>
        )}

        <Divider />

        <List.Section>
          <List.Subheader>Préférences</List.Subheader>

          <List.Item
            title="Thème sombre"
            left={(props) => <List.Icon {...props} icon="theme-light-dark" />}
            right={() => (
              <Switch
                value={preferences?.theme === 'dark'}
                onValueChange={(value) =>
                  setPreferences({
                    ...(preferences || {}),
                    theme: value ? 'dark' : 'light',
                  })
                }
              />
            )}
          />

          <List.Item
            title="Langue"
            description={preferences?.language === 'fr' ? 'Français' : 'English'}
            left={(props) => <List.Icon {...props} icon="translate" />}
          />
        </List.Section>

        <Divider />

        <List.Section>
          <List.Subheader>Notifications</List.Subheader>

          <List.Item
            title="Rappels de tâches"
            left={(props) => <List.Icon {...props} icon="bell" />}
            right={() => (
              <Switch
                value={notificationPrefs?.reminders ?? true}
                onValueChange={(value) =>
                  setNotificationPrefs({
                    ...(notificationPrefs || {}),
                    reminders: value,
                  })
                }
              />
            )}
          />

          <List.Item
            title="Messages de motivation"
            left={(props) => <List.Icon {...props} icon="emoticon-happy" />}
            right={() => (
              <Switch
                value={notificationPrefs?.motivation ?? true}
                onValueChange={(value) =>
                  setNotificationPrefs({
                    ...(notificationPrefs || {}),
                    motivation: value,
                  })
                }
              />
            )}
          />

          <List.Item
            title="Progrès et achievements"
            left={(props) => <List.Icon {...props} icon="trophy" />}
            right={() => (
              <Switch
                value={notificationPrefs?.achievements ?? true}
                onValueChange={(value) =>
                  setNotificationPrefs({
                    ...(notificationPrefs || {}),
                    achievements: value,
                  })
                }
              />
            )}
          />
        </List.Section>

        <Divider />

        <List.Section>
          <List.Subheader>À propos</List.Subheader>

          <List.Item
            title="Version"
            description="1.0.0"
            left={(props) => <List.Icon {...props} icon="information" />}
          />

          <List.Item
            title="Conditions d'utilisation"
            left={(props) => <List.Icon {...props} icon="file-document" />}
            onPress={() => console.log('Terms')}
          />

          <List.Item
            title="Politique de confidentialité"
            left={(props) => <List.Icon {...props} icon="shield-check" />}
            onPress={() => console.log('Privacy')}
          />
        </List.Section>

        <View style={styles.logoutContainer}>
          <Button
            mode="outlined"
            onPress={handleLogout}
            style={styles.logoutButton}
            textColor={theme.colors.error}
          >
            Se déconnecter
          </Button>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#f5f5f5',
  },
  header: {
    alignItems: 'center',
    padding: 24,
    backgroundColor: '#ffffff',
  },
  avatar: {
    backgroundColor: theme.colors.primary,
  },
  name: {
    marginTop: 16,
    fontWeight: 'bold',
  },
  email: {
    color: '#666',
    marginTop: 4,
  },
  subscription: {
    marginTop: 8,
    color: theme.colors.primary,
  },
  title: {
    marginTop: 4,
    fontWeight: '600',
    color: theme.colors.secondary,
  },
  statsSection: {
    padding: 16,
    gap: 16,
  },
  statsCard: {
    backgroundColor: '#fff',
  },
  sectionTitle: {
    fontWeight: 'bold',
    marginBottom: 12,
  },
  levelContainer: {
    flexDirection: 'row',
    alignItems: 'baseline',
    justifyContent: 'space-between',
    marginBottom: 8,
  },
  level: {
    fontWeight: 'bold',
    color: theme.colors.primary,
  },
  xp: {
    color: '#666',
  },
  xpBar: {
    height: 10,
    borderRadius: 5,
  },
  xpLabel: {
    color: '#666',
    marginTop: 4,
  },
  statsRow: {
    flexDirection: 'row',
    gap: 12,
  },
  statBox: {
    flex: 1,
    padding: 16,
    borderRadius: 12,
    alignItems: 'center',
    backgroundColor: '#fff',
  },
  statValue: {
    fontWeight: 'bold',
    color: theme.colors.primary,
  },
  statLabel: {
    color: '#666',
    marginTop: 4,
  },
  attributeRow: {
    marginBottom: 12,
  },
  attributeName: {
    fontSize: 14,
    marginBottom: 4,
    fontWeight: '500',
  },
  attributeBarContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  attributeBar: {
    flex: 1,
    height: 8,
    borderRadius: 4,
  },
  attributeValue: {
    width: 30,
    fontSize: 12,
    color: '#666',
    textAlign: 'right',
  },
  logoutContainer: {
    padding: 16,
    marginTop: 16,
  },
  logoutButton: {
    borderColor: theme.colors.error,
  },
});
