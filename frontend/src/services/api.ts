/**
 * Axios 实例封装
 * - baseURL 指向 /api/v1（Vite 代理到 localhost:8000）
 * - 请求拦截器自动附加 JWT Bearer Token
 * - 响应拦截器 401 自动跳转登录页
 */
import axios, { AxiosError, InternalAxiosRequestConfig } from 'axios';

const TOKEN_KEY = 'agentscope_token';

const api = axios.create({
  baseURL: '/api/v1',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// ---------- 请求拦截器 ----------
api.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const token = localStorage.getItem(TOKEN_KEY);
    if (token && config.headers) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error),
);

// ---------- 响应拦截器 ----------
api.interceptors.response.use(
  (response) => response,
  (error: AxiosError<ApiResponse>) => {
    if (error.response?.status === 401) {
      // Token 过期或无效，清除本地状态并跳转登录
      localStorage.removeItem(TOKEN_KEY);
      localStorage.removeItem('agentscope_user');
      // 避免登录页本身 401 时死循环
      if (!window.location.pathname.startsWith('/login')) {
        window.location.href = '/login';
      }
    }
    // 将后端业务错误信息附加到 error 上，方便前端 catch 中读取
    if (error.response?.data?.message) {
      error.message = error.response.data.message;
    }
    return Promise.reject(error);
  },
);

// ---------- 泛型请求方法 ----------

/** 后端统一响应结构 */
export interface ApiResponse<T = unknown> {
  code: number;
  message: string;
  data: T;
}

/** 分页响应结构 */
export interface PaginatedData<T = unknown> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

export async function get<T>(url: string, params?: Record<string, unknown>): Promise<T> {
  const res = await api.get<ApiResponse<T>>(url, { params });
  return res.data.data;
}

export async function post<T>(url: string, data?: unknown): Promise<T> {
  const res = await api.post<ApiResponse<T>>(url, data);
  return res.data.data;
}

export async function put<T>(url: string, data?: unknown): Promise<T> {
  const res = await api.put<ApiResponse<T>>(url, data);
  return res.data.data;
}

export async function del<T>(url: string): Promise<T> {
  const res = await api.delete<ApiResponse<T>>(url);
  return res.data?.data as T;
}

export default api;