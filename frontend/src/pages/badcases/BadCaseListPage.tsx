/**
 * Bad Case 列表页
 *
 * 统计概览卡片 + 筛选栏（状态/标签/负责人） + 分页表格 + 状态流转操作
 */
import { useEffect, useState, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Table,
  Select,
  Input,
  Tag,
  Typography,
  message,
  Space,
  Row,
  Col,
  Card,
  Statistic,
  Modal,
  Form,
  Button,
} from 'antd';
import { ReloadOutlined, WarningOutlined, CheckCircleOutlined, ClockCircleOutlined, SyncOutlined, LinkOutlined } from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import {
  listBadCases,
  updateBadCase,
  getBadCaseStats,
  BadCaseInfo,
  BadCaseStats,
  BadCaseTag,
  BadCaseStatus,
  BAD_CASE_TAG_LABELS,
  BAD_CASE_TAG_COLORS,
  BAD_CASE_STATUS_LABELS,
  BAD_CASE_STATUS_COLORS,
  BAD_CASE_NEXT_STATUS,
} from '@/services/badcase';
import dayjs from 'dayjs';

const { Title, Text } = Typography;
const { TextArea } = Input;

export default function BadCaseListPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();

  // 列表
  const [cases, setCases] = useState<BadCaseInfo[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [loading, setLoading] = useState(true);

  // 筛选
  const [filterStatus, setFilterStatus] = useState<string | undefined>();
  const [filterTag, setFilterTag] = useState<string | undefined>();
  const [filterAssignee, setFilterAssignee] = useState('');

  // 统计
  const [stats, setStats] = useState<BadCaseStats | null>(null);

  // 状态流转 Modal
  const [transitionOpen, setTransitionOpen] = useState(false);
  const [transitionCase, setTransitionCase] = useState<BadCaseInfo | null>(null);
  const [transitionForm] = Form.useForm();
  const [transitioning, setTransitioning] = useState(false);

  const fetchList = useCallback(async () => {
    if (!projectId) return;
    setLoading(true);
    try {
      const res = await listBadCases(projectId, page, pageSize, {
        status: filterStatus,
        tag: filterTag,
        assignee_id: filterAssignee.trim() || undefined,
      });
      setCases(res.items);
      setTotal(res.total);
    } catch {
      message.error('加载 Bad Case 列表失败');
    } finally {
      setLoading(false);
    }
  }, [projectId, page, pageSize, filterStatus, filterTag, filterAssignee]);

  const fetchStats = useCallback(async () => {
    if (!projectId) return;
    try {
      const s = await getBadCaseStats(projectId);
      setStats(s);
    } catch {
      // 静默
    }
  }, [projectId]);

  useEffect(() => {
    fetchList();
    fetchStats();
  }, [fetchList, fetchStats]);

  // 打开状态流转弹窗
  function openTransition(bc: BadCaseInfo) {
    setTransitionCase(bc);
    transitionForm.resetFields();
    transitionForm.setFieldsValue({
      status: bc.status,
      resolution: bc.resolution || '',
    });
    setTransitionOpen(true);
  }

  async function handleTransition(values: { status: BadCaseStatus; resolution?: string }) {
    if (!projectId || !transitionCase) return;
    setTransitioning(true);
    try {
      await updateBadCase(projectId, transitionCase.id, {
        status: values.status,
        resolution: values.resolution || undefined,
      });
      message.success('状态更新成功');
      setTransitionOpen(false);
      await fetchList();
      await fetchStats();
    } catch (err: unknown) {
      message.error((err as { message?: string })?.message ?? '更新失败');
    } finally {
      setTransitioning(false);
    }
  }

  // 快速流转（不打开弹窗）
  async function quickTransition(bc: BadCaseInfo, nextStatus: BadCaseStatus) {
    if (!projectId) return;
    try {
      await updateBadCase(projectId, bc.id, { status: nextStatus });
      message.success(`状态已更新为"${BAD_CASE_STATUS_LABELS[nextStatus]}"`);
      await fetchList();
      await fetchStats();
    } catch (err: unknown) {
      message.error((err as { message?: string })?.message ?? '更新失败');
    }
  }

  // 表格列
  const columns: ColumnsType<BadCaseInfo> = [
    {
      title: 'Trace ID',
      dataIndex: 'trace_id',
      key: 'trace_id',
      width: 180,
      render: (v: string) => (
        <Text
          code
          copyable={{ text: v }}
          style={{ fontSize: 11, cursor: 'pointer' }}
          onClick={() => navigate(`/projects/${projectId}/traces/${v}`)}
        >
          <LinkOutlined style={{ marginRight: 4 }} />
          {v.slice(0, 8)}...
        </Text>
      ),
    },
    {
      title: '标签',
      dataIndex: 'tag',
      key: 'tag',
      width: 90,
      render: (v: BadCaseTag) => (
        <Tag color={BAD_CASE_TAG_COLORS[v]}>{BAD_CASE_TAG_LABELS[v]}</Tag>
      ),
    },
    {
      title: '描述',
      dataIndex: 'description',
      key: 'description',
      ellipsis: true,
      width: 200,
      render: (v: string | undefined) => v || '-',
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 100,
      render: (v: BadCaseStatus) => (
        <Tag color={BAD_CASE_STATUS_COLORS[v]}>{BAD_CASE_STATUS_LABELS[v]}</Tag>
      ),
    },
    {
      title: '解决方案',
      dataIndex: 'resolution',
      key: 'resolution',
      ellipsis: true,
      width: 180,
      render: (v: string | undefined) => v || '-',
    },
    {
      title: '标记时间',
      dataIndex: 'marked_at',
      key: 'marked_at',
      width: 160,
      render: (v: string | undefined) => (v ? dayjs(v).format('YYYY-MM-DD HH:mm') : '-'),
    },
    {
      title: '解决时间',
      dataIndex: 'resolved_at',
      key: 'resolved_at',
      width: 160,
      render: (v: string | undefined) => (v ? dayjs(v).format('YYYY-MM-DD HH:mm') : '-'),
    },
    {
      title: '操作',
      key: 'actions',
      width: 180,
      fixed: 'right',
      render: (_: unknown, record: BadCaseInfo) => {
        const nextStatuses = BAD_CASE_NEXT_STATUS[record.status];
        return (
          <Space size="small" wrap>
            {nextStatuses.length > 0 &&
              nextStatuses.map((ns) => (
                <a
                  key={ns}
                  onClick={() => {
                    // resolved/closed 需要填写 resolution，弹窗处理
                    if (ns === 'resolved' && !record.resolution) {
                      openTransition(record);
                    } else {
                      quickTransition(record, ns);
                    }
                  }}
                >
                  {ns === 'in_progress' ? '开始处理' : ns === 'resolved' ? '标记解决' : ns === 'closed' ? '关闭' : '重开'}
                </a>
              ))}
            <a onClick={() => openTransition(record)}>更多</a>
          </Space>
        );
      },
    },
  ];

  // 统计卡片配置
  const statusIcons: Record<string, React.ReactNode> = {
    open: <WarningOutlined style={{ color: '#ff4d4f' }} />,
    in_progress: <SyncOutlined style={{ color: '#1677ff' }} />,
    resolved: <CheckCircleOutlined style={{ color: '#52c41a' }} />,
    closed: <ClockCircleOutlined style={{ color: '#999' }} />,
  };

  return (
    <div>
      {/* 标题 */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <div>
          <Title level={4} style={{ margin: 0 }}>Bad Case 管理</Title>
          <Text type="secondary">管理和追踪评测中发现的 Bad Case</Text>
        </div>
        <Button icon={<ReloadOutlined />} onClick={() => { fetchList(); fetchStats(); }}>
          刷新
        </Button>
      </div>

      {/* 统计概览 */}
      {stats && (
        <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
          <Col xs={12} sm={6}>
            <Card size="small">
              <Statistic title="总计" value={stats.total} valueStyle={{ color: '#1677ff' }} />
            </Card>
          </Col>
          {(['open', 'in_progress', 'resolved', 'closed'] as BadCaseStatus[]).map((s) => (
            <Col xs={12} sm={4} md={4} lg={3} key={s}>
              <Card size="small">
                <Statistic
                  title={BAD_CASE_STATUS_LABELS[s]}
                  value={stats.by_status[s] || 0}
                  prefix={statusIcons[s]}
                  valueStyle={{
                    color:
                      s === 'open'
                        ? '#ff4d4f'
                        : s === 'in_progress'
                          ? '#1677ff'
                          : s === 'resolved'
                            ? '#52c41a'
                            : '#999',
                  }}
                />
              </Card>
            </Col>
          ))}
        </Row>
      )}

      {/* 标签分布 */}
      {stats && Object.keys(stats.by_tag).length > 0 && (
        <Card size="small" style={{ marginBottom: 16 }}>
          <Text type="secondary" style={{ marginRight: 12, fontSize: 12 }}>标签分布:</Text>
          {(Object.entries(stats.by_tag) as [BadCaseTag, number][]).map(([tag, count]) => (
            <Tag key={tag} color={BAD_CASE_TAG_COLORS[tag]} style={{ marginBottom: 4 }}>
              {BAD_CASE_TAG_LABELS[tag]}: {count}
            </Tag>
          ))}
        </Card>
      )}

      {/* 筛选栏 */}
      <Row gutter={[12, 12]} style={{ marginBottom: 16 }}>
        <Col xs={12} sm={5} md={3}>
          <Select
            allowClear
            placeholder="状态"
            value={filterStatus}
            onChange={(v) => { setFilterStatus(v); setPage(1); }}
            style={{ width: '100%' }}
            options={Object.entries(BAD_CASE_STATUS_LABELS).map(([k, v]) => ({ value: k, label: v }))}
          />
        </Col>
        <Col xs={12} sm={5} md={3}>
          <Select
            allowClear
            placeholder="标签"
            value={filterTag}
            onChange={(v) => { setFilterTag(v); setPage(1); }}
            style={{ width: '100%' }}
            options={Object.entries(BAD_CASE_TAG_LABELS).map(([k, v]) => ({ value: k, label: v }))}
          />
        </Col>
        <Col xs={12} sm={8} md={4}>
          <Input
            placeholder="负责人 ID"
            value={filterAssignee}
            onChange={(e) => setFilterAssignee(e.target.value)}
            onPressEnter={() => { setPage(1); fetchList(); }}
            allowClear
          />
        </Col>
      </Row>

      {/* 表格 */}
      <Table
        rowKey="id"
        columns={columns}
        dataSource={cases}
        loading={loading}
        scroll={{ x: 1200 }}
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

      {/* 状态流转 Modal */}
      <Modal
        title="更新 Bad Case"
        open={transitionOpen}
        onCancel={() => setTransitionOpen(false)}
        footer={null}
        width={480}
        destroyOnClose
      >
        {transitionCase && (
          <div style={{ marginTop: 16 }}>
            {/* 当前信息 */}
            <div style={{ background: '#fafafa', borderRadius: 6, padding: 12, marginBottom: 16 }}>
              <Space wrap>
                <Tag color={BAD_CASE_TAG_COLORS[transitionCase.tag]}>
                  {BAD_CASE_TAG_LABELS[transitionCase.tag]}
                </Tag>
                <Text code style={{ fontSize: 11 }}>
                  {transitionCase.trace_id.slice(0, 12)}...
                </Text>
                <Tag color={BAD_CASE_STATUS_COLORS[transitionCase.status]}>
                  {BAD_CASE_STATUS_LABELS[transitionCase.status]}
                </Tag>
              </Space>
              {transitionCase.description && (
                <div style={{ marginTop: 8 }}>
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    {transitionCase.description.length > 80
                      ? transitionCase.description.slice(0, 80) + '...'
                      : transitionCase.description}
                  </Text>
                </div>
              )}
            </div>

            <Form form={transitionForm} layout="vertical" onFinish={handleTransition}>
              <Form.Item
                name="status"
                label="状态"
                rules={[{ required: true, message: '请选择状态' }]}
              >
                <Select
                  options={(BAD_CASE_NEXT_STATUS[transitionCase.status] || []).concat([transitionCase.status]).map(
                    (s) => ({
                      value: s,
                      label: BAD_CASE_STATUS_LABELS[s],
                    }),
                  )}
                />
              </Form.Item>

              <Form.Item name="resolution" label="解决方案">
                <TextArea placeholder="描述解决方案或处理措施" rows={3} maxLength={2000} showCount />
              </Form.Item>

              <Form.Item style={{ marginBottom: 0, textAlign: 'right' }}>
                <Space>
                  <Button onClick={() => setTransitionOpen(false)}>取消</Button>
                  <Button type="primary" htmlType="submit" loading={transitioning}>
                    确认更新
                  </Button>
                </Space>
              </Form.Item>
            </Form>
          </div>
        )}
      </Modal>
    </div>
  );
}