import React, { createContext, useContext, useMemo, useState } from 'react';

type Toast = { id: number; message: string; tone?: 'success' | 'error' | 'info' };
type ToastContextValue = { toast: (message: string, tone?: Toast['tone']) => void };
const ToastContext = createContext<ToastContextValue | undefined>(undefined);

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [items, setItems] = useState<Toast[]>([]);
  const toast = (message: string, tone: Toast['tone'] = 'info') => {
    const id = Date.now() + Math.random();
    setItems((prev) => [...prev, { id, message, tone }]);
    window.setTimeout(() => setItems((prev) => prev.filter((x) => x.id !== id)), 3200);
  };
  const value = useMemo(() => ({ toast }), []);
  return <ToastContext.Provider value={value}>{children}<div className="fixed bottom-5 end-5 z-[80] grid max-w-sm gap-2">{items.map((x) => <div key={x.id} className={`animate-in rounded-2xl border px-4 py-3 text-sm shadow-glow ${x.tone === 'error' ? 'border-rose-400/30 bg-rose-950/90 text-rose-100' : x.tone === 'success' ? 'border-emerald-400/30 bg-emerald-950/90 text-emerald-100' : 'border-cyan-400/30 bg-slate-950/90 text-cyan-100'}`}>{x.message}</div>)}</div></ToastContext.Provider>;
}

export function useToast() { const ctx = useContext(ToastContext); if (!ctx) throw new Error('useToast must be used within ToastProvider'); return ctx; }
