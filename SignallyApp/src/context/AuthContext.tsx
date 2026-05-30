import React, { createContext, useContext, useState } from 'react';
import { ApiUserRole } from '../api/client';

interface AuthContextValue {
  isLoggedIn: boolean;
  role: ApiUserRole;
  isAdmin: boolean;
  login: (role?: ApiUserRole) => void;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  // TODO: on mount, read JWT from SecureStore; if valid, restore login and role.
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [role, setRole] = useState<ApiUserRole>('ADMIN');

  return (
    <AuthContext.Provider
      value={{
        isLoggedIn,
        role,
        isAdmin: role === 'ADMIN',
        // TODO: store JWT in SecureStore on login, clear it on logout.
        login: (nextRole = 'ADMIN') => {
          setRole(nextRole);
          setIsLoggedIn(true);
        },
        logout: () => setIsLoggedIn(false),
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
