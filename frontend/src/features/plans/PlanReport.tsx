import { useMemo } from 'react';
import { AlertTriangle, CalendarDays, CheckCircle2, CircleHelp, Info } from 'lucide-react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useApp } from '../../app/AppContext';
import { dateLabel, money, number, percent, points, volatilityLabel } from '../../format';
import type { Locale, PlanSnapshot } from '../../types';

const assetOrder = ['co_phieu', 'bat_dong_san', 'etf', 'vang', 'tien_gui', 'trai_phieu'];
const assetNames: Record<string, Record<Locale, string>> = {
  co_phieu: { vi: 'Cổ phiếu', en: 'Stocks' }, bat_dong_san: { vi: 'Bất động sản', en: 'Real-estate stocks' }, etf: { vi: 'ETF', en: 'ETF' }, vang: { vi: 'Vàng SJC', en: 'SJC gold' }, tien_gui: { vi: 'Tiền gửi 12 tháng', en: '12-month deposit' }, trai_phieu: { vi: 'Trái phiếu (quỹ mở)', en: 'Bonds (open-ended fund)' },
};
const profileNames: Record<string, Record<Locale, string>> = {
  than_trong: { vi: 'Thận trọng', en: 'Conservative' }, can_bang: { vi: 'Cân bằng', en: 'Balanced' }, tang_truong: { vi: 'Tăng trưởng', en: 'Growth' },
};
const horizonNames: Record<string, Record<Locale, string>> = {
  ngan_han: { vi: 'Ngắn hạn (dưới 1 năm)', en: 'Short term (under 1 year)' }, trung_han: { vi: 'Trung hạn (1–5 năm)', en: 'Medium term (1–5 years)' }, dai_han: { vi: 'Dài hạn (trên 5 năm)', en: 'Long term (over 5 years)' },
};
const answerLabels: Record<string, Record<Locale, string>> = {
  T1: { vi: 'Phản ứng khi giảm giá', en: 'Response to a price decline' }, T2: { vi: 'Kinh nghiệm đầu tư', en: 'Investment experience' }, T3: { vi: 'Ưu tiên đầu tư', en: 'Investment priority' }, T4: { vi: 'Mức dao động chấp nhận', en: 'Acceptable fluctuation' }, C1: { vi: 'Quỹ dự phòng', en: 'Emergency reserve' }, C2: { vi: 'Tỷ trọng tài sản', en: 'Share of financial assets' }, C3: { vi: 'Ổn định dòng tiền', en: 'Cash-flow stability' }, H: { vi: 'Chân trời đầu tư', en: 'Investment horizon' },
};
function assetLabel(key: string, locale: Locale) { return assetNames[key]?.[locale] || key; }
function unitLabel(value: string, locale: Locale) {
  if (value === 'theo số tiền') return locale === 'vi' ? 'theo số tiền' : 'by amount';
  if (value === 'cổ phiếu') return locale === 'vi' ? 'cổ phiếu' : 'shares';
  if (value.startsWith('chứng chỉ')) {
    const lot = value.match(/lô\s*(\d+)/i)?.[1] || '100';
    return locale === 'vi' ? `chứng chỉ · lô ${lot}` : `units · lot ${lot}`;
  }
  if (value === 'lượng') return locale === 'vi' ? 'lượng' : 'tael';
  return locale === 'vi' ? 'chỉ · 1/10 lượng' : 'chi · 1/10 tael';
}
function vehicle(line: PlanSnapshot['execution']['lines'][number], locale: Locale) {
  if (line.asset_class === 'co_phieu') return locale === 'vi' ? 'Quỹ cổ phiếu đại diện VN-Index' : 'VN-Index proxy equity fund';
  if (line.asset_class === 'bat_dong_san') return locale === 'vi' ? `Cổ phiếu ${line.symbol} · rổ BĐS nghiên cứu` : `${line.symbol} stock · research real-estate basket`;
  if (line.asset_class === 'etf') return 'ETF E1VFVN30';
  if (line.asset_class === 'vang') return locale === 'vi' ? 'Vàng miếng SJC' : 'SJC gold bar';
  if (line.asset_class === 'tien_gui') return locale === 'vi' ? (line.vehicle.includes('chờ') ? 'Tiền mặt chờ đầu tư' : 'Tiền gửi có kỳ hạn 12 tháng') : (line.vehicle.includes('chờ') ? 'Cash awaiting investment' : '12-month bank deposit');
  return locale === 'vi' ? 'Chứng chỉ quỹ trái phiếu mở · proxy NAV quỹ DCBF' : 'Open-ended bond fund units · DCBF NAV proxy';
}
function noUnitReason(line: PlanSnapshot['execution']['lines'][number], locale: Locale, rules: Record<string, unknown>): string {
  if (!line.note) return '';
  const shareLot = Number(rules.share_lot ?? 100);
  const etfLot = Number(rules.etf_lot ?? 100);
  const fundMin = Number(rules.fund_min_vnd ?? 100_000);
  if (line.asset_class === 'bat_dong_san') return locale === 'vi' ? `Không đủ một lô ${number(shareLot, locale, 0)} cổ phiếu ${line.symbol} tại giá tham chiếu.` : `Below one ${number(shareLot, locale, 0)}-share lot of ${line.symbol} at the reference price.`;
  if (line.asset_class === 'etf') return locale === 'vi' ? `Không đủ một lô ETF (${number(etfLot, locale, 0)} chứng chỉ) tại giá tham chiếu.` : `Below one ${number(etfLot, locale, 0)}-unit ETF lot at the reference price.`;
  if (line.asset_class === 'vang') return locale === 'vi' ? `Không đủ một ${line.unit_label} vàng SJC tại giá tham chiếu.` : `Below one ${unitLabel(line.unit_label, locale)} of SJC gold at the reference price.`;
  if (line.asset_class === 'tien_gui') return locale === 'vi' ? 'Nhận phần tiền lẻ từ các đơn vị không thể chia.' : 'Receives indivisible remainders from other allocations.';
  return locale === 'vi' ? `Mục tiêu dưới mức tối thiểu ${money(fundMin, locale)} của quỹ.` : `Target is below the fund minimum of ${money(fundMin, locale)}.`;
}

export function PlanReport({ plan, mode = 'detail' }: { plan: PlanSnapshot; mode?: 'result' | 'detail' | 'shared' | 'print' }) {
  const { t } = useTranslation();
  const { locale } = useApp();
  const metrics = plan.metrics || {};
  const risk = plan.risk_vnd;
  const toleranceProfile = profileNames[plan.tolerance_profile]?.[locale] || plan.tolerance_profile;
  const capacityProfile = profileNames[plan.capacity_profile]?.[locale] || plan.capacity_profile;
  const systemProfile = profileNames[plan.system_profile]?.[locale] || plan.system_profile;
  const selectedProfile = profileNames[plan.chosen_profile]?.[locale] || plan.chosen_profile;
  const horizon = horizonNames[plan.horizon]?.[locale] || plan.horizon;
  const underDeposit = Number(metrics.annualised_return) < Number(metrics.deposit_annualised_return);
  const narrative = useMemo(() => plan.why?.[locale] || [], [plan.why, locale]);
  const rolling = risk?.windows_12m;
  const dataThrough = plan.manifest_data_through || {};
  const amount = plan.amount_vnd || 0;
  const executionRules = plan.execution_rules || {};
  const deviationLimit = Number(executionRules.re_deviation_threshold_pp ?? 2);
  const driftLimit = Number(executionRules.early_rebalance_threshold_pp ?? 5);
  const metricRows = [
    { label: locale === 'vi' ? 'Lợi suất năm hóa' : 'Annualised return', value: percent(Number(metrics.annualised_return), locale), tone: underDeposit ? 'down' : 'neutral', sub: '' },
    { label: locale === 'vi' ? 'Tiền gửi cùng kỳ' : 'Deposit, same period', value: percent(Number(metrics.deposit_annualised_return), locale), tone: 'neutral', sub: '' },
    { label: locale === 'vi' ? 'Biến động năm hóa' : 'Annualised volatility', value: percent(Number(metrics.volatility), locale), tone: 'neutral', sub: volatilityLabel(Number(metrics.volatility), locale) },
    { label: 'Sharpe', value: number(Number(metrics.sharpe_ratio), locale, 3), tone: 'neutral', sub: locale === 'vi' ? 'đã trừ lãi tiền gửi' : 'less deposit rate' },
    { label: 'Max drawdown', value: percent(Number(metrics.max_drawdown), locale), tone: 'down', sub: '' },
    { label: locale === 'vi' ? 'Turnover bình quân' : 'Average turnover', value: percent(Number(metrics.avg_turnover), locale), tone: 'neutral', sub: '' },
  ];
  const warningText = (code: string) => code === 'W1'
    ? (locale === 'vi' ? `Mức chịu đựng rủi ro cao hơn khả năng tài chính; hệ thống dùng ${capacityProfile}.` : `Risk tolerance exceeds financial capacity; the system uses ${capacityProfile}.`)
    : t(`advisor.warnings.${code}`);

  return <div className={`plan-report plan-report-${mode}`}>
    <header className="plan-report-header">
      <div>
        <p className="eyebrow">IPS / PORTFOLIOVN {plan.code ? `· ${plan.code}` : '· RESULT PREVIEW'}</p>
        <h1>{mode === 'result' ? t('advisor.result') : mode === 'shared' ? (locale === 'vi' ? 'Kế hoạch được chia sẻ' : 'Shared plan') : t('plan.title')}</h1>
        <p className="plan-report-deck">{locale === 'vi' ? 'Một snapshot phân bổ dựa trên hồ sơ, khoản tiền và phiên bản nghiên cứu được ghi tại thời điểm tạo.' : 'An allocation snapshot tied to your profile, amount and research version at creation.'}</p>
        <div className="plan-id-row"><span>{plan.code || (locale === 'vi' ? 'Chưa lưu kế hoạch' : 'Plan not yet saved')}</span><span>{plan.created_at ? dateLabel(plan.created_at.slice(0, 10), locale) : 'Preview'}</span><span>{plan.result_version_label}</span></div>
      </div>
      <div className="plan-method-stamp"><span>METHOD</span><strong>RP</strong><small>Risk Parity</small></div>
    </header>
    {plan.outdated && <div className="outdated-banner"><Info size={16} /><span>{t('plan.outdated')}</span></div>}
    {narrative.length > 0 && <section className="plan-narrative"><span className="eyebrow">{locale === 'vi' ? 'TÓM TẮT HỒ SƠ' : 'PROFILE SUMMARY'}</span>{narrative.map((text, index) => <p key={index}>{text}</p>)}</section>}

    <section className="ips-section"><div className="ips-section-heading"><span className="ips-section-number">01</span><div><span className="eyebrow">INVESTOR PROFILE</span><h2>{locale === 'vi' ? 'Hồ sơ và mục tiêu' : 'Profile and objective'}</h2></div></div>
      <div className="profile-summary-grid">
        <div><span className="eyebrow">{locale === 'vi' ? 'HỒ SƠ ĐƯỢC CHỌN' : 'SELECTED PROFILE'}</span><strong>{selectedProfile}</strong><small>{locale === 'vi' ? 'Dải tài sản rủi ro' : 'Risky-asset band'} · {plan.chosen_profile === 'than_trong' ? '10–30%' : plan.chosen_profile === 'can_bang' ? '40–60%' : '70–90%'}</small></div>
        <div><span className="eyebrow">{locale === 'vi' ? 'CHÂN TRỜI' : 'HORIZON'}</span><strong>{horizon}</strong><small>{locale === 'vi' ? 'Giới hạn hệ thống' : 'System cap'} · {profileNames[plan.horizon_cap]?.[locale] || plan.horizon_cap}</small></div>
        <div><span className="eyebrow">{locale === 'vi' ? 'SỐ TIỀN MINH HỌA' : 'ILLUSTRATIVE AMOUNT'}</span><strong className="mono">{money(amount, locale)}</strong><small>{locale === 'vi' ? 'Không phải lệnh giao dịch' : 'Not a trade order'}</small></div>
        <div><span className="eyebrow">{locale === 'vi' ? 'PHƯƠNG PHÁP' : 'METHOD'}</span><strong>Risk Parity</strong><small>{locale === 'vi' ? 'Tỷ trọng đang active' : 'Active result weights'}</small></div>
      </div>
    </section>

    <section className="ips-section"><div className="ips-section-heading"><span className="ips-section-number">02</span><div><span className="eyebrow">SUITABILITY / TRACE</span><h2>{locale === 'vi' ? 'Điểm, câu trả lời và cảnh báo' : 'Scores, answers and warnings'}</h2></div></div>
      <div className="score-grid">
        <div className="score-cell"><span className="eyebrow">TOLERANCE · T1–T4</span><strong className="mono">{plan.scores?.tolerance} / 12</strong><small>{toleranceProfile}</small></div>
        <div className="score-cell"><span className="eyebrow">CAPACITY · C1–C3</span><strong className="mono">{plan.scores?.capacity} / 9</strong><small>{capacityProfile}</small></div>
        <div className="score-cell"><span className="eyebrow">SYSTEM PROFILE</span><strong>{systemProfile}</strong><small>{locale === 'vi' ? 'Mức thấp nhất trong chịu đựng / khả năng / giới hạn chân trời' : 'Lowest of tolerance / capacity / horizon cap'}</small></div>
        <div className="score-cell"><span className="eyebrow">CHOSEN PROFILE</span><strong>{selectedProfile}</strong><small>{plan.choice_type === 'one_level_higher' ? (locale === 'vi' ? 'Cao hơn hệ thống một mức' : 'One level above system') : plan.choice_type === 'lower' ? (locale === 'vi' ? 'Mức thấp hơn tự chọn' : 'Lower level chosen') : (locale === 'vi' ? 'Theo mức hệ thống' : 'System level')}</small></div>
      </div>
      {plan.answers && <div className="answer-audit-grid">{['T1','T2','T3','T4','C1','C2','C3','H'].map((id) => <div className="answer-audit" key={id}><span className="mono">{id}</span><span>{answerLabels[id][locale]}</span><b>{plan.answer_text?.[locale]?.[id] || (id === 'H' ? horizonNames[String(plan.answers?.[id])]?.[locale] : `${plan.answers?.[id]} / 3`)}</b></div>)}</div>}
      {plan.warnings?.length > 0 && <div className="warning-stack print-warning">{plan.warnings.map((code) => <div className="warning-callout" key={code}><AlertTriangle size={15} /><span className="mono">{code}</span><p>{warningText(code)}</p></div>)}</div>}
      {plan.acknowledgement?.version && <div className="acknowledgement-note"><CheckCircle2 size={16} /><div><strong>{plan.acknowledgement.version}</strong><p>{plan.acknowledgement.text}</p><small>{plan.acknowledgement.accepted_at}</small></div></div>}
    </section>

    <section className="ips-section"><div className="ips-section-heading"><span className="ips-section-number">03</span><div><span className="eyebrow">ALLOCATION / TARGET</span><h2>{t('plan.target')}</h2></div><span className="target-band-tag">{locale === 'vi' ? 'Dải rủi ro' : 'Risk band'} · {plan.chosen_profile === 'than_trong' ? '10–30%' : plan.chosen_profile === 'can_bang' ? '40–60%' : '70–90%'}</span></div>
      <div className="allocation-bars">{assetOrder.map((key) => {
        const targetWeight = Number(plan.weights?.[key] || 0);
        const executedVnd = Number(plan.execution?.executed_vnd?.[key] || 0);
        const targetVnd = Number(plan.targets_vnd?.[key] || 0);
        const executedWeight = amount ? executedVnd / amount : 0;
        return <div className="allocation-bar-row" key={key}><div className="allocation-bar-label"><span>{assetLabel(key, locale)}</span><b className="mono">{percent(targetWeight, locale)}</b></div><div className="allocation-track"><i className="allocation-target" style={{ width: `${Math.max(0.7, targetWeight * 100)}%` }} /><i className="allocation-executed" style={{ width: `${Math.max(0.7, executedWeight * 100)}%` }} /></div><div className="allocation-value-row"><span>{locale === 'vi' ? 'Mục tiêu' : 'Target'} · <b className="mono">{money(targetVnd, locale)}</b></span><span>{locale === 'vi' ? 'Thực hiện' : 'Executed'} · <b className="mono">{money(executedVnd, locale)}</b></span><span className={Number(plan.execution?.deviation_pp?.[key] || 0) > 0 ? 'up' : Number(plan.execution?.deviation_pp?.[key] || 0) < 0 ? 'down' : 'flat'}>{points(Number(plan.execution?.deviation_pp?.[key] || 0), locale, 2)}</span></div></div>;
      })}</div>
      <div className="allocation-legend"><span><i className="legend-target" />{locale === 'vi' ? 'Mục tiêu Risk Parity' : 'Risk Parity target'}</span><span><i className="legend-executed" />{locale === 'vi' ? 'Phân bổ theo đơn vị thực hiện' : 'Executable allocation'}</span></div>
      {plan.execution?.deviation_warning && <div className="deviation-warning"><AlertTriangle size={16} /><div><strong>{locale === 'vi' ? `Lệch tối đa ${number(plan.execution.deviation_warning.max_deviation_pp, locale, 2)} điểm %` : `Maximum deviation ${number(plan.execution.deviation_warning.max_deviation_pp, locale, 2)} pp`}</strong><p>{locale === 'vi' ? `Lớp ${assetLabel(plan.execution.deviation_warning.asset_class, locale)}. Số tiền tối thiểu để lệch không quá ${number(deviationLimit, locale, 0)} điểm %: ${plan.execution.deviation_warning.min_amount_vnd ? money(plan.execution.deviation_warning.min_amount_vnd, locale) : 'trên 2 tỷ ₫'} (tham khảo).` : `Asset class ${assetLabel(plan.execution.deviation_warning.asset_class, locale)}. Minimum amount for deviation of ${number(deviationLimit, locale, 0)} pp or less: ${plan.execution.deviation_warning.min_amount_vnd ? money(plan.execution.deviation_warning.min_amount_vnd, locale) : 'over VND 2bn'} (indicative).`}</p></div></div>}
    </section>

    <section className="ips-section"><div className="ips-section-heading"><span className="ips-section-number">04</span><div><span className="eyebrow">EXECUTION / MONTH-END REFERENCE</span><h2>{t('plan.execution')}</h2></div></div>
      <div className="execution-note"><Info size={15} /><span>{locale === 'vi' ? `Giá tham chiếu cuối tháng ${plan.reference_month} (tạm tính). Không phải giá khớp; chưa gồm phí và thuế.` : `Month-end reference prices for ${plan.reference_month} (provisional). Not execution prices; fees and taxes excluded.`} {t('common.researchProxy')}</span></div>
      <div className="table-scroll"><table className="data-table execution-table"><thead><tr><th>{locale === 'vi' ? 'Lớp / phương tiện' : 'Class / vehicle'}</th><th className="align-right">{locale === 'vi' ? 'Đơn vị' : 'Units'}</th><th className="align-right">{locale === 'vi' ? 'Giá tham chiếu' : 'Reference price'}</th><th className="align-right">{locale === 'vi' ? 'Mục tiêu' : 'Target'}</th><th className="align-right">{locale === 'vi' ? 'Số tiền' : 'Amount'}</th><th className="align-right">{locale === 'vi' ? 'Lệch' : 'Deviation'}</th></tr></thead><tbody>{(plan.execution?.lines || []).map((line, index) => {
        const reason = noUnitReason(line, locale, executionRules);
        return <tr key={`${line.asset_class}-${line.symbol || line.vehicle}-${index}`}><td><b>{assetLabel(line.asset_class, locale)}</b><small>{vehicle(line, locale)}{reason && <em className="execution-reason">{reason}</em>}</small></td><td className="align-right mono">{line.unit_label === 'theo số tiền' ? money(line.units, locale) : `${number(line.units, locale, 0)} ${unitLabel(line.unit_label, locale)}`}</td><td className="align-right mono">{line.unit_price ? money(line.unit_price, locale) : '—'}</td><td className="align-right mono">{money(line.target, locale)}</td><td className="align-right mono"><b>{money(line.amount, locale)}</b></td><td className="align-right mono">{points(line.deviation_pp, locale, 2)}</td></tr>;
      })}</tbody><tfoot><tr><th colSpan={4}>{locale === 'vi' ? 'Tổng phân bổ' : 'Total allocated'}</th><th className="align-right mono">{money(plan.execution?.total_vnd || 0, locale)}</th><th className="align-right"><CheckCircle2 size={14} /></th></tr></tfoot></table></div>
      <div className="leftover-grid"><span className="eyebrow">{locale === 'vi' ? 'PHẦN LẺ / DƯ CHUYỂN SANG TIỀN GỬI' : 'LEFTOVERS / ROLLED INTO DEPOSIT'}</span>{assetOrder.filter((key) => key !== 'tien_gui' && Number(plan.execution?.leftovers_vnd?.[key] || 0) > 0).map((key) => <span key={key}>{assetLabel(key, locale)} · {money(Number(plan.execution.leftovers_vnd[key]), locale)}</span>)}<strong>{locale === 'vi' ? 'Tổng tiền được phân bổ chính xác' : 'Total allocated exactly'} · {money(plan.execution?.total_vnd || 0, locale)}</strong></div>
    </section>

    <section className="ips-section"><div className="ips-section-heading"><span className="ips-section-number">05</span><div><span className="eyebrow">RISK / HISTORICAL OBSERVATIONS</span><h2>{t('plan.risk')}</h2></div><Link className="method-tooltip" to="/analysis/methodology" aria-label={t('analysis.method')}><CircleHelp size={15} /></Link></div>
      <div className="risk-metric-row"><div><span className="eyebrow">{t('plan.drawdown')}</span><strong className="mono down">{percent(risk?.max_drawdown ?? 0, locale)}</strong><small>{locale === 'vi' ? `Tổn thất minh họa: ${money(risk?.drawdown_loss_vnd ?? 0, locale)}` : `Illustrative loss: ${money(risk?.drawdown_loss_vnd ?? 0, locale)}`}</small></div><div><span className="eyebrow">{t('plan.remaining')}</span><strong className="mono">{money(risk?.remaining_vnd ?? amount, locale)}</strong><small>{locale === 'vi' ? 'Từ khoản ban đầu sau drawdown lịch sử lớn nhất' : 'Initial amount after maximum historical drawdown'}</small></div><div><span className="eyebrow">{locale === 'vi' ? 'CỬA SỔ 12 THÁNG ÂM' : 'NEGATIVE 12-MONTH WINDOWS'}</span><strong className="mono">{rolling?.negative_count ?? '—'} <small>/ {rolling?.count ?? '—'}</small></strong><small>{locale === 'vi' ? 'cửa sổ liên tục trong giai đoạn kiểm tra' : 'rolling windows in the test period'}</small></div></div>
      <div className="rolling-range"><div className="rolling-range-head"><span className="eyebrow">{t('plan.rolling')}</span><span className="mono">{rolling?.count ?? 0} {locale === 'vi' ? 'cửa sổ' : 'windows'}</span></div><div className="range-stat-grid"><div><small>{locale === 'vi' ? 'Tối thiểu' : 'Minimum'}</small><b className="mono down">{percent(rolling?.min ?? 0, locale)}</b><span>{money(rolling?.min_vnd ?? 0, locale)}</span></div><div><small>{locale === 'vi' ? 'Trung vị' : 'Median'}</small><b className="mono">{percent(rolling?.median ?? 0, locale)}</b><span>{money(rolling?.median_vnd ?? 0, locale)}</span></div><div><small>{locale === 'vi' ? 'Tối đa' : 'Maximum'}</small><b className="mono up">{percent(rolling?.max ?? 0, locale)}</b><span>{money(rolling?.max_vnd ?? 0, locale)}</span></div></div></div>
      <div className="dot-strip-wrap"><span className="eyebrow">{locale === 'vi' ? '12 THÁNG GẦN NHẤT · LỢI SUẤT BACKTEST' : 'LAST 12 MONTHS · BACKTEST RETURNS'}</span><div className="dot-strip">{risk?.last_12_months?.map((row) => <div className={`dot-month ${row.return < 0 ? 'negative' : 'positive'}`} key={row.month} title={`${row.month}: ${percent(row.return, locale)}`}><i /><span>{row.month.slice(5)}</span></div>)}</div></div>
      <div className="stress-grid">{[{ id: 'S1', data: risk?.stress_s1, title: locale === 'vi' ? 'VN-Index giảm mạnh nhất' : 'Worst VN-Index month', note: locale === 'vi' ? 'Trong các tháng của panel nghiên cứu.' : 'Among months of the research panel.' }, { id: 'S2', data: risk?.stress_s2, title: locale === 'vi' ? 'Tháng giảm notable gần nhất' : 'Most recent notable down month', note: locale === 'vi' ? 'Tháng stress áp lên tỷ trọng Risk Parity hiện tại; không phải dự báo.' : 'Stress month applied to current Risk Parity weights; not a forecast.' }].map((item) => <div className="stress-card" key={item.id}><span className="eyebrow">{item.id} / {item.title}</span><strong className="mono">{item.data?.month || '—'}</strong><span className={Number(item.data?.portfolio_return || 0) < 0 ? 'down' : 'up'}>{percent(item.data?.portfolio_return || 0, locale)} · {money(item.data?.change_vnd || 0, locale)}</span><small>{item.note}</small></div>)}</div>
      <p className="risk-formula">{locale === 'vi' ? 'Công thức: khoản tiền × lợi suất/drawdown lịch sử của danh mục Risk Parity đã chọn. Cửa sổ 12 tháng là tích lũy liên tục; giá trị theo VND được làm tròn half-up.' : 'Formula: amount × historical return/drawdown for the selected Risk Parity portfolio. 12-month windows compound monthly returns; VND uses half-up rounding.'}</p><p className="risk-disclaimer">{t('common.disclaimer')}</p>
    </section>

    <section className="ips-section"><div className="ips-section-heading"><span className="ips-section-number">06</span><div><span className="eyebrow">REBALANCING / DRIFT</span><h2>{t('plan.rebalance')}</h2></div></div>
      <div className="rebalance-card"><CalendarDays size={18} /><div><span className="eyebrow">{locale === 'vi' ? 'NGÀY DỰ KIẾN TIẾP THEO' : 'NEXT SCHEDULED DATE'}</span><strong className="mono">{plan.rebalance_date ? dateLabel(plan.rebalance_date, locale) : '—'}</strong><small>{locale === 'vi' ? 'Nếu rơi vào ngày nghỉ, chuyển sang ngày làm việc kế tiếp.' : 'If it falls on a non-business day, move to the next business day.'}</small></div><span className="tag tag-outline">{horizon}</span></div>
      {plan.drift?.available ? <div className={`drift-card ${plan.drift.rebalance_early ? 'drift-warning' : ''}`}><div><span className="eyebrow">{locale === 'vi' ? 'DRIFT THEO DỮ LIỆU SAU NGÀY LẬP' : 'POST-PLAN DATA DRIFT'}</span><strong>{locale === 'vi' ? plan.drift.message_vi : plan.drift.message_en}</strong></div><span className="mono">{points(Number(plan.drift.max_abs_drift_pp || 0), locale)}</span><p>{locale === 'vi' ? `Drift trên ${number(driftLimit, locale, 0)} điểm %: xem xét tái cân bằng sớm.` : `Drift above ${number(driftLimit, locale, 0)} pp: consider rebalancing early.`}</p></div> : <div className="drift-card"><Info size={15} /><span>{locale === 'vi' ? plan.drift?.message_vi || t('plan.noLaterData') : plan.drift?.message_en || t('plan.noLaterData')}</span></div>}
    </section>

    <section className="ips-section"><div className="ips-section-heading"><span className="ips-section-number">07</span><div><span className="eyebrow">BACKTEST / RESEARCH METRICS</span><h2>{t('plan.metrics')}</h2></div></div>
      <div className="metric-card-grid">{metricRows.map((row) => <div className="metric-card" key={row.label}><span className="eyebrow">{row.label}</span><strong className={`mono ${row.tone}`}>{row.value}</strong>{row.sub && <small>{row.sub}</small>}</div>)}</div>
      <div className={`benchmark-result ${underDeposit ? 'under-deposit' : ''}`}><span className="eyebrow">{locale === 'vi' ? 'SO VỚI TIỀN GỬI 12 THÁNG CÙNG GIAI ĐOẠN' : 'VS 12-MONTH DEPOSIT OVER THE SAME PERIOD'}</span><strong>{underDeposit ? t('analysis.depositUnder') : (locale === 'vi' ? 'Lợi suất năm hóa danh mục không thấp hơn tiền gửi trong tổng hợp giai đoạn này.' : 'The portfolio annualised return was not below deposits in this summary.')}</strong><p>{locale === 'vi' ? 'Không gọi số liệu backtest là lợi nhuận kỳ vọng. Metric được đọc nguyên từ performance_summary.csv; không tính lại.' : 'Backtest figures are not “expected returns.” Metrics are read as-is from performance_summary.csv, not recalculated.'}</p><small>{String(metrics.start)} — {String(metrics.end)} · {metrics.n_months} {locale === 'vi' ? 'tháng' : 'months'}</small></div>
    </section>

    <section className="ips-section"><div className="ips-section-heading"><span className="ips-section-number">08</span><div><span className="eyebrow">PROVENANCE / VERSION / TESTS</span><h2>{locale === 'vi' ? 'Phương pháp và dữ liệu' : 'Method and data'}</h2></div></div>
      <div className="method-note-grid"><div className="method-note"><span className="eyebrow">METHOD / WHY RISK PARITY</span><p>{locale === 'vi' ? 'Risk Parity được chọn theo cơ sở lý thuyết (cân bằng đóng góp rủi ro, Maillard, Roncalli & Teïletche 2010; không cần dự báo lợi nhuận), không phải vì Sharpe backtest cao nhất. Tỷ trọng nhóm rủi ro do dải khẩu vị quyết định (thiết kế hai tầng). Explore cho thấy không phương pháp nào khác biệt có ý nghĩa thống kê.' : 'Risk Parity is selected on theoretical grounds (equal risk contributions, Maillard, Roncalli & Teïletche 2010; no return forecasts needed), not because it has the highest backtest Sharpe. The risky-asset share is set by the profile band (two-tier design). Explore shows no method differs significantly.'}</p><Link to="/analysis/compare" className="text-link">{locale === 'vi' ? 'Mở so sánh 7 phương pháp' : 'Compare seven methods'}<span>↗</span></Link></div>
        <div className="method-note"><span className="eyebrow">VERSION / SNAPSHOT</span><p>{plan.result_version_label}</p><p>{locale === 'vi' ? 'Tháng tham chiếu' : 'Reference month'} · {plan.reference_month}</p><p>{locale === 'vi' ? 'Tháng tạm tính' : 'Provisional month'} · {plan.manifest_provisional_month || '—'}</p></div>
        <div className="method-note"><span className="eyebrow">DATA THROUGH / SOURCE</span>{Object.entries(dataThrough).map(([source, date]) => <p key={source}>{source} · {date}</p>)}<p>{locale === 'vi' ? 'Dữ liệu lịch sử trong gói pipeline luận văn đã cung cấp.' : 'Historical data from the supplied thesis pipeline package.'}</p></div>
        <div className="method-note"><span className="eyebrow">TEST COVERAGE / JK–MEMMEL</span><p>{plan.test_summary?.count ?? 27} {locale === 'vi' ? 'cặp kiểm định' : 'pairwise tests'} · {plan.test_summary?.significant_after_holm ?? 0} {locale === 'vi' ? 'có ý nghĩa sau Holm–Bonferroni.' : 'significant after Holm–Bonferroni.'}</p><p>{locale === 'vi' ? 'Khoảng bootstrap 90% chưa hiệu chỉnh; không gộp với ý nghĩa thống kê sau Holm.' : '90% bootstrap intervals are unadjusted; distinct from Holm-adjusted significance.'}</p><Link to="/analysis/methodology" className="text-link">{locale === 'vi' ? 'Xem bảng 27 kiểm định' : 'View 27 tests'}<span>↗</span></Link></div>
      </div>
    </section>

    <section className="ips-disclaimer"><div className="ips-section-heading"><span className="ips-section-number">09</span><div><span className="eyebrow">DISCLAIMER / GENERAL INFORMATION</span><h2>{locale === 'vi' ? 'Miễn trừ và giới hạn' : 'Disclaimer and limitations'}</h2></div></div><p>{plan.disclaimer?.[locale] || t('common.disclaimer')}</p><p>{locale === 'vi' ? 'Không phải khuyến nghị đầu tư, tư vấn tài chính hay chỉ dẫn giao dịch. Lợi suất, biến động và drawdown trong lịch sử không dự báo kết quả tương lai. Giá tham chiếu cuối tháng chưa gồm phí và thuế; mã/công cụ đại diện là proxy nghiên cứu. Dữ liệu nghiên cứu dừng ở tháng 07/2026; tháng 08/2026 chưa trọn nên không dùng.' : 'Not investment advice, financial advice or a trade instruction. Historical returns, volatility and drawdowns do not predict future results. Month-end reference prices exclude costs and taxes; proxy instruments are for research only. Research data ends in July 2026; the incomplete August 2026 is not used.'}</p></section>
  </div>;
}
