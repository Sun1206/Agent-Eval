"""
ClickHouse 连接管理 — Trace 数据写入与查询

架构:
  ClickHouseClient  — 单例客户端，惰性初始化
  get_clickhouse() — 模块级便捷函数
"""
import logging
from typing import Any, Optional

import clickhouse_connect

from app.config import get_settings

logger = logging.getLogger(__name__)

# 模块级单例
_client: Optional["ClickHouseClient"] = None


class ClickHouseClient:
    """ClickHouse 客户端封装（clickhouse-connect 纯 Python 实现）"""

    def __init__(self):
        settings = get_settings()
        logger.info(
            f"初始化 ClickHouse 连接: {settings.clickhouse_host}:{settings.clickhouse_port}/{settings.clickhouse_db}"
        )
        self._ch = clickhouse_connect.get_client(
            host=settings.clickhouse_host,
            port=settings.clickhouse_port,
            username=settings.clickhouse_user,
            password=settings.clickhouse_password,
            database=settings.clickhouse_db,
        )
        # 自动初始化表结构
        self._ensure_table()

    # ==================== 写入方法 ====================

    def insert_trace(self, data: dict[str, Any]) -> None:
        """
        写入单条 Trace

        Args:
            data: Trace 数据字典，字段需与 traces 表列名一致。
                  示例: {"trace_id": "...", "project_id": "...", "input": "..."}
        """
        columns = list(data.keys())
        values = [list(data.values())]
        self._ch.insert(
            table="traces",
            data=values,
            column_names=columns,
        )
        logger.debug(f"写入单条 Trace: trace_id={data.get('trace_id')}")

    def insert_traces_batch(self, data_list: list[dict[str, Any]]) -> None:
        """
        批量写入 Trace

        Args:
            data_list: Trace 数据字典列表，所有条目字段需一致
        """
        if not data_list:
            return

        columns = list(data_list[0].keys())
        values = [list(d.values()) for d in data_list]
        self._ch.insert(
            table="traces",
            data=values,
            column_names=columns,
        )
        logger.debug(f"批量写入 Trace: {len(data_list)} 条")

    # ==================== 查询方法 ====================

    def get_trace_by_id(self, trace_id: str) -> Optional[dict[str, Any]]:
        """
        按 trace_id 查询单条 Trace

        Args:
            trace_id: Trace UUID 字符串

        Returns:
            查询到的 Trace dict，未找到返回 None
        """
        result = self._ch.query(
            "SELECT * FROM traces WHERE trace_id = {trace_id:String}",
            parameters={"trace_id": trace_id},
        )
        rows = list(result.named_results())
        return rows[0] if rows else None

    def query_traces(
        self,
        filters: Optional[dict[str, Any]] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict[str, Any]:
        """
        分页查询 Trace 列表，支持多条件筛选

        Args:
            filters: 可选筛选条件，支持的 key:
                - project_id: 项目 UUID
                - agent_id:   Agent UUID
                - session_id: 会话 ID
                - user_id:    终端用户 ID
                - status:     状态（SUCCESS/ERROR）
                - start_time_from: 开始时间起始 (datetime / str)
                - start_time_to:   开始时间截止 (datetime / str)
            page: 页码（从 1 开始）
            page_size: 每页条数

        Returns:
            {"items": [...], "total": N, "page": N, "page_size": N}
        """
        filters = filters or {}

        where_parts = []
        params: dict[str, Any] = {}

        for field in ("project_id", "agent_id", "session_id", "user_id", "status"):
            value = filters.get(field)
            if value:
                where_parts.append(f"{field} = {{{field}:String}}")
                params[field] = value

        if "start_time_from" in filters:
            where_parts.append("start_time >= {start_time_from:DateTime}")
            params["start_time_from"] = filters["start_time_from"]

        if "start_time_to" in filters:
            where_parts.append("start_time <= {start_time_to:DateTime}")
            params["start_time_to"] = filters["start_time_to"]

        where_clause = " AND ".join(where_parts) if where_parts else "1=1"

        # 查询总数
        count_sql = f"SELECT count() AS cnt FROM traces WHERE {where_clause}"
        count_result = self._ch.query(count_sql, parameters=params)
        total = count_result.first_item["cnt"]

        # 分页查询
        offset = (page - 1) * page_size
        data_sql = (
            f"SELECT * FROM traces WHERE {where_clause} "
            f"ORDER BY start_time DESC "
            f"LIMIT {page_size} OFFSET {offset}"
        )
        data_result = self._ch.query(data_sql, parameters=params)
        items = list(data_result.named_results())

        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    def search_traces(
        self, keyword: str, limit: int = 50
    ) -> list[dict[str, Any]]:
        """
        关键词全文搜索 Trace（搜索 input 和 output 字段）

        利用 ClickHouse 的 tokenbf_v1 索引 + LIKE 实现。
        若未建 tokenbf_v1 索引，降级为纯 LIKE 查询。

        Args:
            keyword: 搜索关键词
            limit:   返回条数上限

        Returns:
            匹配的 Trace 列表
        """
        sql = (
            "SELECT * FROM traces "
            "WHERE input  LIKE {kw:String} "
            "   OR output LIKE {kw:String} "
            "ORDER BY start_time DESC "
            f"LIMIT {limit}"
        )
        result = self._ch.query(
            sql,
            parameters={"kw": f"%{keyword}%"},
        )
        return list(result.named_results())

    # ==================== 生命周期 ====================

    def _ensure_table(self):
        """自动初始化 traces 表（CREATE TABLE IF NOT EXISTS，幂等操作）"""
        try:
            self._ch.command("""
                CREATE TABLE IF NOT EXISTS traces (
                    id              String DEFAULT '',
                    trace_id        String,
                    project_id      String,
                    agent_id        String DEFAULT '',
                    session_id      String DEFAULT '',
                    user_id         String DEFAULT '',
                    input           String DEFAULT '',
                    output          String DEFAULT '',
                    start_time      DateTime64(3),
                    end_time        DateTime64(3) DEFAULT toDateTime64('1970-01-01 00:00:00', 3),
                    duration_ms     Int64 DEFAULT 0,
                    total_tokens    Int64 DEFAULT 0,
                    total_cost      Decimal64(6) DEFAULT 0,
                    status          LowCardinality(String) DEFAULT 'success',
                    spans           String DEFAULT '[]',
                    tags            String DEFAULT '[]',
                    metadata        String DEFAULT '{}',
                    created_at      DateTime64(3) DEFAULT now64(3)
                )
                ENGINE = ReplacingMergeTree()
                PARTITION BY toYYYYMM(start_time)
                ORDER BY (project_id, start_time, trace_id)
                SETTINGS index_granularity = 8192
            """)
            logger.info("ClickHouse traces 表初始化完成")
        except Exception as e:
            logger.warning(f"ClickHouse traces 表初始化失败: {e}")

    def close(self):
        """关闭连接"""
        if self._ch:
            self._ch.close()
            logger.info("ClickHouse 连接已关闭")

    # ==================== 辅助方法 ====================

    def is_alive(self) -> bool:
        """检查连接是否可用"""
        try:
            self._ch.query("SELECT 1")
            return True
        except Exception:
            return False


def get_clickhouse() -> ClickHouseClient:
    """获取 ClickHouse 客户端单例（惰性初始化）"""
    global _client
    if _client is None:
        _client = ClickHouseClient()
    return _client


def close_clickhouse():
    """关闭 ClickHouse 客户端"""
    global _client
    if _client is not None:
        _client.close()
        _client = None