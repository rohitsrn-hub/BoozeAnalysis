from pathlib import Path
import os
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[2]
load_dotenv(ROOT_DIR / '.env')

MONGO_URL = os.getenv('MONGO_URL', '')
DB_NAME = os.getenv('DB_NAME', '')
LIQUOR_PREFIX = 'liquor_'
ALLOWED_ORIGINS = [
    'http://localhost:3000',
    'http://127.0.0.1:3000',
]
