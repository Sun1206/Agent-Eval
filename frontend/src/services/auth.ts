/**
 * 认证工具
 * - login / register / logout
 * - Token 存储于 localStorage
 * - getCurrentUser 从 localStorage 读取缓存的用户信息
 */
import { get, post, del } from './api';

const TOKEN_KEY = 'agentscope_token';
const USER_KEY = 'agentscope_user';

// ---------- 类型 ----------

export interface UserInfo {
  id: string;
  username: string;
  email: string;
  role: string;
}

export interface AuthTokens {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

// ---------- Token 管理 ----------

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

export function removeToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}

// ---------- 用户信息 ----------

export function getCurrentUser(): UserInfo | null {
  const raw = localStorage.getItem(USER_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

export function setCurrentUser(user: UserInfo): void {
  localStorage.setItem(USER_KEY, JSON.stringify(user));
}

export function removeCurrentUser(): void {
  localStorage.removeItem(USER_KEY);
}

// ---------- API 调用 ----------

export async function login(login_: string, password: string): Promise<UserInfo> {
  // 后端 LoginRequest: { login, password }，返回 LoginResponse: { access_token, refresh_token, user }
  const res = await post<{ access_token: string; refresh_token: string; user: UserInfo }>(
    '/auth/login',
    { login: login_, password },
  );
  setToken(res.access_token);
  setCurrentUser(res.user);
  return res.user;
}

export async function register(
  username: string,
  email: string,
  password: string,
  display_name?: string,
): Promise<UserInfo> {
  // 后端 RegisterRequest → LoginResponse: { access_token, refresh_token, user }
  const res = await post<{ access_token: string; refresh_token: string; user: UserInfo }>(
    '/auth/register',
    { username, email, password, display_name },
  );
  setToken(res.access_token);
  setCurrentUser(res.user);
  return res.user;
}

export function logout(): void {
  removeToken();
  removeCurrentUser();
  window.location.href = '/login';
}

export function isAuthenticated(): boolean {
  return !!getToken();
}

// ---------- API Key 管理 ----------

export interface ApiKeyInfo {
  id: string;
  name: string;
  key_prefix: string;
  is_active: boolean;
  last_used_at?: string;
  expires_at?: string;
  created_at: string;
}

export interface ApiKeyCreateInfo extends ApiKeyInfo {
  full_key: string;
}

/** 列出当前用户的 API Key */
export function listApiKeys(): Promise<ApiKeyInfo[]> {
  return get<ApiKeyInfo[]>('/auth/api-keys');
}

/** 创建 API Key（完整 Key 仅此时返回） */
export function createApiKey(
  name: string,
  expires_at?: string,
): Promise<ApiKeyCreateInfo> {
  return post<ApiKeyCreateInfo>('/auth/api-keys', { name, expires_at });
}

/** 吊销 API Key */
export function revokeApiKey(keyId: string): Promise<void> {
  return del<void>(`/auth/api-keys/${keyId}`);
}