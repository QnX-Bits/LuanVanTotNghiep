import { lazy, Suspense } from 'react';
import { Navigate, Outlet, Route, Routes, useLocation } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useApp } from './AppContext';
import { Shell } from '../components/Shell';

const LoginPage = lazy(() => import('../features/LoginPage').then((module) => ({ default: module.LoginPage })));
const DashboardPage = lazy(() => import('../features/markets/DashboardPage').then((module) => ({ default: module.DashboardPage })));
const MarketsPage = lazy(() => import('../features/markets/MarketsPage').then((module) => ({ default: module.MarketsPage })));
const MarketDetailPage = lazy(() => import('../features/markets/MarketsPage').then((module) => ({ default: module.MarketDetailPage })));
const NewsPage = lazy(() => import('../features/news/NewsPage').then((module) => ({ default: module.NewsPage })));
const ArticlePage = lazy(() => import('../features/news/NewsPage').then((module) => ({ default: module.ArticlePage })));
const AdvisorPage = lazy(() => import('../features/advisor/AdvisorPage').then((module) => ({ default: module.AdvisorPage })));
const AdvisorResultPage = lazy(() => import('../features/advisor/AdvisorPage').then((module) => ({ default: module.AdvisorResultPage })));
const PlansPage = lazy(() => import('../features/plans/PlansPage').then((module) => ({ default: module.PlansPage })));
const PlanDetailPage = lazy(() => import('../features/plans/PlansPage').then((module) => ({ default: module.PlanDetailPage })));
const PrintPlanPage = lazy(() => import('../features/plans/PlansPage').then((module) => ({ default: module.PrintPlanPage })));
const SharedPlanPage = lazy(() => import('../features/plans/PlansPage').then((module) => ({ default: module.SharedPlanPage })));
const ComparePage = lazy(() => import('../features/analysis/AnalysisPages').then((module) => ({ default: module.ComparePage })));
const MethodologyPage = lazy(() => import('../features/analysis/AnalysisPages').then((module) => ({ default: module.MethodologyPage })));
const SensitivityPage = lazy(() => import('../features/analysis/AnalysisPages').then((module) => ({ default: module.SensitivityPage })));
const ModelsPage = lazy(() => import('../features/analysis/AnalysisPages').then((module) => ({ default: module.ModelsPage })));
const AboutPage = lazy(() => import('../features/AboutPage').then((module) => ({ default: module.AboutPage })));
const AdminVersionsPage = lazy(() => import('../features/admin/AdminPages').then((module) => ({ default: module.AdminVersionsPage })));
const AdminRunsPage = lazy(() => import('../features/admin/AdminPages').then((module) => ({ default: module.AdminRunsPage })));
const AdminAuditPage = lazy(() => import('../features/admin/AdminPages').then((module) => ({ default: module.AdminAuditPage })));
const AdminNewsPage = lazy(() => import('../features/admin/AdminPages').then((module) => ({ default: module.AdminNewsPage })));
const AdminRulesPage = lazy(() => import('../features/admin/AdminPages').then((module) => ({ default: module.AdminRulesPage })));

function Protected({ roles }: { roles?: string[] }) {
  const { user, loading } = useApp();
  const location = useLocation();
  if (loading) return <div className="loading-screen"><span className="eyebrow">PORTFOLIOVN</span><span className="loading-bar" /></div>;
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  if (roles && !roles.includes(user.role)) return <Navigate to="/" replace />;
  return <Outlet />;
}

function MissingPage() {
  const { t } = useTranslation();
  return <section className="empty-state"><span className="eyebrow">404 / NOT FOUND</span><h1>{t('common.noData')}</h1><p>{t('common.monthlyData')}</p></section>;
}

function RouteFallback() {
  return <main className="route-loading" aria-live="polite"><span className="eyebrow">PORTFOLIOVN / DATA</span><span className="loading-bar" /></main>;
}

export function App() {
  return <Suspense fallback={<RouteFallback />}><Routes>
    <Route path="/login" element={<LoginPage />} />
    <Route path="/share/:token" element={<SharedPlanPage />} />
    <Route element={<Protected />}>
      <Route element={<Shell />}>
        <Route index element={<DashboardPage />} />
        <Route path="markets" element={<MarketsPage />} />
        <Route path="markets/:asset" element={<MarketDetailPage />} />
        <Route path="news" element={<NewsPage />} />
        <Route path="news/:slug" element={<ArticlePage />} />
        <Route path="advisor" element={<AdvisorPage />} />
        <Route path="advisor/result" element={<AdvisorResultPage />} />
        <Route path="plans" element={<PlansPage />} />
        <Route path="plans/:code" element={<PlanDetailPage />} />
        <Route path="print/plans/:code" element={<PrintPlanPage />} />
        <Route path="analysis/compare" element={<ComparePage />} />
        <Route path="analysis/methodology" element={<MethodologyPage />} />
        <Route path="analysis/sensitivity" element={<SensitivityPage />} />
        <Route path="analysis/models" element={<ModelsPage />} />
        <Route path="about" element={<AboutPage />} />
        <Route path="about/data-sources" element={<AboutPage />} />
        <Route path="about/disclaimer" element={<AboutPage />} />
      </Route>
    </Route>
    <Route element={<Protected roles={['admin', 'reviewer']} />}>
      <Route element={<Shell />}>
        <Route path="admin/versions" element={<AdminVersionsPage />} />
        <Route path="admin/runs" element={<AdminRunsPage />} />
        <Route path="admin/runs/:id" element={<AdminRunsPage />} />
        <Route path="admin/audit" element={<AdminAuditPage />} />
      </Route>
    </Route>
    <Route element={<Protected roles={['admin']} />}>
      <Route element={<Shell />}>
        <Route path="admin/news" element={<AdminNewsPage />} />
        <Route path="admin/news/new" element={<AdminNewsPage />} />
        <Route path="admin/news/:id" element={<AdminNewsPage />} />
        <Route path="admin/execution-rules" element={<AdminRulesPage />} />
      </Route>
    </Route>
    <Route path="*" element={<MissingPage />} />
  </Routes></Suspense>;
}
