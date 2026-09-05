/**
 * Bad Case API 封装
 */
import { get, post, put, PaginatedData } from './api';

// ---------- 类型 ----------

/** Bad Case 标签 */
export type BadCaseTag = 'hallucination' | 'error' | 'omission' | 'timeout' | 'other';

/** Bad Case 状态 */
export type BadCaseStatus = 'open' | 'in_progress' | 'resolved' | 'closed';

/** Bad Case 列表项 */
export interface BadCaseInfo {
  id: string;
  project_id: string;
  trace_id: string;
  tag: BadCaseTag;
  description?: string;
  status: BadCaseStatus;
  assignee_id?: string;
  resolution?: string;
  marked_by: string;
  marked_at?: string;
  resolved_at?: string;
  created_at?: string;
  updated_at?: string;
}

/** 统计摘要 */
export interface BadCaseStats {
  total: number;
  by_status: Record<string, number>;
  by_tag: Record<string, number>;
}

// ---------- 标签/状态 中文映射 ----------

export const BAD_CASE_TAG_LABELS: Record<BadCaseTag, string> = {
  hallucination: '幻觉',
  error: '错误',
  omission: '遗漏',
  timeout: '超时',
  other: '其他',
};

export const BAD_CASE_TAG_COLORS: Record<BadCaseTag, string> = {
  hallucination: 'purple',
  error: 'red',
  omission: 'orange',
  timeout: 'gold',
  other: 'default',
};

export const BAD_CASE_STATUS_LABELS: Record<BadCaseStatus, string> = {
  open: '待处理',
  in_progress: '处理中',
  resolved: '已解决',
  closed: '已关闭',
};

export const BAD_CASE_STATUS_COLORS: Record<BadCaseStatus, string> = {
  open: 'red',
  in_progress: 'processing',
  resolved: 'green',
  closed: 'default',
};

/** 允许的状态流转（与后端 VALID_TRANSITIONS 保持一致） */
export const BAD_CASE_NEXT_STATUS: Record<BadCaseStatus, BadCaseStatus[]> = {
  open: ['in_progress', 'closed'],
  in_progress: ['resolved', 'closed'],
  resolved: ['closed'],
  closed: [],
};

// ---------- API ----------

export function listBadCases(
  projectId: string,
  page = 1,
  pageSize = 20,
  filters?: {
    status?: string;
    tag?: string;
    assignee_id?: string;
  },
): Promise<PaginatedData<BadCaseInfo>> {
  return get<PaginatedData<BadCaseInfo>>(
    `/projects/${projectId}/bad-cases`,
    {
      page,
      page_size: pageSize,
      ...filters,
    },
  );
}

export function markBadCase(
  projectId: string,
  data: {
    trace_id: string;
    tag: BadCaseTag;
    description?: string;
    assignee_id?: string;
  },
): Promise<BadCaseInfo> {
  return post<BadCaseInfo>(
    `/projects/${projectId}/bad-cases`,
    data,
  );
}

export function getBadCaseDetail(
  projectId: string,
  caseId: string,
): Promise<BadCaseInfo> {
  return get<BadCaseInfo>(
    `/projects/${projectId}/bad-cases/${caseId}`,
  );
}

export function updateBadCase(
  projectId: string,
  caseId: string,
  data: {
    status?: BadCaseStatus;
    assignee_id?: string;
    resolution?: string;
  },
): Promise<BadCaseInfo> {
  return put<BadCaseInfo>(
    `/projects/${projectId}/bad-cases/${caseId}`,
    data,
  );
}

export function getBadCaseStats(
  projectId: string,
): Promise<BadCaseStats> {
  return get<BadCaseStats>(
    `/projects/${projectId}/bad-cases/stats`,
  );
}