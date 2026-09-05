/**
 * 项目工作台布局
 *
 * 左侧导航栏(240px) + 右侧(顶栏 + 内容区)
 * 侧栏导航菜单对应各子页面，使用 React Router Outlet 渲染子路由内容
 */
import { useState, useEffect } from 'react';
import { Outlet, useNavigate, useParams, useLocation } from 'react-router-dom';
import { Layout, Menu, Button, Dropdown, Avatar, Space, Typography, Breadcrumb } from 'antd';
import type { MenuProps } from 'antd';
import {
  DashboardOutlined,
  RobotOutlined,
  DatabaseOutlined,
  BugOutlined,
  ExperimentOutlined,
  ApartmentOutlined,
  LogoutOutlined,
  UserOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  KeyOutlined,
} from '@ant-design/icons';

import { getCurrentUser, logout } from '@/services/auth';
import { getProject } from '@/services/project';

const { Header, Sider, Content } = Layout;
const { Text } = Typography;

// 侧栏导航配置
const menuItems: MenuProps['items'] = [
  {
    key: '',
    icon: <DashboardOutlined />,
    label: '工作台',
  },
  {
    key: 'agents',
    icon: <RobotOutlined />,
    label: 'Agent 管理',
  },
  {
    key: 'datasets',
    icon: <DatabaseOutlined />,
    label: '数据集管理',
  },
  {
    key: 'traces',
    icon: <ApartmentOutlined />,
    label: 'Trace 查询',
  },
  {
    key: 'evaluations',
    icon: <ExperimentOutlined />,
    label: '评测任务',
  },
  {
    key: 'bad-cases',
    icon: <BugOutlined />,
    label: 'Bad Case',
  },
];

/** 路径段 → 中文名称映射（与侧栏菜单 key 一致） */
const PATH_LABEL_MAP: Record<string, string> = {
  '': '工作台',
  agents: 'Agent 管理',
  datasets: '数据集管理',
  evaluations: '评测任务',
  traces: 'Trace 查询',
  'bad-cases': 'Bad Case 管理',
};

export default function ProjectLayout() {
  const navigate = useNavigate();
  const location = useLocation();
  const { projectId } = useParams<{ projectId: string }>();
  const [collapsed, setCollapsed] = useState(false);
  const [projectName, setProjectName] = useState<string>('');

  // 加载项目名称
  useEffect(() => {
    if (projectId) {
      getProject(projectId)
        .then((p) => setProjectName(p.name))
        .catch(() => setProjectName(''));
    }
  }, [projectId]);

  const user = getCurrentUser();

  // 从 URL 路径提取当前激活的侧栏菜单 key
  // 路径: /projects/:projectId/xxx → key = 'xxx'（无子路径则为空字符串="工作台"）
  const pathParts = location.pathname.split('/');
  // ['', 'projects', ':projectId', 'xxx', ...]
  const activeKey = pathParts.length >= 4 ? pathParts[3] : '';

  // 生成面包屑
  // 路径: /projects/:projectId/xxx 或 /projects/:projectId/xxx/:subId
  const breadcrumbItems = [
    { title: <Breadcrumb.Item key="project">{projectName || '项目'}</Breadcrumb.Item> },
  ];
  if (pathParts.length >= 4 && pathParts[3]) {
    const pageLabel = PATH_LABEL_MAP[pathParts[3]] || pathParts[3];
    // 只有顶级页面路径时可以点击（如 /projects/1/agents）
    if (pathParts.length === 4) {
      breadcrumbItems.push({
        title: <Breadcrumb.Item key="page">{pageLabel}</Breadcrumb.Item>,
      });
    } else {
      // 有子路径时（如 /projects/1/datasets/xxx）
      // 父级面包屑可点击
      breadcrumbItems.push({
        title: (
          <Breadcrumb.Item
            key="page"
            href={`/projects/${projectId}/${pathParts[3]}`}
            onClick={(e) => {
              e.preventDefault();
              navigate(`/projects/${projectId}/${pathParts[3]}`);
            }}
          >
            {pageLabel}
          </Breadcrumb.Item>
        ),
      });
      breadcrumbItems.push({
        title: <Breadcrumb.Item key="detail">详情</Breadcrumb.Item>,
      });
    }
  }

  // 菜单点击跳转
  function onMenuClick(info: { key: string }) {
    const targetPath = info.key
      ? `/projects/${projectId}/${info.key}`
      : `/projects/${projectId}`;
    navigate(targetPath);
  }

  // 用户下拉菜单
  const userMenuItems: MenuProps['items'] = [
    {
      key: 'api-keys',
      icon: <KeyOutlined />,
      label: 'API Key 管理',
    },
    { type: 'divider' },
    {
      key: 'logout',
      icon: <LogoutOutlined />,
      label: '退出登录',
      danger: true,
    },
  ];

  function onUserMenuClick(info: { key: string }) {
    if (info.key === 'logout') {
      logout();
    } else if (info.key === 'api-keys') {
      navigate('/api-keys');
    }
  }

  return (
    <Layout style={{ minHeight: '100vh' }}>
      {/* 左侧导航 */}
      <Sider
        collapsible
        collapsed={collapsed}
        onCollapse={setCollapsed}
        width={240}
        style={{ background: '#001529' }}
      >
        <div
          style={{
            height: 48,
            margin: 12,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: '#fff',
            fontWeight: 700,
            fontSize: collapsed ? 14 : 18,
            whiteSpace: 'nowrap',
            overflow: 'hidden',
          }}
        >
          {collapsed ? 'AS' : 'AgentScope'}
        </div>
        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={[activeKey]}
          items={menuItems}
          onClick={onMenuClick}
        />
      </Sider>

      {/* 右侧区域 */}
      <Layout>
        {/* 顶栏 */}
        <Header
          style={{
            background: '#fff',
            padding: '0 24px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            borderBottom: '1px solid #f0f0f0',
            height: 56,
          }}
        >
          <Space>
            <Button
              type="text"
              icon={collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
              onClick={() => setCollapsed(!collapsed)}
            />
            <Breadcrumb
              items={breadcrumbItems}
              style={{ fontSize: 13 }}
            />
          </Space>

          <Space size={16}>
            {projectName && (
              <Text strong style={{ fontSize: 13 }}>
                {projectName}
              </Text>
            )}
            <Text type="secondary" style={{ fontSize: 13 }}>
              {user?.username ?? '未登录'}
            </Text>
            <Dropdown menu={{ items: userMenuItems, onClick: onUserMenuClick }} trigger={['click']}>
              <Avatar
                size="small"
                icon={<UserOutlined />}
                style={{ cursor: 'pointer', backgroundColor: '#1677FF' }}
              />
            </Dropdown>
          </Space>
        </Header>

        {/* 内容区 */}
        <Content
          style={{
            margin: 16,
            padding: 24,
            background: '#fff',
            borderRadius: 8,
            minHeight: 280,
            overflow: 'auto',
          }}
        >
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  );
}