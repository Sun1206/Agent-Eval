/**
 * 数据集 API 封装
 */
import { get, post, put, del, PaginatedData } from './api';

// ---------- 类型 ----------

export interface DatasetInfo {
  id: string;
  project_id: string;
  name: string;
  description?: string;
  tags: string[];
  item_count: number;
  created_by?: string;
  created_at: string;
  updated_at: string;
}

export interface DatasetItem {
  id: string;
  dataset_id: string;
  sort_order: number;
  input: string;
  expected_output?: string;
  context?: string;
  tags: string[];
  metadata: Record<string, unknown>;
  created_at: string;
}

export interface ImportResult {
  total: number;
  imported: number;
  skipped: number;
  errors: string[];
}

// ---------- 数据集 CRUD ----------

export function listDatasets(projectId: string): Promise<DatasetInfo[]> {
  return get<DatasetInfo[]>(`/projects/${projectId}/datasets`);
}

export function getDataset(projectId: string, datasetId: string): Promise<DatasetInfo> {
  return get<DatasetInfo>(`/projects/${projectId}/datasets/${datasetId}`);
}

export function createDataset(
  projectId: string,
  data: { name: string; description?: string; tags?: string[] },
): Promise<DatasetInfo> {
  return post<DatasetInfo>(`/projects/${projectId}/datasets`, data);
}

export function updateDataset(
  projectId: string,
  datasetId: string,
  data: { name?: string; description?: string; tags?: string[] },
): Promise<DatasetInfo> {
  return put<DatasetInfo>(`/projects/${projectId}/datasets/${datasetId}`, data);
}

export function deleteDataset(projectId: string, datasetId: string): Promise<void> {
  return del<void>(`/projects/${projectId}/datasets/${datasetId}`);
}

// ---------- 条目 CRUD ----------

export function listDatasetItems(
  projectId: string,
  datasetId: string,
  page = 1,
  pageSize = 20,
): Promise<PaginatedData<DatasetItem>> {
  return get<PaginatedData<DatasetItem>>(
    `/projects/${projectId}/datasets/${datasetId}/items`,
    { page, page_size: pageSize },
  );
}

export function addDatasetItem(
  projectId: string,
  datasetId: string,
  data: {
    input: string;
    expected_output?: string;
    context?: string;
    tags?: string[];
    metadata?: Record<string, unknown>;
    sort_order?: number;
  },
): Promise<DatasetItem> {
  return post<DatasetItem>(
    `/projects/${projectId}/datasets/${datasetId}/items`,
    data,
  );
}

export function updateDatasetItem(
  projectId: string,
  datasetId: string,
  itemId: string,
  data: {
    input?: string;
    expected_output?: string;
    context?: string;
    tags?: string[];
    metadata?: Record<string, unknown>;
    sort_order?: number;
  },
): Promise<DatasetItem> {
  return put<DatasetItem>(
    `/projects/${projectId}/datasets/${datasetId}/items/${itemId}`,
    data,
  );
}

export function deleteDatasetItem(
  projectId: string,
  datasetId: string,
  itemId: string,
): Promise<void> {
  return del<void>(
    `/projects/${projectId}/datasets/${datasetId}/items/${itemId}`,
  );
}

export function batchDeleteDatasetItems(
  projectId: string,
  datasetId: string,
  itemIds: string[],
): Promise<{ deleted: number }> {
  return post<{ deleted: number }>(
    `/projects/${projectId}/datasets/${datasetId}/items/batch-delete`,
    { item_ids: itemIds },
  );
}

// ---------- 导入导出 ----------

export async function importDatasetFile(
  projectId: string,
  datasetId: string,
  file: File,
): Promise<ImportResult> {
  const formData = new FormData();
  formData.append('file', file);

  // multipart 请求使用带 token 的 fetch（避开 axios 的 JSON Content-Type）
  const token = localStorage.getItem('agentscope_token');
  const res = await fetch(
    `/api/v1/projects/${projectId}/datasets/${datasetId}/import`,
    {
      method: 'POST',
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      body: formData,
    },
  );
  if (!res.ok) {
    const errBody = await res.json().catch(() => ({}));
    throw new Error(errBody.detail || `导入失败 (HTTP ${res.status})`);
  }
  const json = await res.json();
  return json.data;
}

export function getExportUrl(
  projectId: string,
  datasetId: string,
  fmt: 'json' | 'csv' = 'json',
): string {
  return `/api/v1/projects/${projectId}/datasets/${datasetId}/export?fmt=${fmt}`;
}