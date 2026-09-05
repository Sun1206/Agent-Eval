/**
 * Trace API 封装
 */
import { get, PaginatedData } from './api';

// ---------- 类型 ----------

/** Span 类型 */
export type SpanType = 'chain' | 'llm_call' | 'tool_call' | 'retrieval' | 'embedding';

/** Span 执行的元数据 */
export interface SpanMetadata {
  model?: string;
  token_usage?: {
    prompt?: number;
    completion?: number;
    total?: number;
  };
  cost?: number;
}

/** 单个 Span（已从树结构中解析） */
export interface SpanNode {
  span_id: string;
  parent_span_id?: string;
  type: SpanType;
  name: string;
  start_time: string;
  end_time?: string;
  status: string;
  input?: Record<string, unknown>;
  output?: Record<string, unknown>;
  metadata: SpanMetadata;
  /** 前端构建的树结构 */
  children: SpanNode[];
}

/** Trace 列表项 */
export interface TraceListItem {
  id: string;
  trace_id: string;
  project_id: string;
  agent_id?: string;
  session_id?: string;
  user_id?: string;
  input?: string;
  output?: string;
  start_time: string;
  end_time?: string;
  duration_ms?: number;
  total_tokens: number;
  total_cost: number;
  status: string;
  span_count: number;
  tags: string[];
  created_at?: string;
}

/** Trace 详情（含完整 spans） */
export interface TraceDetail {
  id: string;
  trace_id: string;
  project_id: string;
  agent_id?: string;
  session_id?: string;
  user_id?: string;
  input?: string;
  output?: string;
  start_time: string;
  end_time?: string;
  duration_ms?: number;
  total_tokens: number;
  total_cost: number;
  status: string;
  spans: SpanNode[];
  tags: string[];
  metadata: Record<string, unknown>;
  created_at?: string;
}

/** Trace 列表查询参数 */
export interface TraceListParams {
  page?: number;
  page_size?: number;
  agent_id?: string;
  session_id?: string;
  user_id?: string;
  status?: string;
  start_time_from?: string;
  start_time_to?: string;
  keyword?: string;
  sort_by?: string;
  sort_order?: string;
}

// ---------- API ----------

export function listTraces(
  projectId: string,
  params: TraceListParams = {},
): Promise<PaginatedData<TraceListItem>> {
  return get<PaginatedData<TraceListItem>>(
    `/projects/${projectId}/traces`,
    params as Record<string, unknown>,
  );
}

export function getTraceDetail(
  projectId: string,
  traceId: string,
): Promise<TraceDetail> {
  return get<TraceDetail>(
    `/projects/${projectId}/traces/${traceId}`,
  );
}

// ---------- 工具函数 ----------

/**
 * 将扁平的 Span 数组构建为树结构
 */
export function buildSpanTree(flatSpans: SpanNode[]): SpanNode[] {
  const map = new Map<string, SpanNode>();
  const roots: SpanNode[] = [];

  // 初始化所有节点，添加 children
  for (const span of flatSpans) {
    map.set(span.span_id, { ...span, children: [] });
  }

  // 建立父子关系
  for (const span of flatSpans) {
    const node = map.get(span.span_id)!;
    if (span.parent_span_id && map.has(span.parent_span_id)) {
      map.get(span.parent_span_id)!.children.push(node);
    } else {
      roots.push(node);
    }
  }

  return roots;
}