import { useEffect, useState } from 'react';
import { ArrowRight, ChevronRight, Database, ExternalLink, ShieldCheck } from 'lucide-react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { ApiError, api } from '../../api';
import { Sparkline } from '../../components/Sparkline';
import { useApp } from '../../app/AppContext';
import { changeDirection, money, monthLabel, number, percent } from '../../format';
import { articleText } from '../../locales/article';
import type { MarketAsset, NewsArticle } from '../../types';

type DashboardData = {
  version: { label: string; status: string; manifest?: { data_through?: string } };
  assets: MarketAsset[];
  latest_news: NewsArticle[];
  balanced_medium: { annualised_return: number; deposit_annualised_return: number; volatility: number; sharpe_ratio: number; max_drawdown: number; n_months: number; start: string; end: string };
  methods: { method: string; sharpe_ratio: number; annualised_return: number; max_drawdown: number }[];
  data_confidence: { data_through?: Record<string, string>; provisional_month?: string; validation?: { valid?: boolean; reasons?: string[] } };
};
const canonical = ['Cổ phiếu', 'Bất động sản', 'ETF', 'Vàng SJC', 'Tiền gửi 12 tháng', 'Trái phiếu Chính phủ 5 năm'];
const fallbackNames = ['Stocks', 'Real-estate stocks', 'ETF', 'SJC gold', '12-month deposits', '5-year government bonds'];
function assetLevel(asset: MarketAsset, locale: 'vi' | 'en') {
  if (asset.key === 'vang' || asset.key === 'etf') return money(asset.level, locale);
  if (asset.key === 'tien_gui' || asset.key === 'trai_phieu') return `${number(asset.level, locale)}%`;
  return number(asset.level, locale);
}

export function DashboardPage() {
  const { t } = useTranslation(); const { locale } = useApp();
  const [data, setData] = useState<DashboardData | null>(null); const [error, setError] = useState('');
  useEffect(() => { api<DashboardData>('/dashboard').then(setData).catch((e) => setError(e instanceof ApiError ? e.detail : 'Unable to load dashboard')); }, []);
  if (!data) return error ? <section className="error-panel"><span className="eyebrow">DATA REQUEST</span><h1>{t('common.error')}</h1><p>{error}</p></section> : <div className="loading-block"><span className="eyebrow">PORTFOLIOVN / DATA</span><span className="loading-bar" /></div>;
  const metric = data.balanced_medium;
  const asOf = monthLabel(data.assets[0]?.as_of || '2026-07', locale);
  return <>
    <section className="hero-ledger">
      <div className="hero-copy"><p className="eyebrow">{t('home.eyebrow')}</p><h1>{t('home.headline').split('\n').map((line) => <span key={line}>{line}<br /></span>)}</h1><p className="hero-intro">{t('home.intro')}</p><div className="hero-actions"><Link className="button button-dark" to="/markets">{t('home.markets')}<ArrowRight size={16} /></Link><Link className="text-link" to="/advisor">{t('home.advisor')}<span>↗</span></Link></div><div className="hero-footnote"><span className="data-square" />{t('common.asOf')} <b>{asOf}</b>{data.data_confidence.provisional_month && <span className="tag tag-provisional">{t('common.provisional')}</span>}<span>{t('home.note')}</span></div></div>
      <div className="hero-graphic" aria-hidden="true"><div className="folio-stamp"><span>PVN / 01</span><strong>06</strong><small>{locale === 'vi' ? 'LỚP TÀI SẢN' : 'ASSET CLASSES'}</small></div><div className="folio-lines"><i /><i /><i /><i /><i /><i /><i /><i /><i /><i /><i /><i /></div><div className="folio-caption">{locale === 'vi' ? 'DỮ LIỆU THÁNG · LỊCH SỬ' : 'MONTHLY DATA · HISTORICAL'}</div></div>
    </section>

    <section className="section-block market-ledger-section">
      <div className="section-heading"><div><p className="eyebrow">01 / {locale === 'vi' ? 'BẢNG TỔNG QUAN' : 'MARKET LEDGER'}</p><h2>{t('home.ledger')}</h2></div><Link to="/markets" className="arrow-link">{t('home.markets')}<ArrowRight size={15} /></Link></div>
      <div className="market-table-wrap"><table className="market-table"><thead><tr><th>{t('market.asset')}</th><th className="align-right">{t('market.price')}</th><th className="align-right">{t('common.monthChange')}</th><th className="align-right hide-mobile">{t('common.ytd')}</th><th className="chart-cell hide-tablet">36M</th><th className="hide-tablet">{t('market.source')}</th></tr></thead><tbody>{data.assets.map((asset, index) => {
        const move = asset.key === 'tien_gui' || asset.key === 'trai_phieu' ? asset.monthly_change_pp : asset.monthly_return;
        const tone = changeDirection(move, locale);
        const change = asset.key === 'tien_gui' || asset.key === 'trai_phieu' ? (move === null ? '—' : `${move > 0 ? '+' : move < 0 ? '−' : ''}${number(Math.abs(move), locale)} ${locale === 'vi' ? 'đ.%' : 'pp'}`) : percent(move, locale, 2, true);
        return <tr key={asset.key}><td><Link to={`/markets/${asset.key}`} className="asset-name-cell"><span className="row-index">0{index + 1}</span><span><b>{asset.label[locale]}</b><small className="asset-subtitle">{canonical[index] || fallbackNames[index]}</small></span></Link></td><td className="align-right mono level-cell">{assetLevel(asset, locale)}{asset.is_provisional && <span className="hollow-dot" aria-label={t('common.provisional')} />}</td><td className={`align-right mono change-cell ${tone.className}`}>{change}</td><td className={`align-right mono hide-mobile ${asset.ytd_return !== null ? changeDirection(asset.ytd_return, locale).className : ''}`}>{asset.key === 'tien_gui' || asset.key === 'trai_phieu' ? (asset.ytd_change_pp === null ? '—' : `${asset.ytd_change_pp > 0 ? '+' : asset.ytd_change_pp < 0 ? '−' : ''}${number(Math.abs(asset.ytd_change_pp), locale)} ${locale === 'vi' ? 'đ.%' : 'pp'}`) : percent(asset.ytd_return, locale, 2, true)}</td><td className="chart-cell hide-tablet"><Sparkline values={asset.series.map((row) => row.value)} positive={move === null || move >= 0} label={`${asset.label[locale]} monthly trend`} /></td><td className="source-cell hide-tablet">{asset.source}</td></tr>;
      })}</tbody></table></div>
      <div className="table-source-note"><span className="data-square" />{t('common.monthlyData')} <span>·</span>{data.assets[0]?.as_of} <span>·</span><Link to="/about/data-sources">{t('common.source')} ↗</Link></div>
    </section>

    <section className="section-block advisor-strip"><div className="advisor-strip-meta"><p className="eyebrow">02 / {locale === 'vi' ? 'HỒ SƠ NHÀ ĐẦU TƯ' : 'INVESTOR PROFILE'}</p><h2>{t('home.spotlight')}</h2><p>{locale === 'vi' ? 'Bảy câu hỏi chấm điểm và chân trời đầu tư. Phân bổ tra cứu theo phiên bản kết quả đang hoạt động.' : 'Seven scored questions plus your horizon. Allocation follows the active result version.'}</p><Link className="button button-light" to="/advisor">{t('nav.start')}<ArrowRight size={15} /></Link></div><div className="advisor-stat-grid"><div className="advisor-stat"><span className="eyebrow">{locale === 'vi' ? 'KỊCH BẢN' : 'SCENARIOS'}</span><strong>09</strong><small>3 {locale === 'vi' ? 'hồ sơ' : 'profiles'} × 3 {locale === 'vi' ? 'thời hạn' : 'horizons'}</small></div><div className="advisor-stat"><span className="eyebrow">{locale === 'vi' ? 'PHƯƠNG PHÁP' : 'METHOD'}</span><strong>HRP</strong><small>{locale === 'vi' ? 'Tỷ trọng dữ liệu hiện hành' : 'Current data weights'}</small></div><div className="advisor-stat"><span className="eyebrow">{locale === 'vi' ? 'ĐÁNH GIÁ' : 'EVALUATION'}</span><strong>VND</strong><small>{locale === 'vi' ? 'Rủi ro quy đổi theo khoản tiền' : 'Risk shown in your amount'}</small></div></div></section>

    <section className="section-block news-method-grid"><div className="news-panel"><div className="section-heading compact"><div><p className="eyebrow">03 / {locale === 'vi' ? 'TÓM TẮT THỊ TRƯỜNG' : 'MARKET BRIEF'}</p><h2>{t('home.recent')}</h2></div><Link to="/news" className="small-arrow" aria-label={locale === 'vi' ? 'Xem tất cả tin' : 'All news'}><ArrowRight size={17} /></Link></div><div className="latest-news-list">{data.latest_news.map((article, index) => <Link className="latest-news-item" key={article.slug} to={`/news/${article.slug}`}><span className="news-index">0{index + 1}</span><div className="news-item-copy"><div className="news-meta">{article.period || article.kind.replace('_', ' ')}{article.is_provisional && <span className="tag tag-provisional">{t('common.provisional')}</span>}</div><h3>{articleText(article.title, locale)}</h3><p>{articleText(article.summary, locale)}</p></div><ChevronRight className="news-chevron" size={16} /></Link>)}</div></div>
      <div className="methods-panel"><div className="section-heading compact"><div><p className="eyebrow">04 / EXPLORE</p><h2>{t('home.methodology')}</h2></div><Link to="/analysis/compare" className="small-arrow" aria-label={t('analysis.compare')}><ArrowRight size={17} /></Link></div><div className="benchmark-tag"><span>{t('home.benchmark')}</span><span className="tag tag-outline">n = {metric.n_months}</span></div><div className="metric-table">{data.methods.slice(0, 7).map((row, i) => <div className={`metric-row ${row.method === 'HRP' ? 'metric-row-selected' : ''}`} key={row.method}><span className="metric-rank">0{i + 1}</span><span className="metric-name">{row.method}{row.method === 'HRP' && <span className="selected-label">SELECTED</span>}</span><span className="mono metric-number">{number(row.sharpe_ratio, locale, 3)}</span><span className={`mono ${row.annualised_return < metric.deposit_annualised_return ? 'down' : 'up'}`}>{percent(row.annualised_return, locale, 2)}</span></div>)}</div><div className="method-under-note">{t('analysis.hrp')}</div></div></section>

    <section className="confidence-band"><div className="confidence-title"><ShieldCheck size={18} /><div><span className="eyebrow">{t('home.confidence')}</span><strong>{data.version.label}</strong></div></div><div className="confidence-stat"><span className="mono">27</span><small>{t('home.validation')}</small></div><div className="confidence-stat"><span className="mono">{metric.n_months}</span><small>{locale === 'vi' ? 'tháng kiểm tra' : 'test months'}, {monthLabel(metric.start, locale)}–{monthLabel(metric.end, locale)}</small></div><div className="confidence-stat">{data.data_confidence.provisional_month ? <><span className="tag tag-provisional">{asOf} · {t('common.provisional')}</span><small>{locale === 'vi' ? 'chưa đủ dữ liệu hết tháng' : 'month not yet complete'}</small></> : <><span className="mono">{asOf}</span><small>{locale === 'vi' ? 'tháng cuối đủ dữ liệu; 08/2026 chưa trọn nên bị loại' : 'last complete month; partial Aug 2026 excluded'}</small></>}</div><Link to="/about/data-sources" className="confidence-more">{t('common.source')}<ArrowRight size={15} /></Link></section>

    <div className="disclaimer-strip"><Database size={15} /><span>{t('common.disclaimer')}</span><Link to="/about/disclaimer">{locale === 'vi' ? 'Đọc thêm' : 'Read more'}<ExternalLink size={12} /></Link></div>
  </>;
}
