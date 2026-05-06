from typing import Optional
from app.models.common import BaseLogWithStatus


class Category(BaseLogWithStatus):
    name: str
    slug: str
    description: Optional[str] = None
    icon: Optional[str] = None
    parent_id: Optional[str] = None

    class Settings:
        name = "categories"
        indexes = [
            # Compound indexes matching actual query patterns
            [("name", 1), ("is_deleted", 1)],                      # duplicate name check
            [("slug", 1), ("is_deleted", 1)],                      # slug lookup (unique)
            [("parent_id", 1), ("is_deleted", 1), ("status", 1)],  # get_subcategories + delete guard
            [("status", 1), ("is_deleted", 1)],                    # get_all
            # Additional indexes
            [("status", 1), ("order", 1)],  # ordered category list
            [("parent_id", 1), ("status", 1)],  # active subcategories
        ]