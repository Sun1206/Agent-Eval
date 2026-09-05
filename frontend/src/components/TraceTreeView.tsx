/**
 * Trace 树形视图组件
 *
 * 递归渲染 Span 树 + 彩色类型标签 + 展开/折叠 + 全部展开/折叠
 * 每个节点：缩进 + 展开箭头 + 类型色标 + 名称 + 耗时 + 状态指示
 */
import { useState } from 'react';
import { Tag, Typography, Button, Space, Tooltip } from 'antd';
import {
  CaretRightOutlined,
  CaretDownOutlined,
  ExpandOutlined,
  CompressOutlined,
} from '@ant-design/icons';
import type { SpanNode, SpanType } from '@/services/trace';
import dayjs from 'dayjs';

const { Text } = Typography;

/** Span 类型颜色 */
const SPAN_TYPE_COLORS: Record<SpanType, string> = {
  chain: '#1677ff',
  llm_call: '#722ed1',
  tool_call: '#52c41a',
  retrieval: '#fa8c16',
  embedding: '#13c2c2',
};

const SPAN_TYPE_LABELS: Record<SpanType, string> = {
  chain: 'Chain',
  llm_call: 'LLM',
  tool_call: 'Tool',
  retrieval: 'RAG',
  embedding: 'Embed',
};

/** 计算耗时字符串 */
function formatDuration(start: string, end?: string): string {
  const s = dayjs(start);
  const e = end ? dayjs(end) : dayjs();
  const ms = e.diff(s);
  if (ms >= 1000) return `${(ms / 1000).toFixed(2)}s`;
  return `${ms}ms`;
}

export interface TraceTreeViewProps {
  roots: SpanNode[];
  onSelectSpan: (span: SpanNode) => void;
  selectedSpanId?: string;
}

// ---------- 单个树节点 ----------

function SpanTreeNode({
  node,
  depth,
  onSelectSpan,
  selectedSpanId,
  defaultExpanded,
}: {
  node: SpanNode;
  depth: number;
  onSelectSpan: (span: SpanNode) => void;
  selectedSpanId?: string;
  defaultExpanded: boolean;
}) {
  const [expanded, setExpanded] = useState(defaultExpanded);
  const hasChildren = node.children.length > 0;
  const isSelected = node.span_id === selectedSpanId;
  const isError = node.status === 'error';
  const typeColor = SPAN_TYPE_COLORS[node.type] || '#999';
  const typeLabel = SPAN_TYPE_LABELS[node.type] || node.type;
  const duration = formatDuration(node.start_time, node.end_time);

  const indent = depth * 24;

  return (
    <div>
      {/* 节点行 */}
      <div
        onClick={() => onSelectSpan(node)}
        style={{
          display: 'flex',
          alignItems: 'center',
          padding: '4px 8px 4px 4px',
          paddingLeft: indent + 4,
          cursor: 'pointer',
          background: isSelected ? '#e6f4ff' : 'transparent',
          borderLeft: isError ? '3px solid #ff4d4f' : '3px solid transparent',
          borderRadius: 4,
          transition: 'background 0.15s',
        }}
        onMouseEnter={(e) => {
          if (!isSelected) (e.currentTarget as HTMLElement).style.background = '#fafafa';
        }}
        onMouseLeave={(e) => {
          if (!isSelected) (e.currentTarget as HTMLElement).style.background = 'transparent';
        }}
      >
        {/* 展开/折叠 */}
        <span style={{ width: 18, display: 'inline-flex', justifyContent: 'center', flexShrink: 0 }}>
          {hasChildren ? (
            expanded ? (
              <CaretDownOutlined
                style={{ fontSize: 10, color: '#999' }}
                onClick={(e) => { e.stopPropagation(); setExpanded(false); }}
              />
            ) : (
              <CaretRightOutlined
                style={{ fontSize: 10, color: '#999' }}
                onClick={(e) => { e.stopPropagation(); setExpanded(true); }}
              />
            )
          ) : (
            <span style={{ width: 8 }} />
          )}
        </span>

        {/* 类型标签 */}
        <Tag
          color={typeColor}
          style={{
            fontSize: 10,
            lineHeight: '16px',
            padding: '0 4px',
            marginRight: 6,
            borderRadius: 3,
          }}
        >
          {typeLabel}
        </Tag>

        {/* 名称 */}
        <Text
          ellipsis
          style={{
            flex: 1,
            fontSize: 13,
            fontWeight: isSelected ? 600 : 400,
            color: isError ? '#ff4d4f' : undefined,
          }}
        >
          {node.name}
        </Text>

        {/* 耗时 */}
        <Tooltip title={`${node.start_time ? dayjs(node.start_time).format('HH:mm:ss.SSS') : '-'} ~ ${node.end_time ? dayjs(node.end_time).format('HH:mm:ss.SSS') : '-'}`}>
          <Text
            type="secondary"
            style={{ fontSize: 11, marginLeft: 8, marginRight: 8, whiteSpace: 'nowrap' }}
          >
            {duration}
          </Text>
        </Tooltip>

        {/* Token */}
        {node.metadata?.token_usage?.total != null && node.metadata.token_usage.total > 0 && (
          <Text type="secondary" style={{ fontSize: 10, marginRight: 6 }}>
            {node.metadata.token_usage.total}T
          </Text>
        )}

        {/* 状态指示 */}
        {isError && (
          <span
            style={{
              width: 8,
              height: 8,
              borderRadius: '50%',
              background: '#ff4d4f',
              flexShrink: 0,
            }}
          />
        )}
      </div>

      {/* 子节点 */}
      {expanded &&
        hasChildren &&
        node.children.map((child) => (
          <SpanTreeNode
            key={child.span_id}
            node={child}
            depth={depth + 1}
            onSelectSpan={onSelectSpan}
            selectedSpanId={selectedSpanId}
            defaultExpanded={false}
          />
        ))}
    </div>
  );
}

// ---------- 树容器 ----------

export default function TraceTreeView({ roots, onSelectSpan, selectedSpanId }: TraceTreeViewProps) {
  const [expandAll, setExpandAll] = useState(false);

  return (
    <div>
      {/* 操作栏 */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8, padding: '0 4px' }}>
        <Text type="secondary" style={{ fontSize: 12 }}>
          共 {countNodes(roots)} 个 Span
        </Text>
        <Space size={4}>
          <Button
            type="text"
            size="small"
            icon={<ExpandOutlined />}
            onClick={() => setExpandAll(true)}
          >
            全部展开
          </Button>
          <Button
            type="text"
            size="small"
            icon={<CompressOutlined />}
            onClick={() => setExpandAll(false)}
          >
            全部折叠
          </Button>
        </Space>
      </div>

      {/* 树形列表 */}
      <div style={{ maxHeight: 'calc(100vh - 280px)', overflow: 'auto', border: '1px solid #f0f0f0', borderRadius: 4 }}>
        {roots.length === 0 ? (
          <div style={{ padding: 24, textAlign: 'center', color: '#999' }}>
            <Text type="secondary">暂无 Span 数据</Text>
          </div>
        ) : (
          roots.map((root) => (
            <SpanTreeNode
              key={root.span_id}
              node={root}
              depth={0}
              onSelectSpan={onSelectSpan}
              selectedSpanId={selectedSpanId}
              defaultExpanded={expandAll}
            />
          ))
        )}
      </div>
    </div>
  );
}

/** 递归计算节点总数 */
function countNodes(nodes: SpanNode[]): number {
  let count = nodes.length;
  for (const node of nodes) {
    count += countNodes(node.children);
  }
  return count;
}