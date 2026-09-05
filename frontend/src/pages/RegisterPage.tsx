/**
 * 注册页
 *
 * 居中卡片式，用户名 / 邮箱 / 密码 / 确认密码 / 显示名称
 * 注册成功 → 跳转登录页
 */
import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Form, Input, Button, Card, Typography, message } from 'antd';
import {
  UserOutlined,
  MailOutlined,
  LockOutlined,
  IdcardOutlined,
  ExperimentOutlined,
} from '@ant-design/icons';
import { register } from '@/services/auth';

const { Title, Text } = Typography;

interface RegisterFormValues {
  username: string;
  email: string;
  password: string;
  confirmPassword: string;
  display_name?: string;
}

export default function RegisterPage() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [form] = Form.useForm<RegisterFormValues>();

  async function onFinish(values: RegisterFormValues) {
    setLoading(true);
    try {
      await register(
        values.username,
        values.email,
        values.password,
        values.display_name,
      );
      message.success('注册成功，请登录');
      navigate('/login', { replace: true });
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        (err as { message?: string })?.message ??
        '注册失败，请重试';
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
        <div style={{ display: 'flex', height: 500 }}>
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
              创建您的账号，开始评测
            </Text>
          </div>

          {/* 右侧表单区域 */}
          <div style={{ flex: 1, padding: '32px 48px', display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
            <Title level={4} style={{ marginBottom: 4 }}>
              创建账号
            </Title>
            <Text type="secondary" style={{ marginBottom: 24, display: 'block' }}>
              请填写以下信息完成注册
            </Text>

            <Form
              form={form}
              layout="vertical"
              onFinish={onFinish}
              autoComplete="off"
              size="large"
            >
              <Form.Item
                name="username"
                rules={[
                  { required: true, message: '请输入用户名' },
                  { min: 3, message: '用户名至少 3 个字符' },
                  { max: 50, message: '用户名不超过 50 个字符' },
                  {
                    pattern: /^[a-zA-Z0-9_-]+$/,
                    message: '只能包含字母、数字、下划线和连字符',
                  },
                ]}
              >
                <Input
                  prefix={<UserOutlined style={{ color: '#bfbfbf' }} />}
                  placeholder="用户名"
                />
              </Form.Item>

              <Form.Item
                name="email"
                rules={[
                  { required: true, message: '请输入邮箱' },
                  { type: 'email', message: '邮箱格式不正确' },
                ]}
              >
                <Input
                  prefix={<MailOutlined style={{ color: '#bfbfbf' }} />}
                  placeholder="邮箱"
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
                  placeholder="密码（8位以上，含大小写+数字）"
                />
              </Form.Item>

              <Form.Item
                name="confirmPassword"
                dependencies={['password']}
                rules={[
                  { required: true, message: '请确认密码' },
                  ({ getFieldValue }) => ({
                    validator(_, value) {
                      if (!value || getFieldValue('password') === value) {
                        return Promise.resolve();
                      }
                      return Promise.reject(new Error('两次输入的密码不一致'));
                    },
                  }),
                ]}
              >
                <Input.Password
                  prefix={<LockOutlined style={{ color: '#bfbfbf' }} />}
                  placeholder="确认密码"
                />
              </Form.Item>

              <Form.Item
                name="display_name"
                rules={[{ max: 100, message: '显示名称不超过 100 个字符' }]}
              >
                <Input
                  prefix={<IdcardOutlined style={{ color: '#bfbfbf' }} />}
                  placeholder="显示名称（选填）"
                />
              </Form.Item>

              <Form.Item style={{ marginBottom: 12 }}>
                <Button
                  type="primary"
                  htmlType="submit"
                  loading={loading}
                  block
                >
                  注册
                </Button>
              </Form.Item>
            </Form>

            <div style={{ textAlign: 'center' }}>
              <Text type="secondary">
                已有账号？ <Link to="/login">去登录</Link>
              </Text>
            </div>
          </div>
        </div>
      </Card>
    </div>
  );
}