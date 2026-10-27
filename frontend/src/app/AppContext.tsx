import { createContext, useContext, useEffect, useMemo, useState } from 'react';
import type { ReactNode } from 'react';
import { useNavigate } from 'react-router-dom';
import i18n from '../locales/i18n';
import { api } from '../api';
import type { Locale, UserSession } from '../types';

type AppContextValue = {
  user: UserSession | null;
  loading: boolean;
  locale: Locale;
  setLocale: (locale: Locale) => void;
  login: (passcode: string, userId: string) => Promise<void>;
  logout: () => Promise<void>;
  reloadSession: () => Promise<void>;
};
const Context = createContext<AppContextValue | null>(null);

export function AppProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserSession | null>(null);
  const [loading, setLoading] = useState(true);
  const [locale, setLocaleState] = useState<Locale>(i18n.language === 'en' ? 'en' : 'vi');
  const navigate = useNavigate();

  const setLocale = (next: Locale) => {
    setLocaleState(next);
    window.localStorage.setItem('pvn-locale', next);
    void i18n.changeLanguage(next);
  };

  const reloadSession = async () => {
    try {
      const session = await api<UserSession>('/auth/session');
      setUser(session);
      const saved = window.localStorage.getItem('pvn-locale');
      setLocale(saved === 'en' || saved === 'vi' ? saved : session.locale);
    } catch {
      setUser(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { void reloadSession(); }, []);

  const login = async (passcode: string, userId: string) => {
    const session = await api<UserSession>('/auth/login', { method: 'POST', body: JSON.stringify({ passcode, user_id: userId }) });
    setUser(session);
    setLocale(session.locale);
    navigate('/', { replace: true });
  };

  const logout = async () => {
    try { await api('/auth/logout', { method: 'POST' }); } finally {
      setUser(null);
      navigate('/login', { replace: true });
    }
  };

  const value = useMemo(() => ({ user, loading, locale, setLocale, login, logout, reloadSession }), [user, loading, locale]);
  return <Context.Provider value={value}>{children}</Context.Provider>;
}

export function useApp() {
  const value = useContext(Context);
  if (!value) throw new Error('useApp must be within AppProvider');
  return value;
}
