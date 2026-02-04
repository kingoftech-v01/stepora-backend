import React from 'react';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { useTheme } from 'react-native-paper';
import Icon from 'react-native-vector-icons/MaterialCommunityIcons';

import { ChatScreen } from '../screens/ChatScreen';
import { CalendarScreen } from '../screens/CalendarScreen';
import { DreamsScreen } from '../screens/DreamsScreen';
import { ProfileScreen } from '../screens/ProfileScreen';
import { MainTabParamList } from '../types';
import { AppTheme } from '../theme';

const Tab = createBottomTabNavigator<MainTabParamList>();

const getTabIcon = (routeName: string, focused: boolean) => {
  const icons: Record<string, string> = {
    Chat: focused ? 'chat' : 'chat-outline',
    Calendar: focused ? 'calendar' : 'calendar-outline',
    Dreams: focused ? 'target' : 'target',
    Profile: focused ? 'account' : 'account-outline',
  };
  return icons[routeName] || 'circle';
};

export const MainNavigator: React.FC = () => {
  const theme = useTheme() as AppTheme;

  return (
    <Tab.Navigator
      screenOptions={({ route }) => ({
        headerShown: false,
        tabBarIcon: ({ focused, color, size }) => (
          <Icon name={getTabIcon(route.name, focused)} size={size} color={color} />
        ),
        tabBarActiveTintColor: theme.colors.primary,
        tabBarInactiveTintColor: theme.custom.colors.textMuted,
        tabBarStyle: {
          backgroundColor: theme.colors.surface,
          borderTopColor: theme.custom.colors.border,
          paddingBottom: 8,
          paddingTop: 8,
          height: 64,
        },
        tabBarLabelStyle: {
          fontSize: 12,
          fontWeight: '500',
        },
      })}
    >
      <Tab.Screen
        name="Chat"
        component={ChatScreen}
        options={{ tabBarLabel: 'Chat' }}
      />
      <Tab.Screen
        name="Calendar"
        component={CalendarScreen}
        options={{ tabBarLabel: 'Calendrier' }}
      />
      <Tab.Screen
        name="Dreams"
        component={DreamsScreen}
        options={{ tabBarLabel: 'Rêves' }}
      />
      <Tab.Screen
        name="Profile"
        component={ProfileScreen}
        options={{ tabBarLabel: 'Profil' }}
      />
    </Tab.Navigator>
  );
};
