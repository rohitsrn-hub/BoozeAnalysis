from motor.motor_asyncio import AsyncIOMotorClient
from app.core.config import MONGO_URL, DB_NAME, LIQUOR_PREFIX

client = AsyncIOMotorClient(MONGO_URL)
db = client[DB_NAME]

class Collections:
    @property
    def liquor_data(self):
        return db[f'{LIQUOR_PREFIX}data']

    @property
    def upload_history(self):
        return db[f'{LIQUOR_PREFIX}upload_history']

    @property
    def stock_backups(self):
        return db[f'{LIQUOR_PREFIX}stock_backups']

    @property
    def brands_master(self):
        return db[f'{LIQUOR_PREFIX}brands_master']

collections = Collections()
