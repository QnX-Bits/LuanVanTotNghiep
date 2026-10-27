import { useEffect, useMemo, useState } from 'react';
import { ArrowLeft, ArrowRight, Check, LockKeyhole, RotateCcw } from 'lucide-react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { api } from '../../api';
import { useApp } from '../../app/AppContext';
import { formatMoneyInput, money, parseMoneyInput } from '../../format';
import type { Locale, PlanSnapshot } from '../../types';
import { PlanReport } from '../plans/PlanReport';

type QuestionData = {
  tolerance: Record<Locale, string[][]>;
  capacity: Record<Locale, string[][]>;
  horizons: Record<string, Record<Locale, string>>;
  profiles: Record<string, Record<Locale, string>>;
};
type Choice = { profile: string; enabled: boolean; requires_ack: boolean; choice_type: string; reason: string | null };
type Assessment = { scores: { tolerance: number; capacity: number }; tolerance_profile: string; capacity_profile: string; horizon: string; horizon_cap: string; system_profile: string; warnings: string[]; warning_copy: Record<string, string>; choices: Choice[]; acknowledgement: string };
const order = ['T1', 'T2', 'T3', 'T4', 'C1', 'C2', 'C3', 'H'] as const;
const questionLabels: Record<string, Record<Locale, { title: string; helper: string }>> = {
  T1: { vi: { title: 'Nếu giá trị danh mục giảm mạnh trong thời gian ngắn, bạn sẽ làm gì?', helper: 'Hãy chọn phản ứng gần nhất với cách bạn thường ra quyết định.' }, en: { title: 'If your portfolio fell sharply over a short period, what would you do?', helper: 'Choose the response closest to how you usually make decisions.' } },
  T2: { vi: { title: 'Bạn đã có kinh nghiệm đầu tư ở mức nào?', helper: 'Tính đến kinh nghiệm thực tế với cổ phiếu, quỹ hoặc tài sản đầu tư.' }, en: { title: 'How much investing experience do you have?', helper: 'Consider hands-on experience with stocks, funds or investments.' } },
  T3: { vi: { title: 'Bạn ưu tiên điều gì trong mục tiêu đầu tư?', helper: 'Không có câu trả lời đúng hoặc sai.' }, en: { title: 'What do you prioritize in your investment objective?', helper: 'There is no right or wrong answer.' } },
  T4: { vi: { title: 'Mức dao động lợi nhuận nào bạn có thể chấp nhận?', helper: 'Các con số dưới đây là ví dụ minh họa theo năm.' }, en: { title: 'What level of return fluctuation could you accept?', helper: 'These amounts are illustrative annual scenarios.' } },
  C1: { vi: { title: 'Quỹ dự phòng hiện tại có thể trang trải chi tiêu trong bao lâu?', helper: 'Không bao gồm khoản tiền dành cho kế hoạch đầu tư này.' }, en: { title: 'How long could your emergency fund cover expenses?', helper: 'Exclude the money set aside for this investment plan.' } },
  C2: { vi: { title: 'Khoản đầu tư này chiếm bao nhiêu phần trăm tài sản tài chính?', helper: 'Ước tính tỷ trọng so với tổng tài sản tài chính của bạn.' }, en: { title: 'What share of your financial assets is this investment?', helper: 'Estimate it as a share of your total financial assets.' } },
  C3: { vi: { title: 'Tình hình thu nhập và dòng tiền của bạn như thế nào?', helper: 'Chọn phương án phản ánh ổn định tài chính hiện tại.' }, en: { title: 'How would you describe your income and cash flow?', helper: 'Choose the option that best reflects your current financial stability.' } },
  H: { vi: { title: 'Bạn dự định đầu tư trong khoảng thời gian nào?', helper: 'Chân trời ngắn hơn một năm giới hạn mức rủi ro tối đa ở Cân bằng.' }, en: { title: 'What is your intended investment horizon?', helper: 'A horizon under one year caps the maximum risk level at Balanced.' } },
};
const profiles: { id: string; band: string; wording: Record<Locale, string> }[] = [
  { id: 'than_trong', band: '10–30%', wording: { vi: 'Biến động thấp hơn, ưu tiên bảo toàn vốn.', en: 'Lower volatility, with greater emphasis on capital preservation.' } },
  { id: 'can_bang', band: '40–60%', wording: { vi: 'Cân bằng giữa tăng trưởng và ổn định.', en: 'Balance growth and stability.' } },
  { id: 'tang_truong', band: '70–90%', wording: { vi: 'Chấp nhận mức biến động cao hơn.', en: 'Accept higher portfolio volatility.' } },
];
const titleFor = (id: string, lang: Locale) => questionLabels[id]?.[lang]?.title || '';

export function AdvisorPage() {
  const { t } = useTranslation(); const { locale } = useApp(); const navigate = useNavigate();
  const [questions, setQuestions] = useState<QuestionData | null>(null);
  const [answers, setAnswers] = useState<Record<string, number | string>>({});
  const [step, setStep] = useState(0);
  const [assessment, setAssessment] = useState<Assessment | null>(null);
  const [assessmentError, setAssessmentError] = useState('');
  const [chosen, setChosen] = useState('');
  const [acknowledged, setAcknowledged] = useState(false);
  const [amount, setAmount] = useState('100000000');
  const [busy, setBusy] = useState(false);
  const [formError, setFormError] = useState('');
  useEffect(() => { api<QuestionData>('/advisor/questions').then(setQuestions).catch(() => setQuestions(null)); }, []);
  useEffect(() => {
    const stored = sessionStorage.getItem('pvn-advisor-flow');
    if (!stored) return;
    try { const flow = JSON.parse(stored); setAnswers(flow.answers || {}); setStep(Math.min(9, Math.max(0, flow.step || 0))); setAmount(flow.amount || '100000000'); setChosen(flow.chosen || ''); setAcknowledged(Boolean(flow.acknowledged)); } catch { sessionStorage.removeItem('pvn-advisor-flow'); }
  }, []);
  useEffect(() => { sessionStorage.setItem('pvn-advisor-flow', JSON.stringify({ answers, step, amount, chosen, acknowledged })); }, [answers, step, amount, chosen, acknowledged]);
  useEffect(() => {
    if (step !== 8 || order.some((key) => answers[key] === undefined)) return;
    setAssessment(null); setAssessmentError('');
    api<Assessment>('/advisor/assess', { method: 'POST', body: JSON.stringify({ answers, locale }) }).then((result) => {
      setAssessment(result); if (!chosen || !result.choices.some((choice) => choice.profile === chosen && choice.enabled)) { setChosen(result.system_profile); setAcknowledged(false); }
    }).catch((error: Error) => setAssessmentError(error.message));
  }, [step, answers, locale]);

  const current = order[step];
  const options = useMemo(() => {
    if (!questions || !current) return [];
    if (current.startsWith('T')) return questions.tolerance[locale][Number(current[1]) - 1].map((text, index) => ({ value: index + 1, label: text }));
    if (current.startsWith('C')) return questions.capacity[locale][Number(current[1]) - 1].map((text, index) => ({ value: index + 1, label: text }));
    return Object.entries(questions.horizons).map(([value, label]) => ({ value, label: label[locale] }));
  }, [questions, current, locale]);

  if (!questions) return <div className="loading-block"><span className="eyebrow">ADVISOR / PROFILE QUESTIONS</span><span className="loading-bar" /></div>;
  const resetFlow = () => { setAnswers({}); setStep(0); setAssessment(null); setAssessmentError(''); setChosen(''); setAcknowledged(false); setAmount('100000000'); setFormError(''); sessionStorage.removeItem('pvn-advisor-flow'); };
  const answer = (value: number | string) => {
    const next = { ...answers, [current]: value };
    const index = order.indexOf(current);
    order.slice(index + 1).forEach((id) => delete next[id]);
    setAnswers(next); setAssessment(null); setChosen(''); setAcknowledged(false); setStep(step + 1);
  };
  const currentChoice = assessment?.choices.find((choice) => choice.profile === chosen);
  const goToAmount = () => { if (!chosen) return; if (currentChoice?.requires_ack && !acknowledged) { setFormError(t('advisor.ack')); return; } setFormError(''); setStep(9); };
  const submit = async (event: React.FormEvent) => {
    event.preventDefault(); setFormError('');
    const parsedAmount = parseMoneyInput(amount, locale);
    if (parsedAmount === null || !Number.isSafeInteger(parsedAmount) || parsedAmount < 1_000_000 || parsedAmount > 100_000_000_000) { setFormError(t('advisor.amountError')); return; }
    setBusy(true);
    try {
      const result = await api<PlanSnapshot>('/advisor/result', { method: 'POST', body: JSON.stringify({ answers, chosen_profile: chosen, acknowledged, amount_vnd: parsedAmount, locale }) });
      sessionStorage.setItem('pvn-advisor-result', JSON.stringify(result));
      navigate('/advisor/result', { state: { result } });
    } catch (error) { setFormError(error instanceof Error ? error.message : t('common.error')); }
    finally { setBusy(false); }
  };

  const progress = step < 8 ? (step + 1) / 8 * 100 : 100;
  return <div className="advisor-page">
    <section className="page-intro page-intro-rule"><div><p className="eyebrow">PROFILE / SUITABILITY · 08 QUESTIONS</p><h1>{t('advisor.title')}</h1><p>{t('advisor.intro')}</p></div><button className="icon-text-button" onClick={resetFlow}><RotateCcw size={14} />{t('advisor.restart')}</button></section>
    <div className="advisor-shell"><aside className="advisor-sidebar"><div className="advisor-progress-label"><span>{t('advisor.step')}</span><b className="mono">{String(Math.min(step + 1, 10)).padStart(2, '0')} / 10</b></div><div className="progress-track"><i style={{ width: `${progress}%` }} /></div><div className="wizard-steps">{order.map((id, index) => <div key={id} className={`wizard-step ${index < step ? 'complete' : index === step ? 'current' : ''}`}><span className="wizard-step-number">{index < step ? <Check size={13} /> : String(index + 1).padStart(2, '0')}</span><span>{id}</span><small>{id.startsWith('T') ? t('advisor.tolerance') : id.startsWith('C') ? t('advisor.capacity') : t('advisor.horizon')}</small></div>)}<div className={`wizard-step ${step >= 8 ? 'current' : ''}`}><span className="wizard-step-number">09</span><span>PROFILE</span><small>{t('advisor.review')}</small></div><div className={`wizard-step ${step >= 9 ? 'current' : ''}`}><span className="wizard-step-number">10</span><span>AMOUNT</span><small>{t('advisor.amount')}</small></div></div><div className="sidebar-footnote"><span className="eyebrow">DATA → METHOD → PLAN</span><p>{locale === 'vi' ? 'Câu trả lời được lưu trong snapshot riêng của kế hoạch; không dùng danh tính thật.' : 'Answers are stored only in the saved plan snapshot; no real identity is collected.'}</p></div></aside>
      <section className="wizard-card" aria-live="polite">
        {step < 8 && <><div className="question-meta"><span className="eyebrow">{current?.startsWith('T') ? '01 / RISK TOLERANCE' : current?.startsWith('C') ? '02 / FINANCIAL CAPACITY' : '03 / INVESTMENT HORIZON'}</span><span className="mono">{String(step + 1).padStart(2, '0')} / 08</span></div><h2 className="question-title">{titleFor(current, locale)}</h2><p className="question-helper">{questionLabels[current][locale].helper}</p><div className="answer-list">{options.map((option, index) => { const selected = answers[current] === option.value; return <button className={`answer-option ${selected ? 'selected' : ''}`} key={String(option.value)} onClick={() => answer(option.value)}><span className="answer-number">0{index + 1}</span><span className="answer-copy">{option.label}</span><span className="answer-radio">{selected ? <i /> : null}</span></button>; })}</div><div className="wizard-footer">{step > 0 ? <button className="button button-outline" onClick={() => setStep(step - 1)}><ArrowLeft size={15} />{t('common.back')}</button> : <Link className="text-link" to="/">{locale === 'vi' ? '← Về trang chủ' : '← Return home'}</Link>}<span className="wizard-hint">{locale === 'vi' ? 'Chọn một phương án để tiếp tục' : 'Select one option to continue'}</span></div></>}
        {step === 8 && <>{!assessment ? <div className="loading-block"><span className="eyebrow">SCORING / PROFILE REVIEW</span><span className="loading-bar" />{assessmentError && <p className="form-error">{assessmentError}</p>}</div> : <><div className="question-meta"><span className="eyebrow">04 / PROFILE REVIEW</span><span className="tag tag-outline">{locale === 'vi' ? 'Thuần xác định' : 'Deterministic'}</span></div><h2 className="question-title">{t('advisor.review')}</h2><div className="score-ribbon"><div><span className="eyebrow">TOLERANCE · T1–T4</span><strong className="mono">{assessment.scores.tolerance} / 12</strong><small>{questions.profiles[assessment.tolerance_profile][locale]}</small></div><div><span className="eyebrow">CAPACITY · C1–C3</span><strong className="mono">{assessment.scores.capacity} / 9</strong><small>{questions.profiles[assessment.capacity_profile][locale]}</small></div><div><span className="eyebrow">{t('advisor.system')}</span><strong>{questions.profiles[assessment.system_profile][locale]}</strong><small>{questions.horizons[assessment.horizon][locale]}</small></div></div>{assessment.warnings.length > 0 && <div className="warning-stack">{assessment.warnings.map((code) => <div className="warning-callout" key={code}><span>{code}</span><p>{assessment.warning_copy[code] || t(`advisor.warnings.${code}`)}</p></div>)}</div>}<div className="profile-choice-heading"><span className="eyebrow">{t('advisor.choose')}</span><span className="eyebrow">{locale === 'vi' ? 'DẢI TÀI SẢN RỦI RO' : 'RISKY ASSET BAND'}</span></div><div className="profile-choice-list">{profiles.map((profile) => { const allowed = assessment.choices.find((item) => item.profile === profile.id); return <button type="button" key={profile.id} disabled={!allowed?.enabled} aria-pressed={chosen === profile.id} className={`profile-choice ${chosen === profile.id ? 'selected' : ''} ${!allowed?.enabled ? 'disabled' : ''}`} onClick={() => { if (!allowed?.enabled) return; setChosen(profile.id); setAcknowledged(false); setFormError(''); }}><span className="profile-choice-icon">{!allowed?.enabled ? <LockKeyhole size={15} /> : chosen === profile.id ? <Check size={15} /> : <span />}</span><span className="profile-choice-copy"><b>{questions.profiles[profile.id][locale]}</b><small>{profile.wording[locale]}{allowed?.reason ? ` · ${locale === 'vi' ? 'Không khả dụng' : 'Unavailable'}` : ''}</small></span><span className="profile-band mono">{profile.band}</span></button>; })}</div>{currentChoice?.requires_ack && <label className="ack-check"><input type="checkbox" checked={acknowledged} onChange={(event) => setAcknowledged(event.target.checked)} /><span>{assessment.acknowledgement}<small>ack-v1 · {locale === 'vi' ? 'ghi nhận cùng thời điểm lưu kế hoạch' : 'recorded with the saved plan timestamp'}</small></span></label>}<div className="wizard-footer"><button className="button button-outline" onClick={() => setStep(7)}><ArrowLeft size={15} />{t('common.back')}</button><button className="button button-dark" onClick={goToAmount} disabled={!chosen || Boolean(currentChoice?.requires_ack && !acknowledged)}>{t('advisor.continueAmount')}<ArrowRight size={15} /></button></div>{formError && <p className="form-error" role="alert">{formError}</p>}</>}</>}
        {step === 9 && <><div className="question-meta"><span className="eyebrow">05 / PLAN INPUT</span><span className="tag tag-outline">{questions.profiles[chosen][locale]}</span></div><h2 className="question-title">{t('advisor.amount')}</h2><p className="question-helper">{t('advisor.amountHelp')}</p><form onSubmit={submit}><label htmlFor="amount-vnd" className="eyebrow field-label">{locale === 'vi' ? 'SỐ TIỀN (VND)' : 'AMOUNT (VND)'}</label><div className="amount-input-wrap"><input id="amount-vnd" className="amount-input mono" inputMode="numeric" type="text" autoComplete="off" aria-describedby="amount-help" value={amount} onChange={(event) => setAmount(event.target.value)} onBlur={() => setAmount((value) => formatMoneyInput(value, locale))} required /><span>₫</span></div><div id="amount-help" className="amount-value-text">{(() => { const parsed = parseMoneyInput(amount, locale); return parsed !== null ? money(parsed, locale) : '—'; })()}</div><div className="input-disclaimer"><span className="hollow-dot" />{locale === 'vi' ? 'Số tiền này chỉ dùng để minh họa rủi ro và đơn vị phân bổ. Website không thực hiện giao dịch.' : 'This amount only illustrates risk and allocation units. The site does not place trades.'}</div>{formError && <p className="form-error" role="alert">{formError}</p>}<div className="wizard-footer"><button type="button" className="button button-outline" onClick={() => setStep(8)}><ArrowLeft size={15} />{t('common.back')}</button><button type="submit" className="button button-dark" disabled={busy}>{busy ? t('common.loading') : <>{t('advisor.result')}<ArrowRight size={15} /></>}</button></div></form></>}
      </section>
    </div>
    <p className="page-disclaimer">{t('common.disclaimer')}</p>
  </div>;
}

export function AdvisorResultPage() {
  const { t } = useTranslation(); const { locale } = useApp(); const navigate = useNavigate(); const location = useLocation();
  const [result, setResult] = useState<PlanSnapshot | null>((location.state as { result?: PlanSnapshot } | null)?.result || null);
  const [saving, setSaving] = useState(false); const [error, setError] = useState('');
  useEffect(() => { if (!result) { const raw = sessionStorage.getItem('pvn-advisor-result'); if (raw) try { setResult(JSON.parse(raw)); } catch { setResult(null); } } }, [result]);
  const save = async () => {
    if (saving || !result) return; setSaving(true); setError('');
    try {
      const flow = JSON.parse(sessionStorage.getItem('pvn-advisor-flow') || '{}');
      const saved = await api<PlanSnapshot>('/plans', { method: 'POST', body: JSON.stringify({ answers: flow.answers, chosen_profile: flow.chosen, acknowledged: flow.acknowledged, amount_vnd: parseMoneyInput(String(flow.amount || ''), locale), locale }) });
      sessionStorage.removeItem('pvn-advisor-flow'); sessionStorage.removeItem('pvn-advisor-result'); navigate(`/plans/${encodeURIComponent(saved.code || '')}`, { replace: true, state: { plan: saved } });
    } catch (e) { setError(e instanceof Error ? e.message : t('common.error')); } finally { setSaving(false); }
  };
  if (!result) return <div className="empty-state"><span className="eyebrow">RESULT / NO SNAPSHOT</span><h1>{t('common.noData')}</h1><Link className="button button-dark" to="/advisor">{t('nav.start')}</Link></div>;
  return <div className="advisor-result-page"><div className="result-actions no-print"><Link className="text-link" to="/advisor"><ArrowLeft size={14} />{t('advisor.restart')}</Link><button className="button button-dark" onClick={() => void save()} disabled={saving}>{saving ? t('common.loading') : <>{t('common.save')}<ArrowRight size={15} /></>}</button></div>{error && <p className="form-error" role="alert">{error}</p>}<PlanReport plan={result} mode="result" /></div>;
}
