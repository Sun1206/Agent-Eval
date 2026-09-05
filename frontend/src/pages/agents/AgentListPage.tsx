/**
 * Agent 管理页
 *
 * Agent 列表表格 + 注册 Modal + 删除操作
 */
import { useEffect, useState, useCallback } from 'react';
import { useParams } from 'react-router-dom';
import {
  Table,
  Button,
  Modal,
  Form,
  Input,
  Select,
  message,
  Popconfirm,
  Tag,
  Typography,
  Space,
  Empty,
  Tooltip,
} from 'antd';
import {
  PlusOutlined,
  ReloadOutlined,
  DeleteOutlined,
} from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import {
  listAgents,
  createAgent,
  deleteAgent,
  AgentInfo,
  AgentCreateData,
} from '@/services/agent';
import dayjs from 'dayjs';

const { Title, Text } = Typography;
const { TextArea } = Input;

/** 版本号校验正则 */
const SEMVER_REGEX = /^\d+\.\d+\.\d+$/;

export default function AgentListPage() {
  const { projectId } = useParams<{ projectId: string }>();

  // 列表状态
  const [agents, setAgents] = useState<AgentInfo[]>([]);
  const [loading, setLoading] = useState(true);

  // 注册 Modal
  const [createOpen, setCreateOpen] = useState(false);
  const [createLoading, setCreateLoading] = useState(false);
  const [form] = Form.useForm();

  // 鉴权类型状态
  const authType = Form.useWatch('auth_type', form);

  // 加载列表
  const fetchList = useCallback(async () => {
    if (!projectId) return;
    setLoading(true);
    try {
      const data = await listAgents(projectId);
      setAgents(data);
    } catch (err: unknown) {
      message.error((err as { message?: string })?.message ?? '加载 Agent 列表失败');
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    fetchList();
  }, [fetchList]);

  // 注册 Agent
  async function handleCreate(values: {
    name: string;
    version: string;
    description?: string;
    endpoint_url?: string;
    config_json?: string;
    auth_type?: string;
    auth_token?: string;
    auth_api_key?: string;
    auth_header_name?: string;
    auth_custom_headers?: string;
  }) {
    if (!projectId) return;

    // 解析 config JSON
    let config: Record<string, unknown> = {};
    if (values.config_json && values.config_json.trim()) {
      try {
        config = JSON.parse(values.config_json);
      } catch {
        message.error('配置字段 JSON 格式不正确');
        return;
      }
    }

    // 组装鉴权信息到 config.auth
    if (values.auth_type && values.auth_type !== 'none') {
      const auth: Record<string, unknown> = { type: values.auth_type };
      if (values.auth_type === 'bearer' && values.auth_token) {
        auth.token = values.auth_token;
      } else if (values.auth_type === 'api_key') {
        auth.key = values.auth_api_key || '';
        if (values.auth_header_name) {
          auth.header_name = values.auth_header_name;
        }
      } else if (values.auth_type === 'custom' && values.auth_custom_headers) {
        try {
          auth.headers = JSON.parse(values.auth_custom_headers);
        } catch {
          message.error('自定义请求头 JSON 格式不正确');
          return;
        }
      }
      config.auth = auth;
    }

    setCreateLoading(true);
    try {
      const data: AgentCreateData = {
        name: values.name,
        version: values.version,
        description: values.description || undefined,
        endpoint_url: values.endpoint_url || undefined,
        config,
      };
      await createAgent(projectId, data);
      message.success('Agent 注册成功');
      form.resetFields();
      setCreateOpen(false);
      fetchList();
    } catch (err: unknown) {
      message.error((err as { message?: string })?.message ?? '注册失败');
    } finally {
      setCreateLoading(false);
    }
  }

  // 删除 Agent
  async function handleDelete(agentId: string) {
    if (!projectId) return;
    try {
      await deleteAgent(projectId, agentId);
      message.success('Agent 已删除');
      await fetchList();
    } catch (err: unknown) {
      message.error((err as { message?: string })?.message ?? '删除失败');
    }
  }

  // 表格列
  const columns: ColumnsType<AgentInfo> = [
    {
      title: '名称',
      dataIndex: 'name',
      key: 'name',
      width: 160,
      render: (v: string) => <Text strong>{v}</Text>,
    },
    {
      title: '版本号',
      dataIndex: 'version',
      key: 'version',
      width: 120,
      render: (v: string) => <Tag color="blue">{v}</Tag>,
    },
    {
      title: '描述',
      dataIndex: 'description',
      key: 'description',
      ellipsis: true,
      render: (v: string | undefined) => v || '-',
    },
    {
      title: '端点 URL',
      dataIndex: 'endpoint_url',
      key: 'endpoint_url',
      width: 240,
      ellipsis: true,
      render: (v: string | undefined) =>
        v ? (
          <Tooltip title={v}>
            <Text code copyable style={{ fontSize: 12 }}>
              {v.length > 30 ? `${v.slice(0, 30)}...` : v}
            </Text>
          </Tooltip>
        ) : (
          <Text type="secondary">-</Text>
        ),
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 170,
      render: (v: string | undefined) =>
        v ? dayjs(v).format('YYYY-MM-DD HH:mm:ss') : '-',
    },
    {
      title: '操作',
      key: 'actions',
      width: 80,
      align: 'center',
      render: (_: unknown, record: AgentInfo) => (
        <Popconfirm
          title="确定删除该 Agent？"
          description={`确定要删除 Agent「${record.name}」吗？删除后关联评测数据保留。`}
          onConfirm={() => handleDelete(record.id)}
          okText="确定删除"
          cancelText="取消"
          okButtonProps={{ danger: true }}
        >
          <Button
            type="link"
            danger
            icon={<DeleteOutlined />}
            size="small"
          >
            删除
          </Button>
        </Popconfirm>
      ),
    },
  ];

  return (
    <div>
      {/* 标题栏 */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: 16,
        }}
      >
        <div>
          <Title level={4} style={{ margin: 0 }}>
            Agent 管理
          </Title>
          <Text type="secondary">注册和管理需要评测的 Agent</Text>
        </div>
        <Space>
          <Button icon={<ReloadOutlined />} onClick={fetchList}>
            刷新
          </Button>
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={() => setCreateOpen(true)}
          >
            注册 Agent
          </Button>
        </Space>
      </div>

      {/* 表格 / 空态 */}
      {!loading && agents.length === 0 ? (
        <Empty
          description="暂无 Agent，点击注册第一个 Agent"
          style={{ marginTop: 60 }}
        >
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={() => setCreateOpen(true)}
          >
            注册 Agent
          </Button>
        </Empty>
      ) : (
        <Table
          rowKey="id"
          columns={columns}
          dataSource={agents}
          loading={loading}
          scroll={{ x: 900 }}
          pagination={
            agents.length > 20
              ? { pageSize: 20, showTotal: (t) => `共 ${t} 个` }
              : false
          }
        />
      )}

      {/* 注册 Agent Modal */}
      <Modal
        title="注册 Agent"
        open={createOpen}
        onCancel={() => {
          form.resetFields();
          setCreateOpen(false);
        }}
        footer={null}
        width={520}
        destroyOnClose
      >
        <Form
          form={form}
          layout="vertical"
          onFinish={handleCreate}
          initialValues={{ config_json: '{}' }}
        >
          <Form.Item
            name="name"
            label="Agent 名称"
            rules={[
              { required: true, message: '请输入 Agent 名称' },
              { max: 100, message: '名称最长 100 个字符' },
            ]}
          >
            <Input placeholder="例如：CustomerBot" />
          </Form.Item>

          <Form.Item
            name="version"
            label="版本号"
            rules={[
              { required: true, message: '请输入版本号' },
              {
                pattern: SEMVER_REGEX,
                message: '版本号格式不正确，例如 1.0.0',
              },
            ]}
          >
            <Input placeholder="例如：1.0.0" />
          </Form.Item>

          <Form.Item
            name="description"
            label="描述（选填）"
            rules={[{ max: 2000, message: '描述最长 2000 个字符' }]}
          >
            <TextArea
              placeholder="描述该 Agent 的用途和特点"
              rows={2}
              maxLength={2000}
              showCount
            />
          </Form.Item>

          <Form.Item
            name="endpoint_url"
            label="端点 URL（选填）"
            rules={[{ max: 500, message: '端点 URL 最长 500 个字符' }]}
          >
            <Input placeholder="例如：http://agent-service:8080/api/chat" />
          </Form.Item>

          <Form.Item
            name="auth_type"
            label="接口鉴权"
            initialValue="none"
          >
            <Select>
              <Select.Option value="none">无需鉴权</Select.Option>
              <Select.Option value="bearer">Bearer Token</Select.Option>
              <Select.Option value="api_key">API Key</Select.Option>
              <Select.Option value="custom">自定义请求头</Select.Option>
            </Select>
          </Form.Item>

          {authType === 'bearer' && (
            <Form.Item name="auth_token" label="Token">
              <Input.Password placeholder="输入 Bearer Token" />
            </Form.Item>
          )}

          {authType === 'api_key' && (
            <>
              <Form.Item name="auth_api_key" label="API Key">
                <Input.Password placeholder="输入 API Key" />
              </Form.Item>
              <Form.Item name="auth_header_name" label="请求头名称" initialValue="X-API-Key">
                <Input placeholder="默认 X-API-Key" />
              </Form.Item>
            </>
          )}

          {authType === 'custom' && (
            <Form.Item
              name="auth_custom_headers"
              label="自定义请求头（JSON）"
              rules={[
                {
                  validator: (_, value) => {
                    if (!value || !value.trim()) return Promise.resolve();
                    try {
                      JSON.parse(value);
                      return Promise.resolve();
                    } catch {
                      return Promise.reject(new Error('JSON 格式不正确'));
                    }
                  },
                },
              ]}
            >
              <TextArea
                placeholder='{"X-Custom-Auth": "value"}'
                rows={2}
              />
            </Form.Item>
          )}

          <Form.Item
            name="config_json"
            label="配置（选填，JSON 格式）"
            rules={[
              {
                validator: (_, value) => {
                  if (!value || !value.trim()) return Promise.resolve();
                  try {
                    JSON.parse(value);
                    return Promise.resolve();
                  } catch {
                    return Promise.reject(new Error('配置字段 JSON 格式不正确'));
                  }
                },
              },
            ]}
          >
            <TextArea
              placeholder='{"model": "gpt-4", "temperature": 0.1}'
              rows={3}
            />
          </Form.Item>

          <Form.Item style={{ marginBottom: 0, textAlign: 'right' }}>
            <Space>
              <Button
                onClick={() => {
                  form.resetFields();
                  setCreateOpen(false);
                }}
              >
                取消
              </Button>
              <Button type="primary" htmlType="submit" loading={createLoading}>
                确认注册
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}