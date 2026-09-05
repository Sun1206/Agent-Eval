/**
 * Trace 列表页
 *
 * 筛选栏（Agent/状态/时间范围/关键词搜索） + 分页表格
 */
import { useEffect, useState, useCallback } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  Table,
  Select,
  Input,
  DatePicker,
  Tag,
  Typography,
  message,
  Space,
  Row,
  Col,
  Button,
} from 'antd';
import { SearchOutlined, ReloadOutlined } from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import { listTraces, TraceListItem, TraceListParams } from '@/services/trace';
import { listAgents, AgentInfo } from '@/services/agent';
import dayjs from 'dayjs';

const { Title, Text } = Typography;
const { RangePicker } = DatePicker;

/** 格式化毫秒 */
function fmtMs(ms?: number): string {
  if (ms == null) return '-';
  if (ms >= 1000) return `${(ms / 1000).toFixed(2)}s`;
  return `${ms}ms`;
}

/** 截断文本 */
function truncate(text?: string, max = 40): string {
  if (!text) return '-';
  return text.length > max ? text.slice(0, max) + '...' : text;
}

export default function TraceListPage() {
  const navigate = useNavigate();
  const { projectId } = useParams<{ projectId: string }>();

  // 列表
  const [traces, setTraces] = useState<TraceListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [loading, setLoading] = useState(true);

  // 筛选
  const [agents, setAgents] = useState<AgentInfo[]>([]);
  const [agentId, setAgentId] = useState<string | undefined>();
  const [status, setStatus] = useState<string | undefined>();
  const [timeRange, setTimeRange] = useState<[dayjs.Dayjs, dayjs.Dayjs] | null>(null);
  const [keyword, setKeyword] = useState('');
  const [sortBy, setSortBy] = useState('start_time');
  const [sortOrder, setSortOrder] = useState('DESC');

  // 加载 Agent 列表
  useEffect(() => {
    if (!projectId) return;
    listAgents(projectId)
      .then(setAgents)
      .catch(() => {});
  }, [projectId]);

  // 加载列表
  const fetchList = useCallback(async () => {
    if (!projectId) return;
    setLoading(true);
    try {
      const params: TraceListParams = {
        page,
        page_size: pageSize,
        agent_id: agentId,
        status: status?.toUpperCase(),
        keyword: keyword.trim() || undefined,
        sort_by: sortBy,
        sort_order: sortOrder,
      };
      if (timeRange && timeRange[0] && timeRange[1]) {
        params.start_time_from = timeRange[0].toISOString();
        params.start_time_to = timeRange[1].toISOString();
      }
      const res = await listTraces(projectId, params);
      setTraces(res.items);
      setTotal(res.total);
    } catch {
      message.error('加载 Trace 列表失败');
    } finally {
      setLoading(false);
    }
  }, [projectId, page, pageSize, agentId, status, timeRange, keyword, sortBy, sortOrder]);

  useEffect(() => {
    fetchList();
  }, [fetchList]);

  // 表格列
  const columns: ColumnsType<TraceListItem> = [
    {
      title: 'Trace ID',
      dataIndex: 'trace_id',
      key: 'trace_id',
      width: 200,
      render: (v: string) => (
        <Text code copyable={{ text: v }} style={{ fontSize: 11 }}>
          {v.slice(0, 8)}...
        </Text>
      ),
    },
    {
      title: 'Agent',
      dataIndex: 'agent_id',
      key: 'agent_id',
      width: 120,
      render: (v: string | undefined) => {
        if (!v) return '-';
        const agent = agents.find((a) => a.id === v);
        return agent ? <Text>{agent.name}</Text> : <Text code style={{ fontSize: 11 }}>{v.slice(0, 8)}...</Text>;
      },
    },
    {
      title: '输入',
      dataIndex: 'input',
      key: 'input',
      ellipsis: true,
      width: 220,
      render: (v: string | undefined) => truncate(v),
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 80,
      align: 'center',
      render: (v: string) => (
        <Tag color={v === 'SUCCESS' ? 'success' : 'error'}>
          {v === 'SUCCESS' ? '成功' : '失败'}
        </Tag>
      ),
    },
    {
      title: '耗时',
      dataIndex: 'duration_ms',
      key: 'duration_ms',
      width: 100,
      align: 'center',
      sorter: true,
      render: (v: number | undefined) => fmtMs(v),
    },
    {
      title: 'Token',
      dataIndex: 'total_tokens',
      key: 'total_tokens',
      width: 90,
      align: 'center',
      render: (v: number) => (v > 0 ? v.toLocaleString() : '-'),
    },
    {
      title: 'Span',
      dataIndex: 'span_count',
      key: 'span_count',
      width: 70,
      align: 'center',
      render: (v: number) => v,
    },
    {
      title: '时间',
      dataIndex: 'start_time',
      key: 'start_time',
      width: 170,
      sorter: true,
      render: (v: string) => dayjs(v).format('YYYY-MM-DD HH:mm:ss'),
    },
    {
      title: '操作',
      key: 'actions',
      width: 80,
      fixed: 'right',
      render: (_: unknown, record: TraceListItem) => (
        <a onClick={() => navigate(record.trace_id)}>详情</a>
      ),
    },
  ];

  return (
    <div>
      {/* 标题 */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <div>
          <Title level={4} style={{ margin: 0 }}>Trace 轨迹</Title>
          <Text type="secondary">查看 Agent 调用的完整链路追踪</Text>
        </div>
        <Space>
          <Select
            value={sortBy}
            onChange={(v) => setSortBy(v)}
            style={{ width: 110 }}
            options={[
              { value: 'start_time', label: '按时间' },
              { value: 'duration_ms', label: '按耗时' },
            ]}
          />
          <Select
            value={sortOrder}
            onChange={(v) => setSortOrder(v)}
            style={{ width: 80 }}
            options={[
              { value: 'DESC', label: '降序' },
              { value: 'ASC', label: '升序' },
            ]}
          />
          <Button icon={<ReloadOutlined />} onClick={fetchList}>刷新</Button>
        </Space>
      </div>

      {/* 筛选栏 */}
      <Row gutter={[12, 12]} style={{ marginBottom: 16 }}>
        <Col xs={24} sm={8} md={4}>
          <Select
            allowClear
            placeholder="Agent"
            value={agentId}
            onChange={(v) => { setAgentId(v); setPage(1); }}
            style={{ width: '100%' }}
            options={agents.map((a) => ({ value: a.id, label: a.name }))}
          />
        </Col>
        <Col xs={24} sm={8} md={3}>
          <Select
            allowClear
            placeholder="状态"
            value={status}
            onChange={(v) => { setStatus(v); setPage(1); }}
            style={{ width: '100%' }}
            options={[
              { value: 'SUCCESS', label: '成功' },
              { value: 'ERROR', label: '失败' },
            ]}
          />
        </Col>
        <Col xs={24} sm={12} md={7}>
          <RangePicker
            showTime
            value={timeRange}
            onChange={(v) => { setTimeRange(v as [dayjs.Dayjs, dayjs.Dayjs] | null); setPage(1); }}
            style={{ width: '100%' }}
            placeholder={['开始时间', '截止时间']}
          />
        </Col>
        <Col xs={24} sm={8} md={5}>
          <Input
            prefix={<SearchOutlined />}
            placeholder="搜索输入/输出关键词"
            value={keyword}
            onChange={(e) => setKeyword(e.target.value)}
            onPressEnter={() => { setPage(1); fetchList(); }}
            allowClear
          />
        </Col>
      </Row>

      {/* 表格 */}
      <Table
        rowKey="id"
        columns={columns}
        dataSource={traces}
        loading={loading}
        scroll={{ x: 1300 }}
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