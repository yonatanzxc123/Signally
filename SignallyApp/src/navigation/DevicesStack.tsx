import React from 'react';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import DevicesScreen from '../screens/DevicesScreen';
import DeviceDetailScreen from '../screens/DeviceDetailScreen';

export type DevicesStackParamList = {
  DevicesList: undefined;
  DeviceDetail: { deviceId: string };
};

const Stack = createNativeStackNavigator<DevicesStackParamList>();

export default function DevicesStack() {
  return (
    <Stack.Navigator screenOptions={{ headerShown: false }}>
      <Stack.Screen name="DevicesList" component={DevicesScreen} />
      <Stack.Screen name="DeviceDetail" component={DeviceDetailScreen} />
    </Stack.Navigator>
  );
}
