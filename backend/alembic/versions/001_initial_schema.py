"""初始化全部表结构

Revision ID: 001_initial_schema
Revises: None
Create Date: 2026-05-20

创建 11 张业务表 + 全部索引 + 外键约束:
  users, api_keys, projects, project_members, agents,
  datasets, dataset_items, eval_runs, eval_results, traces, bad_cases
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # =============================================================
    # 1. users - 用户表
    # =============================================================
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), comment="主键"),
        sa.Column("username", sa.String(50), unique=True, nullable=False, comment="用户名"),
        sa.Column("email", sa.String(255), unique=True, nullable=False, comment="邮箱"),
        sa.Column("password_hash", sa.String(255), nullable=False, comment="密码哈希 (bcrypt)"),
        sa.Column("display_name", sa.String(100), nullable=True, comment="显示名称"),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), comment="是否激活"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), comment="创建时间"),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), comment="更新时间"),
    )
    op.create_index("idx_users_username", "users", ["username"])
    op.create_index("idx_users_email", "users", ["email"])

    # =============================================================
    # 2. api_keys - API Key 表
    # =============================================================
    op.create_table(
        "api_keys",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), comment="主键"),
        sa.Column("user_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, comment="所属用户"),
        sa.Column("key_hash", sa.String(255), nullable=False, comment="API Key 哈希 (SHA256)"),
        sa.Column("name", sa.String(100), nullable=False, comment="Key 名称"),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), comment="是否有效"),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True, comment="最后使用时间"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True, comment="过期时间"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), comment="创建时间"),
    )
    op.create_index("idx_api_keys_user", "api_keys", ["user_id"])
    op.create_index("idx_api_keys_hash", "api_keys", ["key_hash"])

    # =============================================================
    # 3. projects - 项目表
    # =============================================================
    op.create_table(
        "projects",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), comment="主键"),
        sa.Column("name", sa.String(100), nullable=False, comment="项目名称"),
        sa.Column("description", sa.Text(), nullable=True, comment="项目描述"),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, comment="创建者"),
        sa.Column("is_deleted", sa.Boolean(), server_default=sa.text("false"), comment="软删除标记"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), comment="创建时间"),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), comment="更新时间"),
    )
    op.create_index("idx_projects_owner", "projects", ["owner_id"])
    # 按 owner_id + name 唯一（排除已删除项目）
    op.create_index(
        "idx_projects_name",
        "projects",
        ["owner_id", "name"],
        unique=True,
        postgresql_where=sa.text("is_deleted = FALSE"),
    )

    # =============================================================
    # 4. project_members - 项目成员表
    # =============================================================
    op.create_table(
        "project_members",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), comment="主键"),
        sa.Column("project_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, comment="所属项目"),
        sa.Column("user_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, comment="成员用户"),
        sa.Column("role", sa.String(20), nullable=False, server_default="member",
                  comment="角色: owner/admin/member/viewer"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), comment="加入时间"),
    )
    op.create_index("idx_pm_project_user", "project_members", ["project_id", "user_id"], unique=True)

    # =============================================================
    # 5. agents - Agent 注册表
    # =============================================================
    op.create_table(
        "agents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), comment="主键"),
        sa.Column("project_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, comment="所属项目"),
        sa.Column("name", sa.String(100), nullable=False, comment="Agent 名称"),
        sa.Column("version", sa.String(20), nullable=False, comment="版本号 (SemVer)"),
        sa.Column("description", sa.Text(), nullable=True, comment="描述"),
        sa.Column("endpoint_url", sa.String(500), nullable=True, comment="Agent 服务地址"),
        sa.Column("config", postgresql.JSONB(), server_default=sa.text("'{}'"), comment="Agent 配置"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), comment="注册时间"),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), comment="更新时间"),
    )
    op.create_index("idx_agents_project", "agents", ["project_id"])
    op.create_index("idx_agents_name_version", "agents", ["project_id", "name", "version"], unique=True)

    # =============================================================
    # 6. datasets - 数据集表
    # =============================================================
    op.create_table(
        "datasets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), comment="主键"),
        sa.Column("project_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, comment="所属项目"),
        sa.Column("name", sa.String(200), nullable=False, comment="数据集名称"),
        sa.Column("description", sa.Text(), nullable=True, comment="描述"),
        sa.Column("tags", postgresql.ARRAY(sa.String(50)), server_default=sa.text("'{}'"), comment="标签数组"),
        sa.Column("item_count", sa.Integer(), server_default=sa.text("0"), comment="数据条目数"),
        sa.Column("created_by", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True, comment="创建者"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), comment="创建时间"),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), comment="更新时间"),
    )
    op.create_index("idx_datasets_project", "datasets", ["project_id"])
    op.create_index("idx_datasets_tags", "datasets", ["tags"], postgresql_using="gin")

    # =============================================================
    # 7. dataset_items - 数据集条目表
    # =============================================================
    op.create_table(
        "dataset_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), comment="主键"),
        sa.Column("dataset_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False, comment="所属数据集"),
        sa.Column("sort_order", sa.Integer(), server_default=sa.text("0"), comment="排序序号"),
        sa.Column("input", sa.Text(), nullable=False, comment="用户输入/问题"),
        sa.Column("expected_output", sa.Text(), nullable=True, comment="期望输出/参考答案"),
        sa.Column("context", sa.Text(), nullable=True, comment="上下文信息"),
        sa.Column("tags", postgresql.ARRAY(sa.String(50)), server_default=sa.text("'{}'"), comment="条目级标签"),
        sa.Column("metadata", postgresql.JSONB(), server_default=sa.text("'{}'"), comment="扩展元数据"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), comment="创建时间"),
    )
    op.create_index("idx_di_dataset", "dataset_items", ["dataset_id"])
    op.create_index("idx_di_dataset_sort", "dataset_items", ["dataset_id", "sort_order"])

    # =============================================================
    # 8. eval_runs - 评测任务表
    # =============================================================
    op.create_table(
        "eval_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), comment="主键"),
        sa.Column("project_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, comment="所属项目"),
        sa.Column("dataset_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("datasets.id", ondelete="RESTRICT"), nullable=False, comment="使用的数据集"),
        sa.Column("agent_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("agents.id", ondelete="RESTRICT"), nullable=False, comment="被评测的 Agent"),
        sa.Column("name", sa.String(200), nullable=True, comment="任务名称"),
        sa.Column("status", sa.String(20), nullable=False, server_default="PENDING",
                  comment="PENDING/RUNNING/COMPLETED/FAILED/CANCELLED"),
        sa.Column("judge_config", postgresql.JSONB(), nullable=False, comment="评分配置"),
        sa.Column("concurrency", sa.Integer(), server_default=sa.text("5"), comment="并发数"),
        sa.Column("total_items", sa.Integer(), server_default=sa.text("0"), comment="总用例数"),
        sa.Column("completed_items", sa.Integer(), server_default=sa.text("0"), comment="已完成用例数"),
        sa.Column("failed_items", sa.Integer(), server_default=sa.text("0"), comment="失败用例数"),
        sa.Column("avg_score", sa.Numeric(5, 2), nullable=True, comment="平均分"),
        sa.Column("pass_rate", sa.Numeric(5, 2), nullable=True, comment="通过率"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True, comment="开始时间"),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True, comment="完成时间"),
        sa.Column("error_message", sa.Text(), nullable=True, comment="失败原因"),
        sa.Column("created_by", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True, comment="创建者"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), comment="创建时间"),
    )
    op.create_index("idx_er_project", "eval_runs", ["project_id"])
    op.create_index("idx_er_status", "eval_runs", ["status"])
    op.create_index("idx_er_agent", "eval_runs", ["agent_id"])
    op.create_index("idx_er_dataset", "eval_runs", ["dataset_id"])
    op.create_index("idx_er_created", "eval_runs", [sa.text("created_at DESC")])

    # =============================================================
    # 9. eval_results - 评测结果表（先于 traces 创建，因为 FK 到 traces）
    # 注意: trace_id FK 需要 traces 表存在，在 traces 表之后通过单独的 ALTER 添加
    # =============================================================
    op.create_table(
        "eval_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), comment="主键"),
        sa.Column("eval_run_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("eval_runs.id", ondelete="CASCADE"), nullable=False, comment="所属评测任务"),
        sa.Column("dataset_item_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("dataset_items.id", ondelete="RESTRICT"), nullable=False, comment="数据集条目"),
        sa.Column("sort_order", sa.Integer(), server_default=sa.text("0"), comment="执行顺序"),
        sa.Column("agent_input", sa.Text(), nullable=False, comment="发送给 Agent 的输入"),
        sa.Column("agent_output", sa.Text(), nullable=True, comment="Agent 的输出"),
        sa.Column("total_score", sa.Numeric(5, 2), nullable=True, comment="总分 (0-100)"),
        sa.Column("dimension_scores", postgresql.JSONB(), server_default=sa.text("'{}'"), comment="各维度得分"),
        sa.Column("judge_reason", sa.Text(), nullable=True, comment="LLM Judge 评分理由"),
        sa.Column("status", sa.String(20), nullable=False, comment="SUCCESS/FAILURE/ERROR/TIMEOUT"),
        sa.Column("trace_id", postgresql.UUID(as_uuid=True),  # FK added later
                  nullable=True, comment="关联的 Trace ID"),
        sa.Column("error_message", sa.Text(), nullable=True, comment="错误信息"),
        sa.Column("duration_ms", sa.Integer(), nullable=True, comment="执行耗时（毫秒）"),
        sa.Column("token_usage", postgresql.JSONB(), server_default=sa.text("'{}'"), comment="Token 用量"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), comment="创建时间"),
    )
    op.create_index("idx_eres_run", "eval_results", ["eval_run_id"])
    op.create_index("idx_eres_run_status", "eval_results", ["eval_run_id", "status"])

    # =============================================================
    # 10. traces - Trace/轨迹表（PRIMARY Key in PostgreSQL）
    # =============================================================
    op.create_table(
        "traces",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), comment="主键"),
        sa.Column("project_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, comment="所属项目"),
        sa.Column("agent_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("agents.id", ondelete="SET NULL"), nullable=True, comment="关联 Agent"),
        sa.Column("session_id", sa.String(255), nullable=True, comment="会话 ID"),
        sa.Column("user_id", sa.String(255), nullable=True, comment="终端用户 ID"),
        sa.Column("input", sa.Text(), nullable=True, comment="用户输入"),
        sa.Column("output", sa.Text(), nullable=True, comment="最终输出"),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=False, comment="开始时间"),
        sa.Column("end_time", sa.DateTime(timezone=True), nullable=True, comment="结束时间"),
        sa.Column("duration_ms", sa.Integer(), nullable=True, comment="总耗时（毫秒）"),
        sa.Column("total_tokens", sa.Integer(), server_default=sa.text("0"), comment="总 Token 用量"),
        sa.Column("total_cost", sa.Numeric(10, 6), server_default=sa.text("0"), comment="总成本（美元）"),
        sa.Column("status", sa.String(20), nullable=False, server_default="SUCCESS", comment="SUCCESS/ERROR"),
        sa.Column("spans", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'"), comment="Span 数组"),
        sa.Column("metadata", postgresql.JSONB(), server_default=sa.text("'{}'"), comment="扩展元数据"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), comment="入库时间"),
    )
    op.create_index("idx_traces_project", "traces", ["project_id"])
    op.create_index("idx_traces_agent", "traces", ["agent_id"])
    op.create_index("idx_traces_session", "traces", ["session_id"])
    op.create_index("idx_traces_user", "traces", ["user_id"])
    op.create_index("idx_traces_status", "traces", ["status"])
    op.create_index("idx_traces_start_time", "traces", [sa.text("start_time DESC")])
    # GIN 全文搜索索引
    op.create_index("idx_traces_input_gin", "traces",
                    [sa.text("to_tsvector('simple', input)")], postgresql_using="gin")
    op.create_index("idx_traces_output_gin", "traces",
                    [sa.text("to_tsvector('simple', output)")], postgresql_using="gin")

    # =============================================================
    # 为 eval_results 补充 FK 到 traces（traces 已创建）
    # =============================================================
    op.create_foreign_key(
        "fk_eres_trace",
        "eval_results", "traces",
        ["trace_id"], ["id"],
        ondelete="SET NULL",
    )
    op.create_index("idx_eres_trace", "eval_results", ["trace_id"])

    # =============================================================
    # 11. bad_cases - Bad Case 表
    # =============================================================
    op.create_table(
        "bad_cases",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), comment="主键"),
        sa.Column("project_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, comment="所属项目"),
        sa.Column("trace_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("traces.id", ondelete="RESTRICT"), nullable=False, comment="关联的 Trace"),
        sa.Column("tag", sa.String(50), nullable=False, comment="标签: hallucination/error/omission/timeout/other"),
        sa.Column("description", sa.Text(), nullable=True, comment="问题描述"),
        sa.Column("status", sa.String(20), nullable=False, server_default="open",
                  comment="open/in_progress/resolved/closed"),
        sa.Column("assignee_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True, comment="负责人"),
        sa.Column("resolution", sa.Text(), nullable=True, comment="解决方案"),
        sa.Column("marked_by", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, comment="标记人"),
        sa.Column("marked_at", sa.DateTime(timezone=True), server_default=sa.func.now(), comment="标记时间"),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True, comment="解决时间"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), comment="创建时间"),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), comment="更新时间"),
    )
    op.create_index("idx_bc_project", "bad_cases", ["project_id"])
    op.create_index("idx_bc_trace", "bad_cases", ["trace_id"])
    op.create_index("idx_bc_status", "bad_cases", ["status"])
    op.create_index("idx_bc_tag", "bad_cases", ["tag"])
    op.create_index("idx_bc_assignee", "bad_cases", ["assignee_id"])


def downgrade() -> None:
    """回滚：按依赖顺序逆序删除所有表"""
    op.drop_table("bad_cases")
    op.drop_table("eval_results")
    op.drop_table("eval_runs")
    op.drop_table("traces")
    op.drop_table("dataset_items")
    op.drop_table("datasets")
    op.drop_table("agents")
    op.drop_table("project_members")
    op.drop_table("projects")
    op.drop_table("api_keys")
    op.drop_table("users")