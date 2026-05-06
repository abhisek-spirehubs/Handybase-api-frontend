# scripts/backfill_trends.py

import asyncio
from datetime import date, timedelta
from app.core.database import init_db   # adjust to match your actual db init function

async def main():
    await init_db()   # connect to MongoDB first

    from app.background_task.analytics_tasks import aggregate_daily_booking_trends

    # Backfill last 30 days
    for i in range(30):
        d = date.today() - timedelta(days=i)
        print(f"Aggregating {d}...")
        await aggregate_daily_booking_trends(for_date=d)

    print("Done.")

asyncio.run(main())