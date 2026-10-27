import { useEffect, useState } from 'react';
import { ArrowRight, Copy, ExternalLink, FileText, Printer, RefreshCw, Share2, ShieldAlert, XCircle } from 'lucide-react';
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { api } from '../../api';
import { PlanReport } from './PlanReport';
import { useApp } from '../../app/AppContext';
import { dateLabel, money } from '../../format';
import type { PlanSnapshot } from '../../types';

type PlanListItem = { code: string; created_at: string; profile: string; horizon: string; amount_vnd: number; version_label: string; outdated: boolean };
type ShareResponse = { token: string; path: string; ips_path: string; revoked: boolean };
const profileNames: Record<string, Record<'vi'|'en', string>> = { than_trong: { vi: 'Thận trọng', en: 'Conservative' }, can_bang: { vi: 'Cân bằng', en: 'Balanced' }, tang_truong: { vi: 'Tăng trưởng', en: 'Growth' } };

export function PlansPage() {
  const { t } = useTranslation(); const { locale, user } = useApp();
  const [items, setItems] = useState<PlanListItem[]>([]); const [error, setError] = useState('');
  useEffect(() => { api<{ items: PlanListItem[] }>('/plans').then((result) => setItems(result.items)).catch((e: Error) => setError(e.message)); }, []);
  if (user?.role === 'reviewer' || error.includes('403')) return <div className="permission-state"><ShieldAlert size={20} /><h1>{locale === 'vi' ? 'Reviewer chỉ đọc' : 'Reviewer is read-only'}</h1><p>{locale === 'vi' ? 'Quyền Reviewer chỉ xem phiên bản, pipeline run và audit log; không truy cập kế hoạch cá nhân.' : 'Reviewer can view versions, pipeline runs and audit logs, not personal plans.'}</p><Link to="/" className="text-link">{locale === 'vi' ? 'Quay lại trang chủ' : 'Return home'}<ArrowRight size={14} /></Link></div>;
  return <div className="plans-page"><section className="page-intro page-intro-rule"><div><p className="eyebrow">PLAN INDEX / PRIVATE TO INVESTOR</p><h1>{t('plan.title')}</h1><p>{locale === 'vi' ? 'Mỗi kế hoạch là snapshot bất biến gắn với phiên bản dữ liệu lúc tạo.' : 'Every saved plan is an immutable snapshot tied to its creation data version.'}</p></div><Link className="button button-dark" to="/advisor">{t('nav.start')}<ArrowRight size={15} /></Link></section>
    {error ? <div className="error-panel"><p>{error}</p></div> : items.length ? <div className="plan-list">{items.map((item, index) => <Link className="plan-list-row" to={`/plans/${encodeURIComponent(item.code)}`} key={item.code}><span className="row-index">0{index + 1}</span><div className="plan-list-profile"><span className="eyebrow">{item.code}</span><strong>{profileNames[item.profile]?.[locale] || item.profile}</strong><small>{item.horizon.replace('_', ' ')} · {item.version_label}</small></div><div className="plan-list-amount"><span className="eyebrow">{t('plan.amount')}</span><strong className="mono">{money(item.amount_vnd, locale)}</strong></div><div className="plan-list-date"><span className="eyebrow">{t('plan.savedAt')}</span><strong className="mono">{dateLabel(item.created_at.slice(0, 10), locale)}</strong></div>{item.outdated && <span className="tag tag-provisional">{locale === 'vi' ? 'Phiên bản cũ' : 'Older data'}</span>}<ArrowRight className="plan-row-arrow" size={16} /></Link>)}</div> : <div className="empty-state"><span className="eyebrow">PLAN INDEX / 00</span><h2>{t('plan.noPlan')}</h2><Link className="button button-dark" to="/advisor">{t('nav.start')}<ArrowRight size={15} /></Link></div>}
  </div>;
}

export function PlanDetailPage() {
  const { code = '' } = useParams(); const { t } = useTranslation(); const { locale } = useApp(); const navigate = useNavigate();
  const [plan, setPlan] = useState<PlanSnapshot | null>(null); const [share, setShare] = useState<ShareResponse | null>(null); const [busy, setBusy] = useState(false); const [message, setMessage] = useState(''); const [error, setError] = useState('');
  useEffect(() => { void api<PlanSnapshot>(`/plans/${encodeURIComponent(code)}`).then(setPlan).catch((e: Error) => setError(e.message)); }, [code]);
  const refreshPlan = async () => {
    setBusy(true); setError('');
    try { const newer = await api<PlanSnapshot>(`/plans/${encodeURIComponent(code)}/refresh`, { method: 'POST' }); navigate(`/plans/${encodeURIComponent(newer.code || '')}`, { replace: true }); }
    catch (e) { setError(e instanceof Error ? e.message : t('common.error')); }
    finally { setBusy(false); }
  };
  const createShare = async () => {
    setBusy(true); setError('');
    try { const result = await api<ShareResponse>(`/plans/${encodeURIComponent(code)}/share`, { method: 'POST' }); setShare(result); }
    catch (e) { setError(e instanceof Error ? e.message : t('common.error')); }
    finally { setBusy(false); }
  };
  const revoke = async () => {
    setBusy(true); setError('');
    try { await api(`/plans/${encodeURIComponent(code)}/share`, { method: 'DELETE' }); setShare(null); setMessage(locale === 'vi' ? 'Liên kết đã bị thu hồi.' : 'The link has been revoked.'); }
    catch (e) { setError(e instanceof Error ? e.message : t('common.error')); }
    finally { setBusy(false); }
  };
  const copy = async () => { if (!share) return; try { await navigator.clipboard.writeText(`${window.location.origin}${share.path}`); setMessage(locale === 'vi' ? 'Đã sao chép liên kết.' : 'Link copied.'); } catch { setMessage(share.path); } };
  if (!plan) return error ? <div className="empty-state"><span className="eyebrow">404 / PLAN</span><h1>{locale === 'vi' ? 'Không tìm thấy kế hoạch' : 'Plan not found'}</h1><p>{error}</p><Link to="/plans" className="text-link">{t('nav.plans')}<ArrowRight size={14} /></Link></div> : <div className="loading-block"><span className="eyebrow">PLAN / SNAPSHOT</span><span className="loading-bar" /></div>;
  return <div className="plan-detail-page"><div className="plan-detail-toolbar no-print"><Link to="/plans" className="text-link">← {t('nav.plans')}</Link><div><Link className="button button-outline" to={`/print/plans/${encodeURIComponent(code)}`}><FileText size={14} />{t('common.print')}</Link><button className="button button-outline" onClick={() => void createShare()} disabled={busy}><Share2 size={14} />{t('plan.share')}</button>{plan.outdated && <button className="button button-dark" onClick={() => void refreshPlan()} disabled={busy}><RefreshCw size={14} />{busy ? t('common.loading') : t('common.refresh')}</button>}</div></div>
    {plan.outdated && <div className="outdated-banner no-print"><span>{t('plan.outdated')}</span></div>}
    {share && <div className="share-panel no-print"><div><span className="eyebrow">{t('plan.shares')}</span><strong>{share.path}</strong><small>{locale === 'vi' ? 'Không hiển thị tên, user ID hoặc câu trả lời. Có thể thu hồi.' : 'No name, user ID or answers are shown. You can revoke it.'}</small></div><button className="button button-outline" onClick={() => void copy()}><Copy size={14} />{locale === 'vi' ? 'Sao chép' : 'Copy'}</button><button className="button button-outline" onClick={() => window.open(share.path, '_blank', 'noopener,noreferrer')}><ExternalLink size={14} />{locale === 'vi' ? 'Mở' : 'Open'}</button><button className="button button-danger" onClick={() => void revoke()} disabled={busy}><XCircle size={14} />{t('plan.revoke')}</button></div>}
    {message && <div className="inline-success no-print" role="status">{message}</div>}{error && <div className="form-error no-print" role="alert">{error}</div>}
    <PlanReport plan={plan} mode="detail" />
  </div>;
}

export function PrintPlanPage() {
  const { code = '' } = useParams(); const { locale } = useApp(); const [plan, setPlan] = useState<PlanSnapshot | null>(null); const [error, setError] = useState('');
  useEffect(() => { api<PlanSnapshot>(`/print/plans/${encodeURIComponent(code)}`).then((result) => setPlan(result)).catch((e: Error) => setError(e.message)); }, [code]);
  useEffect(() => { if (plan) { const timer = window.setTimeout(() => window.print(), 450); return () => window.clearTimeout(timer); } }, [plan]);
  if (!plan) return error ? <div className="empty-state"><h1>{locale === 'vi' ? 'Không tìm thấy IPS' : 'IPS not found'}</h1><p>{error}</p></div> : <div className="loading-block"><span className="loading-bar" /></div>;
  return <div className="print-document"><div className="print-toolbar no-print"><Link to={`/plans/${encodeURIComponent(code)}`}>← {locale === 'vi' ? 'Về kế hoạch' : 'Back to plan'}</Link><button className="button button-dark" onClick={() => window.print()}><Printer size={15} />{locale === 'vi' ? 'In / Lưu PDF' : 'Print / Save PDF'}</button></div><div className="print-page-header">PortfolioVN <span>{code}</span></div><PlanReport plan={plan} mode="print" /><div className="print-page-footer">{code} · {plan.created_at?.slice(0, 10)} · {plan.result_version_label}</div></div>;
}

export function SharedPlanPage() {
  const { token = '' } = useParams(); const { t } = useTranslation(); const { locale, setLocale } = useApp(); const [searchParams] = useSearchParams(); const [plan, setPlan] = useState<PlanSnapshot | null>(null); const [error, setError] = useState('');
  useEffect(() => { api<PlanSnapshot>(`/share/${encodeURIComponent(token)}`).then(setPlan).catch((e: Error) => setError(e.message)); }, [token]);
  useEffect(() => { if (plan && searchParams.get('print') === '1') { const timer = window.setTimeout(() => window.print(), 500); return () => window.clearTimeout(timer); } }, [plan, searchParams]);
  return <div className="share-page"><header className="share-page-header"><Link to="/" className="login-brand"><span className="ledger-mark" aria-hidden="true"><i /><i /><i /><i /><i /><i /></span><span>Portfolio<b>VN</b></span></Link><div><span className="share-read-only"><span className="live-dot" />{locale === 'vi' ? 'Chỉ đọc · liên kết công khai' : 'Read only · public share link'}</span><button className="language-button" onClick={() => setLocale(locale === 'vi' ? 'en' : 'vi')}>{locale.toUpperCase()}</button></div></header>{error ? <div className="share-error"><span className="eyebrow">SHARE / 404</span><h1>{locale === 'vi' ? 'Liên kết không khả dụng' : 'Link unavailable'}</h1><p>{error}</p><p>{locale === 'vi' ? 'Liên kết có thể đã bị thu hồi.' : 'The link may have been revoked.'}</p></div> : plan ? <><div className="shared-banner"><ShieldAlert size={16} /><span>{locale === 'vi' ? 'Bản chia sẻ đã lược bỏ tên và câu trả lời chi tiết; điểm và hồ sơ vẫn được giữ.' : 'This share omits names and detailed answers; scores and profile are retained.'}</span><button className="text-link" onClick={() => window.print()}><Printer size={14} />{t('common.print')}</button></div><main className="share-report"><PlanReport plan={plan} mode="shared" /></main></> : <div className="loading-block"><span className="loading-bar" /></div>}<footer className="share-footer">{t('common.disclaimer')}</footer></div>;
}
