from fastapi import FastAPI, APIRouter, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
import uuid
from datetime import datetime, timezone
import pandas as pd
import io
import json
from io import BytesIO

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Create the main app without a prefix
app = FastAPI()

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# Data Models
class LiquorData(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    brand_name: str
    rate: float
    daily_sales: Dict[str, int] = Field(default_factory=dict)
    monthly_sale_qty: int
    monthly_sale_value: float
    avg_daily_sale: float
    stock_available_days: float
    stock_value_before: float
    stock_value_today: float
    stock_ratio: float
    upload_timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class OverstockConfig(BaseModel):
    multiplier: float = 3.0

class AnalyticsResponse(BaseModel):
    total_brands: int
    total_stock_value: float
    total_overstocked_value: float
    overstocked_brands: int
    top_selling_brands: List[Dict[str, Any]]
    overstocked_items: List[Dict[str, Any]]
    sales_trends: Dict[str, Any]

# Helper functions
def parse_excel_data(file_content: bytes) -> List[Dict[str, Any]]:
    """Parse Excel file and return structured data"""
    try:
        # Try to read as Excel first
        try:
            df = pd.read_excel(io.BytesIO(file_content))
        except Exception:
            # If Excel fails, try CSV
            try:
                df = pd.read_csv(io.BytesIO(file_content))
            except Exception as csv_error:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Unable to parse file. Please ensure it's a valid Excel or CSV file. Error: {str(csv_error)}"
                )
        
        if df.empty:
            raise HTTPException(status_code=400, detail="The uploaded file is empty or contains no data")
        
        # Check if required columns exist
        if 'Brand Name' not in df.columns:
            raise HTTPException(
                status_code=400, 
                detail="Required column 'Brand Name' not found in the file. Please ensure your file has the correct structure."
            )
        
        # Clean column names
        df.columns = df.columns.str.strip()
        
        # Filter out summary rows (like 'Total')
        df = df[df['Brand Name'].notna()]
        df = df[~df['Brand Name'].str.contains('Total', na=False, case=False)]
        
        if df.empty:
            raise HTTPException(status_code=400, detail="No valid brand data found in the file after filtering")
        
        liquor_data = []
        
        for _, row in df.iterrows():
            try:
                # Extract daily sales data
                daily_sales = {}
                for col in df.columns:
                    if any(date_indicator in col.lower() for date_indicator in ['aug', 'sep', 'oct', 'nov', 'dec', 'jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul']):
                        if col not in ['Monthly Sale (25 Aug - 19 Sep)', 'Monthly Sale value (a)']:
                            try:
                                daily_sales[col] = int(row[col]) if pd.notna(row[col]) else 0
                            except (ValueError, TypeError):
                                daily_sales[col] = 0
                
                # Extract main metrics
                brand_data = {
                    'brand_name': str(row['Brand Name']).strip(),
                    'rate': float(row['Rate']) if pd.notna(row['Rate']) else 0.0,
                    'daily_sales': daily_sales,
                    'monthly_sale_qty': int(row.get('Monthly Sale (25 Aug - 19 Sep)', 0)) if pd.notna(row.get('Monthly Sale (25 Aug - 19 Sep)', 0)) else 0,
                    'monthly_sale_value': float(row.get('Monthly Sale value (a)', 0)) if pd.notna(row.get('Monthly Sale value (a)', 0)) else 0.0,
                    'avg_daily_sale': float(row.get('Avg Daily SALE (b)', 0)) if pd.notna(row.get('Avg Daily SALE (b)', 0)) else 0.0,
                    'stock_available_days': float(row.get('Stock avlb for days (c)', 0)) if pd.notna(row.get('Stock avlb for days (c)', 0)) else 0.0,
                    'stock_value_before': float(row.get('Stock Value before collection 19 Sep 25 (d)', 0)) if pd.notna(row.get('Stock Value before collection 19 Sep 25 (d)', 0)) else 0.0,
                    'stock_value_today': float(row.get('Stock value Today (29 Sep) ( e)', 0)) if pd.notna(row.get('Stock value Today (29 Sep) ( e)', 0)) else 0.0,
                    'stock_ratio': float(row.get('Stock ratio (e/a)', 0)) if pd.notna(row.get('Stock ratio (e/a)', 0)) else 0.0,
                }
                
                liquor_data.append(brand_data)
                
            except Exception as e:
                logging.warning(f"Error parsing row for {row.get('Brand Name', 'Unknown')}: {e}")
                continue
        
        if not liquor_data:
            raise HTTPException(status_code=400, detail="No valid liquor data could be extracted from the file")
        
        return liquor_data
    
    except HTTPException:
        # Re-raise HTTPExceptions as-is
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error parsing file: {str(e)}")

def calculate_overstocking(data: List[Dict], multiplier: float = 3.0) -> List[Dict]:
    """Calculate overstocking based on configurable multiplier"""
    overstocked_items = []
    
    for item in data:
        monthly_avg_sale = item.get('monthly_sale_value', 0)
        current_stock_value = item.get('stock_value_today', 0)
        
        # Calculate threshold (multiplier * monthly average)
        threshold = monthly_avg_sale * multiplier
        
        if current_stock_value > threshold and monthly_avg_sale > 0:
            overstock_value = current_stock_value - threshold
            overstocked_items.append({
                'brand_name': item['brand_name'],
                'current_stock_value': current_stock_value,
                'monthly_avg_sale': monthly_avg_sale,
                'threshold': threshold,
                'overstock_value': overstock_value,
                'stock_ratio': item.get('stock_ratio', 0)
            })
    
    return sorted(overstocked_items, key=lambda x: x['overstock_value'], reverse=True)

# API Endpoints
@api_router.get("/")
async def root():
    return {"message": "Liquor Sales Analysis Dashboard API"}

@api_router.post("/upload-data")
async def upload_liquor_data(file: UploadFile = File(...)):
    """Upload and process Excel/CSV file with liquor data"""
    try:
        # Validate file type first
        if not file.filename or not file.filename.endswith(('.xlsx', '.xls', '.csv')):
            raise HTTPException(
                status_code=400, 
                detail={
                    "error": "Invalid file type",
                    "message": "Only Excel (.xlsx, .xls) and CSV files are supported",
                    "supported_formats": [".xlsx", ".xls", ".csv"]
                }
            )
        
        # Read file content
        content = await file.read()
        
        if len(content) == 0:
            raise HTTPException(status_code=400, detail="Empty file uploaded")
        
        # Parse the data
        parsed_data = parse_excel_data(content)
        
        if not parsed_data:
            raise HTTPException(status_code=400, detail="No valid data found in the file")
        
        # Clear existing data and insert new data
        await db.liquor_data.delete_many({})
        
        # Convert to LiquorData models and insert
        liquor_objects = []
        for item_data in parsed_data:
            liquor_obj = LiquorData(**item_data)
            liquor_objects.append(liquor_obj.dict())
        
        if liquor_objects:
            await db.liquor_data.insert_many(liquor_objects)
        
        return JSONResponse(
            status_code=200,
            content={
                "message": f"Successfully uploaded {len(liquor_objects)} liquor records",
                "total_records": len(liquor_objects)
            }
        )
        
    except HTTPException:
        # Re-raise HTTPExceptions (400 errors) as-is
        raise
    except Exception as e:
        logging.error(f"Error uploading data: {e}")
        raise HTTPException(status_code=500, detail=f"Error processing file: {str(e)}")

@api_router.get("/analytics", response_model=AnalyticsResponse)
async def get_analytics(overstock_multiplier: float = 3.0):
    """Get comprehensive analytics including overstocking analysis"""
    try:
        # Fetch all liquor data
        liquor_records = await db.liquor_data.find().to_list(1000)
        
        if not liquor_records:
            raise HTTPException(status_code=404, detail="No data found. Please upload liquor data first.")
        
        # Convert to dict format for calculations
        data_dicts = [
            {
                'brand_name': record['brand_name'],
                'rate': record['rate'],
                'daily_sales': record['daily_sales'],
                'monthly_sale_qty': record['monthly_sale_qty'],
                'monthly_sale_value': record['monthly_sale_value'],
                'avg_daily_sale': record['avg_daily_sale'],
                'stock_available_days': record['stock_available_days'],
                'stock_value_before': record['stock_value_before'],
                'stock_value_today': record['stock_value_today'],
                'stock_ratio': record['stock_ratio']
            }
            for record in liquor_records
        ]
        
        # Calculate overstocked items
        overstocked_items = calculate_overstocking(data_dicts, overstock_multiplier)
        
        # Calculate top selling brands
        top_selling = sorted(data_dicts, key=lambda x: x['monthly_sale_value'], reverse=True)[:10]
        
        # Calculate totals
        total_stock_value = sum(item['stock_value_today'] for item in data_dicts)
        total_overstocked_value = sum(item['overstock_value'] for item in overstocked_items)
        
        # Prepare sales trends data
        sales_trends = {}
        for record in data_dicts:
            for date, sales in record['daily_sales'].items():
                if date not in sales_trends:
                    sales_trends[date] = 0
                sales_trends[date] += sales
        
        # Sort sales trends by date
        sorted_trends = dict(sorted(sales_trends.items()))
        
        return AnalyticsResponse(
            total_brands=len(data_dicts),
            total_stock_value=total_stock_value,
            total_overstocked_value=total_overstocked_value,
            overstocked_brands=len(overstocked_items),
            top_selling_brands=[
                {
                    'brand_name': item['brand_name'],
                    'monthly_sale_value': item['monthly_sale_value'],
                    'stock_value_today': item['stock_value_today'],
                    'stock_ratio': item['stock_ratio']
                }
                for item in top_selling
            ],
            overstocked_items=overstocked_items,
            sales_trends=sorted_trends
        )
        
    except Exception as e:
        logging.error(f"Error getting analytics: {e}")
        raise HTTPException(status_code=500, detail=f"Error calculating analytics: {str(e)}")

@api_router.get("/brands")
async def get_all_brands():
    """Get all brand data"""
    try:
        liquor_records = await db.liquor_data.find().to_list(1000)
        return [LiquorData(**record) for record in liquor_records]
    except Exception as e:
        logging.error(f"Error fetching brands: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching brands: {str(e)}")

# Include the router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()