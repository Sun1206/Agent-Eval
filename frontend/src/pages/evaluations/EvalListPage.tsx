/**
 * 评测任务列表页
 *
 * 表格：名称/数据集/Agent/状态(含进度)/通过率/平均分/创建时间 + 新建评测按钮
 */
import { useEffect, useState, useCallback } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { Table, Button, Tag, Progress, Typography, message, Space, Popconfirm } from 'antd';
import { PlusOutlined, ReloadOutlined, RedoOutlined, DeleteOutlined } from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import {
  listEvalRuns,
  cancelEvalRun,
  retryEvalRun,
  deleteEvalRun,
  EvalRunListItem,
} from '@/services/evaluation';
import EvalCreateModal from './EvalCreateModal';
import dayjs from 'dayjs';

const { Title, Text } = Typography;

/** 状态标签 */
function StatusTag({ status, total, completed }: { status: string; total: number; completed: number }) {
  const config: Record<string, { color: string; text: string }> = {
    PENDING: { color: 'default', text: '等待中' },
    RUNNING: { color: 'processing', text: '运行中' },
    COMPLETED: { color: 'success', text: '已完成' },
    FAILED: { color: 'error', text: '失败' },
    CANCELLED: { color: 'warning', text: '已取消' },
  };
  const c = config[status] || { color: 'default', text: status };
  const percent = total > 0 ? Math.round((completed / total) * 100) : 0;

  return (
    <div>
      <Tag color={c.color}>{c.text}</Tag>
      {status === 'RUNNING' && (
        <Progress
          percent={percent}
          size="small"
          style={{ width: 120 }}
          format={() => `${completed}/${total}`}
        />
      )}
    </div>
  );
}

export default function EvalListPage() {
  const navigate = useNavigate();
  const { projectId } = useParams<{ projectId: string }>();
  const [runs, setRuns] = useState<EvalRunListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [loading, setLoading] = useState(true);
  const [createOpen, setCreateOpen] = useState(false);
  const [cancelling, setCancelling] = useState<string | null>(null);

  const fetchList = useCallback(async () => {
    if (!projectId) return;
    setLoading(true);
    try {
      const res = await listEvalRuns(projectId, page, pageSize);
      setRuns(res.items);
      setTotal(res.total);
    } catch {
      message.error('加载评测列表失败');
    } finally {
      setLoading(false);
    }
  }, [projectId, page, pageSize]);

  useEffect(() => {
    fetchList();
  }, [fetchList]);

  // 运行中的每 5 秒自动刷新
  useEffect(() => {
    if (runs.some((r) => r.status === 'RUNNING')) {
      const timer = setInterval(fetchList, 5000);
      return () => clearInterval(timer);
    }
  }, [runs, fetchList]);

  /** 取消评测 */
  async function handleCancel(runId: string) {
    if (!projectId) return;
    setCancelling(runId);
    try {
      await cancelEvalRun(projectId, runId);
      message.success('评测已取消');
      await fetchList();
    } catch (err: unknown) {
      message.error((err as { message?: string })?.message ?? '取消失败');
    } finally {
      setCancelling(null);
    }
  }

  /** 重试评测 */
  async function handleRetry(runId: string) {
    if (!projectId) return;
    try {
      await retryEvalRun(projectId, runId);
      message.success('评测已重新开始');
      await fetchList();
    } catch (err: unknown) {
      message.error((err as { message?: string })?.message ?? '重试失败');
    }
  }

  /** 删除评测 */
  async function handleDelete(runId: string) {
    if (!projectId) return;
    try {
      await deleteEvalRun(projectId, runId);
      message.success('评测已删除');
      await fetchList();
    } catch (err: unknown) {
      message.error((err as { message?: string })?.message ?? '删除失败');
    }
  }

  const columns: ColumnsType<EvalRunListItem> = [
    {
      title: '名称',
      dataIndex: 'name',
      key: 'name',
      ellipsis: true,
      render: (v: string | undefined, record: EvalRunListItem) => (
        <a onClick={() => navigate(record.id)}>{v || '(未命名)'}</a>
      ),
    },
    {
      title: '状态',
      key: 'status',
      width: 180,
      render: (_: unknown, record: EvalRunListItem) => (
        <StatusTag
          status={record.status}
          total={record.total_items}
          completed={record.completed_items}
        />
      ),
    },
    {
      title: '通过率',
      dataIndex: 'pass_rate',
      key: 'pass_rate',
      width: 90,
      align: 'center',
      render: (v: number | undefined) =>
        v != null ? `${(v * 100).toFixed(1)}%` : '-',
    },
    {
      title: '平均分',
      dataIndex: 'avg_score',
      key: 'avg_score',
      width: 90,
      align: 'center',
      render: (v: number | undefined) =>
        v != null ? v.toFixed(1) : '-',
    },
    {
      title: '进度',
      key: 'progress',
      width: 130,
      render: (_: unknown, record: EvalRunListItem) =>
        `${record.completed_items}/${record.total_items}`,
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 170,
      render: (v: string | undefined) => (v ? dayjs(v).format('YYYY-MM-DD HH:mm') : '-'),
    },
    {
      title: '操作',
      key: 'actions',
      width: 160,
      fixed: 'right',
      render: (_: unknown, record: EvalRunListItem) => (
        <Space size="small">
          <a onClick={() => navigate(record.id)}>详情</a>
          {record.status === 'RUNNING' && (
            <a
              onClick={() => handleCancel(record.id)}
              style={{ color: '#faad14' }}
            >
              {cancelling === record.id ? '取消中...' : '取消'}
            </a>
          )}
          {(record.status === 'FAILED' || record.status === 'CANCELLED' || record.status === 'PENDING') && (
            <a onClick={() => handleRetry(record.id)} style={{ color: '#1677FF' }}>
              重试
            </a>
          )}
          {record.status !== 'RUNNING' && (
            <Popconfirm
              title="确定删除此评测任务？"
              description="删除后数据将无法恢复"
              onConfirm={() => handleDelete(record.id)}
            >
              <a style={{ color: '#ff4d4f' }}>删除</a>
            </Popconfirm>
          )}
        </Space>
      ),
    },
  ];

  return (
    <div>
      {/* 头部 */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <div>
          <Title level={4} style={{ margin: 0 }}>评测管理</Title>
          <Text type="secondary">管理 Agent 评测任务和结果</Text>
        </div>
        <Space>
          <Button icon={<ReloadOutlined />} onClick={fetchList}>刷新</Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => setCreateOpen(true)}>
            新建评测
          </Button>
        </Space>
      </div>

      {/* 表格 */}
      <Table
        rowKey="id"
        columns={columns}
        dataSource={runs}
        loading={loading}
        pagination={{
          current: page,
          pageSize,
          total,
          showSizeChanger: true,
          showTotal: (t) => `共 ${t} 条`,
          onChange: (p, ps) => {
            setPage(p);
            setPageSize(ps);
          },
        }}
      />

      {/* 新建评测 Modal */}
      <EvalCreateModal
        projectId={projectId!}
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        onSuccess={fetchList}
      />
    </div>
  );
}