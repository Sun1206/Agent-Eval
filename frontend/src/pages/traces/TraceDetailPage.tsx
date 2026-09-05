/**
 * Trace 详情页
 *
 * 上方基本信息条 + 左侧树形视图 + 右侧 Span 详情面板
 */
import { useEffect, useState, useCallback, useMemo } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Card,
  Descriptions,
  Tag,
  Typography,
  message,
  Button,
  Row,
  Col,
  Empty,
} from 'antd';
import { ArrowLeftOutlined, WarningOutlined } from '@ant-design/icons';
import {
  getTraceDetail,
  buildSpanTree,
  TraceDetail,
  SpanNode,
} from '@/services/trace';
import TraceTreeView from '@/components/TraceTreeView';
import SpanDetailPanel from '@/components/SpanDetailPanel';
import BadCaseMarkModal from '@/pages/badcases/BadCaseMarkModal';
import dayjs from 'dayjs';

const { Text } = Typography;

export default function TraceDetailPage() {
  const { projectId, traceId } = useParams<{ projectId: string; traceId: string }>();
  const navigate = useNavigate();

  const [trace, setTrace] = useState<TraceDetail | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [loading, setLoading] = useState(true);
  const [selectedSpan, setSelectedSpan] = useState<SpanNode | null>(null);
  const [markModalOpen, setMarkModalOpen] = useState(false);

  const fetchDetail = useCallback(async () => {
    if (!projectId || !traceId) return;
    setLoading(true);
    setNotFound(false);
    try {
      const data = await getTraceDetail(projectId, traceId);
      if (data) {
        setTrace(data);
        // 默认选中第一个 Span
        const tree = buildSpanTree(data.spans);
        if (tree.length > 0) {
          setSelectedSpan(tree[0]);
        }
      } else {
        setNotFound(true);
      }
    } catch {
      setNotFound(true);
    } finally {
      setLoading(false);
    }
  }, [projectId, traceId]);

  useEffect(() => {
    fetchDetail();
  }, [fetchDetail]);

  // 构建树结构
  const spanTree = useMemo(() => {
    if (!trace?.spans) return [];
    return buildSpanTree(trace.spans);
  }, [trace?.spans]);

  function handleSelectSpan(span: SpanNode) {
    setSelectedSpan(span);
  }

  function handleClosePanel() {
    setSelectedSpan(null);
  }

  return (
    <div>
      {/* 返回 + 标题 + 操作 */}
      <div style={{ marginBottom: 12, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <Button
            type="text"
            icon={<ArrowLeftOutlined />}
            onClick={() => navigate(-1)}
          />
          <span>
            <Text strong style={{ fontSize: 16 }}>Trace 详情</Text>
            {trace && (
              <Text code copyable style={{ marginLeft: 12, fontSize: 12 }}>
                {trace.trace_id}
              </Text>
            )}
          </span>
        </div>
        <Button
          icon={<WarningOutlined />}
          onClick={() => setMarkModalOpen(true)}
        >
          标记 Bad Case
        </Button>
      </div>

      {/* Trace 不存在提示 */}
      {notFound && (
        <Card style={{ marginTop: 12 }}>
          <Empty
            description={
              <span>
                未找到 Trace 数据
                <br />
                <Text type="secondary" style={{ fontSize: 12 }}>
                  Trace 数据需要通过 SDK 上报后才能查看，该 Trace 可能来自外部系统
                </Text>
              </span>
            }
          >
            <Button onClick={() => navigate(-1)}>返回上一页</Button>
          </Empty>
        </Card>
      )}

      {/* 基本信息 */}
      {trace && (
        <Card size="small" style={{ marginBottom: 12 }} loading={loading}>
          <Descriptions column={6} size="small">
            <Descriptions.Item label="状态">
              <Tag color={trace.status === 'SUCCESS' ? 'success' : 'error'}>
                {trace.status === 'SUCCESS' ? '成功' : '失败'}
              </Tag>
            </Descriptions.Item>
            <Descriptions.Item label="总耗时">
              {trace.duration_ms != null
                ? trace.duration_ms >= 1000
                  ? `${(trace.duration_ms / 1000).toFixed(2)}s`
                  : `${trace.duration_ms}ms`
                : '-'}
            </Descriptions.Item>
            <Descriptions.Item label="Token">{trace.total_tokens.toLocaleString()}</Descriptions.Item>
            <Descriptions.Item label="Span 数">{trace.spans.length}</Descriptions.Item>
            <Descriptions.Item label="用户">{trace.user_id || '-'}</Descriptions.Item>
            <Descriptions.Item label="会话">{trace.session_id || '-'}</Descriptions.Item>
            <Descriptions.Item label="开始时间">
              {dayjs(trace.start_time).format('YYYY-MM-DD HH:mm:ss.SSS')}
            </Descriptions.Item>
            <Descriptions.Item label="结束时间">
              {trace.end_time ? dayjs(trace.end_time).format('HH:mm:ss.SSS') : '-'}
            </Descriptions.Item>
            {trace.tags.length > 0 && (
              <Descriptions.Item label="标签">
                {trace.tags.map((t) => (
                  <Tag key={t}>{t}</Tag>
                ))}
              </Descriptions.Item>
            )}
          </Descriptions>
        </Card>
      )}

      {/* 输入/输出 */}
      {trace && (
        <Row gutter={12} style={{ marginBottom: 12 }}>
          <Col span={12}>
            <Card size="small" title="输入 (Input)" bodyStyle={{ maxHeight: 100, overflow: 'auto' }}>
              <Text style={{ fontSize: 12, whiteSpace: 'pre-wrap' }}>
                {trace.input || '(无)'}
              </Text>
            </Card>
          </Col>
          <Col span={12}>
            <Card size="small" title="输出 (Output)" bodyStyle={{ maxHeight: 100, overflow: 'auto' }}>
              <Text style={{ fontSize: 12, whiteSpace: 'pre-wrap' }}>
                {trace.output || '(无)'}
              </Text>
            </Card>
          </Col>
        </Row>
      )}

      {/* 树形视图 + 详情面板 */}
      <Row gutter={12}>
        <Col span={selectedSpan ? 12 : 24}>
          <Card
            size="small"
            title={<Text strong style={{ fontSize: 13 }}>Span 树形结构</Text>}
            bodyStyle={{ padding: '8px 12px' }}
            loading={loading}
          >
            <TraceTreeView
              roots={spanTree}
              onSelectSpan={handleSelectSpan}
              selectedSpanId={selectedSpan?.span_id}
            />
          </Card>
        </Col>
        {selectedSpan && (
          <Col span={12}>
            <Card
              size="small"
              title={<Text strong style={{ fontSize: 13 }}>Span 详情</Text>}
              bodyStyle={{ padding: 0 }}
              style={{ maxHeight: 'calc(100vh - 160px)', overflow: 'auto' }}
            >
              <SpanDetailPanel span={selectedSpan} onClose={handleClosePanel} />
            </Card>
          </Col>
        )}
      </Row>

      {/* 标记 Bad Case Modal */}
      {trace && projectId && (
        <BadCaseMarkModal
          projectId={projectId}
          open={markModalOpen}
          onClose={() => setMarkModalOpen(false)}
          onSuccess={() => {}}
          tracePreview={{
            trace_id: trace.trace_id,
            input: trace.input,
            output: trace.output,
            status: trace.status,
          }}
        />
      )}
    </div>
  );
}