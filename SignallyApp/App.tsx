import React from 'react';
import { NavigationContainer } from '@react-navigation/native';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { StatusBar } from 'expo-status-bar';
import { AuthProvider, useAuth } from './src/context/AuthContext';
import { DevicesProvider } from './src/context/DevicesContext';
import AppNavigator from './src/navigation/AppNavigator';
import AuthScreen from './src/screens/AuthScreen';

function Root() {
  const { isLoggedIn, login } = useAuth();

  return (
    <>
      <StatusBar style="dark" />
      {isLoggedIn ? (
        <NavigationContainer>
          <AppNavigator />
        </NavigationContainer>
      ) : (
        <AuthScreen onAuth={login} />
      )}
    </>
  );
}

export default function App() {
  return (
    <SafeAreaProvider>
      <AuthProvider>
        <DevicesProvider>
          <Root />
        </DevicesProvider>
      </AuthProvider>
    </SafeAreaProvider>
  );
}
