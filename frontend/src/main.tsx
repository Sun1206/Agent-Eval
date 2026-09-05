/**
 * React 应用入口
 *
 * 这是前端的第一个执行文件，职责：
 *   1. 创建 React 根节点并挂载到 HTML 的 #root 元素
 *   2. 配置 Ant Design 中文语言包和主题色
 *   3. 包裹 BrowserRouter 启用前端路由
 *   4. 渲染 App 组件（路由配置）
 *
 * 执行流程: index.html → main.tsx → App.tsx → 各页面组件
 */
import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import { ConfigProvider, App as AntApp } from 'antd';
import zhCN from 'antd/locale/zh_CN';
import App from './App';

// 全局样式：Ant Design 5 默认即用，仅做最小补充
import './index.css';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <ConfigProvider
    locale={zhCN}
    theme={{
      token: {
        colorPrimary: '#1677FF',
      },
    }}
  >
    <AntApp>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </AntApp>
  </ConfigProvider>
);
