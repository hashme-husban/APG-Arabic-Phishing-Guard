import { FormEvent, useState } from 'react';
import { Navigate } from 'react-router-dom';
import { Lock, Mail, Globe } from 'lucide-react';
import { useAuth } from '../store/AuthContext';
import { useI18n } from '../i18n';

export default function LoginPage() {
  const { user, login } = useAuth();
  const { t, lang, setLang, dir } = useI18n();
  const [email, setEmail] = useState('admin@apg-secure.com');
  const [password, setPassword] = useState('admin123');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  if (user) return <Navigate to="/monitoring" replace />;

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await login(email, password);
    } catch (err: any) {
      setError(err.message || t('login.invalid'));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      dir={dir}
      className="relative flex min-h-screen items-center justify-center overflow-hidden p-4"
      style={{
        background: 'radial-gradient(ellipse at 20% 10%, rgba(34,211,238,0.09) 0%, transparent 45%), radial-gradient(ellipse at 80% 90%, rgba(99,102,241,0.09) 0%, transparent 45%), #07111C',
      }}
    >
      {/* Cyber grid overlay */}
      <div className="cyber-grid pointer-events-none absolute inset-0 opacity-60" />

      {/* Glow orbs */}
      <div
        className="pointer-events-none absolute left-1/4 top-1/3 h-72 w-72 -translate-x-1/2 -translate-y-1/2 rounded-full opacity-20 blur-3xl"
        style={{ background: 'radial-gradient(circle, rgba(34,211,238,0.35), transparent 70%)' }}
      />
      <div
        className="pointer-events-none absolute bottom-1/4 right-1/4 h-56 w-56 translate-x-1/2 translate-y-1/2 rounded-full opacity-15 blur-3xl"
        style={{ background: 'radial-gradient(circle, rgba(99,102,241,0.4), transparent 70%)' }}
      />

      {/* Login card */}
      <div className="animate-in relative z-10 w-full max-w-sm">
        {/* Header */}
        <div className="mb-7 text-center">
          <div className="mx-auto mb-6 flex items-center justify-center">
            <img
              src="/branding/apg_dashboard_branding.png?v=2"
              alt="APG Admin Console"
              className="w-[200px] sm:w-[260px] h-auto object-contain drop-shadow-[0_0_40px_rgba(34,211,238,0.30)]"
              draggable={false}
            />
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-50">{t('login.title')}</h1>
          <p className="mt-1.5 text-[13px] text-slate-500">{t('login.subtitle')}</p>
        </div>

        {/* Card */}
        <div
          className="rounded-2xl border border-white/8 p-6"
          style={{ background: 'rgba(11, 18, 32, 0.82)', backdropFilter: 'blur(20px)' }}
        >
          {/* Language picker */}
          <div className="mb-5 flex items-center justify-between">
            <div className="flex items-center gap-1.5 text-[12px] text-slate-500">
              <Globe size={13} />
              <span>{t('topbar.language')}</span>
            </div>
            <div className="flex overflow-hidden rounded-lg border border-white/10">
              <button
                type="button"
                onClick={() => setLang('ar')}
                className={`px-3 py-1.5 text-[12px] transition ${lang === 'ar' ? 'bg-cyan-400/15 text-cyan-300 font-medium' : 'text-slate-400 hover:text-slate-200'}`}
              >
                العربية
              </button>
              <button
                type="button"
                onClick={() => setLang('en')}
                className={`px-3 py-1.5 text-[12px] transition ${lang === 'en' ? 'bg-cyan-400/15 text-cyan-300 font-medium' : 'text-slate-400 hover:text-slate-200'}`}
              >
                English
              </button>
            </div>
          </div>

          <form onSubmit={submit} className="grid gap-4">
            {/* Email */}
            <label className="grid gap-1.5">
              <span className="text-[13px] font-medium text-slate-400">{t('login.email')}</span>
              <div className="flex items-center gap-3 rounded-xl border border-white/10 bg-white/[0.04] px-3.5 py-3 transition focus-within:border-cyan-400/40 focus-within:bg-white/[0.06]">
                <Mail size={15} className="shrink-0 text-slate-500" />
                <input
                  className="w-full bg-transparent text-sm text-slate-100 outline-none placeholder:text-slate-600"
                  value={email}
                  onChange={e => setEmail(e.target.value)}
                  placeholder="admin@apg-secure.com"
                  autoComplete="email"
                  dir="ltr"
                />
              </div>
            </label>

            {/* Password */}
            <label className="grid gap-1.5">
              <span className="text-[13px] font-medium text-slate-400">{t('login.password')}</span>
              <div className="flex items-center gap-3 rounded-xl border border-white/10 bg-white/[0.04] px-3.5 py-3 transition focus-within:border-cyan-400/40 focus-within:bg-white/[0.06]">
                <Lock size={15} className="shrink-0 text-slate-500" />
                <input
                  className="w-full bg-transparent text-sm text-slate-100 outline-none placeholder:text-slate-600"
                  type="password"
                  value={password}
                  onChange={e => setPassword(e.target.value)}
                  placeholder="••••••••"
                  autoComplete="current-password"
                  dir="ltr"
                />
              </div>
            </label>

            {/* Error */}
            {error && (
              <div className="flex items-start gap-2.5 rounded-xl border border-rose-400/20 bg-rose-400/8 px-3.5 py-3 text-sm text-rose-300">
                {error.includes('Invalid') || error.includes('غير') ? t('login.invalid') : error}
              </div>
            )}

            {/* Submit */}
            <button
              type="submit"
              disabled={!email || !password || loading}
              className="mt-1 rounded-xl bg-cyan-400 py-3 text-sm font-semibold text-slate-950 transition hover:bg-cyan-300 active:scale-[.98] disabled:cursor-not-allowed disabled:opacity-45"
            >
              {loading ? t('login.loading') : t('login.login')}
            </button>
          </form>

          {/* Dev hint */}
          <p className="mt-4 text-center text-[11px] text-slate-600" dir="ltr">
            {t('login.dev')}: admin@apg-secure.com / admin123
          </p>
        </div>

        {/* Footer brand */}
        <div className="mt-5 flex flex-col items-center gap-2">
          <img
            src="/branding/apg_logo_white.png?v=2"
            alt=""
            aria-hidden="true"
            className="h-5 w-auto object-contain opacity-20"
            draggable={false}
          />
          <p className="text-center text-[11px] text-slate-700">
            APG Security Platform · SOC Admin
          </p>
        </div>
      </div>
    </div>
  );
}
