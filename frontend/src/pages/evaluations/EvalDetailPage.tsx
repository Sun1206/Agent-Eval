/**
 * 评测详情页
 *
 * 任务信息 + 统计卡片行 (通过率/平均分/维度得分/总耗时) + 结果表格 (分页/状态筛选/排序/Trace 跳转)
 * 运行中任务每 5 秒自动轮询进度
 */
import { useEffect, useState, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Card,
  Table,
  Button,
  Descriptions,
  Tag,
  Typography,
  message,
  Space,
  Select,
  Row,
  Col,
  Statistic,
  Progress,
  Tooltip,
} from 'antd';
import {
  ReloadOutlined,
  LinkOutlined,
  TrophyOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  ClockCircleOutlined,
  StarOutlined,
  RedoOutlined,
} from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import {
  getEvalRunDetail,
  listEvalResults,
  getEvalStats,
  getEvalProgress,
  retryEvalResult,
  EvalRunDetail,
  EvalResultItem,
  EvalStats,
} from '@/services/evaluation';
import dayjs from 'dayjs';

const { Title, Text } = Typography;

/** 状态标签 */
function ResultStatusTag({ status }: { status: string }) {
  const config: Record<string, { color: string; text: string }> = {
    SUCCESS: { color: 'success', text: '成功' },
    FAILURE: { color: 'error', text: '失败' },
    ERROR: { color: 'error', text: '错误' },
    TIMEOUT: { color: 'warning', text: '超时' },
    PENDING: { color: 'default', text: '等待中' },
    RUNNING: { color: 'processing', text: '运行中' },
  };
  const c = config[status] || { color: 'default', text: status };
  return <Tag color={c.color}>{c.text}</Tag>;
}

export default function EvalDetailPage() {
  const { projectId, runId } = useParams<{ projectId: string; runId: string }>();
  const navigate = useNavigate();

  // 任务详情
  const [detail, setDetail] = useState<EvalRunDetail | null>(null);

  // 统计
  const [stats, setStats] = useState<EvalStats | null>(null);

  // 结果表格
  const [results, setResults] = useState<EvalResultItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [loading, setLoading] = useState(true);

  // 筛选 / 排序
  const [filterStatus, setFilterStatus] = useState<string | undefined>(undefined);
  const [sortBy, setSortBy] = useState<string>('sort_order');
  const [sortOrder, setSortOrder] = useState<string>('asc');

  // 进度
  const [progress, setProgress] = useState<{
    completed: number;
    total: number;
    status: string;
    avg_score: number | null;
    pass_rate: number | null;
  }>({ completed: 0, total: 0, status: 'UNKNOWN', avg_score: null, pass_rate: null });

  // ---------- 加载 ----------

  const fetchDetail = useCallback(async () => {
    if (!projectId || !runId) return;
    try {
      const d = await getEvalRunDetail(projectId, runId);
      setDetail(d);
    } catch {
      message.error('加载评测详情失败');
    }
  }, [projectId, runId]);

  const fetchStats = useCallback(async () => {
    if (!projectId || !runId) return;
    try {
      const s = await getEvalStats(projectId, runId);
      setStats(s);
    } catch {
      // 任务可能刚开始没有统计
    }
  }, [projectId, runId]);

  const fetchResults = useCallback(async () => {
    if (!projectId || !runId) return;
    setLoading(true);
    try {
      const res = await listEvalResults(projectId, runId, page, pageSize, {
        status: filterStatus,
        sort_by: sortBy,
        sort_order: sortOrder,
      });
      setResults(res.items);
      setTotal(res.total);
    } catch {
      message.error('加载评测结果失败');
    } finally {
      setLoading(false);
    }
  }, [projectId, runId, page, pageSize, filterStatus, sortBy, sortOrder]);

  const fetchProgress = useCallback(async () => {
    if (!projectId || !runId) return;
    try {
      const p = await getEvalProgress(projectId, runId);
      setProgress({
        completed: p.completed_items,
        total: p.total_items,
        status: p.status,
        avg_score: p.avg_score ?? null,
        pass_rate: p.pass_rate ?? null,
      });
      return p;
    } catch {
      return null;
    }
  }, [projectId, runId]);

  useEffect(() => {
    fetchDetail();
    fetchStats();
    fetchResults();
  }, [fetchDetail, fetchStats, fetchResults]);

  // 智能轮询：RUNNING 2秒，PENDING 5秒，已完成/失败停止
  useEffect(() => {
    const isActive = detail?.status === 'RUNNING' || detail?.status === 'PENDING';
    if (!isActive) return;

    const interval = detail.status === 'RUNNING' ? 2000 : 5000;

    const timer = setInterval(async () => {
      const p = await fetchProgress();
      if (!p) return;

      // 任务完成时，刷新全量数据并停止轮询
      if (p.status === 'COMPLETED' || p.status === 'FAILED' || p.status === 'CANCELLED') {
        clearInterval(timer);
        fetchDetail();
        fetchStats();
        fetchResults();
      } else if (p.status === 'RUNNING') {
        // 运行中只刷新结果列表，不刷新详情和统计（节省性能）
        fetchResults();
      }
    }, interval);

    return () => clearInterval(timer);
  }, [detail?.status, fetchProgress, fetchDetail, fetchStats, fetchResults]);

  // ---------- 表格列 ----------

  const columns: ColumnsType<EvalResultItem> = [
    {
      title: '#',
      dataIndex: 'sort_order',
      key: 'sort_order',
      width: 50,
      align: 'center',
    },
    {
      title: '输入',
      dataIndex: 'agent_input',
      key: 'agent_input',
      ellipsis: true,
      width: 250,
    },
    {
      title: 'Agent 输出',
      dataIndex: 'agent_output',
      key: 'agent_output',
      ellipsis: true,
      width: 280,
      render: (v: string | undefined) => v || '-',
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 80,
      render: (v: string) => <ResultStatusTag status={v} />,
    },
    {
      title: '总分',
      dataIndex: 'total_score',
      key: 'total_score',
      width: 80,
      align: 'center',
      sorter: true,
      render: (v: number | undefined) =>
        v != null ? <Text strong>{v.toFixed(1)}</Text> : '-',
    },
    {
      title: '维度得分',
      dataIndex: 'dimension_scores',
      key: 'dimension_scores',
      width: 180,
      render: (scores: Record<string, number>) => {
        if (!scores || Object.keys(scores).length === 0) return '-';
        return Object.entries(scores).map(([k, v]) => (
          <Tag key={k} style={{ fontSize: 11 }}>
            {k}: {v.toFixed(1)}
          </Tag>
        ));
      },
    },
    {
      title: '耗时',
      dataIndex: 'duration_ms',
      key: 'duration_ms',
      width: 90,
      align: 'center',
      sorter: true,
      render: (v: number | undefined) =>
        v != null ? `${(v / 1000).toFixed(1)}s` : '-',
    },
    {
      title: '错误信息',
      dataIndex: 'error_message',
      key: 'error_message',
      ellipsis: true,
      width: 150,
      render: (v: string | undefined) => v || '-',
    },
    {
      title: 'Trace',
      dataIndex: 'trace_id',
      key: 'trace_id',
      width: 80,
      align: 'center',
      render: (traceId: string | undefined) =>
        traceId ? (
          <Tooltip title={`Trace: ${traceId}`}>
            <a
              onClick={() => {
                navigate(`/projects/${projectId}/traces/${traceId}`);
              }}
              style={{ fontSize: 12 }}
            >
              <LinkOutlined /> 查看
            </a>
          </Tooltip>
        ) : (
          '-'
        ),
    },
    {
      title: '操作',
      key: 'actions',
      width: 80,
      align: 'center',
      render: (_: unknown, record: EvalResultItem) => {
        const canRetry = ['ERROR', 'TIMEOUT', 'FAILURE'].includes(record.status);
        if (!canRetry) return '-';
        return (
          <a
            onClick={async () => {
              if (!projectId || !runId) return;
              try {
                await retryEvalResult(projectId, runId, record.id);
                message.success('重试已开始');
                fetchResults();
                fetchStats();
                fetchDetail();
              } catch (err: unknown) {
                message.error((err as { message?: string })?.message ?? '重试失败');
              }
            }}
            style={{ color: '#1677FF', fontSize: 12 }}
          >
            <RedoOutlined /> 重试
          </a>
        );
      },
    },
  ];

  return (
    <div>
      {/* 任务信息 */}
      <Card style={{ marginBottom: 16 }}>
        <Descriptions title="评测任务信息" column={4} size="small">
          <Descriptions.Item label="名称">{detail?.name || '(未命名)'}</Descriptions.Item>
          <Descriptions.Item label="状态">
            {detail && (
              <Tag
                color={
                  detail.status === 'COMPLETED'
                    ? 'success'
                    : detail.status === 'RUNNING'
                      ? 'processing'
                      : detail.status === 'FAILED'
                        ? 'error'
                        : detail.status === 'CANCELLED'
                          ? 'warning'
                          : 'default'
                }
              >
                {{ PENDING: '等待中', RUNNING: '运行中', COMPLETED: '已完成', FAILED: '失败', CANCELLED: '已取消' }[detail.status] || detail.status}
              </Tag>
            )}
          </Descriptions.Item>
          <Descriptions.Item label="并发">{detail?.concurrency ?? '-'}</Descriptions.Item>
          <Descriptions.Item label="创建时间">
            {detail?.created_at ? dayjs(detail.created_at).format('YYYY-MM-DD HH:mm') : '-'}
          </Descriptions.Item>
          <Descriptions.Item label="评审模型">
            {detail?.judge_config
              ? `${detail.judge_config.provider}/${detail.judge_config.model}`
              : '-'}
          </Descriptions.Item>
          <Descriptions.Item label="评审维度">
            {detail?.judge_config?.dimensions?.join('、') || '-'}
          </Descriptions.Item>
          <Descriptions.Item label="开始时间">
            {detail?.started_at ? dayjs(detail.started_at).format('YYYY-MM-DD HH:mm') : '-'}
          </Descriptions.Item>
          <Descriptions.Item label="完成时间">
            {detail?.completed_at ? dayjs(detail.completed_at).format('YYYY-MM-DD HH:mm') : '-'}
          </Descriptions.Item>
          {detail?.error_message && (
            <Descriptions.Item label="错误信息" span={2}>
              <Text type="danger">{detail.error_message}</Text>
            </Descriptions.Item>
          )}
        </Descriptions>

        {/* 运行中进度条 */}
        {(detail?.status === 'RUNNING' || detail?.status === 'PENDING') && (
          <div style={{ marginTop: 12 }}>
            <Progress
              percent={progress.total > 0 ? Math.round((progress.completed / progress.total) * 100) : 0}
              format={() => `${progress.completed}/${progress.total}`}
              status={detail.status === 'PENDING' ? 'normal' : 'active'}
            />
            {progress.avg_score != null && (
              <div style={{ marginTop: 8, display: 'flex', gap: 24 }}>
                <Text type="secondary">平均分: <Text strong>{progress.avg_score.toFixed(1)}</Text></Text>
                <Text type="secondary">通过率: <Text strong>{progress.pass_rate != null ? (progress.pass_rate * 100).toFixed(1) + '%' : '-'}</Text></Text>
              </div>
            )}
          </div>
        )}
      </Card>

      {/* 统计卡片 */}
      {stats && detail?.status === 'COMPLETED' && (
        <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
          <Col xs={12} sm={6}>
            <Card size="small">
              <Statistic
                title="通过率"
                value={stats.pass_rate != null ? (stats.pass_rate * 100).toFixed(1) : '-'}
                suffix="%"
                prefix={<CheckCircleOutlined />}
                valueStyle={{ color: (stats.pass_rate ?? 0) >= 0.8 ? '#52c41a' : '#faad14' }}
              />
            </Card>
          </Col>
          <Col xs={12} sm={6}>
            <Card size="small">
              <Statistic
                title="平均分"
                value={stats.avg_score != null ? stats.avg_score.toFixed(1) : '-'}
                prefix={<StarOutlined />}
                valueStyle={{ color: (stats.avg_score ?? 0) >= 80 ? '#52c41a' : '#faad14' }}
              />
            </Card>
          </Col>
          <Col xs={12} sm={6}>
            <Card size="small">
              <Statistic
                title="成功"
                value={stats.success_items}
                suffix={`/ ${stats.total_items}`}
                prefix={<TrophyOutlined />}
                valueStyle={{ color: '#1677ff' }}
              />
            </Card>
          </Col>
          <Col xs={12} sm={6}>
            <Card size="small">
              <Statistic
                title="平均耗时"
                value={stats.avg_duration_ms != null ? (stats.avg_duration_ms / 1000).toFixed(1) : '-'}
                suffix="s"
                prefix={<ClockCircleOutlined />}
              />
            </Card>
          </Col>
        </Row>
      )}

      {/* 维度平均分卡片 */}
      {stats && stats.dimension_avgs && Object.keys(stats.dimension_avgs).length > 0 && (
        <Card title="各维度平均分" size="small" style={{ marginBottom: 16 }}>
          <Row gutter={[12, 12]}>
            {Object.entries(stats.dimension_avgs).map(([dim, score]) => (
              <Col key={dim} xs={12} sm={8} md={6} lg={4}>
                <Card size="small" style={{ textAlign: 'center' }}>
                  <Text type="secondary" style={{ fontSize: 12 }}>{dim}</Text>
                  <div>
                    <Text strong style={{ fontSize: 20 }}>{score.toFixed(1)}</Text>
                  </div>
                </Card>
              </Col>
            ))}
          </Row>
        </Card>
      )}

      {/* 结果表格 */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <Title level={5} style={{ margin: 0 }}>评测结果（共 {total} 条）</Title>
        <Space>
          <Select
            allowClear
            placeholder="筛选状态"
            value={filterStatus}
            onChange={(v) => { setFilterStatus(v); setPage(1); }}
            style={{ width: 130 }}
            options={[
              { value: 'SUCCESS', label: '成功' },
              { value: 'FAILURE', label: '失败' },
              { value: 'ERROR', label: '错误' },
              { value: 'TIMEOUT', label: '超时' },
            ]}
          />
          <Select
            value={sortBy}
            onChange={(v) => { setSortBy(v); setPage(1); }}
            style={{ width: 110 }}
            options={[
              { value: 'sort_order', label: '序号' },
              { value: 'total_score', label: '总分' },
              { value: 'duration_ms', label: '耗时' },
            ]}
          />
          <Select
            value={sortOrder}
            onChange={(v) => { setSortOrder(v); setPage(1); }}
            style={{ width: 90 }}
            options={[
              { value: 'asc', label: '升序' },
              { value: 'desc', label: '降序' },
            ]}
          />
          <Button icon={<ReloadOutlined />} onClick={fetchResults}>刷新</Button>
        </Space>
      </div>

      <Table
        rowKey="id"
        columns={columns}
        dataSource={results}
        loading={loading}
        scroll={{ x: 1400 }}
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
    </div>
  );
}