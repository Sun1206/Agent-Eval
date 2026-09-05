/**
 * 数据集列表页
 *
 * 搜索框 + 新建按钮 + Table 展示（名称/描述/标签/条目数/创建时间）
 */
import { useEffect, useState, useCallback } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { Table, Button, Input, Modal, Form, Tag, Typography, message, Space } from 'antd';
import { PlusOutlined, SearchOutlined, ReloadOutlined } from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import {
  listDatasets,
  createDataset,
  DatasetInfo,
} from '@/services/dataset';
import dayjs from 'dayjs';

const { Title, Text } = Typography;

export default function DatasetListPage() {
  const navigate = useNavigate();
  const { projectId } = useParams<{ projectId: string }>();
  const [datasets, setDatasets] = useState<DatasetInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [modalOpen, setModalOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  const [form] = Form.useForm();

  const fetchList = useCallback(async () => {
    if (!projectId) return;
    setLoading(true);
    try {
      const data = await listDatasets(projectId);
      setDatasets(data);
    } catch {
      message.error('加载数据集列表失败');
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    fetchList();
  }, [fetchList]);

  // 搜索过滤
  const filtered = search.trim()
    ? datasets.filter((d) => d.name.toLowerCase().includes(search.toLowerCase()))
    : datasets;

  // 新建
  async function handleCreate(values: { name: string; description?: string; tags?: string[] }) {
    if (!projectId) return;
    setCreating(true);
    try {
      await createDataset(projectId, {
        name: values.name,
        description: values.description,
        tags: values.tags,
      });
      message.success('数据集创建成功');
      setModalOpen(false);
      form.resetFields();
      await fetchList();
    } catch (err: unknown) {
      message.error((err as { message?: string })?.message ?? '创建失败');
    } finally {
      setCreating(false);
    }
  }

  const columns: ColumnsType<DatasetInfo> = [
    {
      title: '名称',
      dataIndex: 'name',
      key: 'name',
      render: (text: string, record: DatasetInfo) => (
        <a onClick={() => navigate(record.id)}>{text}</a>
      ),
    },
    {
      title: '描述',
      dataIndex: 'description',
      key: 'description',
      ellipsis: true,
      render: (v: string | undefined) => v || '-',
    },
    {
      title: '标签',
      dataIndex: 'tags',
      key: 'tags',
      width: 200,
      render: (tags: string[]) =>
        tags?.length
          ? tags.map((t) => <Tag key={t}>{t}</Tag>)
          : '-',
    },
    {
      title: '条目数',
      dataIndex: 'item_count',
      key: 'item_count',
      width: 100,
      align: 'center',
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 180,
      render: (v: string) => dayjs(v).format('YYYY-MM-DD HH:mm'),
    },
  ];

  return (
    <div>
      {/* 头部 */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <div>
          <Title level={4} style={{ margin: 0 }}>数据集管理</Title>
          <Text type="secondary">管理评测用的数据集和条目</Text>
        </div>
        <Space>
          <Input
            prefix={<SearchOutlined />}
            placeholder="搜索数据集名称"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            allowClear
            style={{ width: 240 }}
          />
          <Button icon={<ReloadOutlined />} onClick={fetchList}>刷新</Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => setModalOpen(true)}>
            新建数据集
          </Button>
        </Space>
      </div>

      {/* 表格 */}
      <Table
        rowKey="id"
        columns={columns}
        dataSource={filtered}
        loading={loading}
        pagination={false}
        locale={{ emptyText: '暂无数据集，点击右上角"新建数据集"开始' }}
      />

      {/* 新建 Modal */}
      <Modal
        title="新建数据集"
        open={modalOpen}
        onCancel={() => { setModalOpen(false); form.resetFields(); }}
        footer={null}
        destroyOnClose
        width={480}
      >
        <Form form={form} layout="vertical" onFinish={handleCreate} style={{ marginTop: 16 }}>
          <Form.Item
            name="name"
            label="数据集名称"
            rules={[{ required: true, message: '请输入数据集名称' }, { max: 200 }]}
          >
            <Input placeholder="输入数据集名称" maxLength={200} />
          </Form.Item>
          <Form.Item
            name="description"
            label="描述"
            rules={[{ max: 2000 }]}
          >
            <Input.TextArea placeholder="输入描述（选填）" rows={3} maxLength={2000} showCount />
          </Form.Item>
          <Form.Item
            name="tags"
            label="标签"
            help="按 Enter 添加标签"
          >
            {/* @ts-ignore Ant Design Select mode="tags" 类型兼容 */}
            {/* eslint-disable-next-line @typescript-eslint/no-explicit-any */}
            {Form.useWatch('tags', form) !== undefined || true ? (
              <Input placeholder="输入标签后按回车" onPressEnter={(e) => {
                const value = (e.target as HTMLInputElement).value.trim();
                if (value) {
                  const currentTags: string[] = form.getFieldValue('tags') || [];
                  if (!currentTags.includes(value)) {
                    form.setFieldsValue({ tags: [...currentTags, value] });
                  }
                  (e.target as HTMLInputElement).value = '';
                }
              }} />
            ) : (
              <Input placeholder="输入标签后按回车" />
            )}
          </Form.Item>
          <Form.Item style={{ marginBottom: 0, textAlign: 'right' }}>
            <Space>
              <Button onClick={() => { setModalOpen(false); form.resetFields(); }}>取消</Button>
              <Button type="primary" htmlType="submit" loading={creating}>创建</Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}