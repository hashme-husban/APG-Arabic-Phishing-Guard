import React, { createContext, useContext, useEffect, useMemo, useState } from 'react';
import en from './en';
import ar from './ar';

type Lang = 'en' | 'ar';
type Dict = typeof en;
const dictionaries: Record<Lang, Dict> = { en, ar };

type I18nContextValue = { lang: Lang; dir: 'ltr' | 'rtl'; setLang: (lang: Lang) => void; t: (key: string) => string; raw: Dict };
const I18nContext = createContext<I18nContextValue | undefined>(undefined);

function get(obj: any, path: string): string | undefined { return path.split('.').reduce((acc, part) => acc?.[part], obj); }

export function I18nProvider({ children }: { children: React.ReactNode }) {
  const [lang, setLangState] = useState<Lang>(() => (localStorage.getItem('apg_admin_lang') as Lang) || 'en');
  const setLang = (next: Lang) => { setLangState(next); localStorage.setItem('apg_admin_lang', next); };
  const dir: 'ltr' | 'rtl' = lang === 'ar' ? 'rtl' : 'ltr';
  useEffect(() => { document.documentElement.lang = lang; document.documentElement.dir = dir; }, [lang, dir]);
  const value = useMemo(() => ({ lang, dir, setLang, raw: dictionaries[lang], t: (key: string) => get(dictionaries[lang], key) || get(en, key) || key }), [lang, dir]);
  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n() { const ctx = useContext(I18nContext); if (!ctx) throw new Error('useI18n must be used within I18nProvider'); return ctx; }
export const labelFor = (value: string, t: (k: string) => string) => {
  const map: Record<string,string> = { high: 'common.high', medium: 'common.medium', low: 'common.low', active: 'common.active', monitoring: 'common.monitoring', resolved: 'common.resolved', safe: 'monitoring.safe', suspicious: 'monitoring.suspicious', dangerous: 'monitoring.highRisk' };
  return map[value] ? t(map[value]) : value;
};
