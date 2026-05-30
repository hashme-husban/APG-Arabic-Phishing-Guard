import React, { createContext, useContext, useEffect, useMemo, useState } from 'react';

type ThemeMode = 'dark' | 'light' | 'system';
type ThemeContextValue = { theme: ThemeMode; resolvedTheme: 'dark' | 'light'; setTheme: (theme: ThemeMode) => void };

const ThemeContext = createContext<ThemeContextValue | undefined>(undefined);

function resolveTheme(theme: ThemeMode): 'dark' | 'light' {
  if (theme === 'system') {
    return window.matchMedia?.('(prefers-color-scheme: light)').matches ? 'light' : 'dark';
  }
  return theme;
}

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [theme, setThemeState] = useState<ThemeMode>(() => (localStorage.getItem('apg_admin_theme') as ThemeMode) || 'dark');
  const [resolvedTheme, setResolvedTheme] = useState<'dark' | 'light'>(() => (typeof window === 'undefined' ? 'dark' : resolveTheme(theme)));

  const setTheme = (next: ThemeMode) => {
    setThemeState(next);
    localStorage.setItem('apg_admin_theme', next);
    setResolvedTheme(resolveTheme(next));
  };

  useEffect(() => {
    const apply = () => {
      const next = resolveTheme(theme);
      setResolvedTheme(next);
      document.documentElement.dataset.theme = next;
      document.documentElement.style.colorScheme = next;
    };
    apply();
    const mq = window.matchMedia?.('(prefers-color-scheme: light)');
    mq?.addEventListener?.('change', apply);
    return () => mq?.removeEventListener?.('change', apply);
  }, [theme]);

  const value = useMemo(() => ({ theme, resolvedTheme, setTheme }), [theme, resolvedTheme]);
  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme() {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error('useTheme must be used within ThemeProvider');
  return ctx;
}
