import React from 'react';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import AppNavigator from './AppNavigator';
import UserSettingsScreen from '../screens/UserSettingsScreen';

export type RootStackParamList = {
  Tabs: undefined;
  UserSettings: undefined;
};

const Stack = createNativeStackNavigator<RootStackParamList>();

export default function RootNavigator() {
  return (
    <Stack.Navigator screenOptions={{ headerShown: false }}>
      <Stack.Screen name="Tabs" component={AppNavigator} />
      <Stack.Screen name="UserSettings" component={UserSettingsScreen} />
    </Stack.Navigator>
  );
}
