from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie

from app.core.config import settings
from app.utils.logger import app_logger

# Import all models
from app.models.user import User
from app.models.category import Category
from app.models.provider import ProviderProfile
from app.models.service import Service
from app.models.booking import Booking
from app.models.notification import Notification
from app.models.review import Review
from app.models.chat_room import ChatRoom
from app.models.chat_message import ChatMessage
from app.models.client_plan import ClientPlan
from app.models.provider_plan import ProviderPlan
from app.models.client_subscription import ClientSubscription
from app.models.provider_subscription import ProviderSubscription
from app.models.invoice import Invoice
from app.models.provider_availability import ProviderAvailability
from app.models.provider_analytics import (
    ProviderProfileVisit,
)
from app.models.client_review import ClientReview
from app.models.quotation import Quotation
from app.models.job_request import JobRequest, JobApplication
from app.models.support_ticket import SupportTicket
from app.models.announcement import Announcement
from app.models.fcm_token import FCMToken

client: AsyncIOMotorClient | None = None


async def connect_to_mongo():
    """
    Initialize MongoDB connection and Beanie ODM.
    """
    global client

    client = AsyncIOMotorClient(settings.MONGO_URI)

    db = client[settings.DATABASE_NAME]

    await init_beanie(
        database=db,
        document_models=[
            User,
            Category,
            ProviderProfile,
            Service,
            Booking,
            Notification,
            ChatRoom,
            ChatMessage,
            Review,
            ClientPlan,
            ProviderPlan,
            ClientSubscription,
            ProviderSubscription,
            Invoice,
            ProviderAvailability,
            ProviderProfileVisit,
            ClientReview,
            Quotation,
            JobRequest, 
            JobApplication,
            SupportTicket,
            Announcement,
            FCMToken,

        ],
    )

    app_logger.info("MongoDB connected and Beanie initialized")


async def close_mongo_connection():
    """
    Close MongoDB connection.
    """
    global client

    if client:
        client.close()
        app_logger.info("MongoDB connection closed")