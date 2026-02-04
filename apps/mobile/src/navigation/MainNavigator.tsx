/**
 * Main navigator with 5 bottom tabs and nested stack navigators.
 * Tabs: Home, Calendar, Chat, Social, Profile
 * Each tab with sub-screens uses a native stack navigator.
 */

import React from 'react';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import Icon from 'react-native-vector-icons/MaterialCommunityIcons';

import { HomeScreen } from '../screens/main/HomeScreen';
import { CalendarScreen } from '../screens/main/CalendarScreen';
import { ChatScreen } from '../screens/ChatScreen';
import { ProfileScreen } from '../screens/main/ProfileScreen';
import { SocialScreen } from '../screens/SocialScreen';
import { LeaderboardScreen } from '../screens/main/LeaderboardScreen';
import { CirclesScreen } from '../screens/CirclesScreen';
import { CircleDetailScreen } from '../screens/CircleDetailScreen';
import { DreamBuddyScreen } from '../screens/DreamBuddyScreen';
import { MicroStartScreen } from '../screens/MicroStartScreen';
import { SubscriptionScreen } from '../screens/SubscriptionScreen';
import { StoreScreen } from '../screens/StoreScreen';
import { LeagueScreen } from '../screens/LeagueScreen';
import { VisionBoardScreen } from '../screens/VisionBoardScreen';
import { NotificationsScreen } from '../screens/NotificationsScreen';
import { DreamDetailScreen } from '../screens/DreamDetailScreen';
import { CreateDreamScreen } from '../screens/CreateDreamScreen';

import {
  MainTabParamList,
  HomeStackParamList,
  SocialStackParamList,
  ProfileStackParamList,
} from './types';
import { theme } from '../theme';

// Stack navigators for each tab
const HomeStack = createNativeStackNavigator<HomeStackParamList>();
const SocialStack = createNativeStackNavigator<SocialStackParamList>();
const ProfileStack = createNativeStackNavigator<ProfileStackParamList>();
const Tab = createBottomTabNavigator<MainTabParamList>();

/** Home tab stack: Dreams list, detail, creation, vision boards, micro-tasks. */
function HomeStackNavigator() {
  return (
    <HomeStack.Navigator screenOptions={{ headerShown: false }}>
      <HomeStack.Screen name="HomeScreen" component={HomeScreen} />
      <HomeStack.Screen name="DreamDetail" component={DreamDetailScreen} />
      <HomeStack.Screen name="CreateDream" component={CreateDreamScreen} />
      <HomeStack.Screen name="VisionBoard" component={VisionBoardScreen} />
      <HomeStack.Screen name="MicroStart" component={MicroStartScreen} />
      <HomeStack.Screen name="Notifications" component={NotificationsScreen} />
    </HomeStack.Navigator>
  );
}

/** Social tab stack: Feed, circles, buddy, leaderboard, leagues. */
function SocialStackNavigator() {
  return (
    <SocialStack.Navigator screenOptions={{ headerShown: false }}>
      <SocialStack.Screen name="SocialScreen" component={SocialScreen} />
      <SocialStack.Screen name="Circles" component={CirclesScreen} />
      <SocialStack.Screen name="CircleDetail" component={CircleDetailScreen} />
      <SocialStack.Screen name="DreamBuddy" component={DreamBuddyScreen} />
      <SocialStack.Screen name="Leaderboard" component={LeaderboardScreen} />
      <SocialStack.Screen name="League" component={LeagueScreen} />
    </SocialStack.Navigator>
  );
}

/** Profile tab stack: Profile, subscription management, store, settings. */
function ProfileStackNavigator() {
  return (
    <ProfileStack.Navigator screenOptions={{ headerShown: false }}>
      <ProfileStack.Screen name="ProfileScreen" component={ProfileScreen} />
      <ProfileStack.Screen name="Subscription" component={SubscriptionScreen} />
      <ProfileStack.Screen name="Store" component={StoreScreen} />
    </ProfileStack.Navigator>
  );
}

/** Main bottom tab navigator with 5 tabs. */
export function MainNavigator() {
  return (
    <Tab.Navigator
      screenOptions={{
        tabBarActiveTintColor: theme.colors.primary,
        tabBarInactiveTintColor: '#999',
        tabBarStyle: {
          backgroundColor: '#ffffff',
          borderTopColor: '#e0e0e0',
        },
        headerShown: false,
      }}
    >
      <Tab.Screen
        name="HomeTab"
        component={HomeStackNavigator}
        options={{
          tabBarLabel: 'Home',
          tabBarIcon: ({ color, size }) => <Icon name="home" size={size} color={color} />,
        }}
      />
      <Tab.Screen
        name="CalendarTab"
        component={CalendarScreen}
        options={{
          tabBarLabel: 'Calendar',
          tabBarIcon: ({ color, size }) => <Icon name="calendar" size={size} color={color} />,
        }}
      />
      <Tab.Screen
        name="ChatTab"
        component={ChatScreen}
        options={{
          tabBarLabel: 'Chat',
          tabBarIcon: ({ color, size }) => <Icon name="chat" size={size} color={color} />,
        }}
      />
      <Tab.Screen
        name="SocialTab"
        component={SocialStackNavigator}
        options={{
          tabBarLabel: 'Social',
          tabBarIcon: ({ color, size }) => <Icon name="account-group" size={size} color={color} />,
        }}
      />
      <Tab.Screen
        name="ProfileTab"
        component={ProfileStackNavigator}
        options={{
          tabBarLabel: 'Profile',
          tabBarIcon: ({ color, size }) => <Icon name="account" size={size} color={color} />,
        }}
      />
    </Tab.Navigator>
  );
}
