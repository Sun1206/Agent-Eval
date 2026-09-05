/**
 * Span 详情面板
 *
 * 右侧展示选中 Span 的详细信息：类型/名称/状态/耗时/输入/输出/Token/元数据
 * 支持 JSON 展示 + 一键复制
 */
import { Typography, Descriptions, Tag, Button, message, Divider } from 'antd';
import { CopyOutlined, CloseOutlined } from '@ant-design/icons';
import type { SpanNode, SpanType } from '@/services/trace';
import dayjs from 'dayjs';

const { Text } = Typography;

/** Span 类型颜色映射 */
const SPAN_TYPE_COLORS: Record<SpanType, string> = {
  chain: '#1677ff',
  llm_call: '#722ed1',
  tool_call: '#52c41a',
  retrieval: '#fa8c16',
  embedding: '#13c2c2',
};

/** Span 类型中文 */
const SPAN_TYPE_LABELS: Record<SpanType, string> = {
  chain: '编排链',
  llm_call: 'LLM 调用',
  tool_call: '工具调用',
  retrieval: '检索',
  embedding: '向量嵌入',
};

export interface SpanDetailPanelProps {
  span: SpanNode | null;
  onClose: () => void;
}

/** JSON 展示组件 */
function JsonBlock({ data, label }: { data: unknown; label: string }) {
  const jsonStr = data != null ? JSON.stringify(data, null, 2) : '';

  return (
    <div style={{ marginBottom: 12 }}>
      <Text type="secondary" style={{ fontSize: 12, marginBottom: 4, display: 'block' }}>
        {label}
      </Text>
      {jsonStr ? (
        <div style={{ position: 'relative' }}>
          <pre
            style={{
              background: '#f5f5f5',
              border: '1px solid #e8e8e8',
              borderRadius: 4,
              padding: '10px 36px 10px 10px',
              fontSize: 12,
              fontFamily: 'Consolas, Monaco, monospace',
              maxHeight: 220,
              overflow: 'auto',
              margin: 0,
              whiteSpace: 'pre-wrap',
              wordBreak: 'break-all',
            }}
          >
            {jsonStr}
          </pre>
          <Button
            type="text"
            size="small"
            icon={<CopyOutlined />}
            onClick={() => {
              navigator.clipboard.writeText(jsonStr);
              message.success('已复制');
            }}
            style={{ position: 'absolute', top: 4, right: 4 }}
          />
        </div>
      ) : (
        <Text type="secondary" style={{ fontSize: 12 }}>(无)</Text>
      )}
    </div>
  );
}

/** 计算 Span 耗时（毫秒） */
function calcDuration(span: SpanNode): number | null {
  if (!span.start_time) return null;
  const start = dayjs(span.start_time);
  const end = span.end_time ? dayjs(span.end_time) : dayjs();
  return end.diff(start);
}

export default function SpanDetailPanel({ span, onClose }: SpanDetailPanelProps) {
  if (!span) {
    return (
      <div
        style={{
          padding: 24,
          textAlign: 'center',
          color: '#999',
          borderLeft: '1px solid #f0f0f0',
          height: '100%',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}
      >
        <Text type="secondary">点击左侧 Span 节点查看详情</Text>
      </div>
    );
  }

  const duration = calcDuration(span);
  const typeColor = SPAN_TYPE_COLORS[span.type] || '#999';
  const typeLabel = SPAN_TYPE_LABELS[span.type] || span.type;

  return (
    <div style={{ padding: 16, borderLeft: '1px solid #f0f0f0', height: '100%', overflow: 'auto' }}>
      {/* 头部 */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 16 }}>
        <div>
          <Tag color={typeColor} style={{ marginBottom: 6 }}>{typeLabel}</Tag>
          <div>
            <Text strong style={{ fontSize: 15 }}>{span.name}</Text>
          </div>
        </div>
        <Button type="text" size="small" icon={<CloseOutlined />} onClick={onClose} />
      </div>

      <Divider style={{ margin: '12px 0' }} />

      {/* 基本信息 */}
      <Descriptions column={1} size="small" colon={false} labelStyle={{ fontSize: 12, color: '#999' }} contentStyle={{ fontSize: 13 }}>
        <Descriptions.Item label="Span ID">
          <Text code style={{ fontSize: 11 }}>{span.span_id}</Text>
        </Descriptions.Item>
        <Descriptions.Item label="状态">
          <Tag color={span.status === 'error' ? 'error' : 'success'}>
            {span.status === 'error' ? '错误' : '成功'}
          </Tag>
        </Descriptions.Item>
        {duration != null && (
          <Descriptions.Item label="耗时">
            {duration >= 1000 ? `${(duration / 1000).toFixed(2)}s` : `${duration}ms`}
          </Descriptions.Item>
        )}
        {span.metadata?.model && (
          <Descriptions.Item label="模型">{span.metadata.model}</Descriptions.Item>
        )}
        {span.metadata?.token_usage && (
          <Descriptions.Item label="Token">
            {span.metadata.token_usage.total != null
              ? span.metadata.token_usage.total
              : `prompt: ${span.metadata.token_usage.prompt ?? 0}, completion: ${span.metadata.token_usage.completion ?? 0}`}
          </Descriptions.Item>
        )}
        {span.metadata?.cost != null && (
          <Descriptions.Item label="成本">${span.metadata.cost.toFixed(6)}</Descriptions.Item>
        )}
        {span.start_time && (
          <Descriptions.Item label="开始时间">
            {dayjs(span.start_time).format('HH:mm:ss.SSS')}
          </Descriptions.Item>
        )}
        {span.end_time && (
          <Descriptions.Item label="结束时间">
            {dayjs(span.end_time).format('HH:mm:ss.SSS')}
          </Descriptions.Item>
        )}
      </Descriptions>

      <Divider style={{ margin: '12px 0' }} />

      {/* 输入 / 输出 JSON */}
      <JsonBlock data={span.input} label="输入 (Input)" />
      <JsonBlock data={span.output} label="输出 (Output)" />

      {/* 元数据 */}
      {span.metadata && Object.keys(span.metadata).length > 0 && (
        <>
          <Divider style={{ margin: '12px 0' }} />
          <JsonBlock data={span.metadata} label="元数据 (Metadata)" />
        </>
      )}
    </div>
  );
}