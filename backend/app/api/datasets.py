"""
数据集路由 — 数据集 CRUD + 条目管理 + 导入导出
"""
import io
from uuid import UUID

from fastapi import APIRouter, Depends, File, Query, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.exceptions import ValidationException
from app.models.user import User
from app.schemas.common import BaseResponse, PaginationData
from app.schemas.dataset import (
    BatchDeleteRequest,
    BatchDeleteResponse,
    DatasetCreate,
    DatasetItemCreate,
    DatasetItemResponse,
    DatasetItemUpdate,
    DatasetResponse,
    DatasetUpdate,
    ImportResultResponse,
)
from app.services.dataset_service import DatasetService

router = APIRouter(prefix="/projects/{project_id}/datasets", tags=["数据集管理"])


# ==================== 数据集 CRUD ====================

@router.post("", response_model=BaseResponse[DatasetResponse])
async def create_dataset(
    project_id: str,
    data: DatasetCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """创建数据集"""
    result = await DatasetService.create(db, UUID(project_id), data, current_user)
    return BaseResponse.ok(result, "数据集创建成功")


@router.get("", response_model=BaseResponse[list[DatasetResponse]])
async def list_datasets(
    project_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取数据集列表"""
    result = await DatasetService.list_by_project(db, UUID(project_id), current_user)
    return BaseResponse.ok(result)


@router.get("/{dataset_id}", response_model=BaseResponse[DatasetResponse])
async def get_dataset(
    project_id: str,
    dataset_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取数据集详情"""
    result = await DatasetService.get_by_id(
        db, UUID(project_id), UUID(dataset_id), current_user
    )
    return BaseResponse.ok(result)


@router.put("/{dataset_id}", response_model=BaseResponse[DatasetResponse])
async def update_dataset(
    project_id: str,
    dataset_id: str,
    data: DatasetUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """更新数据集"""
    result = await DatasetService.update(
        db, UUID(project_id), UUID(dataset_id), data, current_user
    )
    return BaseResponse.ok(result, "数据集更新成功")


@router.delete("/{dataset_id}", response_model=BaseResponse[None])
async def delete_dataset(
    project_id: str,
    dataset_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除数据集"""
    await DatasetService.delete(db, UUID(project_id), UUID(dataset_id), current_user)
    return BaseResponse.ok(None, "数据集已删除")


# ==================== 条目 CRUD ====================

@router.post(
    "/{dataset_id}/items",
    response_model=BaseResponse[DatasetItemResponse],
)
async def add_item(
    project_id: str,
    dataset_id: str,
    data: DatasetItemCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """添加数据集条目"""
    result = await DatasetService.add_item(
        db, UUID(project_id), UUID(dataset_id), data, current_user
    )
    return BaseResponse.ok(result, "条目添加成功")


@router.get("/{dataset_id}/items", response_model=BaseResponse[PaginationData])
async def list_items(
    project_id: str,
    dataset_id: str,
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页条数"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """分页查询数据集条目"""
    items, total = await DatasetService.list_items(
        db, UUID(project_id), UUID(dataset_id), current_user, page, page_size
    )
    return BaseResponse.paginated(items, total, page, page_size)


@router.put(
    "/{dataset_id}/items/{item_id}",
    response_model=BaseResponse[DatasetItemResponse],
)
async def update_item(
    project_id: str,
    dataset_id: str,
    item_id: str,
    data: DatasetItemUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """更新数据集条目"""
    result = await DatasetService.update_item(
        db, UUID(project_id), UUID(dataset_id), UUID(item_id), data, current_user
    )
    return BaseResponse.ok(result, "条目更新成功")


@router.delete("/{dataset_id}/items/{item_id}", response_model=BaseResponse[None])
async def delete_item(
    project_id: str,
    dataset_id: str,
    item_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除数据集条目"""
    await DatasetService.delete_item(
        db, UUID(project_id), UUID(dataset_id), UUID(item_id), current_user
    )
    return BaseResponse.ok(None, "条目已删除")


@router.post(
    "/{dataset_id}/items/batch-delete",
    response_model=BaseResponse[BatchDeleteResponse],
)
async def batch_delete_items(
    project_id: str,
    dataset_id: str,
    data: BatchDeleteRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """批量删除数据集条目"""
    result = await DatasetService.batch_delete_items(
        db, UUID(project_id), UUID(dataset_id), data.item_ids, current_user
    )
    return BaseResponse.ok(result, f"已删除 {result.deleted} 条条目")


# ==================== 导入导出 ====================

@router.post("/{dataset_id}/import", response_model=BaseResponse[ImportResultResponse])
async def import_dataset(
    project_id: str,
    dataset_id: str,
    file: UploadFile = File(..., description="JSON 或 CSV 文件"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """导入数据集（JSON/CSV）"""
    # 文件类型校验
    filename = file.filename or ""
    if not filename.lower().endswith((".json", ".csv")):
        raise ValidationException("仅支持 JSON 和 CSV 文件")

    content = await file.read()
    result = await DatasetService.import_file(
        db, UUID(project_id), UUID(dataset_id), current_user, content, filename
    )
    return BaseResponse.ok(result, "导入完成")


@router.get("/{dataset_id}/export")
async def export_dataset(
    project_id: str,
    dataset_id: str,
    fmt: str = Query("json", pattern="^(json|csv)$", description="导出格式: json 或 csv"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """导出数据集"""
    content, media_type, filename = await DatasetService.export_data(
        db, UUID(project_id), UUID(dataset_id), current_user, fmt
    )
    return StreamingResponse(
        io.BytesIO(content),
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )