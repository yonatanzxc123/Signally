import React from 'react';
import { NavigationContainer } from '@react-navigation/native';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { StatusBar } from 'expo-status-bar';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AuthProvider, useAuth } from './src/context/AuthContext';
import { DevicesProvider } from './src/context/DevicesContext';
import { EventsProvider } from './src/context/EventsContext';
import AppNavigator from './src/navigation/AppNavigator';
import AuthScreen from './src/screens/AuthScreen';

const queryClient = new QueryClient();

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
    <QueryClientProvider client={queryClient}>
      <SafeAreaProvider>
        <AuthProvider>
          <DevicesProvider>
            <EventsProvider>
              <Root />
            </EventsProvider>
          </DevicesProvider>
        </AuthProvider>
      </SafeAreaProvider>
    </QueryClientProvider>
  );
}
