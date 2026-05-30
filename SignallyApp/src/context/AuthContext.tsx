import React, { createContext, useContext, useEffect, useState } from 'react';
import * as SecureStore from 'expo-secure-store';
import { ApiAuthResponse, ApiUserRole } from '../api/client';

const STORAGE_KEY = 'signally_auth';

export interface AuthUser {
  userId: number;
  displayName: string;
  role: ApiUserRole;
}

interface AuthContextValue {
  isLoggedIn: boolean;
  user: AuthUser | null;
  role: ApiUserRole;
  isAdmin: boolean;
  token: string | null;
  login: (response: ApiAuthResponse) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [user, setUser] = useState<AuthUser | null>(null);
  const [token, setToken] = useState<string | null>(null);

  useEffect(() => {
    SecureStore.getItemAsync(STORAGE_KEY).then((stored) => {
      if (!stored) return;
      try {
        const { token: t, user_id, display_name, role } = JSON.parse(stored);
        setToken(t);
        setUser({ userId: user_id, displayName: display_name, role });
        setIsLoggedIn(true);
      } catch {
        SecureStore.deleteItemAsync(STORAGE_KEY);
      }
    });
  }, []);

  async function login(response: ApiAuthResponse) {
    await SecureStore.setItemAsync(STORAGE_KEY, JSON.stringify(response));
    setToken(response.token);
    setUser({ userId: response.user_id, displayName: response.display_name, role: response.role });
    setIsLoggedIn(true);
  }

  async function logout() {
    await SecureStore.deleteItemAsync(STORAGE_KEY);
    setToken(null);
    setUser(null);
    setIsLoggedIn(false);
  }

  return (
    <AuthContext.Provider
      value={{
        isLoggedIn,
        user,
        role: user?.role ?? 'ADMIN',
        isAdmin: user?.role === 'ADMIN',
        token,
        login,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider');
  return ctx;
}
