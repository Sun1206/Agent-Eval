/**
 * API Key 管理页
 *
 * API Key 列表 + 创建 Modal + 吊销操作
 */
import { useEffect, useState, useCallback } from 'react';
import {
  Table,
  Button,
  Modal,
  Form,
  Input,
  message,
  Popconfirm,
  Tag,
  Typography,
  Space,
  Alert,
  DatePicker,
} from 'antd';
import {
  PlusOutlined,
  ReloadOutlined,
  KeyOutlined,
  CopyOutlined,
} from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import dayjs from 'dayjs';
import {
  listApiKeys,
  createApiKey,
  revokeApiKey,
  ApiKeyInfo,
} from '@/services/auth';

const { Text } = Typography;

export default function ApiKeyPage() {
  const [keys, setKeys] = useState<ApiKeyInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [modalOpen, setModalOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  const [form] = Form.useForm();

  // 新创建的 Key（仅展示一次）
  const [newKeyResult, setNewKeyResult] = useState<{ name: string; full_key: string } | null>(null);

  const fetchKeys = useCallback(async () => {
    setLoading(true);
    try {
      const data = await listApiKeys();
      setKeys(data);
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        (err as { message?: string })?.message ??
        '获取 API Key 列表失败';
      message.error(msg);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchKeys();
  }, [fetchKeys]);

  // 创建 API Key
  async function handleCreate(values: { name: string; expires_at?: dayjs.Dayjs }) {
    setCreating(true);
    try {
      const result = await createApiKey(
        values.name,
        values.expires_at?.toISOString(),
      );
      message.success('API Key 创建成功');
      setModalOpen(false);
      form.resetFields();
      // 展示完整 Key（仅此一次）
      setNewKeyResult({ name: result.name, full_key: result.full_key });
      await fetchKeys();
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        (err as { message?: string })?.message ??
        '创建失败';
      message.error(msg);
    } finally {
      setCreating(false);
    }
  }

  // 吊销 API Key
  async function handleRevoke(keyId: string) {
    try {
      await revokeApiKey(keyId);
      message.success('API Key 已吊销');
      await fetchKeys();
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        (err as { message?: string })?.message ??
        '吊销失败';
      message.error(msg);
    }
  }

  // 复制到剪贴板
  function copyToClipboard(text: string) {
    navigator.clipboard.writeText(text).then(
      () => message.success('已复制到剪贴板'),
      () => message.error('复制失败'),
    );
  }

  // 表格列定义
  const columns: ColumnsType<ApiKeyInfo> = [
    {
      title: '名称',
      dataIndex: 'name',
      key: 'name',
      width: 180,
    },
    {
      title: 'Key 前缀',
      dataIndex: 'key_prefix',
      key: 'key_prefix',
      width: 160,
      render: (val: string) => <Text code>{val}</Text>,
    },
    {
      title: '状态',
      dataIndex: 'is_active',
      key: 'is_active',
      width: 80,
      render: (val: boolean) =>
        val ? <Tag color="green">有效</Tag> : <Tag color="default">已吊销</Tag>,
    },
    {
      title: '过期时间',
      dataIndex: 'expires_at',
      key: 'expires_at',
      width: 180,
      render: (val?: string) =>
        val ? dayjs(val).format('YYYY-MM-DD HH:mm') : <Text type="secondary">永不过期</Text>,
    },
    {
      title: '最后使用',
      dataIndex: 'last_used_at',
      key: 'last_used_at',
      width: 180,
      render: (val?: string) =>
        val ? dayjs(val).format('YYYY-MM-DD HH:mm') : <Text type="secondary">-</Text>,
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 180,
      render: (val: string) => dayjs(val).format('YYYY-MM-DD HH:mm'),
    },
    {
      title: '操作',
      key: 'action',
      width: 100,
      render: (_: unknown, record: ApiKeyInfo) =>
        record.is_active ? (
          <Popconfirm
            title="确定吊销此 API Key？"
            description="吊销后使用该 Key 的 SDK 将无法连接"
            onConfirm={() => handleRevoke(record.id)}
          >
            <Button type="link" danger size="small">
              吊销
            </Button>
          </Popconfirm>
        ) : (
          <Text type="secondary" style={{ fontSize: 12 }}>
            已吊销
          </Text>
        ),
    },
  ];

  return (
    <div style={{ padding: 24 }}>
      <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between' }}>
        <Space>
          <KeyOutlined style={{ fontSize: 20 }} />
          <Text strong style={{ fontSize: 16 }}>
            API Key 管理
          </Text>
        </Space>
        <Space>
          <Button icon={<ReloadOutlined />} onClick={fetchKeys}>
            刷新
          </Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => setModalOpen(true)}>
            创建 Key
          </Button>
        </Space>
      </div>

      {/* 新创建的 Key 提示 */}
      {newKeyResult && (
        <Alert
          type="success"
          showIcon
          closable
          onClose={() => setNewKeyResult(null)}
          style={{ marginBottom: 16 }}
          message={`API Key "${newKeyResult.name}" 创建成功`}
          description={
            <Space direction="vertical" size={4}>
              <Text>请立即复制并保存，关闭后无法再次查看：</Text>
              <Space>
                <Text code style={{ fontSize: 13, wordBreak: 'break-all' }}>
                  {newKeyResult.full_key}
                </Text>
                <Button
                  type="link"
                  icon={<CopyOutlined />}
                  onClick={() => copyToClipboard(newKeyResult.full_key)}
                >
                  复制
                </Button>
              </Space>
            </Space>
          }
        />
      )}

      <Table
        rowKey="id"
        columns={columns}
        dataSource={keys}
        loading={loading}
        pagination={false}
        size="middle"
      />

      {/* 创建 Modal */}
      <Modal
        title="创建 API Key"
        open={modalOpen}
        onCancel={() => {
          setModalOpen(false);
          form.resetFields();
        }}
        footer={null}
        destroyOnClose
        width={480}
      >
        <Form form={form} layout="vertical" onFinish={handleCreate} style={{ marginTop: 16 }}>
          <Form.Item
            name="name"
            label="Key 名称"
            rules={[
              { required: true, message: '请输入 Key 名称' },
              { max: 100, message: '名称不超过 100 个字符' },
            ]}
          >
            <Input placeholder="例如：生产环境 SDK Key" maxLength={100} />
          </Form.Item>

          <Form.Item name="expires_at" label="过期时间（选填）">
            <DatePicker
              showTime
              style={{ width: '100%' }}
              placeholder="不设则永不过期"
              disabledDate={(current) => current && current < dayjs().startOf('day')}
            />
          </Form.Item>

          <Form.Item style={{ marginBottom: 0, textAlign: 'right' }}>
            <Space>
              <Button
                onClick={() => {
                  setModalOpen(false);
                  form.resetFields();
                }}
              >
                取消
              </Button>
              <Button type="primary" htmlType="submit" loading={creating}>
                创建
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
