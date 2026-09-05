# AgentEval — 企业级 AI Agent 评测与可观测性平台

一站式 AI Agent 评测与轨迹分析平台，帮助团队高效评估 Agent 质量、快速定位问题根因、实现数据驱动的模型迭代。

## 核心价值

- **评测自动化**：从手工评测到一键自动化，支持 LLM-as-Judge 多维度评分，评测效率提升 10x
- **问题可追溯**：每一次 Agent 执行都有完整轨迹记录，问题定位从小时级到分钟级
- **决策数据化**：多模型对比、版本趋势一目了然，通过率/平均分/维度得分全面量化

## 功能概览

| 模块 | 功能 |
|------|------|
| **项目管理** | 多项目隔离，成员角色管理 |
| **Agent 管理** | 注册 Agent，配置端点/鉴权（Bearer/API Key/Custom），版本管理 |
| **数据集管理** | 创建/导入数据集，条目增删改查，批量操作，metadata 管理 |
| **评测管理** | 创建评测任务，并发控制，实时进度轮询，多维度 LLM 评分 |
| **评测结果** | 总分/维度得分/通过率/耗时，单条重试，Trace 关联跳转 |
| **Trace 可观测** | SDK 自动采集，Span 树形可视化，LLM/Tool/Retrieval 调用链追踪 |
| **Bad Case** | 标记/分配/解决 Bad Case，闭环问题跟踪 |
| **API Key** | SDK 认证密钥管理，支持创建/吊销 |

## 技术栈

### 后端

| 技术 | 版本 | 用途 |
|------|------|------|
| FastAPI | >=0.115 | Web 框架，异步 API |
| SQLAlchemy | >=2.0 (async) | ORM，异步 PostgreSQL |
| asyncpg | >=0.30 | PostgreSQL 异步驱动 |
| Alembic | >=1.14 | 数据库迁移 |
| ClickHouse Connect | >=0.7 | Trace 数据存储 |
| Redis | >=5.2 | 缓存/会话 |
| httpx | >=0.28 | 异步 HTTP 客户端 |
| Pydantic | >=2.9 | 数据校验 |
| pydantic-settings | >=2.6 | 环境变量配置 |
| python-jose | >=3.3 | JWT Token |
| passlib | >=1.7 | 密码哈希（argon2） |

### 前端

| 技术 | 版本 | 用途 |
|------|------|------|
| React | ^18.3 | UI 框架 |
| TypeScript | ~5.6 | 类型安全 |
| Ant Design | ^5.22 | UI 组件库 |
| React Router | ^6.28 | 路由管理 |
| Axios | ^1.7 | HTTP 客户端 |
| Vite | ^6.0 | 构建工具 |
| dayjs | ^1.11 | 日期处理 |

### 基础设施

| 服务 | 版本 | 端口 | 用途 |
|------|------|------|------|
| PostgreSQL | 16-alpine | 5432 | 主数据库 |
| ClickHouse | 24.8-alpine | 8123/9000 | Trace 数据 |
| Redis | 7-alpine | 6379 | 缓存/会话 |

### Python SDK

| 技术 | 用途 |
|------|------|
| httpx | 异步 Trace 上报（唯一外部依赖） |
| LangChain (可选) | LangChain Callback Handler 集成 |

## 快速开始

### 1. 环境准备

- Python >=3.10, <3.12
- Node.js >=18
- Docker & Docker Compose

### 2. 启动基础设施

```bash
docker-compose up -d
```

启动 PostgreSQL、ClickHouse、Redis 三个服务。

### 3. 配置环境变量

```bash
cp .env.example .env
```

编辑 `.env`，必须配置以下项：

```ini
# 应用密钥（随机字符串，至少32位）
APP_SECRET_KEY=your-random-secret-key-here

# JWT 签名密钥（随机字符串）
JWT_SECRET_KEY=your-random-jwt-key-here

# 数据库密码（需与 docker-compose 中一致）
POSTGRES_PASSWORD=your-password

# ClickHouse 密码
CLICKHOUSE_PASSWORD=your-password

# LLM API Key（至少配置一个，用于评测评分）
OPENAI_API_KEY=sk-your-key
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_DEFAULT_MODEL=gpt-4o-mini
```

### 4. 初始化数据库

```bash
cd backend
pip install -r requirements.txt
alembic upgrade head
```

### 5. 启动后端

```bash
# 开发模式（热重载）
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# 或使用 Windows 脚本
start.bat
```

API 文档：http://localhost:8000/api/docs

### 6. 启动前端

```bash
cd frontend
npm install
npm run dev
```

访问：http://localhost:5173

## 项目结构

```
agent-eval-platform/
├── .env.example                    # 环境变量模板
├── docker-compose.yml              # 基础设施编排
├── requirements.txt                # Python 依赖
│
├── backend/                        # 后端服务
│   ├── alembic/                    # 数据库迁移
│   │   └── versions/               # 迁移脚本
│   ├── app/
│   │   ├── main.py                 # FastAPI 入口
│   │   ├── config.py               # 配置管理
│   │   ├── api/                    # API 路由层
│   │   │   ├── auth.py             # 认证（注册/登录）
│   │   │   ├── projects.py         # 项目管理
│   │   │   ├── agents.py           # Agent 管理
│   │   │   ├── datasets.py         # 数据集管理
│   │   │   ├── evaluations.py      # 评测管理
│   │   │   ├── traces.py           # Trace 管理
│   │   │   ├── bad_cases.py        # Bad Case 管理
│   │   │   └── sdk.py              # SDK 接口
│   │   ├── core/                   # 核心基础设施
│   │   │   ├── database.py         # PostgreSQL 连接池
│   │   │   ├── clickhouse.py       # ClickHouse 连接
│   │   │   ├── redis.py            # Redis 连接
│   │   │   ├── security.py         # 安全（JWT/密码哈希）
│   │   │   └── exceptions.py       # 异常定义
│   │   ├── models/                 # ORM 模型
│   │   ├── schemas/                # Pydantic 模型
│   │   └── services/               # 业务逻辑
│   │       ├── eval_executor.py    # 评测执行引擎
│   │       ├── judge_service.py    # LLM-as-Judge 评分
│   │       ├── llm_client.py       # LLM 客户端（多 Provider）
│   │       ├── agent_adapter.py    # Agent 调用适配器
│   │       └── trace_service.py    # Trace 写入/查询
│   └── start.bat                   # Windows 启动脚本
│
├── frontend/                       # 前端应用
│   ├── src/
│   │   ├── App.tsx                 # 路由配置
│   │   ├── layouts/                # 布局组件
│   │   ├── pages/                  # 页面组件
│   │   │   ├── agents/             # Agent 管理
│   │   │   ├── datasets/           # 数据集管理
│   │   │   ├── evaluations/        # 评测管理
│   │   │   ├── traces/             # Trace 可观测
│   │   │   └── badcases/           # Bad Case
│   │   ├── components/             # 公共组件
│   │   └── services/               # API 调用层
│   └── vite.config.ts              # Vite 配置（API 代理）
│
├── sdk/                            # Python SDK
│   └── agent_eval/
│       ├── client.py               # TraceCollector 上报客户端
│       ├── decorators.py           # @trace 装饰器
│       ├── context.py              # trace_context 上下文管理
│       ├── models.py               # Span/Trace 数据模型
│       └── langchain_hook.py       # LangChain 集成
│
└── docs/                           # 项目文档（21份）
```

## 核心架构

### 评测执行流程

```
创建评测任务 → 后台异步执行 → 逐条处理 → 汇总统计
                                  │
                                  ├─ 调用 Agent（HTTP，支持鉴权）
                                  ├─ 自动生成 Trace（写入 ClickHouse）
                                  ├─ LLM-as-Judge 评分（多维度）
                                  └─ 写入评测结果（PostgreSQL）
```

### LLM-as-Judge 评分

支持多个 LLM Provider 作为评分模型：

| Provider | 默认模型 | 配置项 |
|----------|---------|--------|
| OpenAI | gpt-4o-mini | `OPENAI_API_KEY` / `OPENAI_BASE_URL` |
| DeepSeek | deepseek-chat | `DEEPSEEK_API_KEY` / `DEEPSEEK_BASE_URL` |
| DashEval | qwen-plus | `DASHSCOPE_API_KEY` |

评分流程：
1. 构建评分 Prompt（含评分维度、等级标准、输入/输出/期望输出）
2. 调用 LLM 获取评分
3. 解析响应（优先 JSON，兜底 Markdown 格式解析）
4. 返回总分 + 维度得分 + 评分理由

### Trace 可观测架构

```
Agent 应用 → SDK 采集 → HTTP 上报 → ClickHouse 存储 → 平台查询/可视化
                                                    │
评测执行 ───────────────────────── 自动生成 Trace ──┘
```

- **SDK 集成的 Agent**：通过 `@trace` 装饰器或 LangChain Callback 自动采集，Span 级别数据丰富
- **未集成 SDK 的 Agent**：评测执行时自动生成 Trace（输入/输出/耗时），确保可追溯

## SDK 使用

### 安装

```bash
pip install agent-eval-sdk
```

### 快速开始

```python
from agent_eval import TraceCollector, trace, set_collector

# 1. 初始化 Collector
collector = TraceCollector(
    api_key="agev_xxxxxxxx",
    endpoint="http://localhost:8000/api/v1/sdk",
)
set_collector(collector)

# 2. 使用装饰器追踪函数
@trace(name="my_agent_call", span_type="chain")
async def my_agent(input_text: str) -> str:
    # Agent 逻辑...
    return "response"

# 3. 手动管理 Span
from agent_eval import trace_context

with trace_context("my_trace", input="hello") as tc:
    tc.span("llm_call", input={"prompt": "hello"})
    # ... LLM 调用 ...
    tc.end_span(output={"text": "response"})
```

### LangChain 集成

```python
from agent_eval import AgentEvalCallbackHandler

handler = AgentEvalCallbackHandler(
    api_key="agev_xxxxxxxx",
    endpoint="http://localhost:8000/api/v1/sdk",
)

# 传入 LangChain Agent
agent = AgentExecutor.from_agent_and_tools(
    agent=llm_agent,
    tools=tools,
    callbacks=[handler],  # 自动拦截 LLM/Tool 调用
)
```

## API 概览

所有 API 挂载在 `/api/v1` 前缀下，完整文档见 `/api/docs`。

| 模块 | 方法 | 路径 | 说明 |
|------|------|------|------|
| 认证 | POST | /auth/register | 用户注册 |
| | POST | /auth/login | 用户登录 |
| 项目 | GET | /projects | 项目列表 |
| | POST | /projects | 创建项目 |
| Agent | GET | /projects/{pid}/agents | Agent 列表 |
| | POST | /projects/{pid}/agents | 注册 Agent |
| 数据集 | GET | /projects/{pid}/datasets | 数据集列表 |
| | POST | /projects/{pid}/datasets | 创建数据集 |
| | GET | /projects/{pid}/datasets/{did} | 数据集详情 |
| 评测 | POST | /projects/{pid}/evaluations | 创建评测任务 |
| | GET | /projects/{pid}/evaluations | 评测任务列表 |
| | GET | /projects/{pid}/evaluations/{rid} | 评测详情 |
| | POST | /projects/{pid}/evaluations/{rid}/retry | 重试评测 |
| | GET | /projects/{pid}/evaluations/{rid}/results | 评测结果列表 |
| | POST | /projects/{pid}/evaluations/{rid}/results/{result_id}/retry | 单条结果重试 |
| | GET | /projects/{pid}/evaluations/{rid}/stats | 评测统计 |
| | GET | /projects/{pid}/evaluations/{rid}/progress | 评测进度 |
| Trace | GET | /projects/{pid}/traces | Trace 列表 |
| | GET | /projects/{pid}/traces/{tid} | Trace 详情 |
| SDK | POST | /sdk/traces | 上报 Trace |
| | POST | /sdk/traces/batch | 批量上报 |

## 环境变量

| 分类 | 变量 | 说明 | 必填 |
|------|------|------|------|
| 应用 | `APP_SECRET_KEY` | 应用密钥 | 是 |
| | `APP_ENV` | 运行环境 | 否 |
| | `APP_DEBUG` | 调试模式 | 否 |
| PostgreSQL | `POSTGRES_HOST` | 主机 | 否 |
| | `POSTGRES_PORT` | 端口 | 否 |
| | `POSTGRES_DB` | 数据库名 | 否 |
| | `POSTGRES_USER` | 用户名 | 否 |
| | `POSTGRES_PASSWORD` | 密码 | 是 |
| ClickHouse | `CLICKHOUSE_HOST` | 主机 | 否 |
| | `CLICKHOUSE_PORT` | HTTP 端口 | 否 |
| | `CLICKHOUSE_USER` | 用户名 | 否 |
| | `CLICKHOUSE_PASSWORD` | 密码 | 否 |
| | `CLICKHOUSE_DB` | 数据库名 | 否 |
| Redis | `REDIS_HOST` | 主机 | 否 |
| | `REDIS_PORT` | 端口 | 否 |
| | `REDIS_PASSWORD` | 密码 | 否 |
| JWT | `JWT_SECRET_KEY` | 签名密钥 | 是 |
| | `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | 过期时间 | 否 |
| LLM | `OPENAI_API_KEY` | OpenAI API Key | 否* |
| | `OPENAI_BASE_URL` | OpenAI 基础 URL | 否 |
| | `OPENAI_DEFAULT_MODEL` | 默认模型 | 否 |
| | `DEEPSEEK_API_KEY` | DeepSeek API Key | 否* |
| | `DASHSCOPE_API_KEY` | 通义千问 API Key | 否* |

\* LLM API Key 至少配置一个，否则评测评分无法工作。

## 数据库

### PostgreSQL（主数据库）

11 张业务表：users, api_keys, projects, project_members, agents, datasets, dataset_items, eval_runs, eval_results, traces, bad_cases

### ClickHouse（Trace 存储）

- `traces` 表：ReplacingMergeTree 引擎，按月分区，支持全文搜索
- 自动建表：应用启动时自动创建（如不存在）

### 数据库迁移

```bash
cd backend
alembic upgrade head      # 升级到最新
alembic revision --autogenerate -m "描述"  # 生成迁移脚本
```

## 开发指南

### 后端开发

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate     # Windows
source .venv/bin/activate  # Linux/Mac
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 前端开发

```bash
cd frontend
npm install
npm run dev        # 开发服务器 http://localhost:5173
npm run build      # 生产构建
npm run preview    # 预览生产构建
```

### 代码结构约定

- **后端**：API 路由 → Service 业务逻辑 → Model 数据层，严格分层
- **前端**：Pages 页面 → Services API 调用，Ant Design 组件库
- **配置**：所有敏感信息通过 `.env` 管理，代码中不硬编码

## License

MIT
