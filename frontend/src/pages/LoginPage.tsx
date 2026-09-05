/**
 * 登录页
 *
 * 居中卡片式布局，左侧品牌区域 + 右侧表单区域
 * 登录成功 → 跳转 /projects
 */
import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Form, Input, Button, Card, Typography, message, Space } from 'antd';
import { UserOutlined, LockOutlined, ExperimentOutlined } from '@ant-design/icons';
import { login } from '@/services/auth';

const { Title, Text } = Typography;

interface LoginFormValues {
  login: string;
  password: string;
}

export default function LoginPage() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [form] = Form.useForm<LoginFormValues>();

  async function onFinish(values: LoginFormValues) {
    setLoading(true);
    try {
      await login(values.login, values.password);
      message.success('登录成功');
      navigate('/projects', { replace: true });
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        (err as { message?: string })?.message ??
        '登录失败，请检查用户名和密码';
      message.error(msg);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div
      style={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: 'linear-gradient(135deg, #f5f7fa 0%, #e8ecf1 100%)',
      }}
    >
      <Card
        style={{ width: 720, borderRadius: 12, boxShadow: '0 4px 24px rgba(0,0,0,0.08)' }}
        bodyStyle={{ padding: 0 }}
      >
        <div style={{ display: 'flex', height: 420 }}>
          {/* 左侧品牌区域 */}
          <div
            style={{
              width: 320,
              background: 'linear-gradient(135deg, #1677FF 0%, #0958d9 100%)',
              borderRadius: '12px 0 0 12px',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#fff',
              padding: 40,
            }}
          >
            <ExperimentOutlined style={{ fontSize: 48, marginBottom: 16 }} />
            <Title level={3} style={{ color: '#fff', margin: 0 }}>
              AgentScope
            </Title>
            <Text style={{ color: 'rgba(255,255,255,0.75)', marginTop: 8, textAlign: 'center' }}>
              AI Agent 评测与可观测性平台
            </Text>
          </div>

          {/* 右侧表单区域 */}
          <div style={{ flex: 1, padding: '40px 48px', display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
            <Title level={4} style={{ marginBottom: 4 }}>
              欢迎登录
            </Title>
            <Text type="secondary" style={{ marginBottom: 32, display: 'block' }}>
              请输入您的账号信息
            </Text>

            <Form
              form={form}
              layout="vertical"
              onFinish={onFinish}
              autoComplete="off"
              size="large"
            >
              <Form.Item
                name="login"
                rules={[
                  { required: true, message: '请输入用户名或邮箱' },
                  { min: 3, message: '用户名至少 3 个字符' },
                  { max: 50, message: '用户名不超过 50 个字符' },
                ]}
              >
                <Input
                  prefix={<UserOutlined style={{ color: '#bfbfbf' }} />}
                  placeholder="用户名或邮箱"
                />
              </Form.Item>

              <Form.Item
                name="password"
                rules={[
                  { required: true, message: '请输入密码' },
                  { min: 8, message: '密码至少 8 位' },
                  {
                    pattern: /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d).+$/,
                    message: '密码需包含大小写字母和数字',
                  },
                ]}
              >
                <Input.Password
                  prefix={<LockOutlined style={{ color: '#bfbfbf' }} />}
                  placeholder="密码"
                />
              </Form.Item>

              <Form.Item style={{ marginBottom: 12 }}>
                <Button
                  type="primary"
                  htmlType="submit"
                  loading={loading}
                  block
                >
                  登录
                </Button>
              </Form.Item>
            </Form>

            <div style={{ textAlign: 'center' }}>
              <Text type="secondary">
                还没有账号？ <Link to="/register">立即注册</Link>
              </Text>
            </div>
          </div>
        </div>
      </Card>
    </div>
  );
}