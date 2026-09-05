/**
 * 项目 API 封装
 */
import { get, post, put, del } from './api';

export interface ProjectInfo {
  id: string;
  name: string;
  description?: string;
  owner_id: string;
  is_deleted: boolean;
  created_at: string;
  updated_at: string;
}

export interface ProjectCreatePayload {
  name: string;
  description?: string;
}

export interface ProjectUpdatePayload {
  name?: string;
  description?: string;
}

/** 获取项目列表 */
export async function listProjects(): Promise<ProjectInfo[]> {
  return get<ProjectInfo[]>('/projects');
}

/** 创建项目 */
export async function createProject(data: ProjectCreatePayload): Promise<ProjectInfo> {
  return post<ProjectInfo>('/projects', data);
}

/** 获取项目详情 */
export async function getProject(projectId: string): Promise<ProjectInfo> {
  return get<ProjectInfo>(`/projects/${projectId}`);
}

/** 更新项目 */
export async function updateProject(projectId: string, data: ProjectUpdatePayload): Promise<ProjectInfo> {
  return put<ProjectInfo>(`/projects/${projectId}`, data);
}

/** 删除项目（软删除） */
export async function deleteProject(projectId: string): Promise<void> {
  return del<void>(`/projects/${projectId}`);
}