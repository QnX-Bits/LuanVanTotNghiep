import { useEffect, useMemo, useState } from 'react';
import { Link, NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom';
import { ArrowDownRight, ArrowUpRight, ChevronDown, Globe2, Menu as MenuIcon, Search, X } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { api } from '../api';
import { useApp } from '../app/AppContext';
import { changeDirection, foldDiacritics, money, monthLabel, number, percent } from '../format';
import type { Locale, MarketAsset } from '../types';
import mark from '../assets/portfolio-vn-mark.svg';

const navItems = [
  { title: 'nav.markets', path: '/markets', sections: [{ label: { vi: 'Thị trường', en: 'Markets' }, links: [{ title: { vi: 'VN-Index', en: 'VN-Index' }, path: '/markets/co_phieu' }, { title: { vi: 'Cổ phiếu bất động sản', en: 'Real-estate stocks' }, path: '/markets/bat_dong_san' }, { title: { vi: 'ETF E1VFVN30', en: 'ETF E1VFVN30' }, path: '/markets/etf' }, { title: { vi: 'Vàng SJC', en: 'SJC gold' }, path: '/markets/vang' }, { title: { vi: 'Tiền gửi 12 tháng', en: '12-month deposit' }, path: '/markets/tien_gui' }, { title: { vi: 'TPCP 5 năm', en: '5-year government bonds' }, path: '/markets/trai_phieu' }] }] },
  { title: 'nav.news', path: '/news', sections: [{ label: { vi: 'Tin thị trường', en: 'Market notes' }, links: [{ title: { vi: 'Bản tin theo tháng', en: 'Monthly brief' }, path: '/news?kind=monthly_brief' }, { title: { vi: 'Biến động đáng chú ý', en: 'Notable moves' }, path: '/news?kind=notable_move' }, { title: { vi: 'Thông báo', en: 'Announcements' }, path: '/news?kind=announcement' }] }] },
  { title: 'nav.advisor', path: '/advisor', sections: [{ label: { vi: 'Lập kế hoạch', en: 'Planning' }, links: [{ title: { vi: 'Bắt đầu tư vấn', en: 'Start advisor' }, path: '/advisor' }, { title: { vi: 'Kế hoạch đã lưu', en: 'Saved plans' }, path: '/plans' }] }] },
  { title: 'nav.analysis', path: '/analysis/compare', sections: [{ label: { vi: 'Phân tích', en: 'Research' }, links: [{ title: { vi: 'So sánh 7 phương pháp', en: 'Compare seven methods' }, path: '/analysis/compare' }, { title: { vi: 'Kiểm định thống kê', en: 'Statistical tests' }, path: '/analysis/methodology' }, { title: { vi: 'Độ nhạy', en: 'Sensitivity' }, path: '/analysis/sensitivity' }, { title: { vi: 'Mô hình dự báo', en: 'Forecast models' }, path: '/analysis/models' }] }] },
  { title: 'nav.about', path: '/about', sections: [{ label: { vi: 'Nghiên cứu', en: 'Research notes' }, links: [{ title: { vi: 'Giới thiệu', en: 'About' }, path: '/about' }, { title: { vi: 'Nguồn dữ liệu', en: 'Data sources' }, path: '/about/data-sources' }, { title: { vi: 'Miễn trừ', en: 'Disclaimer' }, path: '/about/disclaimer' }] }] },
];
const pageNames: Record<string, Record<Locale, string>> = {
  '/': { vi: 'Trang chủ', en: 'Home' }, '/markets': { vi: 'Thị trường', en: 'Markets' }, '/news': { vi: 'Tin tức', en: 'News' }, '/advisor': { vi: 'Tư vấn phân bổ', en: 'Allocation advisor' }, '/plans': { vi: 'Kế hoạch của tôi', en: 'My plans' }, '/analysis/compare': { vi: 'So sánh phương pháp', en: 'Method comparison' }, '/analysis/methodology': { vi: 'Phương pháp luận', en: 'Methodology' }, '/analysis/sensitivity': { vi: 'Độ nhạy', en: 'Sensitivity' }, '/analysis/models': { vi: 'Mô hình', en: 'Models' }, '/about': { vi: 'Về dự án', en: 'About' }, '/admin/versions': { vi: 'Quản trị', en: 'Admin' },
};

type MarketResponse = { as_of: string; provisional_month: string | null; assets: MarketAsset[] };

function displayLevel(asset: MarketAsset, locale: Locale): string {
  if (asset.key === 'vang' || asset.key === 'etf') return money(asset.level, locale);
  if (asset.key === 'tien_gui' || asset.key === 'trai_phieu') return `${number(asset.level, locale)}%`;
  if (asset.key === 'bat_dong_san') return number(asset.level, locale);
  return number(asset.level, locale);
}
function monthlyMove(asset: MarketAsset): { value: number | null; isRate: boolean } {
  if (asset.key === 'tien_gui' || asset.key === 'trai_phieu') return { value: asset.monthly_change_pp, isRate: true };
  return { value: asset.monthly_return, isRate: false };
}

export function Shell() {
  const { t } = useTranslation();
  const { user, locale, setLocale, logout } = useApp();
  const [data, setData] = useState<MarketResponse | null>(null);
  const [menu, setMenu] = useState<string | null>(null);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);
  const [search, setSearch] = useState('');
  const location = useLocation();
  const navigate = useNavigate();
  useEffect(() => { api<MarketResponse>('/markets').then(setData).catch(() => setData(null)); }, []);

  const searchResults = useMemo(() => {
    if (!data || !search.trim()) return [];
    const query = foldDiacritics(search.trim());
    return data.assets.filter((item) => foldDiacritics(`${item.label.vi} ${item.label.en} ${item.key}`).includes(query)).slice(0, 6);
  }, [data, search]);

  useEffect(() => {
    setMenu(null); setMobileOpen(false); setSearchOpen(false);
  }, [location.pathname]);

  const breadcrumb = useMemo(() => {
    const known = pageNames[location.pathname];
    if (known) return known[locale];
    if (location.pathname.startsWith('/markets/')) return locale === 'vi' ? 'Chi tiết tài sản' : 'Asset detail';
    if (location.pathname.startsWith('/news/')) return locale === 'vi' ? 'Bài viết' : 'Article';
    if (location.pathname.startsWith('/plans/')) return locale === 'vi' ? 'Chi tiết kế hoạch' : 'Plan detail';
    if (location.pathname.startsWith('/admin')) return t('nav.admin');
    return locale === 'vi' ? 'PortfolioVN' : 'PortfolioVN';
  }, [location.pathname, locale, t]);

  return <div className="site-shell">
    <a className="skip-link" href="#main-content">{locale === 'vi' ? 'Bỏ qua điều hướng' : 'Skip navigation'}</a>
    <div className="utility-bar">
      <div className="container utility-inner">
        <div className="utility-copy"><span className="live-dot" aria-hidden="true" /><span>{t('common.monthlyData')}</span><span className="utility-separator">/</span><span>{monthLabel(data?.as_of || '2026-07', locale)}{data?.provisional_month ? ` · ${t('common.provisional')}` : ''}</span><span className="utility-separator">/</span><span>{t('common.noLive')}</span></div>
        <div className="utility-actions">
          <button className="language-button" onClick={() => setLocale(locale === 'vi' ? 'en' : 'vi')} aria-label={t('common.language')}><Globe2 size={13} />{locale.toUpperCase()}</button>
          <button className="role-button" onClick={() => navigate('/login?switch=1')} aria-label={locale === 'vi' ? 'Đổi vai trò demo' : 'Switch demo role'}>{user?.name}<ChevronDown size={13} /></button>
          <button className="role-menu-logout" onClick={() => void logout()}>{t('common.signOut')}</button>
        </div>
      </div>
    </div>

    <header className="main-header" onMouseLeave={() => setMenu(null)}>
      <div className="container header-main">
        <Link className="brand" to="/" aria-label="PortfolioVN"><img src={mark} alt="PortfolioVN" width="214" height="37" /></Link>
        <nav className="desktop-nav" aria-label={locale === 'vi' ? 'Điều hướng chính' : 'Main navigation'}>
          {navItems.map((item) => <button id={`nav-trigger-${item.path}`} key={item.path} className={`nav-trigger ${menu === item.path ? 'is-open' : ''}`} aria-haspopup="true" aria-expanded={menu === item.path} aria-controls={`mega-${item.path}`} onMouseEnter={() => setMenu(item.path)} onClick={(event) => { const opening = menu !== item.path; setMenu(opening ? item.path : null); if (opening && event.detail === 0) window.requestAnimationFrame(() => document.getElementById(`mega-${item.path}`)?.querySelector<HTMLAnchorElement>('.mega-link')?.focus()); }} onKeyDown={(event) => { if (event.key === 'Escape') setMenu(null); if (event.key === 'ArrowDown') { event.preventDefault(); setMenu(item.path); window.requestAnimationFrame(() => document.getElementById(`mega-${item.path}`)?.querySelector<HTMLAnchorElement>('.mega-link')?.focus()); } }}>
            {t(item.title)}<ChevronDown size={13} />
          </button>)}
          {user?.role === 'admin' && <NavLink to="/admin/versions" className={({ isActive }) => `nav-direct ${isActive ? 'active' : ''}`}>{t('nav.admin')}</NavLink>}
          {user?.role === 'reviewer' && <NavLink to="/admin/versions" className={({ isActive }) => `nav-direct ${isActive ? 'active' : ''}`}>{locale === 'vi' ? 'Rà soát' : 'Review'}</NavLink>}
        </nav>
        <div className="header-tools">
          <button className="search-button" aria-label={t('common.search')} aria-expanded={searchOpen} aria-controls="site-search-panel" onClick={() => { setSearchOpen(!searchOpen); setSearch(''); }}><Search size={18} /></button>
          <Link to="/advisor" className="button button-dark header-cta">{t('nav.start')}<span aria-hidden="true">↗</span></Link>
          <button className="mobile-menu-button" aria-label={mobileOpen ? t('nav.close') : t('nav.open')} onClick={() => setMobileOpen(!mobileOpen)}>{mobileOpen ? <X size={20} /> : <MenuIcon size={20} />}</button>
        </div>
      </div>
      {menu && <div className="mega-backdrop" onClick={() => setMenu(null)} aria-hidden="true" />}
      {menu && <div className="mega-menu" id={`mega-${menu}`} role="region" aria-label={t(navItems.find((item) => item.path === menu)?.title || 'nav.markets')} onKeyDown={(event) => { const links = Array.from(document.getElementById(`mega-${menu}`)?.querySelectorAll<HTMLAnchorElement>('.mega-link') || []); const current = links.indexOf(event.target as HTMLAnchorElement); if (event.key === 'Escape') { setMenu(null); document.getElementById(`nav-trigger-${menu}`)?.focus(); } else if (event.key === 'ArrowDown' || event.key === 'ArrowUp') { event.preventDefault(); links[(current + (event.key === 'ArrowDown' ? 1 : links.length - 1)) % links.length]?.focus(); } else if (event.key === 'Home') { event.preventDefault(); links[0]?.focus(); } else if (event.key === 'End') { event.preventDefault(); links.at(-1)?.focus(); } }}>
        <div className="container mega-inner">
          {navItems.find((item) => item.path === menu)?.sections.map((section) => <div className="mega-col" key={section.label[locale]}><div className="eyebrow">{section.label[locale]}</div>{section.links.map((link) => <Link key={link.path} to={link.path} className="mega-link" onClick={() => setMenu(null)}>{link.title[locale]}<span>↗</span></Link>)}</div>)}
          <button className="mega-close" onClick={() => setMenu(null)} aria-label={t('common.close')}><X size={17} /></button>
        </div>
      </div>}
      {searchOpen && <div className="search-panel" id="site-search-panel"><div className="container search-panel-inner"><label htmlFor="site-search">{t('nav.search')}</label><input autoFocus id="site-search" value={search} onChange={(event) => setSearch(event.target.value)} onKeyDown={(event) => { if (event.key === 'Escape') setSearchOpen(false); if (event.key === 'Enter' && search) navigate(`/news?q=${encodeURIComponent(search)}`); }} placeholder={locale === 'vi' ? 'Thử “vang”, “VN-Index”…' : 'Try “gold”, “VN-Index”…'} />{search && <div className="search-results">{searchResults.map((asset) => <Link key={asset.key} to={`/markets/${asset.key}`} onClick={() => setSearchOpen(false)}><span>{asset.label[locale]}</span><span className="mono">{displayLevel(asset, locale)}</span></Link>)}{!searchResults.length && <Link to={`/news?q=${encodeURIComponent(search)}`} onClick={() => setSearchOpen(false)}>{locale === 'vi' ? `Tìm tin tức “${search}”` : `Search news for “${search}”`}<span>↗</span></Link>}</div>}<button className="search-close" aria-label={t('common.close')} onClick={() => setSearchOpen(false)}><X size={17} /></button></div></div>}
      {mobileOpen && <div className="mobile-nav"><div className="container">{navItems.map((item) => <div className="mobile-nav-group" key={item.path}><button onClick={() => setMenu(menu === item.path ? null : item.path)} aria-expanded={menu === item.path}>{t(item.title)}<ChevronDown size={15} /></button>{menu === item.path && <div className="mobile-nav-sub">{item.sections.flatMap((section) => section.links).map((link) => <Link to={link.path} key={link.path} onClick={() => { setMenu(null); setMobileOpen(false); }}>{link.title[locale]}</Link>)}</div>}</div>)}{(user?.role === 'admin' || user?.role === 'reviewer') && <Link to="/admin/versions" onClick={() => setMobileOpen(false)}>{user?.role === 'admin' ? t('nav.admin') : (locale === 'vi' ? 'Rà soát' : 'Review')}</Link>}</div></div>}
    </header>

    {data?.assets?.length ? <div className="ticker-wrap"><div className="container ticker" aria-label={locale === 'vi' ? 'Bảng chỉ báo thị trường' : 'Market ticker'}>{data.assets.map((asset) => {
      const move = monthlyMove(asset);
      const direction = changeDirection(move.value, locale);
      return <Link className="ticker-item" key={asset.key} to={`/markets/${asset.key}`}><span className="ticker-label">{asset.key === 'co_phieu' ? 'VN-INDEX' : asset.key === 'bat_dong_san' ? 'BĐS' : asset.key === 'tien_gui' ? 'TIỀN GỬI 12T' : asset.key === 'trai_phieu' ? 'TPCP 5N' : asset.key === 'vang' ? 'VÀNG SJC' : 'E1VFVN30'}</span><span className="ticker-value mono">{displayLevel(asset, locale)}</span><span className={`ticker-change ${direction.className}`}>{move.isRate ? `${move.value === null ? '—' : `${move.value > 0 ? '+' : move.value < 0 ? '−' : ''}${number(Math.abs(move.value), locale)} đ.%`}` : percent(move.value, locale, 2, true)}{direction.className === 'up' ? <ArrowUpRight size={12} /> : direction.className === 'down' ? <ArrowDownRight size={12} /> : null}</span></Link>;
    })}</div></div> : null}

    <div className="container breadcrumb-row"><div className="breadcrumbs"><Link to="/">PortfolioVN</Link><span>/</span><span aria-current="page">{breadcrumb}</span></div><span className="data-month">{data?.as_of ? `${t('common.asOf')} ${data.as_of}` : t('common.monthlyData')}</span></div>
    <main id="main-content" className="container page-container"><Outlet /></main>
    <footer className="site-footer"><div className="container footer-top"><div><Link className="footer-brand" to="/">PortfolioVN</Link><p>{t('footer.project')}</p></div><div className="footer-links"><Link to="/about/data-sources">{t('footer.sources')}</Link><Link to="/about/disclaimer">{t('footer.disclaimer')}</Link><Link to="/analysis/methodology">{t('footer.methodology')}</Link><Link to="/plans">{t('nav.plans')}</Link></div></div><div className="container footer-bottom"><span>{t('common.disclaimer')}</span><span>UEH · 2026</span></div></footer>
  </div>;
}
