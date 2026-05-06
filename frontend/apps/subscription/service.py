import httpx
from django.conf import settings

class SubscriptionClient:
    BASE_URL = f"{settings.FASTAPI_BASE_URL}/subscriptions"

    @staticmethod
    async def get_headers(token: str):
        return {"Authorization": f"Bearer {token}"}

    @classmethod
    async def get_current(cls, token: str):
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{cls.BASE_URL}/current", 
                headers=await cls.get_headers(token)
            )
            return response.json()

    @classmethod
    async def upgrade_plan(cls, token: str, plan_id: str, payment_data: dict):
        async with httpx.AsyncClient() as client:
            payload = {
                "plan_id": plan_id,
                **payment_data # payment_id, amount_paid, currency
            }
            response = await client.post(
                f"{cls.BASE_URL}/upgrade",
                json=payload,
                headers=await cls.get_headers(token)
            )
            return response.json()