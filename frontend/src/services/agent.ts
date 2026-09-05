/**
 * Agent API 封装
 */
import { get, post, put, del } from './api';

// ---------- 类型 ----------

export interface AgentInfo {
  id: string;
  project_id: string;
  name: string;
  version: string;
  description?: string;
  endpoint_url?: string;
  config: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

/** 创建 Agent 请求参数 */
export interface AgentCreateData {
  name: string;
  version: string;
  description?: string;
  endpoint_url?: string;
  config?: Record<string, unknown>;
}

/** 更新 Agent 请求参数 */
export interface AgentUpdateData {
  name?: string;
  version?: string;
  description?: string;
  endpoint_url?: string;
  config?: Record<string, unknown>;
}

// ---------- API ----------

/** 获取 Agent 列表 */
export function listAgents(projectId: string): Promise<AgentInfo[]> {
  return get<AgentInfo[]>(`/projects/${projectId}/agents`);
}

/** 注册 Agent */
export function createAgent(
  projectId: string,
  data: AgentCreateData,
): Promise<AgentInfo> {
  return post<AgentInfo>(`/projects/${projectId}/agents`, data);
}

/** 获取 Agent 详情 */
export function getAgentDetail(
  projectId: string,
  agentId: string,
): Promise<AgentInfo> {
  return get<AgentInfo>(`/projects/${projectId}/agents/${agentId}`);
}

/** 更新 Agent */
export function updateAgent(
  projectId: string,
  agentId: string,
  data: AgentUpdateData,
): Promise<AgentInfo> {
  return put<AgentInfo>(`/projects/${projectId}/agents/${agentId}`, data);
}

/** 删除 Agent */
export function deleteAgent(
  projectId: string,
  agentId: string,
): Promise<void> {
  return del<void>(`/projects/${projectId}/agents/${agentId}`);
}