import React, { createContext, useContext, useEffect, useMemo, useState } from 'react';
import { ApiRequestError, api } from '../api/client';
import type { User } from '../types';

type AuthContextValue = {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
  refreshSession: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(() => {
    const raw = localStorage.getItem('apg_admin_user');
    return raw ? JSON.parse(raw) : null;
  });
  const [loading, setLoading] = useState(true);

  const refreshSession = async () => {
    const token = localStorage.getItem('apg_admin_token');
    if (!token) { setLoading(false); return; }
    try {
      const { data } = await api.get('/auth/me');
      setUser(data);
      localStorage.setItem('apg_admin_user', JSON.stringify(data));
    } catch {
      localStorage.removeItem('apg_admin_token');
      localStorage.removeItem('apg_admin_user');
      setUser(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { refreshSession(); }, []);

  const login = async (email: string, password: string) => {
    try {
      const { data } = await api.post('/auth/login', { email, password });
      if (data.user.role !== 'admin') throw new Error('Admin access required');
      localStorage.setItem('apg_admin_token', data.token);
      localStorage.setItem('apg_admin_user', JSON.stringify(data.user));
      setUser(data.user);
    } catch (error: any) {
      if (error instanceof ApiRequestError) {
        if (error.status === 404) {
          throw new Error('Login API endpoint not found. Check API base URL.');
        }
        if (error.status === 401) {
          throw new Error('Invalid email or password.');
        }
        if (error.isNetworkError) {
          throw new Error('Cannot connect to APG backend.');
        }
      }
      throw new Error(error?.message || 'Login failed. Please try again.');
    }
  };

  const logout = () => {
    api.post('/auth/logout').catch(() => undefined);
    localStorage.removeItem('apg_admin_token');
    localStorage.removeItem('apg_admin_user');
    setUser(null);
  };

  const value = useMemo(() => ({ user, loading, login, logout, refreshSession }), [user, loading]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
