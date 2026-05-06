from datetime import datetime, timezone
from typing import Optional, List

from fastapi import APIRouter, Depends, Query, UploadFile, File, Form, status

from app.dependencies.auth import admin_required, get_current_user
from app.models.user import User
from app.services.category_service import CategoryService
from app.schemas.category import (
    CategoryCreate,
    CategoryUpdate,
    CategoryStatusUpdate,
    CategoryResponse,
)
from app.schemas.service import ServiceResponse
from app.schemas.common import (
    StatusEnum,
    APIResponse,
    PaginatedResponse,
    DeleteResponse,
)

router = APIRouter()


# ── Public — read ──────────────────────────────────────────────────────────────

@router.get(
    "",
    response_model=PaginatedResponse[CategoryResponse],
    status_code=status.HTTP_200_OK,
    summary="List categories — admin sees all, others see active only",
)
async def get_categories(
    page:         int           = Query(1,   ge=1),
    limit:        int           = Query(20,  ge=1, le=100),
    search:       Optional[str] = Query(None, max_length=100),
    current_user: Optional[User] = Depends(get_current_user),
):
    result = await CategoryService.get_all(
        page=page,
        limit=limit,
        current_user=current_user,
        search=search,
    )
    result["data"] = [
        CategoryResponse.model_validate(doc, from_attributes=True)
        for doc in result["data"]
    ]
    return result


@router.get(
    "/{category_id}",
    response_model=APIResponse[CategoryResponse],
    status_code=status.HTTP_200_OK,
    summary="Get a single category by ID",
)
async def get_category(category_id: str):
    category = await CategoryService.get_by_id(category_id)
    return {
        "success": True,
        "message": "Category fetched successfully",
        "data":    CategoryResponse.model_validate(category, from_attributes=True),
    }


@router.get(
    "/{category_id}/subcategories",
    response_model=PaginatedResponse[CategoryResponse],
    status_code=status.HTTP_200_OK,
    summary="Get active subcategories of a category",
)
async def get_subcategories(category_id: str):
    items = await CategoryService.get_subcategories(category_id)
    return {
        "success": True,
        "message": "Subcategories fetched successfully",
        "total":   len(items),
        "data":    [
            CategoryResponse.model_validate(i, from_attributes=True)
            for i in items
        ],
    }


@router.get(
    "/{category_id}/services",
    response_model=PaginatedResponse[ServiceResponse],
    status_code=status.HTTP_200_OK,
    summary="Get approved active services under a category",
)
async def get_services_by_category(
    category_id: str,
    page:  int = Query(1,  ge=1),
    limit: int = Query(20, ge=1, le=100),
):
    result = await CategoryService.get_services_by_category(
        category_id=category_id,
        page=page,
        limit=limit,
    )
    result["data"] = [
        ServiceResponse.model_validate(doc, from_attributes=True)
        for doc in result["data"]
    ]
    return result


# ── Admin — write ──────────────────────────────────────────────────────────────

@router.post(
    "",
    response_model=APIResponse[CategoryResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Admin — create a new category",
)
async def create_category(
    name:          str           = Form(..., max_length=100),
    description:   Optional[str] = Form(None, max_length=500),
    parent_id:     Optional[str] = Form(None),
    icon:          Optional[UploadFile] = File(None),
    current_admin: User          = Depends(admin_required),
):
    data     = CategoryCreate(name=name, description=description, parent_id=parent_id)
    category = await CategoryService.create(
        data=data,
        icon=icon,
        user_id=str(current_admin.id),
    )
    return {
        "success": True,
        "message": "Category created successfully",
        "data":    CategoryResponse.model_validate(category, from_attributes=True),
    }


@router.put(
    "/{category_id}",
    response_model=APIResponse[CategoryResponse],
    status_code=status.HTTP_200_OK,
    summary="Admin — update a category (partial)",
)
async def update_category(
    category_id:   str,
    name:          Optional[str] = Form(None, max_length=100),
    description:   Optional[str] = Form(None, max_length=500),
    parent_id:     Optional[str] = Form(None),
    status_field:  Optional[str] = Form(None, alias="status"),
    icon:          Optional[UploadFile] = File(None),
    current_admin: User          = Depends(admin_required),
):
    """
    Empty body rejected by CategoryUpdate.at_least_one_field validator (422).
    """
    data     = CategoryUpdate(
        name=name,
        description=description,
        parent_id=parent_id,
        status=StatusEnum(status_field) if status_field else None,
    )
    category = await CategoryService.update(
        category_id=category_id,
        data=data,
        icon=icon,
        user_id=str(current_admin.id),
    )
    return {
        "success": True,
        "message": "Category updated successfully",
        "data":    CategoryResponse.model_validate(category, from_attributes=True),
    }


@router.patch(
    "/{category_id}/status",
    response_model=APIResponse[CategoryResponse],
    status_code=status.HTTP_200_OK,
    summary="Admin — activate or deactivate a category",
)
async def toggle_category_status(
    category_id:   str,
    data:          CategoryStatusUpdate,
    current_admin: User = Depends(admin_required),
):
    category, message = await CategoryService.toggle_status(
        category_id=category_id,
        status=data.status,
        user_id=str(current_admin.id),
    )
    return {
        "success": True,
        "message": message,   # "Category activated/deactivated successfully"
        "data":    CategoryResponse.model_validate(category, from_attributes=True),
    }


@router.delete(
    "/{category_id}",
    response_model=DeleteResponse,
    status_code=status.HTTP_200_OK,
    summary="Admin — soft-delete a category (blocked if subcategories exist)",
)
async def delete_category(
    category_id:   str,
    current_admin: User = Depends(admin_required),
):
    """
    Response includes:
      id         → frontend removes this ID from its cache / list
      deleted_at → powers "deleted X ago" UI or an undo window
      deleted_by → audit trail
    """
    category = await CategoryService.delete(
        category_id=category_id,
        user_id=str(current_admin.id),
    )
    return {
        "success":    True,
        "message":    "Category deleted successfully",
        "id":         category_id,
        "deleted_at": category.deleted_at or datetime.now(timezone.utc),
        "deleted_by": str(current_admin.id),
    }