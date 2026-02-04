/**
 * Navigation type definitions for DreamPlanner.
 * Defines all screen parameters for type-safe navigation.
 */

import { NavigatorScreenParams } from '@react-navigation/native';

/** Root-level navigator: Auth vs Main conditional rendering. */
export type RootStackParamList = {
  Auth: NavigatorScreenParams<AuthStackParamList>;
  Main: NavigatorScreenParams<MainTabParamList>;
};

/** Authentication flow screens. */
export type AuthStackParamList = {
  Login: undefined;
  Register: undefined;
  ForgotPassword: undefined;
};

/** Bottom tab navigator with 5 tabs. */
export type MainTabParamList = {
  HomeTab: NavigatorScreenParams<HomeStackParamList>;
  CalendarTab: undefined;
  ChatTab: undefined;
  SocialTab: NavigatorScreenParams<SocialStackParamList>;
  ProfileTab: NavigatorScreenParams<ProfileStackParamList>;
};

/** Home tab stack: dream browsing, detail, creation, vision boards, notifications. */
export type HomeStackParamList = {
  HomeScreen: undefined;
  DreamDetail: { dreamId: string };
  CreateDream: undefined;
  VisionBoard: { dreamId: string };
  MicroStart: { dreamId: string; microTask: string };
  Notifications: undefined;
  Calibration: { dreamId: string; dreamTitle: string };
};

/** Social tab stack: social feed, circles, buddy, leaderboard, leagues. */
export type SocialStackParamList = {
  SocialScreen: undefined;
  Circles: undefined;
  CircleDetail: { circleId: string };
  DreamBuddy: undefined;
  Leaderboard: undefined;
  League: undefined;
};

/** Profile tab stack: profile, subscription, store, settings. */
export type ProfileStackParamList = {
  ProfileScreen: undefined;
  Subscription: undefined;
  Store: undefined;
  Settings: undefined;
};
