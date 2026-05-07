import asyncio
import os
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime

async def check_dates():
    mongo_url = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
    db_name = os.environ.get('DB_NAME', 'liquor_sales')
    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]

    print(f"Checking dates in {db_name}...")

    # Check current data
    cursor = db.liquor_data.find({}, {"DL_date": 1, "D1_date": 1, "daily_sales": 1})
    records = await cursor.to_list(None)

    all_dates = set()
    for r in records:
        if r.get('DL_date'): all_dates.add(r['DL_date'])
        if r.get('D1_date'): all_dates.add(r['D1_date'])
        if r.get('daily_sales'):
            for d in r['daily_sales'].keys():
                all_dates.add(d)

    print(f"Found {len(all_dates)} unique dates in liquor_data:")
    for d in sorted(list(all_dates)):
        print(f"  {d}")
        
    client.close()

if __name__ == "__main__":
    asyncio.run(check_dates())
