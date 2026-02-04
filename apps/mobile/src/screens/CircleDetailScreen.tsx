import React, { useState } from 'react';
import { View, ScrollView, StyleSheet, FlatList } from 'react-native';
import {
  Text,
  Card,
  Avatar,
  Button,
  Chip,
  TextInput,
  IconButton,
  Divider,
} from 'react-native-paper';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../services/api';
import { useRoute } from '@react-navigation/native';

export const CircleDetailScreen = () => {
  const route = useRoute();
  const { circleId } = route.params as { circleId: string };
  const queryClient = useQueryClient();
  const [newPost, setNewPost] = useState('');
  const [showChallenges, setShowChallenges] = useState(false);

  const { data: circle } = useQuery({
    queryKey: ['circle', circleId],
    queryFn: async () => {
      const response = await api.get(`/circles/${circleId}`);
      return response.data.circle;
    },
  });

  const { data: feed } = useQuery({
    queryKey: ['circleFeed', circleId],
    queryFn: async () => {
      const response = await api.get(`/circles/${circleId}/feed`);
      return response.data.feed;
    },
    enabled: !showChallenges,
  });

  const leaveCircleMutation = useMutation({
    mutationFn: async () => {
      await api.post(`/circles/${circleId}/leave`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['circle', circleId] });
      queryClient.invalidateQueries({ queryKey: ['circles'] });
    },
  });

  const createPostMutation = useMutation({
    mutationFn: async () => {
      await api.post(`/circles/${circleId}/posts`, { content: newPost });
    },
    onSuccess: () => {
      setNewPost('');
      queryClient.invalidateQueries({ queryKey: ['circleFeed', circleId] });
    },
  });

  const joinChallengeMutation = useMutation({
    mutationFn: async (challengeId: string) => {
      await api.post(`/circles/challenges/${challengeId}/join`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['circle', circleId] });
    },
  });

  if (!circle) return null;

  return (
    <ScrollView style={styles.container}>
      {/* Circle Header */}
      <Card style={styles.headerCard}>
        <Card.Content>
          <View style={styles.header}>
            <View style={styles.headerInfo}>
              <Text variant="headlineMedium" style={styles.circleName}>
                {circle.name}
              </Text>
              {circle.category && (
                <Chip icon="tag" style={styles.categoryChip}>
                  {circle.category}
                </Chip>
              )}
            </View>
            {circle.isMember && (
              <Button
                mode="outlined"
                onPress={() => leaveCircleMutation.mutate()}
                loading={leaveCircleMutation.isPending}
              >
                Leave
              </Button>
            )}
          </View>

          <Text variant="bodyMedium" style={styles.description}>
            {circle.description}
          </Text>

          <View style={styles.stats}>
            <View style={styles.stat}>
              <Text variant="titleMedium">{circle.members?.length || 0}</Text>
              <Text variant="bodySmall" style={styles.statLabel}>
                Members
              </Text>
            </View>
            <View style={styles.stat}>
              <Text variant="titleMedium">{circle.challenges?.length || 0}</Text>
              <Text variant="bodySmall" style={styles.statLabel}>
                Challenges
              </Text>
            </View>
          </View>
        </Card.Content>
      </Card>

      {/* Tabs */}
      <View style={styles.tabs}>
        <Chip
          selected={!showChallenges}
          onPress={() => setShowChallenges(false)}
          style={styles.tab}
        >
          Feed
        </Chip>
        <Chip
          selected={showChallenges}
          onPress={() => setShowChallenges(true)}
          style={styles.tab}
        >
          Challenges
        </Chip>
      </View>

      {/* Feed Tab */}
      {!showChallenges && circle.isMember && (
        <View style={styles.content}>
          {/* Create Post */}
          <Card style={styles.createPostCard}>
            <Card.Content>
              <TextInput
                placeholder="Share your progress..."
                value={newPost}
                onChangeText={setNewPost}
                multiline
                numberOfLines={3}
                style={styles.postInput}
              />
              <Button
                mode="contained"
                onPress={() => createPostMutation.mutate()}
                disabled={!newPost.trim()}
                loading={createPostMutation.isPending}
                style={styles.postButton}
              >
                Post
              </Button>
            </Card.Content>
          </Card>

          {/* Feed Posts */}
          {feed?.map((post: any) => (
            <Card key={post.id} style={styles.postCard}>
              <Card.Content>
                <View style={styles.postHeader}>
                  <Avatar.Image size={40} source={{ uri: post.user.avatar }} />
                  <View style={styles.postUserInfo}>
                    <Text variant="bodyLarge" style={styles.postUsername}>
                      {post.user.username}
                    </Text>
                    <Text variant="bodySmall" style={styles.postTime}>
                      {new Date(post.createdAt).toLocaleDateString('en-US')}
                    </Text>
                  </View>
                </View>
                <Text variant="bodyMedium" style={styles.postContent}>
                  {post.content}
                </Text>
                <View style={styles.postReactions}>
                  {post.reactions?.map((reaction: any) => (
                    <Chip key={reaction.type} compact>
                      {reaction.type}
                    </Chip>
                  ))}
                </View>
              </Card.Content>
            </Card>
          ))}

          {(!feed || feed.length === 0) && (
            <View style={styles.emptyState}>
              <Text variant="bodyMedium" style={styles.emptyText}>
                No posts yet. Be the first to share!
              </Text>
            </View>
          )}
        </View>
      )}

      {/* Challenges Tab */}
      {showChallenges && (
        <View style={styles.content}>
          {circle.challenges?.map((challenge: any) => (
            <Card key={challenge.id} style={styles.challengeCard}>
              <Card.Content>
                <Text variant="titleMedium" style={styles.challengeTitle}>
                  {challenge.title}
                </Text>
                <Text variant="bodyMedium" style={styles.challengeDescription}>
                  {challenge.description}
                </Text>
                <View style={styles.challengeDates}>
                  <Text variant="bodySmall">
                    From {new Date(challenge.startDate).toLocaleDateString('en-US')}
                  </Text>
                  <Text variant="bodySmall">
                    to {new Date(challenge.endDate).toLocaleDateString('en-US')}
                  </Text>
                </View>
                {circle.isMember && (
                  <Button
                    mode="contained"
                    onPress={() => joinChallengeMutation.mutate(challenge.id)}
                    style={styles.joinChallengeButton}
                  >
                    Join
                  </Button>
                )}
              </Card.Content>
            </Card>
          ))}

          {(!circle.challenges || circle.challenges.length === 0) && (
            <View style={styles.emptyState}>
              <Text variant="bodyMedium" style={styles.emptyText}>
                No active challenges
              </Text>
            </View>
          )}
        </View>
      )}

      {/* Members Section */}
      <Card style={styles.membersCard}>
        <Card.Content>
          <Text variant="titleMedium" style={styles.sectionTitle}>
            Members ({circle.members?.length || 0})
          </Text>
          <View style={styles.membersList}>
            {circle.members?.slice(0, 6).map((member: any) => (
              <View key={member.id} style={styles.memberItem}>
                <Avatar.Image size={40} source={{ uri: member.avatar }} />
                <Text variant="bodySmall" style={styles.memberName} numberOfLines={1}>
                  {member.username}
                </Text>
                {member.role === 'admin' && (
                  <Chip compact icon="crown" style={styles.adminBadge}>
                    Admin
                  </Chip>
                )}
              </View>
            ))}
          </View>
        </Card.Content>
      </Card>
    </ScrollView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#f5f5f5',
  },
  headerCard: {
    margin: 15,
    marginBottom: 0,
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: 12,
  },
  headerInfo: {
    flex: 1,
  },
  circleName: {
    fontWeight: 'bold',
    marginBottom: 8,
  },
  categoryChip: {
    alignSelf: 'flex-start',
  },
  description: {
    color: '#666',
    marginBottom: 16,
  },
  stats: {
    flexDirection: 'row',
    gap: 30,
  },
  stat: {
    alignItems: 'center',
  },
  statLabel: {
    color: '#666',
    marginTop: 4,
  },
  tabs: {
    flexDirection: 'row',
    padding: 15,
    gap: 10,
  },
  tab: {
    flex: 1,
  },
  content: {
    padding: 15,
    paddingTop: 0,
  },
  createPostCard: {
    marginBottom: 15,
  },
  postInput: {
    marginBottom: 12,
  },
  postButton: {
    alignSelf: 'flex-end',
  },
  postCard: {
    marginBottom: 10,
  },
  postHeader: {
    flexDirection: 'row',
    marginBottom: 12,
  },
  postUserInfo: {
    marginLeft: 12,
    flex: 1,
  },
  postUsername: {
    fontWeight: '600',
  },
  postTime: {
    color: '#999',
    marginTop: 2,
  },
  postContent: {
    marginBottom: 12,
  },
  postReactions: {
    flexDirection: 'row',
    gap: 8,
  },
  challengeCard: {
    marginBottom: 15,
  },
  challengeTitle: {
    fontWeight: 'bold',
    marginBottom: 8,
  },
  challengeDescription: {
    color: '#666',
    marginBottom: 12,
  },
  challengeDates: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: 12,
  },
  joinChallengeButton: {
    alignSelf: 'flex-start',
  },
  membersCard: {
    margin: 15,
    marginTop: 0,
  },
  sectionTitle: {
    fontWeight: 'bold',
    marginBottom: 12,
  },
  membersList: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 12,
  },
  memberItem: {
    alignItems: 'center',
    width: 80,
  },
  memberName: {
    marginTop: 4,
    fontSize: 12,
    textAlign: 'center',
  },
  adminBadge: {
    marginTop: 4,
  },
  emptyState: {
    padding: 40,
    alignItems: 'center',
  },
  emptyText: {
    color: '#999',
    textAlign: 'center',
  },
});
