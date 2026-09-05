/**
 * 评测 API 封装
 */
import { get, post, del, PaginatedData } from './api';

// ---------- 类型 ----------

/** 评测任务列表项 */
export interface EvalRunListItem {
  id: string;
  project_id: string;
  dataset_id: string;
  agent_id: string;
  name?: string;
  status: string; // PENDING / RUNNING / COMPLETED / FAILED / CANCELLED
  concurrency: number;
  total_items: number;
  completed_items: number;
  failed_items: number;
  avg_score?: number;
  pass_rate?: number;
  created_at?: string;
  started_at?: string;
  completed_at?: string;
  created_by?: string;
}

/** 评分配置 */
export interface JudgeConfig {
  provider: string;
  model: string;
  prompt_template: string;
  dimensions: string[];
  weights: Record<string, number>;
}

/** 评测任务详情 */
export interface EvalRunDetail {
  id: string;
  project_id: string;
  dataset_id: string;
  agent_id: string;
  name?: string;
  status: string;
  judge_config: JudgeConfig;
  concurrency: number;
  total_items: number;
  completed_items: number;
  failed_items: number;
  avg_score?: number;
  pass_rate?: number;
  started_at?: string;
  completed_at?: string;
  error_message?: string;
  created_at?: string;
  created_by?: string;
}

/** 单条评测结果 */
export interface EvalResultItem {
  id: string;
  eval_run_id: string;
  dataset_item_id: string;
  sort_order: number;
  agent_input: string;
  agent_output?: string;
  total_score?: number;
  dimension_scores: Record<string, number>;
  judge_reason?: string;
  status: string; // SUCCESS / FAILURE / ERROR / TIMEOUT
  trace_id?: string;
  error_message?: string;
  duration_ms?: number;
  token_usage: Record<string, unknown>;
  created_at?: string;
}

/** 评测统计摘要 */
export interface EvalStats {
  total_items: number;
  success_items: number;
  failure_items: number;
  pass_rate?: number;
  avg_score?: number;
  dimension_avgs: Record<string, number>;
  score_distribution: Record<string, number>;
  avg_duration_ms?: number;
}

/** 评测进度 */
export interface EvalProgress {
  status: string;
  total_items: number;
  completed_items: number;
  failed_items: number;
  avg_score?: number | null;
  pass_rate?: number | null;
}

// ---------- 评测任务 CRUD ----------

export function listEvalRuns(
  projectId: string,
  page = 1,
  pageSize = 20,
): Promise<PaginatedData<EvalRunListItem>> {
  return get<PaginatedData<EvalRunListItem>>(
    `/projects/${projectId}/evaluations`,
    { page, page_size: pageSize },
  );
}

export function createEvalRun(
  projectId: string,
  data: {
    dataset_id: string;
    agent_id: string;
    name?: string;
    judge_config?: JudgeConfig;
    concurrency?: number;
  },
): Promise<EvalRunDetail> {
  return post<EvalRunDetail>(
    `/projects/${projectId}/evaluations`,
    data,
  );
}

export function getEvalRunDetail(
  projectId: string,
  runId: string,
): Promise<EvalRunDetail> {
  return get<EvalRunDetail>(
    `/projects/${projectId}/evaluations/${runId}`,
  );
}

export function cancelEvalRun(
  projectId: string,
  runId: string,
): Promise<EvalRunDetail> {
  return post<EvalRunDetail>(
    `/projects/${projectId}/evaluations/${runId}/cancel`,
  );
}

export function retryEvalRun(
  projectId: string,
  runId: string,
): Promise<EvalRunDetail> {
  return post<EvalRunDetail>(
    `/projects/${projectId}/evaluations/${runId}/retry`,
  );
}

export function deleteEvalRun(
  projectId: string,
  runId: string,
): Promise<void> {
  return del<void>(
    `/projects/${projectId}/evaluations/${runId}`,
  );
}

// ---------- 结果 / 统计 / 进度 ----------

export function listEvalResults(
  projectId: string,
  runId: string,
  page = 1,
  pageSize = 20,
  filters?: {
    status?: string;
    sort_by?: string;
    sort_order?: string;
  },
): Promise<PaginatedData<EvalResultItem>> {
  return get<PaginatedData<EvalResultItem>>(
    `/projects/${projectId}/evaluations/${runId}/results`,
    {
      page,
      page_size: pageSize,
      ...filters,
    },
  );
}

export function getEvalStats(
  projectId: string,
  runId: string,
): Promise<EvalStats> {
  return get<EvalStats>(
    `/projects/${projectId}/evaluations/${runId}/stats`,
  );
}

export function getEvalProgress(
  projectId: string,
  runId: string,
): Promise<EvalProgress> {
  return get<EvalProgress>(
    `/projects/${projectId}/evaluations/${runId}/progress`,
  );
}

/** 重试单条评测结果 */
export function retryEvalResult(
  projectId: string,
  runId: string,
  resultId: string,
): Promise<EvalResultItem> {
  return post<EvalResultItem>(
    `/projects/${projectId}/evaluations/${runId}/results/${resultId}/retry`,
  );
}