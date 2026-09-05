/**
 * 用户级页面布局
 *
 * 为 /projects 和 /api-keys 等用户级页面提供统一的顶栏布局
 * 顶栏包含：品牌标识、用户信息、退出登录下拉菜单
 * 子路由通过 <Outlet /> 渲染在内容区
 */
import { Outlet, useNavigate, useLocation } from 'react-router-dom';
import { Layout, Dropdown, Avatar, Space, Typography, Button } from 'antd';
import type { MenuProps } from 'antd';
import {
  LogoutOutlined,
  UserOutlined,
  KeyOutlined,
  ProjectOutlined,
} from '@ant-design/icons';

import { getCurrentUser, logout } from '@/services/auth';

const { Header, Content } = Layout;
const { Text } = Typography;

export default function UserLayout() {
  const navigate = useNavigate();
  const location = useLocation();
  const user = getCurrentUser();

  // 用户下拉菜单
  const userMenuItems: MenuProps['items'] = [
    {
      key: 'user-info',
      icon: <UserOutlined />,
      label: user?.username ?? '未知用户',
      disabled: true,
    },
    { type: 'divider' },
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

  // 判断当前是否在项目列表页
  const isProjectsPage = location.pathname === '/projects';

  return (
    <Layout style={{ minHeight: '100vh', background: '#f5f5f5' }}>
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
          position: 'sticky',
          top: 0,
          zIndex: 100,
          boxShadow: '0 1px 4px rgba(0,0,0,0.08)',
        }}
      >
        {/* 左侧：品牌标识 + 导航 */}
        <Space size={24}>
          <Text
            strong
            style={{
              fontSize: 18,
              color: '#1677FF',
              cursor: 'pointer',
              userSelect: 'none',
            }}
            onClick={() => navigate('/projects')}
          >
            AgentScope
          </Text>
          <Button
            type={isProjectsPage ? 'link' : 'text'}
            icon={<ProjectOutlined />}
            onClick={() => navigate('/projects')}
            style={{ fontWeight: isProjectsPage ? 600 : 400 }}
          >
            我的项目
          </Button>
        </Space>

        {/* 右侧：用户信息 + 下拉菜单 */}
        <Space size={12}>
          <Text type="secondary" style={{ fontSize: 13 }}>
            {user?.username ?? '未登录'}
          </Text>
          <Dropdown
            menu={{ items: userMenuItems, onClick: onUserMenuClick }}
            trigger={['click']}
          >
            <Avatar
              size="small"
              icon={<UserOutlined />}
              style={{ cursor: 'pointer', backgroundColor: '#1677FF' }}
            />
          </Dropdown>
        </Space>
      </Header>

      {/* 内容区 */}
      <Content style={{ padding: 24 }}>
        <Outlet />
      </Content>
    </Layout>
  );
}
