/**
 * 项目工作台 Dashboard
 *
 * 展示项目级概览: Agent 数量、数据集数量、最近评测、Bad Case 统计
 */
import { useEffect, useState, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Card, Col, Row, Statistic, Typography, Table, Tag, Spin, Space } from 'antd';
import {
  RobotOutlined,
  DatabaseOutlined,
  ExperimentOutlined,
  BugOutlined,
} from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import dayjs from 'dayjs';

import { listAgents, AgentInfo } from '@/services/agent';
import { listDatasets, DatasetInfo } from '@/services/dataset';
import { listEvalRuns, EvalRunListItem } from '@/services/evaluation';
import { getBadCaseStats, BadCaseStats, BAD_CASE_STATUS_LABELS, BAD_CASE_STATUS_COLORS } from '@/services/badcase';
import { getProject } from '@/services/project';

const { Text, Title } = Typography;

/** 评测状态颜色 */
const EVAL_STATUS_COLORS: Record<string, string> = {
  PENDING: 'default',
  RUNNING: 'processing',
  COMPLETED: 'green',
  FAILED: 'red',
  CANCELLED: 'default',
};

const EVAL_STATUS_LABELS: Record<string, string> = {
  PENDING: '待执行',
  RUNNING: '执行中',
  COMPLETED: '已完成',
  FAILED: '失败',
  CANCELLED: '已取消',
};

export default function DashboardPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();

  const [loading, setLoading] = useState(true);
  const [projectName, setProjectName] = useState('');
  const [agentCount, setAgentCount] = useState(0);
  const [datasetCount, setDatasetCount] = useState(0);
  const [recentEvals, setRecentEvals] = useState<EvalRunListItem[]>([]);
  const [badCaseStats, setBadCaseStats] = useState<BadCaseStats | null>(null);

  const fetchData = useCallback(async () => {
    if (!projectId) return;
    setLoading(true);
    try {
      // 并行请求
      const [project, agents, datasets, evals, stats] = await Promise.allSettled([
        getProject(projectId),
        listAgents(projectId),
        listDatasets(projectId),
        listEvalRuns(projectId, 1, 5),
        getBadCaseStats(projectId),
      ]);

      if (project.status === 'fulfilled') setProjectName(project.value.name);
      if (agents.status === 'fulfilled') setAgentCount(agents.value.length);
      if (datasets.status === 'fulfilled') setDatasetCount(datasets.value.length);
      if (evals.status === 'fulfilled') setRecentEvals(evals.value.items ?? []);
      if (stats.status === 'fulfilled') setBadCaseStats(stats.value);
    } catch {
      // 忽略部分失败
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // 最近评测表格列
  const evalColumns: ColumnsType<EvalRunListItem> = [
    {
      title: '名称',
      dataIndex: 'name',
      key: 'name',
      render: (text: string, record: EvalRunListItem) => (
        <a onClick={() => navigate(`/projects/${projectId}/evaluations/${record.id}`)}>
          {text || `评测 ${record.id.slice(0, 8)}`}
        </a>
      ),
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 100,
      render: (status: string) => (
        <Tag color={EVAL_STATUS_COLORS[status] || 'default'}>
          {EVAL_STATUS_LABELS[status] || status}
        </Tag>
      ),
    },
    {
      title: '通过率',
      dataIndex: 'pass_rate',
      key: 'pass_rate',
      width: 100,
      render: (val?: number) =>
        val != null ? `${(val * 100).toFixed(1)}%` : <Text type="secondary">-</Text>,
    },
    {
      title: '平均分',
      dataIndex: 'avg_score',
      key: 'avg_score',
      width: 100,
      render: (val?: number) =>
        val != null ? val.toFixed(2) : <Text type="secondary">-</Text>,
    },
    {
      title: '进度',
      key: 'progress',
      width: 120,
      render: (_: unknown, record: EvalRunListItem) =>
        `${record.completed_items ?? 0}/${record.total_items ?? 0}`,
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 160,
      render: (val?: string) =>
        val ? dayjs(val).format('YYYY-MM-DD HH:mm') : <Text type="secondary">-</Text>,
    },
  ];

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: 80 }}>
        <Spin size="large" />
      </div>
    );
  }

  return (
    <div>
      <Title level={4} style={{ marginBottom: 24 }}>
        {projectName} - 工作台
      </Title>

      {/* 统计卡片 */}
      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col span={6}>
          <Card hoverable onClick={() => navigate(`/projects/${projectId}/agents`)}>
            <Statistic
              title="Agent 数量"
              value={agentCount}
              prefix={<RobotOutlined style={{ color: '#1677FF' }} />}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card hoverable onClick={() => navigate(`/projects/${projectId}/datasets`)}>
            <Statistic
              title="数据集数量"
              value={datasetCount}
              prefix={<DatabaseOutlined style={{ color: '#52C41A' }} />}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card hoverable onClick={() => navigate(`/projects/${projectId}/evaluations`)}>
            <Statistic
              title="Bad Case 待处理"
              value={badCaseStats?.by_status?.open ?? 0}
              prefix={<BugOutlined style={{ color: '#FF4D4F' }} />}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card hoverable onClick={() => navigate(`/projects/${projectId}/evaluations`)}>
            <Statistic
              title="Bad Case 总数"
              value={badCaseStats?.total ?? 0}
              prefix={<BugOutlined style={{ color: '#FAAD14' }} />}
            />
          </Card>
        </Col>
      </Row>

      {/* Bad Case 状态分布 */}
      {badCaseStats && badCaseStats.total > 0 && (
        <Card title="Bad Case 状态分布" style={{ marginBottom: 24 }} size="small">
          <Space size={16}>
            {Object.entries(badCaseStats.by_status || {}).map(([status, count]) => (
              <Tag
                key={status}
                color={BAD_CASE_STATUS_COLORS[status as keyof typeof BAD_CASE_STATUS_LABELS] || 'default'}
                style={{ fontSize: 14, padding: '4px 12px' }}
              >
                {BAD_CASE_STATUS_LABELS[status as keyof typeof BAD_CASE_STATUS_LABELS] || status}: {count}
              </Tag>
            ))}
          </Space>
        </Card>
      )}

      {/* 最近评测 */}
      <Card
        title="最近评测任务"
        extra={
          <a onClick={() => navigate(`/projects/${projectId}/evaluations`)}>
            查看全部
          </a>
        }
      >
        <Table
          rowKey="id"
          columns={evalColumns}
          dataSource={recentEvals}
          pagination={false}
          size="small"
          locale={{ emptyText: '暂无评测任务' }}
        />
      </Card>
    </div>
  );
}
