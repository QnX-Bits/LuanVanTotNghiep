import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowRight, KeyRound } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { api } from '../api';
import { useApp } from '../app/AppContext';
import type { Role } from '../types';

type DemoUser = { key: string; name: string; role: Role; locale: 'vi' | 'en' };
const roleLabel: Record<Role, Record<'vi' | 'en', string>> = { investor: { vi: 'Investor', en: 'Investor' }, reviewer: { vi: 'Reviewer · chỉ đọc', en: 'Reviewer · read-only' }, admin: { vi: 'Admin', en: 'Admin' } };

export function LoginPage() {
  const { t } = useTranslation();
  const { login, locale } = useApp();
  const [users, setUsers] = useState<DemoUser[]>([]);
  const [selected, setSelected] = useState('an');
  const [passcode, setPasscode] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  useEffect(() => { api<{ users: DemoUser[] }>('/auth/demo-users').then(({ users: list }) => { setUsers(list); const preferred = locale === 'en' ? 'binh' : 'an'; if (list.some((row) => row.key === preferred)) setSelected(preferred); }).catch(() => setUsers([])); }, [locale]);
  const submit = async (event: React.FormEvent) => {
    event.preventDefault(); setError(''); setBusy(true);
    try { await login(passcode, selected); } catch { setError(t('login.error')); } finally { setBusy(false); }
  };
  return <div className="login-page">
    <div className="login-top"><Link to="/" className="login-brand"><span className="ledger-mark" aria-hidden="true"><i /><i /><i /><i /><i /><i /></span><span>Portfolio<b>VN</b></span></Link><span className="eyebrow">UEH · 2026</span></div>
    <div className="login-grid">
      <section className="login-copy"><p className="eyebrow">RESEARCH PORTAL / DEMO ACCESS</p><h1>{t('login.title')}</h1><p>{t('login.intro')}</p><div className="login-data-note"><span className="live-dot" />{t('common.monthlyData')} <span className="dot-separator">·</span> 07/2023–07/2026</div><div className="login-proof"><span className="mono">27</span><span>{t('home.validation')}</span><span className="mono">06</span><span>{locale === 'vi' ? 'lớp tài sản' : 'asset classes'}</span></div></section>
      <form className="login-card" onSubmit={submit}>
        <div className="login-card-icon"><KeyRound size={20} /></div><h2>{locale === 'vi' ? 'Đăng nhập demo' : 'Demo sign in'}</h2><p className="muted">{locale === 'vi' ? 'Dùng passcode do chủ dự án cung cấp.' : 'Use the passcode supplied by the project owner.'}</p>
        <label className="field-label" htmlFor="passcode">{t('login.passcode')}</label><input id="passcode" className="text-input" type="password" autoComplete="current-password" value={passcode} onChange={(event) => setPasscode(event.target.value)} required />
        <div className="field-hint">{t('login.passcodeHint')}</div>
        <div className="field-label role-select-label">{t('login.persona')}</div>
        <div className="persona-list">{users.map((user) => <label key={user.key} className={`persona-option ${selected === user.key ? 'selected' : ''}`}><input type="radio" name="persona" value={user.key} checked={selected === user.key} onChange={() => setSelected(user.key)} /><span className="persona-radio" /><span className="persona-details"><b>{user.name}</b><small>{roleLabel[user.role][locale]}</small></span><span className="persona-locale">{user.locale.toUpperCase()}</span></label>)}</div>
        {error && <div className="form-error" role="alert">{error}</div>}
        <button className="button button-dark login-submit" type="submit" disabled={busy || !users.length}>{busy ? t('common.loading') : <>{t('login.submit')}<ArrowRight size={16} /></>}</button>
        <p className="login-warning">{t('login.warning')}</p>
      </form>
    </div>
    <div className="login-footer"><span>{t('common.disclaimer')}</span><span>PORTFOLIOVN / PRIVATE DEMO</span></div>
  </div>;
}
