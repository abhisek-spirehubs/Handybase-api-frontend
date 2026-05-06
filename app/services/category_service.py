import re
from datetime import datetime, timezone
from typing import List, Optional, Dict

from beanie import PydanticObjectId
from bson import ObjectId

from app.models.category import Category
from app.models.user import User, UserRole
from app.schemas.category import CategoryCreate, CategoryUpdate
from app.schemas.common import StatusEnum
from app.utils.logger import app_logger
from app.utils.file_upload import save_category_icon, delete_file
from app.core.exceptions import (
    NotFoundException,
    ValidationException,
    AppException,
)

# Status-specific messages — avoids the "activedd" f-string bug
_TOGGLE_MESSAGES = {
    StatusEnum.ACTIVE:   "Category activated successfully",
    StatusEnum.INACTIVE: "Category deactivated successfully",
}


class CategoryService:

    @staticmethod
    def generate_slug(name: str) -> str:
        return re.sub(r"[^a-zA-Z0-9]+", "-", name.lower()).strip("-")

    # ─────────────────────────────────────────
    # Create
    # ─────────────────────────────────────────

    @staticmethod
    async def create(
        data:    CategoryCreate,
        icon=None,
        user_id: Optional[str] = None,
    ) -> Category:
        """
        Returns the created Category document.
        Router wraps it in APIResponse[CategoryResponse].
        """
        try:
            slug = CategoryService.generate_slug(data.name)

            existing = await Category.find_one({"name": data.name, "is_deleted": False})
            if existing:
                raise ValidationException("Category already exists")

            if data.parent_id:
                if not ObjectId.is_valid(data.parent_id):
                    raise ValidationException("Invalid parent_id")
                parent = await Category.get(data.parent_id)
                if not parent or parent.is_deleted:
                    raise NotFoundException("Parent category not found")

            icon_url = None
            if icon:
                icon_url = await save_category_icon(icon)

            category = Category(
                name=data.name,
                slug=slug,
                icon=icon_url,
                description=data.description,
                parent_id=data.parent_id,
                created_by=user_id,
                status=StatusEnum.ACTIVE,
            )
            await category.insert()
            return category

        except AppException:
            raise
        except Exception:
            app_logger.exception("Error creating category")
            raise AppException("Failed to create category", status_code=500)

    # ─────────────────────────────────────────
    # Read — list
    # ─────────────────────────────────────────

    @staticmethod
    async def get_all(
        page:         int             = 1,
        limit:        int             = 20,
        current_user: Optional[User]  = None,
        search:       Optional[str]   = None,
    ) -> Dict:
        """
        Returns paginated dict ready to unpack into PaginatedResponse.
        Admin sees all statuses; everyone else sees active only.
        """
        try:
            skip  = (page - 1) * limit
            query: dict = {"is_deleted": False}

            is_admin = (
                current_user is not None
                and current_user.user_type == UserRole.ADMIN
            )
            if not is_admin:
                query["status"] = StatusEnum.ACTIVE

            if search:
                escaped = re.escape(search.strip())
                query["name"] = {"$regex": escaped, "$options": "i"}

            total = await Category.find(query).count()
            data  = await Category.find(query).sort("-created_at").skip(skip).limit(limit).to_list()

            for doc in data:
                if doc.status is None:
                    doc.status = StatusEnum.ACTIVE

            return {
                "success": True,
                "message": "Categories fetched successfully",
                "total":   total,
                "data":    data,
            }

        except AppException:
            raise
        except Exception:
            app_logger.exception("Error fetching categories")
            raise AppException("Failed to fetch categories", status_code=500)

    # ─────────────────────────────────────────
    # Read — single
    # ─────────────────────────────────────────

    @staticmethod
    async def get_by_id(category_id: str) -> Category:
        """
        Returns the Category document directly — NOT a dict envelope.
        Router is responsible for wrapping it in APIResponse[CategoryResponse].

        Also backfills null status for legacy documents on read.
        """
        try:
            if not ObjectId.is_valid(category_id):
                raise ValidationException("Invalid category id")

            # Backfill null status for legacy docs before Beanie parses the doc
            collection = Category.get_pymongo_collection()
            raw = await collection.find_one({"_id": ObjectId(category_id)})
            if not raw:
                raise NotFoundException("Category not found")

            if raw.get("status") is None:
                await collection.update_one(
                    {"_id": ObjectId(category_id)},
                    {"$set": {"status": StatusEnum.ACTIVE.value}},
                )
                app_logger.info("Fixed null status for category %s", category_id)

            category = await Category.get(category_id)
            if not category or category.is_deleted:
                raise NotFoundException("Category not found")

            return category

        except AppException:
            raise
        except Exception:
            app_logger.exception("Error fetching category id=%s", category_id)
            raise AppException("Failed to fetch category", status_code=500)

    # ─────────────────────────────────────────
    # Read — subcategories
    # ─────────────────────────────────────────

    @staticmethod
    async def get_subcategories(category_id: str) -> List[Category]:
        """
        Returns a flat list of active subcategories.
        Router wraps it in PaginatedResponse[CategoryResponse].
        """
        try:
            # Verify parent exists — raises NotFoundException if not
            await CategoryService.get_by_id(category_id)

            return await Category.find({
                "parent_id": category_id,
                "is_deleted": False,
                "status":    StatusEnum.ACTIVE,
            }).sort("-created_at").to_list()

        except AppException:
            raise
        except Exception:
            app_logger.exception("Error fetching subcategories for id=%s", category_id)
            raise AppException("Failed to fetch subcategories", status_code=500)

    # ─────────────────────────────────────────
    # Read — services under category
    # ─────────────────────────────────────────

    @staticmethod
    async def get_services_by_category(
        category_id: str,
        page:        int = 1,
        limit:       int = 20,
    ) -> Dict:
        """
        Returns paginated dict ready for PaginatedResponse[ServiceResponse].
        page/limit are forwarded from the router — no more hard-coded limit=1000.
        """
        try:
            await CategoryService.get_by_id(category_id)

            from app.services.service_service import ServiceService
            return await ServiceService.get_services(
                current_user=None,
                page=page,
                limit=limit,
                category_id=category_id,
            )

        except AppException:
            raise
        except Exception:
            app_logger.exception("Error fetching services for category id=%s", category_id)
            raise AppException("Failed to fetch services for category", status_code=500)

    # ─────────────────────────────────────────
    # Update
    # ─────────────────────────────────────────

    @staticmethod
    async def update(
        category_id: str,
        data:        CategoryUpdate,
        icon=None,
        user_id:     Optional[str] = None,
    ) -> Category:
        """
        Returns the updated Category document.
        Router wraps it in APIResponse[CategoryResponse].
        """
        try:
            if not ObjectId.is_valid(category_id):
                raise ValidationException("Invalid category id")

            # get_by_id now returns Category directly — no dict unwrap needed
            category    = await CategoryService.get_by_id(category_id)
            update_data = data.model_dump(exclude_unset=True)

            if "name" in update_data:
                new_name = update_data["name"]
                if not new_name:
                    raise ValidationException("Name cannot be empty")
                existing = await Category.find_one({
                    "name":       new_name,
                    "_id":        {"$ne": category.id},
                    "is_deleted": False,
                })
                if existing:
                    raise ValidationException("Category name already exists")
                category.name = new_name
                category.slug = CategoryService.generate_slug(new_name)

            if "parent_id" in update_data:
                parent_id = update_data["parent_id"]
                if parent_id:
                    if not ObjectId.is_valid(parent_id):
                        raise ValidationException("Invalid parent_id")
                    if str(parent_id) == str(category.id):
                        raise ValidationException("Category cannot be its own parent")
                    parent = await Category.get(parent_id)
                    if not parent or parent.is_deleted:
                        raise NotFoundException("Parent category not found")
                category.parent_id = parent_id

            if "description" in update_data:
                category.description = update_data["description"]

            if "status" in update_data and update_data["status"] is not None:
                category.status = update_data["status"]

            if icon:
                if category.icon:
                    delete_file(category.icon)
                category.icon = await save_category_icon(icon)

            category.updated_by = user_id
            await category.save()
            return category

        except AppException:
            raise
        except Exception:
            app_logger.exception("Error updating category id=%s", category_id)
            raise AppException("Failed to update category", status_code=500)

    # ─────────────────────────────────────────
    # Toggle status
    # ─────────────────────────────────────────

    @staticmethod
    async def toggle_status(
        category_id: str,
        status:      StatusEnum,
        user_id:     Optional[str] = None,
    ) -> tuple[Category, str]:
        """
        Returns (updated Category, human-readable message).
        Router uses the message for the toast — no string building in router.
        """
        try:
            category        = await CategoryService.get_by_id(category_id)
            category.status = status
            category.updated_by = user_id
            await category.save()

            message = _TOGGLE_MESSAGES.get(status, "Category status updated")
            return category, message

        except AppException:
            raise
        except Exception:
            app_logger.exception("Error toggling status for category id=%s", category_id)
            raise AppException("Failed to update category status", status_code=500)

    # ─────────────────────────────────────────
    # Delete
    # ─────────────────────────────────────────

    @staticmethod
    async def delete(category_id: str, user_id: Optional[str] = None) -> Category:
        """
        Soft-deletes the category and returns the document (with deleted_at stamped).
        Router reads deleted_at from the returned object for DeleteResponse.
        Blocked if active subcategories exist.
        """
        try:
            category = await CategoryService.get_by_id(category_id)

            child = await Category.find_one({
                "parent_id": str(category.id),
                "is_deleted": False,
            })
            if child:
                raise ValidationException(
                    "Cannot delete a category that has subcategories. "
                    "Delete or reassign subcategories first."
                )

            await category.soft_delete(user_id=user_id)
            return category

        except AppException:
            raise
        except Exception:
            app_logger.exception("Error deleting category id=%s", category_id)
            raise AppException("Failed to delete category", status_code=500)