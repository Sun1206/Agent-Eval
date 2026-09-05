"""
数据集业务逻辑 — 数据集 CRUD + 条目管理 + JSON/CSV 导入导出
"""
import asyncio
import csv
import io
import json
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    NotFoundException,
    ValidationException,
)
from app.models.dataset import Dataset, DatasetItem
from app.models.user import User
from app.schemas.dataset import (
    BatchDeleteResponse,
    DatasetCreate,
    DatasetItemCreate,
    DatasetItemResponse,
    DatasetItemUpdate,
    DatasetResponse,
    DatasetUpdate,
    ImportResultResponse,
)
from app.services.project_service import _get_project_and_check_member

# 导入文件大小限制
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


class DatasetService:
    """数据集服务"""

    # ==================== 数据集 CRUD ====================

    @staticmethod
    async def create(
        db: AsyncSession, project_id: UUID, data: DatasetCreate, user: User
    ) -> DatasetResponse:
        """创建数据集"""
        await _get_project_and_check_member(db, project_id, user.id)

        dataset = Dataset(
            project_id=project_id,
            name=data.name,
            description=data.description,
            tags=data.tags,
            created_by=user.id,
        )
        db.add(dataset)
        await db.flush()
        await db.refresh(dataset)  # 刷新对象，获取数据库自动生成的字段
        return DatasetResponse.model_validate(dataset)

    @staticmethod
    async def list_by_project(
        db: AsyncSession, project_id: UUID, user: User
    ) -> list[DatasetResponse]:
        """获取项目下的数据集列表"""
        await _get_project_and_check_member(db, project_id, user.id)

        result = await db.execute(
            select(Dataset)
            .where(Dataset.project_id == project_id)
            .order_by(Dataset.created_at.desc())
        )
        datasets = result.scalars().all()
        return [DatasetResponse.model_validate(d) for d in datasets]

    @staticmethod
    async def get_by_id(
        db: AsyncSession, project_id: UUID, dataset_id: UUID, user: User
    ) -> DatasetResponse:
        """获取数据集详情"""
        await _get_project_and_check_member(db, project_id, user.id)

        dataset = await _get_dataset_or_404(db, dataset_id, project_id)
        return DatasetResponse.model_validate(dataset)

    @staticmethod
    async def update(
        db: AsyncSession, project_id: UUID, dataset_id: UUID,
        data: DatasetUpdate, user: User,
    ) -> DatasetResponse:
        """更新数据集"""
        await _get_project_and_check_member(db, project_id, user.id)

        dataset = await _get_dataset_or_404(db, dataset_id, project_id)

        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(dataset, field, value)

        db.add(dataset)
        await db.flush()
        await db.refresh(dataset)  # 刷新对象，获取数据库自动更新的字段
        return DatasetResponse.model_validate(dataset)

    @staticmethod
    async def delete(
        db: AsyncSession, project_id: UUID, dataset_id: UUID, user: User
    ) -> None:
        """删除数据集（级联删除条目）"""
        await _get_project_and_check_member(db, project_id, user.id)

        dataset = await _get_dataset_or_404(db, dataset_id, project_id)
        await db.delete(dataset)

    # ==================== 条目 CRUD ====================

    @staticmethod
    async def add_item(
        db: AsyncSession, project_id: UUID, dataset_id: UUID,
        data: DatasetItemCreate, user: User,
    ) -> DatasetItemResponse:
        """添加数据集条目"""
        await _get_project_and_check_member(db, project_id, user.id)

        dataset = await _get_dataset_or_404(db, dataset_id, project_id)

        # 自动计算 sort_order（追加到末尾）
        sort_order = data.sort_order
        if sort_order == 0:
            max_order = await db.scalar(
                select(func.max(DatasetItem.sort_order))
                .where(DatasetItem.dataset_id == dataset_id)
            )
            sort_order = (max_order or 0) + 1

        item = DatasetItem(
            dataset_id=dataset_id,
            sort_order=sort_order,
            input=data.input,
            expected_output=data.expected_output,
            context=data.context,
            tags=data.tags,
            metadata=data.metadata,
        )
        db.add(item)

        # 原子更新冗余计数（避免并发竞态：读-改-写 → SQL 原子 +1）
        await db.execute(
            update(Dataset)
            .where(Dataset.id == dataset_id)
            .values(item_count=Dataset.item_count + 1)
        )
        await db.flush()
        await db.refresh(item)  # 刷新对象，获取数据库自动生成的字段
        return DatasetItemResponse.model_validate(item)

    @staticmethod
    async def list_items(
        db: AsyncSession, project_id: UUID, dataset_id: UUID,
        user: User, page: int = 1, page_size: int = 20,
    ) -> tuple[list[DatasetItemResponse], int]:
        """分页查询数据集条目"""
        await _get_project_and_check_member(db, project_id, user.id)
        await _get_dataset_or_404(db, dataset_id, project_id)

        # 并行执行 count + data 查询，减少一次 DB 往返
        offset = (page - 1) * page_size
        count_stmt = select(func.count()).where(DatasetItem.dataset_id == dataset_id)
        data_stmt = (
            select(DatasetItem)
            .where(DatasetItem.dataset_id == dataset_id)
            .order_by(DatasetItem.sort_order.asc(), DatasetItem.created_at.asc())
            .limit(page_size)
            .offset(offset)
        )
        total_result, data_result = await asyncio.gather(
            db.scalar(count_stmt),
            db.execute(data_stmt),
        )
        total = total_result or 0
        items = data_result.scalars().all()
        return [DatasetItemResponse.model_validate(i) for i in items], total

    @staticmethod
    async def update_item(
        db: AsyncSession, project_id: UUID, dataset_id: UUID,
        item_id: UUID, data: DatasetItemUpdate, user: User,
    ) -> DatasetItemResponse:
        """更新数据集条目"""
        await _get_project_and_check_member(db, project_id, user.id)

        item = await _get_item_or_404(db, item_id, dataset_id)

        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(item, field, value)

        db.add(item)
        await db.flush()
        await db.refresh(item)  # 刷新对象，获取数据库自动更新的字段
        return DatasetItemResponse.model_validate(item)

    @staticmethod
    async def delete_item(
        db: AsyncSession, project_id: UUID, dataset_id: UUID,
        item_id: UUID, user: User,
    ) -> None:
        """删除数据集条目"""
        await _get_project_and_check_member(db, project_id, user.id)

        dataset = await _get_dataset_or_404(db, dataset_id, project_id)
        item = await _get_item_or_404(db, item_id, dataset_id)

        await db.delete(item)

        # 原子更新冗余计数（避免并发竞态，最小为 0）
        await db.execute(
            update(Dataset)
            .where(Dataset.id == dataset_id)
            .values(item_count=func.greatest(Dataset.item_count - 1, 0))
        )

    @staticmethod
    async def batch_delete_items(
        db: AsyncSession, project_id: UUID, dataset_id: UUID,
        item_ids: list[UUID], user: User,
    ) -> BatchDeleteResponse:
        """批量删除数据集条目"""
        await _get_project_and_check_member(db, project_id, user.id)
        await _get_dataset_or_404(db, dataset_id, project_id)

        # 查询属于该数据集的指定条目
        result = await db.execute(
            select(DatasetItem).where(
                DatasetItem.dataset_id == dataset_id,
                DatasetItem.id.in_(item_ids),
            )
        )
        items = result.scalars().all()
        deleted = len(items)

        for item in items:
            await db.delete(item)

        # 原子更新冗余计数
        if deleted > 0:
            await db.execute(
                update(Dataset)
                .where(Dataset.id == dataset_id)
                .values(item_count=func.greatest(Dataset.item_count - deleted, 0))
            )

        return BatchDeleteResponse(deleted=deleted)

    # ==================== 导入 ====================

    @staticmethod
    async def import_file(
        db: AsyncSession, project_id: UUID, dataset_id: UUID,
        user: User, content: bytes, filename: str,
    ) -> ImportResultResponse:
        """导入 JSON/CSV 文件"""
        await _get_project_and_check_member(db, project_id, user.id)

        dataset = await _get_dataset_or_404(db, dataset_id, project_id)

        # 文件大小校验
        if len(content) > MAX_FILE_SIZE:
            raise ValidationException(f"文件大小超过限制 ({MAX_FILE_SIZE // 1024 // 1024}MB)")

        # 解析文件
        if filename.lower().endswith(".json"):
            rows, errors = _parse_json(content)
        elif filename.lower().endswith(".csv"):
            rows, errors = _parse_csv(content)
        else:
            raise ValidationException("仅支持 JSON 和 CSV 格式")

        # 获取当前最大 sort_order
        max_order = await db.scalar(
            select(func.max(DatasetItem.sort_order))
            .where(DatasetItem.dataset_id == dataset_id)
        )
        next_order = (max_order or 0) + 1

        # 批量写入（使用 add_all 一次性插入，避免逐条 INSERT）
        imported = 0
        items_to_add = []
        for row in rows:
            if not row.get("input", "").strip():
                continue
            item = DatasetItem(
                dataset_id=dataset_id,
                sort_order=next_order,
                input=row.get("input", ""),
                expected_output=row.get("expected_output"),
                context=row.get("context"),
                tags=row.get("tags", []),
                metadata=row.get("metadata", {}),
            )
            items_to_add.append(item)
            next_order += 1
            imported += 1

        if items_to_add:
            db.add_all(items_to_add)

        # 原子更新冗余计数
        if imported > 0:
            await db.execute(
                update(Dataset)
                .where(Dataset.id == dataset_id)
                .values(item_count=Dataset.item_count + imported)
            )

        return ImportResultResponse(
            total=len(rows) + len(errors),
            imported=imported,
            skipped=len(errors),
            errors=errors,
        )

    # ==================== 导出 ====================

    @staticmethod
    async def export_data(
        db: AsyncSession, project_id: UUID, dataset_id: UUID,
        user: User, fmt: str,
    ) -> tuple[bytes, str, str]:
        """
        导出数据集条目

        Returns:
            (content: bytes, media_type: str, filename: str)
        """
        await _get_project_and_check_member(db, project_id, user.id)

        dataset = await _get_dataset_or_404(db, dataset_id, project_id)

        # 查询所有条目
        result = await db.execute(
            select(DatasetItem)
            .where(DatasetItem.dataset_id == dataset_id)
            .order_by(DatasetItem.sort_order.asc())
        )
        items = result.scalars().all()

        if fmt == "csv":
            content, media_type = _to_csv(items)
            filename = f"{dataset.name}.csv"
        else:
            content, media_type = _to_json(items)
            filename = f"{dataset.name}.json"

        return content, media_type, filename


# ==================== 内部辅助函数 ====================

async def _get_dataset_or_404(
    db: AsyncSession, dataset_id: UUID, project_id: UUID
) -> Dataset:
    """查询数据集，加项目隔离"""
    result = await db.execute(
        select(Dataset).where(
            Dataset.id == dataset_id,
            Dataset.project_id == project_id,
        )
    )
    dataset = result.scalar_one_or_none()
    if dataset is None:
        raise NotFoundException("数据集")
    return dataset


async def _get_item_or_404(
    db: AsyncSession, item_id: UUID, dataset_id: UUID
) -> DatasetItem:
    """查询条目，加数据集隔离"""
    result = await db.execute(
        select(DatasetItem).where(
            DatasetItem.id == item_id,
            DatasetItem.dataset_id == dataset_id,
        )
    )
    item = result.scalar_one_or_none()
    if item is None:
        raise NotFoundException("数据集条目")
    return item


# ==================== 文件解析 ====================

def _parse_json(content: bytes) -> tuple[list[dict], list[str]]:
    """解析 JSON 文件内容"""
    errors: list[str] = []
    try:
        text = content.decode("utf-8")
        data = json.loads(text)
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        raise ValidationException(f"JSON 格式错误: {e}")

    if not isinstance(data, list):
        raise ValidationException("JSON 文件应为数组格式")

    rows = []
    for i, item in enumerate(data):
        if not isinstance(item, dict):
            errors.append(f"第 {i + 1} 行: 非对象格式，已跳过")
            continue
        if not item.get("input", "").strip():
            errors.append(f"第 {i + 1} 行: input 为空，已跳过")
            continue
        # tags 可能是逗号分隔字符串，转为列表
        tags = item.get("tags", [])
        if isinstance(tags, str):
            tags = [t.strip() for t in tags.split(",") if t.strip()]
        item["tags"] = tags
        rows.append(item)

    return rows, errors


def _parse_csv(content: bytes) -> tuple[list[dict], list[str]]:
    """解析 CSV 文件内容（兼容 UTF-8 / UTF-8-BOM / GBK）"""
    errors: list[str] = []

    # 尝试解码
    text = _decode_csv_content(content)

    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        raise ValidationException("CSV 文件为空或无表头")

    # 规范化表头（忽略 BOM 和大小写空白）
    fieldnames = [f.strip().lower() for f in reader.fieldnames]

    # 预构建字段名映射：原始列名 → 标准化列名，避免循环中重复 list() + index()
    field_map = {f.strip().lower(): f.strip() for f in reader.fieldnames}

    required = {"input"}
    if not required.issubset(set(fieldnames)):
        raise ValidationException("CSV 文件缺少 input 列")

    rows = []
    for i, row in enumerate(reader):
        # 映射到标准字段名（使用预构建映射，O(1) 查找）
        mapped = {}
        for std_name in fieldnames:
            original_name = field_map.get(std_name, std_name)
            raw_value = row.get(original_name, "")
            if std_name == "input":
                mapped["input"] = raw_value
            elif std_name == "expected_output":
                mapped["expected_output"] = raw_value
            elif std_name == "context":
                mapped["context"] = raw_value
            elif std_name == "tags":
                mapped["tags"] = [t.strip() for t in raw_value.split(",") if t.strip()]
            elif std_name == "metadata":
                try:
                    mapped["metadata"] = json.loads(raw_value) if raw_value else {}
                except json.JSONDecodeError:
                    mapped["metadata"] = {}

        if not mapped.get("input", "").strip():
            errors.append(f"第 {i + 2} 行: input 为空，已跳过")
            continue
        rows.append(mapped)

    return rows, errors


def _decode_csv_content(content: bytes) -> str:
    """解码 CSV 内容，兼容 UTF-8 / UTF-8-BOM / GBK"""
    # 优先尝试 UTF-8（含 BOM）
    if content[:3] == b"\xef\xbb\xbf":
        return content.decode("utf-8-sig")
    try:
        return content.decode("utf-8")
    except UnicodeDecodeError:
        pass
    # 降级尝试 GBK（Windows 中文环境常见）
    try:
        return content.decode("gbk")
    except UnicodeDecodeError:
        raise ValidationException("无法识别的文件编码，请使用 UTF-8 或 GBK 编码")


def _to_json(items: list[DatasetItem]) -> tuple[bytes, str]:
    """将条目列表转为 JSON 字节"""
    data = [
        {
            "input": item.input,
            "expected_output": item.expected_output,
            "context": item.context,
            "tags": item.tags,
            "metadata": item.item_metadata,
        }
        for item in items
    ]
    content = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
    return content, "application/json; charset=utf-8"


def _to_csv(items: list[DatasetItem]) -> tuple[bytes, str]:
    """将条目列表转为 CSV 字节（UTF-8 with BOM 兼容 Excel）"""
    output = io.StringIO()

    # BOM
    output.write("\ufeff")

    writer = csv.DictWriter(
        output,
        fieldnames=["input", "expected_output", "context", "tags", "metadata"],
    )
    writer.writeheader()

    for item in items:
        writer.writerow({
            "input": item.input or "",
            "expected_output": item.expected_output or "",
            "context": item.context or "",
            "tags": ",".join(item.tags) if item.tags else "",
            "metadata": json.dumps(item.item_metadata, ensure_ascii=False) if item.item_metadata else "{}",
        })

    content = output.getvalue().encode("utf-8")
    return content, "text/csv; charset=utf-8"