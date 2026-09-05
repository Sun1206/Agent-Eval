/**
 * 应用根路由配置
 *
 * 定义了整个前端的页面路由结构，分为三层：
 *
 * 第一层 - 公开页面（无需登录）:
 *   /login       → 登录页
 *   /register    → 注册页
 *
 * 第二层 - 用户级页面（需要登录，不属于某个项目）:
 *   /projects    → 项目列表页
 *   /api-keys    → API Key 管理页
 *
 * 第三层 - 项目级页面（需要登录，属于某个项目，共享侧栏+顶栏布局）:
 *   /projects/:projectId           → 工作台 Dashboard
 *   /projects/:projectId/agents    → Agent 管理
 *   /projects/:projectId/datasets  → 数据集管理
 *   /projects/:projectId/evaluations → 评测任务
 *   /projects/:projectId/traces    → Trace 查询
 *   /projects/:projectId/bad-cases → Bad Case 管理
 *
 * 页面流转: /login → /projects → /projects/:projectId/* (嵌套子页面)
 */
import { Navigate, Route, Routes } from 'react-router-dom';
import { isAuthenticated } from '@/services/auth';

// 布局组件
import ProjectLayout from '@/layouts/ProjectLayout';
import UserLayout from '@/layouts/UserLayout';

// 页面组件
import LoginPage from '@/pages/LoginPage';
import RegisterPage from '@/pages/RegisterPage';
import ProjectListPage from '@/pages/ProjectListPage';
import DatasetListPage from '@/pages/datasets/DatasetListPage';
import DatasetDetailPage from '@/pages/datasets/DatasetDetailPage';
import EvalListPage from '@/pages/evaluations/EvalListPage';
import EvalDetailPage from '@/pages/evaluations/EvalDetailPage';
import TraceListPage from '@/pages/traces/TraceListPage';
import TraceDetailPage from '@/pages/traces/TraceDetailPage';
import BadCaseListPage from '@/pages/badcases/BadCaseListPage';
import AgentListPage from '@/pages/agents/AgentListPage';
import ApiKeyPage from '@/pages/ApiKeyPage';
import DashboardPage from '@/pages/DashboardPage';

/**
 * 路由守卫组件
 *
 * 包裹需要登录才能访问的页面。
 * 如果用户未登录（localStorage 中没有 token），自动跳转到 /login。
 * 用法: <AuthGuard><SomePage /></AuthGuard>
 */
function AuthGuard({ children }: { children: React.ReactNode }) {
  if (!isAuthenticated()) {
    return <Navigate to="/login" replace />;  // replace 表示替换历史记录，不允许后退
  }
  return <>{children}</>;
}

export default function App() {
  return (
    <Routes>
      {/* ============ 第一层：公开页面（无需登录） ============ */}
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />

      {/* ============ 第二层：用户级页面（需要登录，使用 UserLayout 布局） ============ */}
      {/*
        UserLayout 提供顶栏导航（品牌标识 + 用户信息 + 退出登录）
        子路由通过 <Outlet /> 渲染在内容区
      */}
      <Route
        element={
          <AuthGuard>
            <UserLayout />
          </AuthGuard>
        }
      >
        {/* 项目列表页：展示用户参与的所有项目，支持创建/编辑/删除 */}
        <Route path="/projects" element={<ProjectListPage />} />

        {/* API Key 管理页：创建/查看/吊销 API Key（用于 SDK 认证） */}
        <Route path="/api-keys" element={<ApiKeyPage />} />
      </Route>

      {/* ============ 第三层：项目级页面（嵌套在 ProjectLayout 中） ============ */}
      {/*
        ProjectLayout 提供侧栏导航 + 顶栏 + 面包屑
        子路由通过 <Outlet /> 渲染在右侧内容区
      */}
      <Route
        path="/projects/:projectId"
        element={
          <AuthGuard>
            <ProjectLayout />
          </AuthGuard>
        }
      >
        {/* 工作台首页：项目概览（Agent数/数据集数/最近评测/Bad Case统计） */}
        <Route index element={<DashboardPage />} />

        {/* Agent 管理：注册/查看/编辑/删除 Agent */}
        <Route path="agents" element={<AgentListPage />} />

        {/* 数据集管理：列表 + 详情（含条目 CRUD + 导入导出） */}
        <Route path="datasets" element={<DatasetListPage />} />
        <Route path="datasets/:datasetId" element={<DatasetDetailPage />} />

        {/* 评测任务：列表 + 详情（含结果/统计/进度） */}
        <Route path="evaluations" element={<EvalListPage />} />
        <Route path="evaluations/:runId" element={<EvalDetailPage />} />

        {/* Trace 查询：列表 + 详情（含 Span 树形可视化） */}
        <Route path="traces" element={<TraceListPage />} />
        <Route path="traces/:traceId" element={<TraceDetailPage />} />

        {/* Bad Case 管理：列表 + 标记 + 状态流转 */}
        <Route path="bad-cases" element={<BadCaseListPage />} />
      </Route>

      {/* 兜底路由：所有未匹配的路径重定向到项目列表 */}
      <Route path="*" element={<Navigate to="/projects" replace />} />
    </Routes>
  );
}
