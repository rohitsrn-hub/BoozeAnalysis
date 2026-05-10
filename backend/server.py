from fastapi import FastAPI, APIRouter, File, UploadFile, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
import traceback
import uuid
import io
import json
import pytz
import pandas as pd
import re
import sys
from pathlib import Path

# Add the current directory to sys.path so that sibling modules can be imported
# This allows running from root (e.g. gunicorn backend.server:app) 
# or from backend (e.g. uvicorn server:app)
current_dir = Path(__file__).parent
if str(current_dir) not in sys.path:
    sys.path.append(str(current_dir))

from typing import List, Dict, Any, Optional
from datetime import datetime, timezone, timedelta

# Import custom modules
from models import *
from utils.date_helper import parse_date, normalize_date_key
from utils.stock_logic import calculate_movements, detect_monthly_restock

# ReportLab imports for PDF generation
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.graphics.shapes import Drawing
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.charts.piecharts import Pie
from reportlab.lib.colors import HexColor

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ.get('MONGO_URL')
db_name = os.environ.get('DB_NAME')

if not mongo_url or not db_name:
    logging.error("CRITICAL ERROR: MONGO_URL or DB_NAME environment variables are missing!")
    if not mongo_url: logging.error("Missing: MONGO_URL")
    if not db_name: logging.error("Missing: DB_NAME")
    # Don't exit immediately in local dev if you want, but for Render we need these
    # Let's provide a fallback for local testing but log warning
    if not mongo_url: mongo_url = "mongodb://localhost:27017"
    if not db_name: db_name = "booze_analysis_dev"

client = AsyncIOMotorClient(mongo_url)
db = client[db_name]

# Collection name prefixes for data separation
LIQUOR_PREFIX = "liquor_"

# Collection references
class Collections:
    @property
    def liquor_data(self): return db[f"{LIQUOR_PREFIX}data"]
    @property
    def upload_history(self): return db[f"{LIQUOR_PREFIX}upload_history"]
    @property
    def stock_backups(self): return db[f"{LIQUOR_PREFIX}stock_backups"]
    @property
    def brands_master(self): return db[f"{LIQUOR_PREFIX}brands_master"]

collections = Collections()
app = FastAPI()

# Health check endpoint for Render
@app.get("/")
async def root():
    return {"status": "ok", "message": "BoozeAnalysis Backend is running"}

@app.get("/health")
async def health():
    try:
        # Check DB connection
        await client.admin.command('ping')
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}

api_router = APIRouter(prefix="/api")

# --- Helper functions (refactored) ---
async def check_duplicate_dates_in_upload(parsed_data: List[Dict[str, Any]], filename: str):
    """Check if the uploaded data contains dates that already exist in the database"""
    try:
        # Extract dates from the new upload
        new_dates = set()
        for item in parsed_data:
            # Get DL_date (the current/today's date in the upload)
            dl_date = item.get('DL_date')
            if dl_date:
                new_dates.add(dl_date)
            
            # Also check daily_sales dates
            daily_sales = item.get('daily_sales', {}) or {}
            for date_key in daily_sales.keys():
                new_dates.add(date_key)
        
        if not new_dates:
            return  # No dates to check
        
        # Get existing data from database
        existing_records = await collections.liquor_data.find({}, {"daily_sales": 1, "DL_date": 1}).to_list(1000)
        
        # Extract existing dates from database
        existing_dates = set()
        for record in existing_records:
            # Check DL_date
            dl_date = record.get('DL_date')
            if dl_date:
                existing_dates.add(dl_date)
            
            # Check daily_sales dates
            daily_sales = record.get('daily_sales', {}) or {}
            for date_key in daily_sales.keys():
                existing_dates.add(date_key)
        
        # Find duplicate dates
        duplicate_dates = new_dates.intersection(existing_dates)
        
        if duplicate_dates:
            duplicate_list = sorted(list(duplicate_dates))
            raise HTTPException(
                status_code=409,  # 409 Conflict status code for duplicate data
                detail={
                    "error": "Duplicate dates detected",
                    "message": f"The following dates already exist in the database: {', '.join(duplicate_list)}",
                    "duplicate_dates": duplicate_list,
                    "filename": filename,
                    "suggestion": "Please upload data for a new date or use 'Upload Full Monthly Data' to replace all existing data"
                }
            )
        
        print(f"✅ Date validation passed for {filename}. New dates: {sorted(list(new_dates))}")
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Warning: Could not validate dates for duplicate checking: {e}")
        # Don't block upload if date validation fails, just log the warning

def parse_todays_data(file_content: bytes) -> Dict[str, Any]:
    """Parse today's stock data - extract new date column and stock values"""
    try:
        df = pd.read_excel(io.BytesIO(file_content))
        if df.empty: raise HTTPException(status_code=400, detail="File is empty")
        
        df.columns = [str(col).strip() for col in df.columns]
        brand_col, new_date_col = None, None
        
        # We search from right to left to find the MOST RECENT date column
        for col in reversed(df.columns):
            col_str = str(col).strip()
            if not new_date_col and parse_date(col_str) != datetime.min:
                new_date_col = col
            
        # Then find the brand name column
        for col in df.columns:
            col_lower = str(col).lower()
            if 'brand' in col_lower and 'name' in col_lower:
                brand_col = col
                break
            
        if not brand_col or not new_date_col:
            logging.error(f"Upload parsing failed: brand_col={brand_col}, new_date_col={new_date_col}")
            logging.info(f"Available columns: {list(df.columns)}")
            raise HTTPException(status_code=400, detail=f"Missing Brand or Date column. Found brand='{brand_col}', date='{new_date_col}'")
            
        brands_data = {}
        df = df[df[brand_col].notna()]
        for _, row in df.iterrows():
            brand_name = str(row[brand_col]).strip()
            if not brand_name: continue
            
            try:
                raw_val = row[new_date_col]
                stock_qty = float(raw_val) if pd.notna(raw_val) and str(raw_val).strip() != '' else None
                brands_data[brand_name] = {'stock_qty': stock_qty}
            except: continue
            
        return {'new_date_column': str(new_date_col), 'brands_data': brands_data}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error parsing today's data: {str(e)}")

def parse_excel_data(file_content: bytes, upload_type: str = "full_monthly") -> List[Dict[str, Any]]:
    """Generic Excel parser that delegates to specific format parsers"""
    try:
        df = pd.read_excel(io.BytesIO(file_content))
        # Simple heuristic to detect tabular vs list format
        if len(df.columns) >= 3 and any('brand' in str(col).lower() for col in df.columns):
            return parse_tabular_format(df, upload_type)
        return parse_list_format(df)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Excel parse error: {str(e)}")

def parse_tabular_format(df: pd.DataFrame, upload_type: str = "full_monthly") -> List[Dict[str, Any]]:
    """Refactored tabular parser with movement-based logic and blank cell handling"""
    df.columns = [str(col).strip() for col in df.columns]
    brand_col, wholesale_rate_col, selling_rate_col, index_col = None, None, None, None
    date_columns = []

    for col in df.columns:
        col_lower = col.lower()
        if 'brand' in col_lower and 'name' in col_lower: brand_col = col
        elif 'wholesale' in col_lower and 'rate' in col_lower: wholesale_rate_col = col
        elif 'selling' in col_lower and 'rate' in col_lower: selling_rate_col = col
        elif 'rate' in col_lower and not wholesale_rate_col: selling_rate_col = col
        elif col_lower in ['index', 'sl', 'sr', 'no']: index_col = col
        elif parse_date(col) != datetime.min: date_columns.append(col)

    if not brand_col or not date_columns:
        raise HTTPException(status_code=400, detail="Could not identify Brand or Date columns")

    # Sort date columns chronologically using our helper
    date_columns.sort(key=lambda x: parse_date(x))
    
    liquor_data = []
    df = df[df[brand_col].notna()]
    df = df[~df[brand_col].astype(str).str.contains('total|sum', na=False, case=False)]
    
    for idx, row in df.iterrows():
        brand_name = str(row[brand_col]).strip()
        if not brand_name: continue

        # 1. Handle Rates
        s_rate = float(row[selling_rate_col]) if selling_rate_col and pd.notna(row[selling_rate_col]) else 0.0
        w_rate = float(row[wholesale_rate_col]) if wholesale_rate_col and pd.notna(row[wholesale_rate_col]) else s_rate * 0.9

        # 2. Extract Daily Stock with "Hold Last Known" logic
        daily_stock = {}
        last_known_val = 0.0
        
        for i, col in enumerate(date_columns):
            val = row[col]
            if pd.notna(val) and str(val).strip() != '':
                try:
                    curr_val = float(val)
                    daily_stock[col] = curr_val
                    last_known_val = curr_val
                except:
                    daily_stock[col] = last_known_val
            else:
                # BLANK CELL detected - Use last known numeric value (Hold)
                daily_stock[col] = last_known_val

        # 3. Movement Calculations
        D1_date = date_columns[0]
        DL_date = date_columns[-1]
        D1_stock = daily_stock.get(D1_date, 0.0)
        DL_stock = daily_stock.get(DL_date, 0.0)

        sales_qty, restocks_qty, _ = calculate_movements(daily_stock, D1_date, DL_date)
        
        days_analyzed = max(1, len(date_columns))
        avg_daily_qty = sales_qty / days_analyzed if days_analyzed > 0 else 0.0
        monthly_qty = avg_daily_qty * 24 # Standardized to 24-day billing month

        brand_data = {
            'brand_name': brand_name,
            'index_number': int(row[index_col]) if index_col and pd.notna(row[index_col]) else idx + 1,
            'wholesale_rate': w_rate,
            'selling_rate': s_rate,
            'rate': s_rate,
            'D1_date': D1_date,
            'D1_stock': D1_stock,
            'DL_date': DL_date,
            'DL_stock': DL_stock,
            'current_stock_qty': int(DL_stock),
            'total_sales_qty': sales_qty,
            'avg_daily_sales_qty': avg_daily_qty,
            'monthly_sales_qty': monthly_qty,
            'monthly_sale_qty': int(monthly_qty),
            'monthly_sale_value': monthly_qty * s_rate,
            'stock_value_today': DL_stock * s_rate,
            'stock_value_before': D1_stock * s_rate,
            'stock_ratio': (DL_stock * s_rate) / (monthly_qty * s_rate) if monthly_qty > 0 else 0.0,
            'stock_available_days': (DL_stock / avg_daily_qty) if avg_daily_qty > 0 else 999.0,
            'daily_sales': daily_stock,
            'days_analyzed': days_analyzed,
            'avg_daily_sale': (monthly_qty * s_rate) / 30
        }
        liquor_data.append(brand_data)

    print(f"✅ Parsed {len(liquor_data)} brands using movement-based logic.")
    return liquor_data

def parse_list_format(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """Parse simple list format (brand names followed by numerical data)"""
    if df.empty:
        raise HTTPException(status_code=400, detail="The uploaded file is empty or contains no data")
    
    # Flatten all data and separate text from numbers
    all_data = df.values.flatten()
    all_data = [str(x).strip() for x in all_data if pd.notna(x) and str(x).strip()]
    
    brand_names = []
    numerical_data = []
    
    for item in all_data:
        try:
            float(item)
            numerical_data.append(item)
        except (ValueError, TypeError):
            if item and not item.replace('.', '').isdigit():
                brand_names.append(item)
    
    if not brand_names:
        raise HTTPException(status_code=400, detail="No brand names found in the file")
    
    if len(numerical_data) < len(brand_names) * 2:
        raise HTTPException(
            status_code=400, 
            detail=f"Insufficient numerical data. Expected at least {len(brand_names) * 2} values, found {len(numerical_data)}"
        )
    
    liquor_data = []
    
    # Parse in groups of 3 (ID, Rate, Quantity)
    for i in range(len(brand_names)):
        try:
            if i * 3 < len(numerical_data):
                product_id = numerical_data[i * 3] if i * 3 < len(numerical_data) else f"AUTO_{i}"
                rate = float(numerical_data[i * 3 + 1]) if i * 3 + 1 < len(numerical_data) else 100.0
                quantity = int(float(numerical_data[i * 3 + 2])) if i * 3 + 2 < len(numerical_data) else 0
                
                estimated_monthly_sales = max(1, quantity // 4) * rate
                
                brand_data = {
                    'brand_name': brand_names[i],
                    'product_id': product_id,
                    'rate': rate,
                    'current_stock_qty': quantity,
                    'stock_value_today': rate * quantity,
                    'monthly_sale_value': estimated_monthly_sales,
                    'stock_available_days': max(1, quantity // max(1, quantity // 30)) if quantity > 0 else 0,
                    'stock_ratio': (rate * quantity) / max(1, estimated_monthly_sales),
                    'daily_sales': {},
                    'monthly_sale_qty': max(1, quantity // 4),
                    'avg_daily_sale': estimated_monthly_sales / 30,
                    'stock_value_before': rate * quantity * 1.1,
                }
                
                liquor_data.append(brand_data)
                
        except Exception as e:
            logging.warning(f"Error parsing data for {brand_names[i] if i < len(brand_names) else 'Unknown'}: {e}")
            continue
    
    return liquor_data

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

@api_router.post("/upload-full-monthly-data")
async def upload_full_monthly_data(file: UploadFile = File(...)):
    """Upload processing for full monthly data with persistent rates and automated backup"""
    try:
        content = await file.read()
        parsed_data = parse_excel_data(content, "full_monthly")
        
        # 1. Build persistent rates map (Master > Current)
        rates_map = {}
        async for bm in collections.brands_master.find():
            rates_map[bm['brand_name']] = {
                'w': bm.get('wholesale_rate', 0.0),
                's': bm.get('selling_rate', 0.0)
            }
        async for ld in collections.liquor_data.find():
            rates_map[ld['brand_name']] = {
                'w': ld.get('wholesale_rate', 0.0),
                's': ld.get('selling_rate', ld.get('rate', 0.0))
            }

        # 2. Apply rates and update Master
        final_objects = []
        for item in parsed_data:
            name = item['brand_name']
            # Fallback to persistent rates if Excel is 0
            if item.get('selling_rate', 0) == 0 and name in rates_map:
                item['selling_rate'] = rates_map[name]['s']
                item['wholesale_rate'] = rates_map[name]['w']
                item['rate'] = rates_map[name]['s']

            # Update Brands Master if we have valid rates now
            if item.get('selling_rate', 0) > 0:
                await collections.brands_master.update_one(
                    {"brand_name": name},
                    {"$set": {
                        "brand_name": name,
                        "selling_rate": item['selling_rate'],
                        "wholesale_rate": item['wholesale_rate'],
                        "last_updated": datetime.now(timezone.utc)
                    }},
                    upsert=True
                )

            # Recalculate values
            s_rate = item.get('selling_rate', 0.0)
            item['stock_value_today'] = item['current_stock_qty'] * s_rate
            item['monthly_sale_value'] = item.get('monthly_sales_qty', 0) * s_rate
            
            final_objects.append(LiquorData(**item).dict())

        # 3. Backup and Replace
        backup_id = None
        existing = await collections.liquor_data.find({}, {"_id": 0}).to_list(10000)
        if existing:
            backup = StockBackup(data_snapshot=existing, total_records=len(existing), backup_reason="pre_full_monthly")
            await collections.stock_backups.insert_one(backup.dict())
            backup_id = backup.id

        await collections.liquor_data.delete_many({})
        if final_objects:
            await collections.liquor_data.insert_many(final_objects)

        # 4. History
        history = UploadHistory(
            filename=file.filename,
            upload_type="full_monthly",
            records_count=len(final_objects),
            file_size=len(content),
            can_undo=True,
            changes_snapshot={"backup_id": backup_id, "replaced_all": True}
        )
        await collections.upload_history.insert_one(history.dict())

        return {"message": f"Successfully uploaded {len(final_objects)} brands.", "backup_id": backup_id}

    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error in upload_full_monthly_data: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/upload-todays-data")
async def upload_todays_data(file: UploadFile = File(...), confirm_restock: bool = False):
    """Upload today's stock data - with automated Monthly Restock Detection & Verification"""
    try:
        content = await file.read()
        todays_data = parse_todays_data(content)
        new_date_column = todays_data['new_date_column']
        brands_data = todays_data['brands_data']
        
        # 1. Validate for duplicates BEFORE processing
        # This prevents multiple uploads for the same date from creating duplicate history
        await check_duplicate_dates_in_upload(
            parsed_data=[{'brand_name': n, 'DL_date': new_date_column} for n in brands_data.keys()],
            filename=file.filename
        )
        existing_stock = {}
        async for brand in collections.liquor_data.find({}, {"brand_name": 1, "DL_stock": 1}):
            existing_stock[brand['brand_name']] = brand.get('DL_stock', 0.0)
            
        # Convert to list for detection helper
        parsed_list = [{'brand_name': n, 'DL_stock': i['stock_qty']} for n, i in brands_data.items()]
        is_restock, inc_count, inc_brands = detect_monthly_restock(parsed_list, existing_stock)
        
        # 2. Monthly Restock Logic (threshold met)
        if is_restock:
            if not confirm_restock:
                # PAUSE: Ask for user verification
                return JSONResponse(
                    status_code=202, # Accepted but not processed
                    content={
                        "status": "requires_verification",
                        "message": f"🚀 Monthly Restock detected ({inc_count} brands)! Stock increased for brands like {', '.join(inc_brands[:3])}...",
                        "inc_count": inc_count,
                        "inc_brands": inc_brands
                    }
                )
            
            # User confirmed! Trigger Monthly Restock Workflow
            print(f"🚀 User confirmed Monthly Restock. Triggering backup and reset.")
            await internal_reset_stock()
            # After reset, current upload becomes fresh D1 data
            
        elif inc_count > 0:
            # 3. Small increase detected - treat as error per user instructions
            raise HTTPException(
                status_code=400,
                detail=f"⚠️ Potential Error Detected: Stock increased for only {inc_count} brands ({', '.join(inc_brands[:3])}...). Monthly restocks should affect at least 5 brands. Please check your file for typos."
            )
            
        # 3. Process Upload
        db_count = await collections.liquor_data.count_documents({})
        is_fresh = (db_count == 0)
        
        updated, added = 0, 0
        history_snapshot = {"brands_updated": {}, "brands_added": []}

        for name, info in brands_data.items():
            qty = info['stock_qty']
            if qty is None: continue # User requested to ignore blank cells
            
            existing = await collections.liquor_data.find_one({"brand_name": name})
            
            if existing and not is_fresh:
                # Normal Daily Update - Save previous state for undo
                history_snapshot["brands_updated"][existing["id"]] = {
                    "DL_date": existing.get("DL_date"),
                    "DL_stock": existing.get("DL_stock"),
                    "current_stock_qty": existing.get("current_stock_qty"),
                    "total_sales_qty": existing.get("total_sales_qty"),
                    "avg_daily_sales_qty": existing.get("avg_daily_sales_qty"),
                    "days_analyzed": existing.get("days_analyzed"),
                    "monthly_sale_qty": existing.get("monthly_sale_qty"),
                    "monthly_sale_value": existing.get("monthly_sale_value"),
                    "stock_value_today": existing.get("stock_value_today"),
                    "stock_available_days": existing.get("stock_available_days"),
                    "stock_ratio": existing.get("stock_ratio")
                }
                
                old_daily = existing.get('daily_sales', {})
                old_daily[normalize_date_key(new_date_column)] = qty
                
                # Use modular logic for movements (this will be improved in next steps)
                d1_stock = existing.get('D1_stock', qty)
                s_rate = existing.get('selling_rate', 0.0)
                
                # Simplified update for now
                update_fields = {
                    "daily_sales": old_daily,
                    "DL_date": new_date_column,
                    "DL_stock": float(qty),
                    "current_stock_qty": int(qty),
                    "stock_value_today": float(qty * s_rate),
                    "upload_timestamp": datetime.now(timezone.utc)
                }
                await collections.liquor_data.update_one({"_id": existing["_id"]}, {"$set": update_fields})
                updated += 1
            else:
                # Fresh Record (New month or new brand)
                # Fetch rate from brands_master if not in Excel
                master = await collections.brands_master.find_one({"brand_name": name})
                s_rate = master.get('selling_rate', 0.0) if master else 0.0
                w_rate = master.get('wholesale_rate', 0.0) if master else 0.0
                
                new_doc = {
                    "id": str(uuid.uuid4()),
                    "brand_name": name,
                    "selling_rate": s_rate,
                    "wholesale_rate": w_rate,
                    "rate": s_rate,
                    "D1_date": new_date_column,
                    "D1_stock": float(qty),
                    "DL_date": new_date_column,
                    "DL_stock": float(qty),
                    "current_stock_qty": int(qty),
                    "daily_sales": {normalize_date_key(new_date_column): qty},
                    "days_analyzed": 1,
                    "upload_timestamp": datetime.now(timezone.utc)
                }
                await collections.liquor_data.insert_one(new_doc)
                added += 1
                history_snapshot["brands_added"].append(new_doc["id"])

        # Save History
        upload_hist = UploadHistory(
            filename=file.filename,
            upload_type="daily_update",
            records_count=len(brands_data),
            file_size=len(content),
            changes_snapshot={
                **history_snapshot,
                "date_added": normalize_date_key(new_date_column),
                "new_date_column": new_date_column
            }
        )
        await collections.upload_history.insert_one(upload_hist.dict())
        
        return {
            "message": f"Successfully processed upload. {'Restock triggered!' if is_restock else ''}",
            "updated": updated,
            "added": added,
            "is_restock": is_restock
        }
    except Exception as e:
        logging.error(f"Error in upload_todays_data: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/upload-history")
async def get_upload_history():
    """Get history of all uploaded files"""
    try:
        upload_records = await collections.upload_history.find().sort("upload_timestamp", -1).to_list(1000)
        
        # Convert datetime objects to ISO strings for JSON serialization
        result = []
        for record in upload_records:
            upload_timestamp = record.get("upload_timestamp")
            undone_at = record.get("undone_at")
            
            # Convert datetime to ISO string if it's a datetime object
            if upload_timestamp and hasattr(upload_timestamp, 'isoformat'):
                upload_timestamp = upload_timestamp.isoformat()
            elif upload_timestamp:
                upload_timestamp = str(upload_timestamp)
            
            if undone_at and hasattr(undone_at, 'isoformat'):
                undone_at = undone_at.isoformat()
            elif undone_at:
                undone_at = str(undone_at)
            
            result.append({
                "id": record.get("id", str(uuid.uuid4())),
                "filename": record.get("filename", "Unknown"),
                "upload_type": record.get("upload_type", "unknown"),
                "upload_timestamp": upload_timestamp or datetime.now(timezone.utc).isoformat(),
                "records_count": record.get("records_count", 0),
                "file_size": record.get("file_size", 0),  # Default to 0 if missing
                "uploaded_by": record.get("uploaded_by", "dashboard_user"),
                "can_undo": record.get("can_undo", False),
                "undone_at": undone_at
            })
        
        return result
        
    except Exception as e:
        logging.error(f"Error fetching upload history: {e}")
        logging.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Error fetching upload history: {str(e)}")

@api_router.post("/upload-history/{upload_id}/undo")
async def undo_upload(upload_id: str):
    """
    Undo a specific upload by reversing only the changes made by that upload.
    This provides granular undo - only the data from this specific upload is removed.
    """
    try:
        # Find the upload history record
        upload_record = await collections.upload_history.find_one({"id": upload_id})
        
        if not upload_record:
            raise HTTPException(status_code=404, detail="Upload history not found")
        
        if upload_record.get("undone_at"):
            raise HTTPException(status_code=400, detail="This upload has already been undone")
        
        if not upload_record.get("can_undo", False):
            raise HTTPException(status_code=400, detail="This upload cannot be undone")
        
        changes_snapshot = upload_record.get("changes_snapshot", {})
        upload_type = upload_record.get("upload_type")
        
        if not changes_snapshot:
            raise HTTPException(
                status_code=400, 
                detail="No change information available for this upload. Cannot undo."
            )
        
        brands_reverted = 0
        brands_deleted = 0
        
        # Process undo based on upload type
        if upload_type in ["daily_update", "daily", "restock"]:
            # For Today's Data updates, reverse the changes
            brands_updated = changes_snapshot.get("brands_updated", {})
            brands_added = changes_snapshot.get("brands_added", [])
            date_added = changes_snapshot.get("date_added")
            
            # Revert updated brands
            for brand_id, previous_state in brands_updated.items():
                brand_record = await collections.liquor_data.find_one({"id": brand_id})
                
                if brand_record:
                    # Remove the date that was added
                    current_daily_sales = brand_record.get('daily_sales', {})
                    if date_added and date_added in current_daily_sales:
                        del current_daily_sales[date_added]
                    
                    # Restore previous values
                    update_data = {
                        "daily_sales": current_daily_sales,
                        "DL_date": previous_state.get("DL_date"),
                        "DL_stock": previous_state.get("DL_stock"),
                        "current_stock_qty": previous_state.get("current_stock_qty"),
                        "total_sales_qty": previous_state.get("total_sales_qty"),
                        "avg_daily_sales_qty": previous_state.get("avg_daily_sales_qty"),
                        "days_analyzed": previous_state.get("days_analyzed"),
                        "monthly_sale_value": previous_state.get("monthly_sale_value"),
                        "avg_daily_sale": previous_state.get("avg_daily_sale"),
                        "stock_value_today": previous_state.get("stock_value_today"),
                        "stock_available_days": previous_state.get("stock_available_days"),
                        "stock_ratio": previous_state.get("stock_ratio")
                    }
                    
                    await collections.liquor_data.update_one(
                        {"id": brand_id},
                        {"$set": update_data}
                    )
                    brands_reverted += 1
            
            # Delete brands that were newly added
            if brands_added:
                result = await collections.liquor_data.delete_many({"id": {"$in": brands_added}})
                brands_deleted = result.deleted_count

            # Infer date_added if missing (for legacy records)
            if not date_added and upload_type in ["daily_update", "daily", "restock"]:
                # Try to infer from the brands that were updated (if snapshot exists)
                if brands_updated:
                    sample_brand_id = list(brands_updated.keys())[0]
                    # We can't know the date from the state unless we have it saved, 
                    # but we can check the record's current DL_date if it's not undone
                    sample_brand = await collections.liquor_data.find_one({"id": sample_brand_id})
                    if sample_brand:
                        date_added = sample_brand.get("DL_date")
                        logging.info(f"Inferred date_added '{date_added}' from sample brand")
                
                # If still no date, try to find the most recent date in any brand's daily_sales
                if not date_added:
                    sample_brand = await collections.liquor_data.find_one({})
                    if sample_brand and sample_brand.get("DL_date"):
                        date_added = sample_brand.get("DL_date")
                        logging.info(f"Inferred date_added '{date_added}' from most recent DB state")

            # FAILSAFE: Ensure the date is removed from ALL brands, even if snapshot missed them
            # This is critical for trendline accuracy and preventing "date already exists" errors
            if date_added:
                logging.info(f"Running failsafe cleanup for date: {date_added}")
                from utils.date_helper import parse_date
                
                # Normalize the date to match daily_sales format
                def normalize_date_key_for_cleanup(date_str):
                    import re
                    try:
                        date_str = str(date_str).strip()
                        if re.match(r'\d{4}-\d{2}-\d{2}', date_str):
                            dt = datetime.strptime(date_str.split()[0], "%Y-%m-%d")
                            return dt.strftime("%d-%b-%y")
                        match = re.search(r'(\d{1,2})[-/](\w{3})[-/]?(\d{0,4})', date_str, re.IGNORECASE)
                        if match:
                            day, month_name, year_suffix = match.groups()
                            if not year_suffix or len(year_suffix) < 2:
                                year_suffix = '25'
                            elif len(year_suffix) == 4:
                                year_suffix = year_suffix[2:]
                            day = day.zfill(2)
                            month_name = month_name.capitalize()
                            return f"{day}-{month_name}-{year_suffix}"
                    except Exception as e:
                        logging.warning(f"Could not normalize date '{date_str}': {e}")
                    return str(date_str)
                
                normalized_date = normalize_date_key_for_cleanup(date_added)
                
                # Find all brands that have this date in their daily_sales
                affected_brands = await collections.liquor_data.find({
                    "daily_sales." + normalized_date: {"$exists": True}
                }).to_list(10000)
                
                for brand in affected_brands:
                    # If already reverted by the loop above, skip
                    if brand.get("id") in brands_updated:
                        continue
                        
                    daily = brand.get('daily_sales', {})
                    if normalized_date in daily:
                        del daily[normalized_date]
                        update_fields = {"daily_sales": daily}
                        
                        # CRITICAL: If this was the DL_date, we MUST roll it back
                        if brand.get('DL_date') == date_added or brand.get('DL_date') == normalized_date:
                            if daily:
                                sorted_dates = sorted(daily.keys(), key=lambda x: parse_date(x), reverse=True)
                                new_dl = sorted_dates[0]
                                update_fields["DL_date"] = new_dl
                                update_fields["DL_stock"] = daily[new_dl]
                                update_fields["current_stock_qty"] = int(daily[new_dl])
                                # Recalculate stock value if rate is available
                                rate = brand.get('selling_rate', brand.get('rate', 0.0))
                                update_fields["stock_value_today"] = float(daily[new_dl] * rate)
                        
                        await collections.liquor_data.update_one({"_id": brand["_id"]}, {"$set": update_fields})
                        brands_reverted += 1
        
        elif upload_type == "full_monthly":
            # For Full Monthly upload, restore from backup
            backup_id = changes_snapshot.get("backup_id")
            
            if not backup_id:
                raise HTTPException(
                    status_code=400,
                    detail="No backup available for this upload. Cannot undo full monthly upload."
                )
            
            # Fetch the backup
            backup_record = await collections.stock_backups.find_one({
                "$or": [{"id": backup_id}, {"backup_id": backup_id}]
            })
            
            if not backup_record:
                raise HTTPException(
                    status_code=404,
                    detail=f"Backup {backup_id} not found. Cannot restore data."
                )
            
            restored_data = backup_record.get("data_snapshot", [])
            
            if not restored_data:
                raise HTTPException(
                    status_code=400,
                    detail="Backup contains no data. Cannot restore."
                )
            
            # Delete current data and restore from backup
            await collections.liquor_data.delete_many({})
            await collections.liquor_data.insert_many(restored_data)
            
            brands_reverted = len(restored_data)
            logging.info(f"Restored {brands_reverted} brands from backup {backup_id}")
        
        # Mark upload as undone
        await collections.upload_history.update_one(
            {"id": upload_id},
            {"$set": {"undone_at": datetime.now(timezone.utc)}}
        )
        
        # Build appropriate message based on upload type
        if upload_type == "full_monthly":
            message = f"Successfully undone upload. Restored {brands_reverted} brands from backup."
        else:
            message = f"Successfully undone upload. Reverted changes for {brands_reverted} brands and removed {brands_deleted} newly added brands."
        
        logging.info(f"Undone upload {upload_id}: Type={upload_type}, Reverted={brands_reverted}, Deleted={brands_deleted}")
        
        return {
            "success": True,
            "upload_id": upload_id,
            "upload_type": upload_type,
            "brands_reverted": brands_reverted,
            "brands_deleted": brands_deleted,
            "message": message
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error undoing upload: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error undoing upload: {str(e)}")

# Keep existing endpoints for backward compatibility
@api_router.post("/upload-data")
async def upload_liquor_data(file: UploadFile = File(...)):
    """Legacy upload endpoint - redirects to full monthly data upload"""
    return await upload_full_monthly_data(file)

@api_router.get("/analytics", response_model=AnalyticsResponse)
async def get_analytics(overstock_multiplier: float = 3.0):
    """Get comprehensive analytics including overstocking analysis with smart data source selection"""
    try:
        # STEP 1: Determine if we should use historical data
        use_historical, current_days = await should_use_historical_data()
        
        # STEP 2: Fetch appropriate data source
        if use_historical:
            # Use historical averages for projection
            liquor_records = await get_projected_data_from_historical()
            if not liquor_records:
                # Fallback to current data if no historical data available
                liquor_records = await collections.liquor_data.find().to_list(1000)
                use_historical = False
        else:
            # Use current month's actual data
            liquor_records = await collections.liquor_data.find().to_list(1000)
        
        if not liquor_records:
            raise HTTPException(status_code=404, detail="No data found. Please upload liquor data first.")
        
        # Convert to dict format for calculations
        data_dicts = [
            {
                'brand_name': record.get('brand_name', 'Unknown'),
                'rate': record.get('rate', record.get('selling_rate', 0.0)),
                'daily_sales': record.get('daily_sales', {}),
                'monthly_sale_qty': record.get('monthly_sale_qty', 0),
                'monthly_sale_value': record.get('monthly_sale_value', 0.0),
                'avg_daily_sale': record.get('avg_daily_sale', record.get('avg_daily_sales_qty', 0.0)),
                'stock_available_days': record.get('stock_available_days', 0.0),
                'stock_value_before': record.get('stock_value_before', 0.0),
                'stock_value_today': record.get('stock_value_today', 0.0),
                'stock_ratio': record.get('stock_ratio', 0.0)
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
        
        # Define date parsing function for chronological sorting
        def parse_date_for_sorting(date_str):
            """Parse various date formats for chronological sorting"""
            try:
                import re
                
                if not date_str:
                    return datetime.min
                
                date_str = str(date_str).strip()
                
                # Handle full datetime strings
                if 'T' in date_str or len(date_str) > 15:
                    try:
                        dt = datetime.fromisoformat(date_str.replace('T', ' ').replace('Z', ''))
                        return dt
                    except:
                        pass
                
                # Parse various date formats - handle dates with and without years
                # First try: dates with year (21-Sep-25, 01-Oct-25)
                match = re.search(r'(\d{1,2})[-/](\w{3})[-/](\d{2,4})', date_str, re.IGNORECASE)
                if match:
                    day, month_name, year = match.groups()
                    year = f"20{year}" if len(year) == 2 else year
                    full_date = f"{day}-{month_name}-{year}"
                    return datetime.strptime(full_date, "%d-%b-%Y")
                
                # Second try: dates without year (21-Sep, 22-Sep) - assume 2025
                match = re.search(r'(\d{1,2})[-/](\w{3})$', date_str, re.IGNORECASE)
                if match:
                    day, month_name = match.groups()
                    year = "2025"  # Default to 2025
                    full_date = f"{day}-{month_name}-{year}"
                    return datetime.strptime(full_date, "%d-%b-%Y")
                
                print(f"Warning: Could not parse date '{date_str}'")
                return datetime.min
                
            except Exception as e:
                print(f"Warning: Could not parse date '{date_str}': {e}")
                return datetime.min
        
        # Prepare sales trends data - Calculate actual DAILY SALES (units sold per day)
        # Instead of showing stock quantities, calculate sales from stock differences
        sales_trends = {}
        brands_processed = 0
        
        try:
            for record in data_dicts:
                daily_sales_dict = record.get('daily_sales', {}) or {}
                
                if not daily_sales_dict:
                    continue
                
                brands_processed += 1
                
                # Sort dates chronologically for this brand
                try:
                    sorted_dates = sorted(daily_sales_dict.keys(), key=lambda d: parse_date_for_sorting(d))
                except Exception as e:
                    logging.error(f"Error sorting dates for brand {record.get('brand_name')}: {e}")
                    continue
                
                for i, date in enumerate(sorted_dates):
                    try:
                        current_stock = daily_sales_dict[date]
                        
                        if i == 0:
                            # First date - no previous data, sales = 0
                            sales_qty = 0
                        else:
                            # Calculate sales as: previous_stock - current_stock
                            previous_date = sorted_dates[i-1]
                            previous_stock = daily_sales_dict[previous_date]
                            sales_qty = max(0, previous_stock - current_stock)  # Ensure non-negative
                        
                        # Aggregate sales across all brands for this date
                        if date not in sales_trends:
                            sales_trends[date] = 0
                        sales_trends[date] += sales_qty
                        
                    except Exception as e:
                        logging.error(f"Error calculating sales for date {date}: {e}")
                        continue
            
            logging.info(f"📊 Calculated sales trends for {len(sales_trends)} dates from {brands_processed} brands")
            
        except Exception as e:
            logging.error(f"Error in sales trends calculation: {e}", exc_info=True)
        
        # Sort by actual date values, not string comparison
        sorted_trends = dict(sorted(sales_trends.items(), key=lambda item: parse_date_for_sorting(item[0])))
        
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
        liquor_records = await collections.liquor_data.find().to_list(1000)
        return [LiquorData(**record) for record in liquor_records]
    except Exception as e:
        logging.error(f"Error fetching brands: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching brands: {str(e)}")

@api_router.get("/charts", response_model=ChartsResponse)
async def get_charts_data():
    """Get data for performance charts and visualizations"""
    try:
        liquor_records = await collections.liquor_data.find().to_list(1000)
        
        if not liquor_records:
            raise HTTPException(status_code=404, detail="No data found")
        
        # Convert to dict format for calculations
        data_dicts = [
            {
                'brand_name': record.get('brand_name', 'Unknown'),
                'rate': record.get('rate', record.get('selling_rate', 0.0)),
                'current_stock_qty': record.get('current_stock_qty', 0),
                'monthly_sale_value': record.get('monthly_sale_value', 0.0),
                'stock_value_today': record.get('stock_value_today', 0.0),
                'stock_available_days': record.get('stock_available_days', 0.0),
                'stock_ratio': record.get('stock_ratio', 0.0)
            }
            for record in liquor_records
        ]
        
        # Calculate total sales for proportion
        total_sales = sum(item['monthly_sale_value'] for item in data_dicts)
        
        # Volume Leaders (by current stock quantity)
        volume_leaders = sorted(data_dicts, key=lambda x: x.get('current_stock_qty', 0), reverse=True)[:10]
        volume_chart = [
            {
                'name': item['brand_name'][:20],  # Truncate long names
                'value': item.get('current_stock_qty', 0),
                'stock_value': item['stock_value_today']
            }
            for item in volume_leaders if item.get('current_stock_qty', 0) > 0
        ]
        
        # Velocity Leaders (by stock turnover rate)
        velocity_leaders = [item for item in data_dicts if item['stock_available_days'] > 0]
        velocity_leaders = sorted(velocity_leaders, key=lambda x: x['stock_available_days'])[:10]
        velocity_chart = [
            {
                'name': item['brand_name'],
                'velocity': round(30 / item['stock_available_days'], 2) if item['stock_available_days'] > 0 else 0,
                'days_of_stock': item['stock_available_days'],
                'sales_value': item['monthly_sale_value']
            }
            for item in velocity_leaders
        ]
        
        # Revenue Leaders (by estimated sales value)
        revenue_leaders = sorted(data_dicts, key=lambda x: x['monthly_sale_value'], reverse=True)[:10]
        revenue_chart = [
            {
                'name': item['brand_name'],
                'value': item['monthly_sale_value'],
                'stock_value': item['stock_value_today'],
                'stock_ratio': item['stock_ratio']
            }
            for item in revenue_leaders
        ]
        
        # Revenue Proportion (percentage of total estimated sales)
        revenue_proportion = [
            {
                'name': item['brand_name'],
                'value': item['monthly_sale_value'],
                'percentage': round((item['monthly_sale_value'] / total_sales) * 100, 2) if total_sales > 0 else 0,
                'stock_value': item['stock_value_today']
            }
            for item in revenue_leaders if item['monthly_sale_value'] > 0
        ]
        
        return ChartsResponse(
            volume_leaders=volume_chart,
            velocity_leaders=velocity_chart,
            revenue_leaders=revenue_chart,
            revenue_proportion=revenue_proportion
        )
        
    except Exception as e:
        logging.error(f"Error getting charts data: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting charts data: {str(e)}")

@api_router.get("/demand-recommendations")
async def get_demand_recommendations():
    """Get smart demand recommendations with historical data for zero D1 stock items"""
    try:
        liquor_records = await collections.liquor_data.find().to_list(1000)
        
        if not liquor_records:
            raise HTTPException(status_code=404, detail="No data found")
        
        # Fetch historical data from backups
        backups = await collections.stock_backups.find().sort("backup_timestamp", -1).limit(1).to_list(1)
        historical_data = {}
        
        if backups:
            latest_backup = backups[0]
            data_snapshot = latest_backup.get('data_snapshot', [])
            for hist_record in data_snapshot:
                brand_name = hist_record.get('brand_name')
                if brand_name:
                    historical_data[brand_name] = {
                        'monthly_sales_qty': hist_record.get('monthly_sales_qty', hist_record.get('monthly_sale_qty', 0)),
                        'avg_daily_sales_qty': hist_record.get('avg_daily_sales_qty', 0),
                        'total_sales_qty': hist_record.get('total_sales_qty', 0)
                    }
        
        recommendations = []
        
        for record in liquor_records:
            brand_name = record['brand_name']
            selling_rate = record.get('selling_rate', record['rate'])
            wholesale_rate = record.get('wholesale_rate', 0.0)
            current_stock_qty = record.get('current_stock_qty', 0) or 0
            stock_days = record.get('stock_available_days', 0) or 0
            monthly_sales_qty = record.get('monthly_sales_qty', record.get('monthly_sale_qty', 0)) or 0
            
            # Get D1 stock (stock on first day) - use the D1_stock field directly
            d1_stock = record.get('D1_stock', 0)
            
            # Distinguish between:
            # 1. D1=0 AND current_stock>0: Stock added mid-period (treat as regular item)
            # 2. D1=0 AND current_stock=0: Never stocked this period (use historical data)
            has_zero_d1_stock = d1_stock == 0 and current_stock_qty == 0
            was_added_mid_period = d1_stock == 0 and current_stock_qty > 0
            has_low_d1_stock = 0 < d1_stock < 5
            
            remarks = []
            data_source = "current"
            recommended_qty = 0
            urgency = "NONE"
            
            if was_added_mid_period:
                # Stock was added mid-period, not on D1
                # Treat as regular item with current period logic
                if monthly_sales_qty > 0:
                    recommended_qty = max(0, monthly_sales_qty - current_stock_qty)
                    if stock_days < 10:
                        urgency = "HIGH"
                    elif stock_days < 20:
                        urgency = "MEDIUM"
                    else:
                        urgency = "LOW"
                    # Only add remark if there's actual sales/recommendation
                    remarks.append(f"ℹ️ Stock added mid-period (not on D1), current stock: {current_stock_qty} units")
                # If no sales, don't include in recommendations (no recommended_qty, no remarks)
                
            elif has_zero_d1_stock:
                # Brand NOT stocked this period - use historical data for recommendation
                if brand_name in historical_data:
                    hist = historical_data[brand_name]
                    historical_monthly = hist.get('monthly_sales_qty', 0) or 0
                    avg_daily = hist.get('avg_daily_sales_qty', 0) or 0
                    
                    if historical_monthly > 0:
                        # Use historical sales to recommend quantity
                        recommended_qty = historical_monthly
                        data_source = "historical"
                        
                        # Prioritize based on historical demand
                        avg_daily = avg_daily or 0
                        if avg_daily >= 2.0:
                            urgency = "HIGH"
                            remarks.append("⚠️ Brand NOT stocked on D1 (stock was 0)")
                            remarks.append("📊 Using historical data for recommendation")
                            remarks.append(f"🔄 Previous period sales: {hist['total_sales_qty']} units")
                            remarks.append(f"📈 High demand: {round(avg_daily, 1)} units/day avg")
                            remarks.append("🎯 HIGH PRIORITY: Significant historical demand")
                        else:
                            urgency = "MEDIUM"
                            remarks.append("⚠️ Brand NOT stocked on D1 (stock was 0)")
                            remarks.append("📊 Using historical data for recommendation")
                            remarks.append(f"🔄 Previous period sales: {hist['total_sales_qty']} units")
                            remarks.append(f"📉 Moderate demand: {round(avg_daily, 1)} units/day avg")
                            remarks.append("⚖️ MODERATE PRIORITY: Low historical demand")
                    else:
                        # Historical data exists but no sales
                        urgency = "LOW"
                        remarks.append("⚠️ Brand NOT stocked on D1 (stock was 0)")
                        remarks.append("📊 Historical data shows no demand")
                        remarks.append("⬇️ LOW PRIORITY: No historical sales")
                        remarks.append("❓ Consider only for specific requirements")
                else:
                    # No historical data available
                    urgency = "LOW"
                    remarks.append("⚠️ Brand NOT stocked on D1 (stock was 0)")
                    remarks.append("❌ No historical data available")
                    remarks.append("📊 Brand not stocked in previous period")
                    remarks.append("⬇️ LOW PRIORITY: Stock only if specifically required")
                
            elif has_low_d1_stock:
                # Brand had very low starting stock
                if brand_name in historical_data:
                    hist = historical_data[brand_name]
                    hist_monthly = hist.get('monthly_sales_qty', 0) or 0
                    if hist_monthly > (monthly_sales_qty * 1.5):
                        remarks.append(f"⚠️ Low D1 stock ({d1_stock} units)")
                        remarks.append(f"📊 Historical demand: {hist['total_sales_qty']} units/period")
                        remarks.append("📈 Current period may underestimate demand")
                
                # Normal calculation for low D1 items
                if monthly_sales_qty > 0:
                    recommended_qty = max(0, monthly_sales_qty - current_stock_qty)
                    if stock_days < 10:
                        urgency = "HIGH"
                    elif stock_days < 20:
                        urgency = "MEDIUM"
                    else:
                        urgency = "LOW"
                        
            else:
                # Normal brand with D1 stock > 5
                if monthly_sales_qty > 0:
                    recommended_qty = max(0, monthly_sales_qty - current_stock_qty)
                    if stock_days < 10:
                        urgency = "HIGH"
                    elif stock_days < 20:
                        urgency = "MEDIUM"
                    elif stock_days < 30:
                        urgency = "LOW"
            
            # Include in recommendations if quantity needed OR has special remarks
            if recommended_qty > 0 or len(remarks) > 0:
                rec = DemandRecommendation(
                    brand_name=brand_name,
                    selling_rate=selling_rate,
                    wholesale_rate=round(wholesale_rate, 2),
                    current_stock_qty=current_stock_qty,
                    recommended_qty=recommended_qty,
                    urgency_level=urgency
                )
                
                rec_dict = rec.dict()
                rec_dict['remarks'] = remarks if remarks else None
                rec_dict['data_source'] = data_source
                rec_dict['d1_stock'] = d1_stock
                
                recommendations.append(rec_dict)
        
        # Sort: Regular stocked items first (by urgency), then never-stocked items at bottom
        def sort_key(x):
            # Only items that were NEVER stocked (D1=0 AND current=0) go to bottom
            was_never_stocked = x.get('d1_stock') == 0 and x.get('current_stock_qty') == 0
            urgency_order = {"HIGH": 1, "MEDIUM": 2, "LOW": 3, "NONE": 4}
            urgency_val = urgency_order.get(x['urgency_level'], 5)
            # Sort: never-stocked items go to bottom (was_never_stocked=1 sorts after =0)
            # Within each group, sort by urgency, then by recommended quantity
            # Safely handle None values in recommended_qty
            recommended_qty = x.get('recommended_qty') or 0
            return (was_never_stocked, urgency_val, -recommended_qty)
        
        recommendations.sort(key=sort_key)
        
        return recommendations
        
    except Exception as e:
        logging.error(f"Error generating demand recommendations: {e}")
        raise HTTPException(status_code=500, detail=f"Error generating recommendations: {str(e)}")

@api_router.delete("/clear-data")
async def clear_all_data():
    """Clear all liquor data to force re-upload with corrected D1/DL logic"""
    try:
        result = await collections.liquor_data.delete_many({})
        return {"message": f"Cleared {result.deleted_count} records. Please re-upload your data to apply corrected D1/DL calculations."}
    except Exception as e:
        logging.error(f"Error clearing data: {e}")
        raise HTTPException(status_code=500, detail=f"Error clearing data: {str(e)}")

@api_router.get("/database-view")
async def get_database_view():
    """Get complete raw database view for debugging and transparency"""
    try:
        # Get all records with all fields
        all_records = await collections.liquor_data.find().to_list(1000)
        
        if not all_records:
            return {
                "total_records": 0,
                "data": [],
                "summary": {
                    "message": "Database is empty",
                    "unique_dates": [],
                    "date_range": None
                }
            }
        
        # Extract summary information
        all_dates = set()
        d1_dates = set()
        dl_dates = set()
        
        for record in all_records:
            # Collect D1 dates
            if record.get('D1_date'):
                d1_dates.add(str(record['D1_date']))
            
            # Collect DL dates
            if record.get('DL_date'):
                dl_dates.add(str(record['DL_date']))
            
            # Collect daily_sales dates
            daily_sales = record.get('daily_sales', {}) or {}
            if daily_sales:
                for date_key in daily_sales.keys():
                    all_dates.add(str(date_key))
        
        # Prepare clean data for frontend (remove MongoDB ObjectId if present)
        clean_data = []
        for record in all_records:
            clean_record = {}
            for key, value in record.items():
                if key != '_id':  # Skip MongoDB ObjectId
                    clean_record[key] = value
            clean_data.append(clean_record)
        
        # Sort by index_number if available
        try:
            clean_data.sort(key=lambda x: x.get('index_number', 9999))
        except:
            pass
        
        return {
            "total_records": len(all_records),
            "data": clean_data,
            "summary": {
                "unique_d1_dates": sorted(list(d1_dates)),
                "unique_dl_dates": sorted(list(dl_dates)),
                "unique_daily_sales_dates": sorted(list(all_dates)),
                "total_brands": len(all_records),
                "date_range": f"{min(d1_dates)} to {max(dl_dates)}" if d1_dates and dl_dates else None,
                "sample_record_fields": list(all_records[0].keys()) if all_records else []
            }
        }
        
    except Exception as e:
        logging.error(f"Error getting database view: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching database view: {str(e)}")

@api_router.get("/sales-trends")
async def get_sales_trends(period: str = "quarterly", sales_month: Optional[str] = None):
    """
    Get sales trends with D1-DL sales periods from current AND historical data.
    Handles brand additions/removals, mid-month restock periods, and date normalization.
    """
    try:
        from collections import defaultdict
        from utils.date_helper import parse_date, normalize_date_key
        
        def parse_dt(date_str):
            """Parse date string to datetime, returns None on failure"""
            if not date_str or date_str == 'N/A':
                return None
            dt = parse_date(date_str)
            return dt if dt != datetime.min else None

        def normalize_daily_sales(daily_sales_dict):
            """Normalize all date keys in a daily_sales dict to DD-MMM-YY format.
            Merges duplicates (e.g. '2026-04-25 00:00:00' and '25-Apr-26')."""
            if not daily_sales_dict:
                return {}
            normalized = {}
            for raw_key, value in daily_sales_dict.items():
                norm_key = normalize_date_key(raw_key)
                # If duplicate after normalization, keep the one we already have
                if norm_key not in normalized:
                    normalized[norm_key] = value
            return normalized

        def get_period_label(d1_dt, dl_dt):
            """Generate period label like 'Mar-Apr 2026' from D1 and DL datetimes"""
            if not d1_dt or not dl_dt:
                return "Unknown Period"
            d1_month = d1_dt.strftime("%b")
            dl_month = dl_dt.strftime("%b")
            year = dl_dt.strftime("%Y")
            if d1_month == dl_month:
                return f"{d1_month} {year}"
            return f"{d1_month}-{dl_month} {year}"

        def filter_dates_in_range(daily_sales, d1_dt, dl_dt):
            """Remove daily_sales entries that fall outside the D1-DL date range.
            This prevents corrupt entries like '26-Apr-27' (2027) from appearing."""
            if not d1_dt or not dl_dt:
                return daily_sales
            filtered = {}
            # Allow 1 day buffer on each side for timezone edge cases
            range_start = d1_dt - timedelta(days=1)
            range_end = dl_dt + timedelta(days=1)
            for key, value in daily_sales.items():
                dt = parse_dt(key)
                if dt and range_start <= dt <= range_end:
                    filtered[key] = value
                elif dt:
                    logging.debug(f"Filtered out date {key} ({dt}) outside range {d1_dt}-{dl_dt}")
            return filtered

        def compute_daily_sales_for_records(records, period_d1, period_dl):
            """Calculate per-day total sales across all brands, 
            normalizing dates and filtering to period range."""
            daily_sales_by_date = defaultdict(float)
            all_dates = set()
            
            for record in records:
                raw_daily = record.get('daily_sales', {}) or {}
                if not raw_daily:
                    continue
                
                # Step 1: Normalize date keys
                daily_sales = normalize_daily_sales(raw_daily)
                
                # Step 2: Filter to period range
                daily_sales = filter_dates_in_range(daily_sales, period_d1, period_dl)
                
                if not daily_sales:
                    continue
                
                # Step 3: Sort dates for this brand and calculate per-brand sales
                brand_dates = sorted(daily_sales.keys(), key=lambda d: parse_dt(d) or datetime.min)
                all_dates.update(brand_dates)
                
                for i in range(1, len(brand_dates)):
                    curr_d = brand_dates[i]
                    prev_d = brand_dates[i-1]
                    sale = max(0, daily_sales[prev_d] - daily_sales[curr_d])
                    daily_sales_by_date[curr_d] += sale
            
            # Build chart data points sorted chronologically
            sorted_dates = sorted(list(all_dates), key=lambda d: parse_dt(d) or datetime.min)
            day_data = []
            for day_num, date_str in enumerate(sorted_dates, start=1):
                dt = parse_dt(date_str)
                day_data.append({
                    "day": day_num,
                    "date": dt.strftime("%d-%b") if dt else date_str,
                    "sales": round(daily_sales_by_date.get(date_str, 0), 2)
                })
            
            return day_data

        # ============================================================
        # 1. CURRENT PERIOD - all data in liquor_data is one period
        # ============================================================
        current_data = await collections.liquor_data.find().to_list(10000)
        
        period_to_data = {}
        period_info = {}
        
        if current_data:
            global_d1 = None
            global_dl = None
            
            for record in current_data:
                d1 = parse_dt(record.get('D1_date'))
                dl = parse_dt(record.get('DL_date'))
                if d1:
                    global_d1 = d1 if global_d1 is None else min(global_d1, d1)
                if dl:
                    global_dl = dl if global_dl is None else max(global_dl, dl)
            
            if global_d1 and global_dl:
                current_label = get_period_label(global_d1, global_dl)
                period_to_data[current_label] = current_data
                period_info[current_label] = {
                    'd1': global_d1,
                    'dl': global_dl,
                    'd1_str': global_d1.strftime("%d-%b-%y"),
                    'dl_str': global_dl.strftime("%d-%b-%y"),
                    'source': 'current'
                }

        # ============================================================
        # 2. HISTORICAL PERIODS from backups
        #    Include BOTH pre_reset_backup AND auto_reset_on_purchase
        # ============================================================
        backups = await collections.stock_backups.find({
            "backup_reason": {"$in": ["pre_reset_backup", "auto_reset_on_purchase"]}
        }).sort("backup_timestamp", -1).to_list(100)
        
        for backup in backups:
            data_snapshot = backup.get('data_snapshot', [])
            if not data_snapshot:
                continue
            
            # Compute global D1/DL for this backup
            b_d1, b_dl = None, None
            for record in data_snapshot:
                d1 = parse_dt(record.get('D1_date'))
                dl = parse_dt(record.get('DL_date'))
                if d1:
                    b_d1 = d1 if b_d1 is None else min(b_d1, d1)
                if dl:
                    b_dl = dl if b_dl is None else max(b_dl, dl)
            
            if b_d1 and b_dl:
                b_label = get_period_label(b_d1, b_dl)
                
                # Skip if already covered by current data or a more recent backup
                if b_label in period_to_data:
                    continue
                
                period_to_data[b_label] = data_snapshot
                period_info[b_label] = {
                    'd1': b_d1,
                    'dl': b_dl,
                    'd1_str': b_d1.strftime("%d-%b-%y"),
                    'dl_str': b_dl.strftime("%d-%b-%y"),
                    'source': 'historical'
                }

        # ============================================================
        # 3. Calculate daily sales for each period
        # ============================================================
        period_trends = {}
        
        for label, records in period_to_data.items():
            info = period_info[label]
            day_data = compute_daily_sales_for_records(records, info['d1'], info['dl'])
            if day_data:
                period_trends[label] = day_data

        # ============================================================
        # 4. Sort and select periods
        # ============================================================
        sorted_keys = sorted(
            period_trends.keys(),
            key=lambda k: period_info[k]['d1'] if k in period_info else datetime.min
        )
        
        if period == "quarterly":
            selected_keys = sorted_keys[-3:]
        elif period == "yearly":
            selected_keys = sorted_keys[-12:]
        elif period == "single" and sales_month:
            selected_keys = [sales_month] if sales_month in period_trends else []
        else:
            selected_keys = sorted_keys[-3:]

        # ============================================================
        # 5. Build response
        # ============================================================
        final_series = []
        for key in selected_keys:
            if key not in period_info or key not in period_trends:
                continue
            
            records = period_to_data[key]
            total_sales_period = sum(r.get('total_sales_qty', 0) for r in records)
            
            final_series.append({
                "month": key,
                "data": period_trends[key],
                "d1_date": period_info[key]['d1_str'],
                "dl_date": period_info[key]['dl_str'],
                "total_sales": round(total_sales_period, 2)
            })

        total_sales_all = sum(s["total_sales"] for s in final_series)
        
        # available_months for Single Period dropdown
        all_available = sorted(
            period_trends.keys(),
            key=lambda k: period_info[k]['d1'] if k in period_info else datetime.min
        )
        
        return {
            "series": final_series,
            "total_sales": round(total_sales_all, 2),
            "period_type": period,
            "available_months": all_available,
            "summary": {
                "total_sales": round(total_sales_all, 2),
                "periods_count": len(final_series)
            }
        }
        
    except Exception as e:
        logging.error(f"Error in get_sales_trends: {e}")
        logging.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/admin/debug-sales-periods")
async def debug_sales_periods():
    """Diagnostic endpoint to see what periods exist in backups and current data"""
    try:
        from utils.date_helper import parse_date
        
        def parse_dt(date_str):
            dt = parse_date(date_str)
            return dt if dt != datetime.min else None
        
        result = {"current_period": None, "backup_periods": [], "raw_backup_info": []}
        
        # 1. Current data analysis
        current_data = await collections.liquor_data.find().to_list(10000)
        if current_data:
            all_d1 = []
            all_dl = []
            all_daily_dates = set()
            for rec in current_data:
                d1 = parse_dt(rec.get('D1_date'))
                dl = parse_dt(rec.get('DL_date'))
                if d1: all_d1.append(d1)
                if dl: all_dl.append(dl)
                ds = rec.get('daily_sales', {}) or {}
                all_daily_dates.update(ds.keys())
            
            result["current_period"] = {
                "brand_count": len(current_data),
                "global_D1": min(all_d1).strftime("%d-%b-%Y") if all_d1 else None,
                "global_DL": max(all_dl).strftime("%d-%b-%Y") if all_dl else None,
                "unique_D1_dates": sorted(set(d.strftime("%d-%b-%Y") for d in all_d1)),
                "unique_DL_dates": sorted(set(d.strftime("%d-%b-%Y") for d in all_dl)),
                "all_daily_sales_dates": sorted(list(all_daily_dates)),
                "total_daily_dates": len(all_daily_dates)
            }
        
        # 2. Backup analysis
        backups = await collections.stock_backups.find().sort("backup_timestamp", -1).to_list(100)
        for backup in backups:
            snapshot = backup.get('data_snapshot', [])
            b_d1_list = []
            b_dl_list = []
            b_daily_dates = set()
            for rec in snapshot:
                d1 = parse_dt(rec.get('D1_date'))
                dl = parse_dt(rec.get('DL_date'))
                if d1: b_d1_list.append(d1)
                if dl: b_dl_list.append(dl)
                ds = rec.get('daily_sales', {}) or {}
                b_daily_dates.update(ds.keys())
            
            min_d1 = min(b_d1_list).strftime("%d-%b-%Y") if b_d1_list else None
            max_dl = max(b_dl_list).strftime("%d-%b-%Y") if b_dl_list else None
            
            result["raw_backup_info"].append({
                "backup_id": backup.get('id'),
                "backup_reason": backup.get('backup_reason'),
                "backup_timestamp": str(backup.get('backup_timestamp')),
                "record_count": len(snapshot),
                "computed_D1": min_d1,
                "computed_DL": max_dl,
                "daily_sales_dates": sorted(list(b_daily_dates)),
                "unique_D1_dates": sorted(set(d.strftime("%d-%b-%Y") for d in b_d1_list)) if b_d1_list else [],
                "unique_DL_dates": sorted(set(d.strftime("%d-%b-%Y") for d in b_dl_list)) if b_dl_list else []
            })
        
        return result
        
    except Exception as e:
        logging.error(f"Error in debug-sales-periods: {e}")
        logging.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/refresh-analytics")
async def refresh_analytics():
    """Force refresh of all analytics calculations"""
    try:
        # Get all records
        all_records = await collections.liquor_data.find().to_list(1000)
        
        if not all_records:
            raise HTTPException(status_code=404, detail="No data found to refresh")
        
        updated_count = 0
        
        # Find the current D1 and DL dates from the data
        d1_dates = set()
        dl_dates = set()
        
        for record in all_records:
            if record.get('D1_date'):
                d1_dates.add(record['D1_date'])
            if record.get('DL_date'):
                dl_dates.add(record['DL_date'])
        
        print(f"📊 Refreshing analytics for {len(all_records)} records")
        print(f"   D1 dates found: {sorted(d1_dates)}")
        print(f"   DL dates found: {sorted(dl_dates)}")
        
        # Recalculate analytics for each record
        for record in all_records:
            try:
                # Use existing values or recalculate if needed
                D1_stock = record.get('D1_stock', 0)
                DL_stock = record.get('DL_stock', 0)
                selling_rate = record.get('selling_rate', record.get('rate', 0))
                days_analyzed = record.get('days_analyzed', 1)
                
                # Recalculate derived values
                total_sales_qty = max(0, D1_stock - DL_stock)
                avg_daily_sales_qty = total_sales_qty / max(1, days_analyzed)
                monthly_sales_qty = avg_daily_sales_qty * 24
                monthly_sales_value = monthly_sales_qty * selling_rate
                current_stock_value = DL_stock * selling_rate
                stock_ratio = current_stock_value / max(1, monthly_sales_value) if monthly_sales_value > 0 else 0
                stock_available_days = (DL_stock / max(0.1, avg_daily_sales_qty)) if avg_daily_sales_qty > 0 else 999
                
                # Update record with recalculated values
                update_data = {
                    "total_sales_qty": float(total_sales_qty),
                    "avg_daily_sales_qty": float(avg_daily_sales_qty),
                    "monthly_sales_qty": float(monthly_sales_qty),
                    "monthly_sale_qty": int(monthly_sales_qty),
                    "monthly_sale_value": float(monthly_sales_value),
                    "stock_value_today": float(current_stock_value),
                    "stock_ratio": float(stock_ratio),
                    "stock_available_days": float(min(999, max(0, stock_available_days))),
                    "avg_daily_sale": float(monthly_sales_value / 30),
                    "upload_timestamp": datetime.now(timezone.utc)
                }
                
                await collections.liquor_data.update_one(
                    {"_id": record["_id"]}, 
                    {"$set": update_data}
                )
                updated_count += 1
                
            except Exception as e:
                print(f"Warning: Error updating {record.get('brand_name', 'Unknown')}: {e}")
                continue
        
        print(f"✅ Successfully refreshed {updated_count} records")
        
        return {
            "message": f"Successfully refreshed analytics for {updated_count} records",
            "updated_records": updated_count,
            "d1_dates": sorted(list(d1_dates)),
            "dl_dates": sorted(list(dl_dates))
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error refreshing analytics: {e}")
        raise HTTPException(status_code=500, detail=f"Error refreshing analytics: {str(e)}")

@api_router.get("/calculation-details")
async def get_calculation_details():
    """Get detailed calculations for all brands for verification"""
    try:
        liquor_records = await collections.liquor_data.find().to_list(1000)
        
        if not liquor_records:
            raise HTTPException(status_code=404, detail="No data found")
        
        calculation_details = []
        
        for record in liquor_records:
            # Calculate multiplier value (current stock value / monthly sales value)
            current_stock_value = record.get('stock_value_today', 0)
            monthly_sales_value = record.get('monthly_sale_value', 0)
            multiplier_value = current_stock_value / max(1, monthly_sales_value) if monthly_sales_value > 0 else 0
            
            detail = {
                'index': record.get('index_number', record.get('product_id', 'N/A')),
                'brand_name': record['brand_name'],
                'calculated_wholesale_rate': record.get('wholesale_rate', 0),
                'selling_rate': record.get('selling_rate', record.get('rate', 0)),
                'calculated_avg_monthly_sale': record.get('monthly_sale_value', 0),
                'calculated_current_stock_value': current_stock_value,
                'calculated_multiplier_value': round(multiplier_value, 3),
                # Additional useful fields for verification - use actual stored values
                'D1_date': record.get('D1_date', 'N/A'),
                'D1_stock': record.get('D1_stock', 0),
                'DL_date': record.get('DL_date', 'N/A'), 
                'DL_stock': record.get('DL_stock', 0),
                'total_sales_qty': record.get('total_sales_qty', 0),
                'avg_daily_sales_qty': record.get('avg_daily_sales_qty', 0),
                'days_analyzed': record.get('days_analyzed', 0),
                'stock_available_days': record.get('stock_available_days', 0)
            }
            
            calculation_details.append(detail)
        
        # Sort by index number
        def sort_key(x):
            idx_str = str(x['index'])
            try:
                # Try to extract number from index
                import re
                match = re.search(r'\d+', idx_str)
                return int(match.group()) if match else 999
            except:
                return 999
        
        calculation_details.sort(key=sort_key)
        
        return calculation_details
        
    except Exception as e:
        logging.error(f"Error getting calculation details: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting calculation details: {str(e)}")

@api_router.get("/export-demand-list")
async def export_demand_list():
    """Export demand recommendations with updated format"""
    try:
        # Get recommendations
        recommendations_data = await get_demand_recommendations()
        
        if not recommendations_data:
            raise HTTPException(status_code=404, detail="No recommendations to export")
        
        # Get all liquor records to match with recommendations for correct index and monthly sale data
        liquor_records = await collections.liquor_data.find().to_list(1000)
        
        # Create a lookup dictionary for brand data by brand name
        brand_lookup = {record['brand_name']: record for record in liquor_records}
        
        # Convert to updated DataFrame format with correct indexes and monthly sales
        df_data = []
        total_wholesale_cost = 0
        total_quantity_in_stock = 0
        total_quantity_demanded = 0
        total_projected_monthly_sale = 0
        total_cases_demanded = 0
        
        for rec in recommendations_data:
            # Handle both dict and object access
            brand_name = rec.get('brand_name') if isinstance(rec, dict) else rec.brand_name
            recommended_qty = rec.get('recommended_qty') if isinstance(rec, dict) else rec.recommended_qty
            wholesale_rate = rec.get('wholesale_rate') if isinstance(rec, dict) else rec.wholesale_rate
            current_stock_qty = rec.get('current_stock_qty') if isinstance(rec, dict) else rec.current_stock_qty
            
            # Get the original brand record to find the correct index and monthly sales
            brand_record = brand_lookup.get(brand_name)
            
            if brand_record:
                # Use the original index from the brand record
                original_index = brand_record.get('index_number', 'N/A')
                projected_monthly_sale_qty = brand_record.get('monthly_sales_qty', brand_record.get('monthly_sale_qty', 0))
            else:
                original_index = 'N/A'
                projected_monthly_sale_qty = 0
            
            # Calculate number of cases needed (1 case = 12 units, round up to get whole cases)
            import math
            cases_demanded = math.ceil(recommended_qty / 12) if recommended_qty > 0 else 0
            
            # Calculate totals for the summary row
            wholesale_cost_for_demand = wholesale_rate * recommended_qty
            total_wholesale_cost += wholesale_cost_for_demand
            total_quantity_in_stock += current_stock_qty
            total_quantity_demanded += recommended_qty
            total_projected_monthly_sale += projected_monthly_sale_qty
            total_cases_demanded += cases_demanded
            
            df_data.append({
                'Index': original_index,
                'Brand Name': brand_name,
                'Wholesale Rate': wholesale_rate,
                'Projected Monthly Sale (Qty)': int(round(projected_monthly_sale_qty, 0)),
                'Quantity held in Stock': current_stock_qty,
                'Quantity to be Demanded': recommended_qty,
                'Number of Cases to be Demanded': cases_demanded
            })
        
        # Add total row
        df_data.append({
            'Index': 'TOTAL',
            'Brand Name': f'({len(recommendations_data)} brands)',
            'Wholesale Rate': f'Cost: {round(total_wholesale_cost, 2)}',
            'Projected Monthly Sale (Qty)': int(round(total_projected_monthly_sale, 0)),
            'Quantity held in Stock': total_quantity_in_stock,
            'Quantity to be Demanded': total_quantity_demanded,
            'Number of Cases to be Demanded': total_cases_demanded
        })
        
        df = pd.DataFrame(df_data)
        
        # Create Excel file in memory
        from io import BytesIO
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Demand Forecast', index=False)
            
            # Get workbook and worksheet
            workbook = writer.book
            worksheet = writer.sheets['Demand Forecast']
            
            # Auto-adjust column widths for the new 7-column format
            column_widths = {'A': 10, 'B': 30, 'C': 16, 'D': 18, 'E': 18, 'F': 20, 'G': 22}
            for column_letter, width in column_widths.items():
                worksheet.column_dimensions[column_letter].width = width
            
            # Style headers
            from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
            header_font = Font(bold=True, color="FFFFFF")
            header_fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
            
            # Style the header row
            for col in range(1, 8):  # 7 columns now
                cell = worksheet.cell(row=1, column=col)
                cell.font = header_font
                cell.fill = header_fill
                cell.alignment = Alignment(horizontal="center")
            
            # Style the total row (last row)
            total_row = len(df_data)
            total_font = Font(bold=True)
            total_fill = PatternFill(start_color="E8F4FD", end_color="E8F4FD", fill_type="solid")
            border = Border(
                top=Side(border_style="thick", color="366092"),
                bottom=Side(border_style="thick", color="366092"),
                left=Side(border_style="thin", color="366092"),
                right=Side(border_style="thin", color="366092")
            )
            
            for col in range(1, 8):  # 7 columns now
                cell = worksheet.cell(row=total_row + 1, column=col)  # +1 because of header
                cell.font = total_font
                cell.fill = total_fill
                cell.border = border
                cell.alignment = Alignment(horizontal="center")
        
        output.seek(0)
        
        from fastapi.responses import Response
        
        return Response(
            content=output.getvalue(),
            media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            headers={
                'Content-Disposition': f'attachment; filename=liquor_demand_forecast_{datetime.now().strftime("%Y%m%d")}.xlsx'
            }
        )
        
    except Exception as e:
        logging.error(f"Error exporting demand list: {e}")
        raise HTTPException(status_code=500, detail=f"Error exporting demand list: {str(e)}")

# ========================================
# MODULE 1: Brand & Rate Management APIs
# ========================================

@api_router.post("/brands/add")
async def add_brand_manually(brand: AddBrandRequest):
    """Add a new brand manually with rates and initial stock"""
    try:
        # Check if brand with same index already exists
        existing_brand = await collections.liquor_data.find_one({"index_number": brand.index_number})
        if existing_brand:
            raise HTTPException(
                status_code=400, 
                detail=f"Brand with index {brand.index_number} already exists: {existing_brand['brand_name']}"
            )
        
        # Check if brand name already exists
        existing_name = await collections.liquor_data.find_one({"brand_name": brand.brand_name})
        if existing_name:
            raise HTTPException(
                status_code=400, 
                detail=f"Brand name '{brand.brand_name}' already exists with index {existing_name.get('index_number', 'N/A')}"
            )
        
        # Create new brand record with minimal data
        new_brand = LiquorData(
            brand_name=brand.brand_name,
            index_number=brand.index_number,
            wholesale_rate=brand.wholesale_rate,
            selling_rate=brand.selling_rate,
            rate=brand.selling_rate,  # For compatibility
            current_stock_qty=brand.initial_stock_qty,
            D1_stock=float(brand.initial_stock_qty),
            DL_stock=float(brand.initial_stock_qty),
            stock_value_today=brand.selling_rate * brand.initial_stock_qty,
            stock_value_before=brand.selling_rate * brand.initial_stock_qty,
            # Set defaults for calculated fields
            daily_sales={},
            monthly_sale_qty=0,
            monthly_sale_value=0.0,
            avg_daily_sale=0.0,
            stock_available_days=999.0,
            stock_ratio=0.0,
            total_sales_qty=0.0,
            avg_daily_sales_qty=0.0,
            days_analyzed=0,
            D1_date="N/A",
            DL_date="N/A",
            upload_timestamp=datetime.now(timezone.utc)
        )
        
        # Insert into database
        await collections.liquor_data.insert_one(new_brand.dict())
        
        logging.info(f"Successfully added new brand: {brand.brand_name} (Index: {brand.index_number})")
        
        return JSONResponse(
            status_code=201,
            content={
                "message": f"Successfully added brand: {brand.brand_name}",
                "brand": {
                    "index_number": brand.index_number,
                    "brand_name": brand.brand_name,
                    "wholesale_rate": brand.wholesale_rate,
                    "selling_rate": brand.selling_rate,
                    "initial_stock_qty": brand.initial_stock_qty
                }
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error adding brand: {e}")
        raise HTTPException(status_code=500, detail=f"Error adding brand: {str(e)}")

@api_router.get("/brands/rates")
async def get_all_brand_rates():
    """Get all brands with their current rates and stock information"""
    try:
        # Fetch all liquor data sorted by index
        liquor_records = await collections.liquor_data.find().sort("index_number", 1).to_list(1000)
        
        if not liquor_records:
            return []
        
        # Format response
        brand_rates = []
        for record in liquor_records:
            brand_rates.append({
                "id": record.get("id", str(record.get("_id", ""))),
                "index_number": record.get("index_number", 0),
                "brand_name": record.get("brand_name", ""),
                "wholesale_rate": record.get("wholesale_rate", 0.0),
                "selling_rate": record.get("selling_rate", record.get("rate", 0.0)),
                "current_stock_qty": record.get("current_stock_qty", 0),
                "stock_value_today": record.get("stock_value_today", 0.0),
                "last_updated": record.get("upload_timestamp", datetime.now(timezone.utc))
            })
        
        return brand_rates
        
    except Exception as e:
        logging.error(f"Error fetching brand rates: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching brand rates: {str(e)}")

@api_router.post("/brands/update-rates")
async def update_rates_from_excel(file: UploadFile = File(...)):
    """Upload Excel file to update wholesale and retail rates for existing brands"""
    try:
        # Validate file type
        if not file.filename or not file.filename.endswith(('.xlsx', '.xls', '.csv')):
            raise HTTPException(
                status_code=400, 
                detail="Only Excel (.xlsx, .xls) and CSV files are supported"
            )
        
        # Read file content
        content = await file.read()
        
        if len(content) == 0:
            raise HTTPException(status_code=400, detail="Empty file uploaded")
        
        # Parse Excel file
        try:
            df = pd.read_excel(io.BytesIO(content))
        except Exception:
            try:
                df = pd.read_csv(io.BytesIO(content))
            except Exception as e:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Unable to parse file. Error: {str(e)}"
                )
        
        # Clean column names
        df.columns = df.columns.str.strip().str.lower()
        
        # Expected columns: index, brand name, wholesale rate, retail rate
        required_cols = ['index', 'brand name', 'wholesale rate', 'retail rate']
        missing_cols = []
        
        # Flexible column matching
        col_mapping = {}
        for req_col in required_cols:
            found = False
            for df_col in df.columns:
                if req_col.replace(' ', '') in df_col.replace(' ', ''):
                    col_mapping[req_col] = df_col
                    found = True
                    break
            if not found:
                missing_cols.append(req_col)
        
        if missing_cols:
            raise HTTPException(
                status_code=400,
                detail=f"Missing required columns: {', '.join(missing_cols)}. Expected: Index, Brand Name, Wholesale Rate, Retail Rate"
            )
        
        # Process updates
        updated_brands = []
        not_found_brands = []
        updated_count = 0
        
        for idx, row in df.iterrows():
            try:
                index_num = int(float(row[col_mapping['index']]))
                brand_name = str(row[col_mapping['brand name']]).strip()
                wholesale_rate = float(row[col_mapping['wholesale rate']])
                retail_rate = float(row[col_mapping['retail rate']])
                
                # Find brand by index number (primary) or brand name (fallback)
                brand_record = await collections.liquor_data.find_one({"index_number": index_num})
                
                if not brand_record:
                    # Try finding by name
                    brand_record = await collections.liquor_data.find_one({"brand_name": brand_name})
                
                # ALWAYS save/update to brands_master for persistence across resets
                existing_master = await collections.brands_master.find_one({"brand_name": brand_name})
                
                if existing_master:
                    # Update existing master record
                    await collections.brands_master.update_one(
                        {"id": existing_master["id"]},
                        {"$set": {
                            "wholesale_rate": wholesale_rate,
                            "selling_rate": retail_rate,
                            "index_number": index_num,
                            "last_updated": datetime.now(timezone.utc)
                        }}
                    )
                else:
                    # Create new master record
                    brand_master = BrandMaster(
                        brand_name=brand_name,
                        wholesale_rate=wholesale_rate,
                        selling_rate=retail_rate,
                        index_number=index_num
                    )
                    await collections.brands_master.insert_one(brand_master.dict())
                
                if brand_record:
                    # Update rates in current liquor_data and recalculate stock values
                    current_stock_qty = brand_record.get('current_stock_qty', 0)
                    
                    update_data = {
                        "wholesale_rate": wholesale_rate,
                        "selling_rate": retail_rate,
                        "rate": retail_rate,  # For compatibility
                        "stock_value_today": retail_rate * current_stock_qty,
                        "stock_value_before": brand_record.get('D1_stock', 0) * retail_rate,
                        "upload_timestamp": datetime.now(timezone.utc)
                    }
                    
                    # Recalculate monthly sale value if needed
                    if brand_record.get('monthly_sale_qty', 0) > 0:
                        update_data['monthly_sale_value'] = brand_record['monthly_sale_qty'] * retail_rate
                        update_data['avg_daily_sale'] = update_data['monthly_sale_value'] / 30
                    
                    await collections.liquor_data.update_one(
                        {"_id": brand_record["_id"]},
                        {"$set": update_data}
                    )
                    
                    updated_brands.append(brand_name)
                    updated_count += 1
                else:
                    # Brand not in current database, but rates saved to master
                    not_found_brands.append(f"{brand_name} (Index: {index_num}) - Rates saved for future use")
                    
            except Exception as row_error:
                logging.warning(f"Error processing row {idx}: {row_error}")
                continue
        
        return UpdateRatesResponse(
            updated_count=updated_count,
            not_found_count=len(not_found_brands),
            updated_brands=updated_brands,
            not_found_brands=not_found_brands
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error updating rates: {e}")
        raise HTTPException(status_code=500, detail=f"Error updating rates: {str(e)}")

# ========================================
# MODULE 2: Upload History Auto-Cleanup (60 days)
# ========================================

@api_router.delete("/upload-history/{upload_id}")
async def delete_upload_history(upload_id: str, revert_data: bool = True):
    """
    Delete a specific upload history record and optionally revert the data changes.
    
    Args:
        upload_id: The ID of the upload to delete
        revert_data: If True, reverts the data changes made by this upload (default: True)
    
    This endpoint will:
    1. Revert the data changes (restore previous state or clear current data)
    2. Delete the upload history record
    3. Delete the associated backup
    """
    try:
        # Find the upload history record
        upload_record = await collections.upload_history.find_one({"id": upload_id})
        
        if not upload_record:
            raise HTTPException(status_code=404, detail="Upload history record not found")
        
        upload_type = upload_record.get("upload_type")
        changes_snapshot = upload_record.get("changes_snapshot", {})
        brands_reverted = 0
        brands_deleted = 0
        data_reverted = False
        
        # STEP 1: Revert data changes if requested
        if revert_data and not upload_record.get("undone_at"):
            logging.info(f"Reverting data changes for upload {upload_id} (type: {upload_type})")
            
            if upload_type in ["daily_update", "daily", "restock"]:
                # Revert daily update changes
                brands_updated = changes_snapshot.get("brands_updated", {})
                brands_added = changes_snapshot.get("brands_added", [])
                date_added = changes_snapshot.get("date_added")  # Get the date that was added
                
                # Get total count of brands in database for verification
                total_brands_in_db = await collections.liquor_data.count_documents({})
                logging.info(f"Reverting daily update: {len(brands_updated)} brands to restore (out of {total_brands_in_db} total), date_added: {date_added}")
                
                # Restore previous state for updated brands
                for brand_id, previous_state in brands_updated.items():
                    if previous_state:
                        # Build update operation
                        update_data = {}
                        for field in ["DL_date", "DL_stock", "current_stock_qty", 
                                      "days_analyzed", "total_sales_qty", "avg_daily_sales_qty",
                                      "monthly_sales_qty", "monthly_sale_qty", "monthly_sale_value",
                                      "stock_value_today", "stock_available_days", "stock_ratio"]:
                            value = previous_state.get(field)
                            if value is not None:
                                update_data[field] = value
                        
                        # Restore previous daily_sales (which already has the deleted date removed)
                        # The changes_snapshot captured daily_sales BEFORE the new date was added
                        daily_sales_value = previous_state.get("daily_sales")
                        if daily_sales_value is not None:
                            update_data["daily_sales"] = daily_sales_value if isinstance(daily_sales_value, dict) else {}
                            logging.info(f"Restoring daily_sales with {len(update_data['daily_sales'])} dates (excluding '{date_added}')")
                        
                        # Apply the updates if any fields need to be restored
                        if update_data:
                            await collections.liquor_data.update_one(
                                {"id": brand_id},
                                {"$set": update_data}
                            )
                            brands_reverted += 1
                
                # Delete brands that were newly added
                if brands_added:
                    result = await collections.liquor_data.delete_many({"id": {"$in": brands_added}})
                    brands_deleted = result.deleted_count
                
                # Infer date_added if missing (for legacy records)
                if not date_added:
                    # Try to find the most recent date in DB to use as a cleanup target
                    sample_brand = await collections.liquor_data.find_one({})
                    if sample_brand and sample_brand.get("DL_date"):
                        date_added = sample_brand.get("DL_date")
                        logging.info(f"Inferred date_added '{date_added}' for delete failsafe")

                # FAILSAFE: If snapshot is incomplete, remove the date from ALL brands
                # This handles cases where the snapshot didn't capture all brands
                if date_added:
                    logging.info(f"Running failsafe cleanup for date: {date_added}")
                    from utils.date_helper import parse_date, normalize_date_key
                    
                    normalized_date = normalize_date_key(date_added)
                    
                    # Find all brands that have this date (normalized OR raw) in their daily_sales
                    affected_brands = await collections.liquor_data.find({
                        "$or": [
                            {"daily_sales." + normalized_date: {"$exists": True}},
                            {"daily_sales." + str(date_added): {"$exists": True}}
                        ]
                    }).to_list(10000)
                    
                    for brand in affected_brands:
                        # If already reverted by the loop above, skip
                        if brand.get("id") in brands_updated:
                            continue
                            
                        daily = brand.get('daily_sales', {})
                        keys_to_remove = [k for k in daily.keys() if k == normalized_date or k == date_added]
                        
                        if keys_to_remove:
                            for k in keys_to_remove:
                                del daily[k]
                            update_fields = {"daily_sales": daily}
                            
                            # CRITICAL: If this was the DL_date, we MUST roll it back
                            if brand.get('DL_date') in keys_to_remove:
                                if daily:
                                    sorted_dates = sorted(daily.keys(), key=lambda x: parse_date(x), reverse=True)
                                    new_dl = sorted_dates[0]
                                    update_fields["DL_date"] = new_dl
                                    update_fields["DL_stock"] = daily[new_dl]
                                    update_fields["current_stock_qty"] = int(daily[new_dl])
                                    # Recalculate stock value if rate is available
                                    rate = brand.get('selling_rate', brand.get('rate', 0.0))
                                    update_fields["stock_value_today"] = float(daily[new_dl] * rate)
                                else:
                                    # This was the ONLY date, shouldn't happen but handle it
                                    update_fields["DL_date"] = brand.get("D1_date")
                                    update_fields["DL_stock"] = brand.get("D1_stock", 0)
                                    update_fields["current_stock_qty"] = int(brand.get("D1_stock", 0))
                            
                            await collections.liquor_data.update_one({"_id": brand["_id"]}, {"$set": update_fields})
                            brands_reverted += 1
                
                data_reverted = True
                logging.info(f"Reverted daily_update: {brands_reverted} brands updated, {brands_deleted} brands deleted")
            
            elif upload_type == "full_monthly":
                # For Full Monthly upload, restore from backup OR clear data if no backup
                backup_id = changes_snapshot.get("backup_id")
                
                if backup_id:
                    # Try to restore from backup
                    backup_record = await collections.stock_backups.find_one({
                        "$or": [{"id": backup_id}, {"backup_id": backup_id}]
                    })
                    
                    if backup_record:
                        restored_data = backup_record.get("data_snapshot", [])
                        
                        if restored_data:
                            # Delete current data and restore from backup
                            await collections.liquor_data.delete_many({})
                            await collections.liquor_data.insert_many(restored_data)
                            brands_reverted = len(restored_data)
                            data_reverted = True
                            logging.info(f"Restored {brands_reverted} brands from backup {backup_id}")
                        else:
                            logging.warning(f"Backup {backup_id} contains no data")
                    else:
                        logging.warning(f"Backup {backup_id} not found - clearing current data")
                        # No backup found, just clear current data
                        result = await collections.liquor_data.delete_many({})
                        brands_deleted = result.deleted_count
                        data_reverted = True
                else:
                    # No backup ID - this was likely the first upload, just clear data
                    logging.info("No backup found for full_monthly upload - clearing current data")
                    result = await collections.liquor_data.delete_many({})
                    brands_deleted = result.deleted_count
                    data_reverted = True
        
        # STEP 2: Delete the associated backup
        backup_id = changes_snapshot.get("backup_id")
        deleted_backup = False
        if backup_id:
            backup_result = await collections.stock_backups.delete_one({
                "$or": [{"id": backup_id}, {"backup_id": backup_id}]
            })
            deleted_backup = backup_result.deleted_count > 0
            if deleted_backup:
                logging.info(f"Deleted backup {backup_id}")
        
        # STEP 3: Delete the upload history record
        delete_result = await collections.upload_history.delete_one({"id": upload_id})
        
        if delete_result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Failed to delete upload history")
        
        # Build response message
        if data_reverted:
            if upload_type == "full_monthly":
                message = f"Upload deleted and data reverted. Restored {brands_reverted} brands from backup." if brands_reverted > 0 else f"Upload deleted and current data cleared ({brands_deleted} brands removed)."
            else:
                message = f"Upload deleted and changes reverted. {brands_reverted} brands restored, {brands_deleted} brands removed."
        else:
            message = "Upload history deleted successfully (data not reverted)"
        
        return {
            "message": message,
            "upload_id": upload_id,
            "data_reverted": data_reverted,
            "brands_reverted": brands_reverted,
            "brands_deleted": brands_deleted,
            "backup_deleted": deleted_backup,
            "details": {
                "filename": upload_record.get("filename"),
                "upload_type": upload_record.get("upload_type"),
                "records_count": upload_record.get("records_count")
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error deleting upload history: {e}")
        raise HTTPException(status_code=500, detail=f"Error deleting upload history: {str(e)}")

@api_router.delete("/upload-history/cleanup")
async def cleanup_old_upload_history():
    """Delete upload history records older than 60 days"""
    try:
        sixty_days_ago = datetime.now(timezone.utc) - timedelta(days=60)
        
        result = await collections.upload_history.delete_many({
            "upload_timestamp": {"$lt": sixty_days_ago}
        })
        
        return {
            "deleted_count": result.deleted_count,
            "message": f"Cleaned up {result.deleted_count} old upload history records"
        }
        
    except Exception as e:
        logging.error(f"Error cleaning up upload history: {e}")
        raise HTTPException(status_code=500, detail=f"Error cleaning up upload history: {str(e)}")

@api_router.api_route("/admin/fix-database-integrity", methods=["GET", "POST"])
async def fix_database_integrity():
    """
    Administrative utility to fix database integrity issues.
    Supports both GET and POST for easy browser access.
    This endpoint will:
    1. Normalize all daily_sales date keys to DD-MMM-YY format (merge duplicates)
    2. Remove orphaned dates from undone uploads
    3. Ensure all numeric fields have valid values
    4. Sync DL_date/DL_stock with latest daily_sales entry
    5. Recalculate total_sales_qty and derived fields
    6. Return a summary of fixes applied
    """
    try:
        from utils.date_helper import parse_date, normalize_date_key
        
        issues_found = []
        fixes_applied = []
        
        # Step 0: Find ALL valid dates that SHOULD exist in daily_sales
        # A date is valid if it exists in an active (not undone) upload history record
        # OR if it is a D1_date for any brand.
        
        valid_dates = set()
        
        # Get dates from active upload history
        active_uploads = await collections.upload_history.find({
            "undone_at": None
        }).to_list(1000)
        
        for upload in active_uploads:
            snapshot = upload.get("changes_snapshot", {}) or {}
            date_added = snapshot.get("date_added")
            if date_added:
                valid_dates.add(normalize_date_key(date_added))
        
        # Get all current records to find D1_dates
        all_records = await collections.liquor_data.find().to_list(10000)
        
        for record in all_records:
            d1 = record.get("D1_date")
            if d1:
                valid_dates.add(normalize_date_key(d1))
        
        if valid_dates:
            logging.info(f"Integrity check: Found {len(valid_dates)} valid dates in history/D1: {sorted(list(valid_dates))}")
        else:
            issues_found.append("No valid upload history or D1 dates found! Cleanup might be aggressive.")
        
        # Get all records
        all_records = await collections.liquor_data.find().to_list(10000)
        
        if not all_records:
            return {
                "status": "success",
                "message": "Database is empty, nothing to fix",
                "issues_found": [],
                "fixes_applied": []
            }
        
        all_removed_orphans = set()
        for record in all_records:
            brand_id = record.get('id')
            brand_name = record.get('brand_name', 'Unknown')
            record_updated = False
            update_data = {}
            
            # Fix 1: Ensure daily_sales is a dict, not null
            daily_sales = record.get('daily_sales')
            if daily_sales is None:
                issues_found.append(f"Brand '{brand_name}': daily_sales was null")
                daily_sales = {}
                update_data['daily_sales'] = {}
                record_updated = True
            
            # Fix 2: Normalize all daily_sales date keys and remove orphans
            if daily_sales and isinstance(daily_sales, dict):
                normalized = {}
                removed_dates = []
                
                for raw_key, value in daily_sales.items():
                    norm_key = normalize_date_key(raw_key)
                    
                    # Check if this date is valid (exists in history or is a D1 date)
                    if valid_dates and norm_key not in valid_dates:
                        removed_dates.append(raw_key)
                        all_removed_orphans.add(raw_key)
                        continue
                    
                    # Check if key changed format
                    if raw_key != norm_key:
                        issues_found.append(f"Brand '{brand_name}': normalized date key '{raw_key}' -> '{norm_key}'")
                    
                    # Keep the value (if duplicate after normalization, keep first)
                    if norm_key not in normalized:
                        normalized[norm_key] = value
                
                if removed_dates:
                    issues_found.append(f"Brand '{brand_name}': removed orphan dates {removed_dates}")
                
                if normalized != daily_sales:
                    update_data['daily_sales'] = normalized
                    daily_sales = normalized  # Use normalized for subsequent checks
                    record_updated = True
            
            # Fix 3: Ensure ALL required numeric fields are present with consistent names
            # Some parts of the app use 'avg_daily_sale' while others use 'avg_daily_sales_qty'
            # We ensure both are synced here.
            numeric_fields = {
                'current_stock_qty': 0,
                'total_sales_qty': 0.0,
                'avg_daily_sales_qty': 0.0,
                'avg_daily_sale': 0.0, # Required by analytics
                'monthly_sales_qty': 0.0,
                'monthly_sale_qty': 0,
                'monthly_sale_value': 0.0,
                'stock_available_days': 0.0,
                'stock_ratio': 0.0,
                'D1_stock': 0.0,
                'DL_stock': 0.0,
                'days_analyzed': 1,
                'stock_value_before': 0.0, # Required by analytics
                'stock_value_today': 0.0,
                'rate': record.get('selling_rate', 0.0), # Required by analytics
                'selling_rate': record.get('rate', 0.0),
                'wholesale_rate': record.get('wholesale_rate', 0.0)
            }
            
            for field, default_value in numeric_fields.items():
                if record.get(field) is None:
                    issues_found.append(f"Brand '{brand_name}': {field} was missing/None")
                    update_data[field] = default_value
                    record_updated = True
            
            # Fix 4: Sync DL_date/DL_stock with the last entry in daily_sales
            if daily_sales and isinstance(daily_sales, dict) and len(daily_sales) > 0:
                try:
                    sorted_keys = sorted(daily_sales.keys(), key=lambda d: parse_date(d))
                    if sorted_keys:
                        last_date = sorted_keys[-1]
                        last_stock = daily_sales[last_date]
                        first_date = sorted_keys[0]
                        first_stock = daily_sales[first_date]
                        
                        # Sync DL_date
                        current_dl = record.get('DL_date')
                        if current_dl != last_date:
                            norm_current_dl = normalize_date_key(current_dl) if current_dl else None
                            if norm_current_dl != last_date:
                                issues_found.append(f"Brand '{brand_name}': DL_date '{current_dl}' -> '{last_date}'")
                                update_data['DL_date'] = last_date
                                update_data['DL_stock'] = float(last_stock)
                                update_data['current_stock_qty'] = int(last_stock)
                                record_updated = True
                        
                        # Fix 5: Recalculate derived fields
                        d1_stock = update_data.get('D1_stock', record.get('D1_stock', first_stock))
                        dl_stock = update_data.get('DL_stock', record.get('DL_stock', last_stock))
                        selling_rate = update_data.get('selling_rate', record.get('selling_rate', record.get('rate', 0.0)))
                        days = len(sorted_keys)
                        
                        total_sales_qty = max(0, float(d1_stock) - float(dl_stock))
                        avg_daily = total_sales_qty / max(1, days)
                        monthly_qty = avg_daily * 24
                        monthly_val = monthly_qty * selling_rate
                        stock_val = float(dl_stock) * selling_rate
                        
                        update_data['days_analyzed'] = days
                        update_data['total_sales_qty'] = total_sales_qty
                        update_data['avg_daily_sales_qty'] = avg_daily
                        update_data['avg_daily_sale'] = avg_daily # Sync
                        update_data['stock_value_today'] = stock_val
                        update_data['monthly_sale_qty'] = int(monthly_qty)
                        update_data['monthly_sale_value'] = monthly_val
                        update_data['rate'] = selling_rate # Sync
                        
                        # Recalculate stock ratio if possible
                        if monthly_qty > 0:
                            update_data['stock_ratio'] = float(dl_stock) / monthly_qty
                        
                        record_updated = True
                        
                except Exception as e:
                    logging.warning(f"Could not sync fields for {brand_name}: {e}")
            
            # Apply updates if any
            if record_updated and brand_id:
                await collections.liquor_data.update_one(
                    {"id": brand_id},
                    {"$set": update_data}
                )
                fixes_applied.append(f"Fixed {len(update_data)} fields for brand '{brand_name}'")
        
        return {
            "status": "success",
            "message": f"Database integrity check complete. Fixed {len(fixes_applied)} of {len(all_records)} records.",
            "total_records_checked": len(all_records),
            "valid_dates_in_history": sorted(list(valid_dates)),
            "removed_orphans": sorted(list(all_removed_orphans)),
            "issues_found": len(issues_found),
            "fixes_applied": len(fixes_applied),
            "details": {
                "issues": issues_found[:20],
                "fixes": fixes_applied[:20]
            }
        }
        
    except Exception as e:
        logging.error(f"Error in database integrity fix: {e}")
        raise HTTPException(status_code=500, detail=f"Error fixing database: {str(e)}")

# ========================================
# MODULE 3: Stock Reset & Backup APIs
# ========================================

@api_router.post("/stock/backup")
async def create_stock_backup(reason: str = "manual_backup"):
    """Create a backup of all current stock data"""
    try:
        # Fetch all liquor data
        liquor_records = await collections.liquor_data.find().to_list(10000)
        
        if not liquor_records:
            raise HTTPException(status_code=404, detail="No data to backup")
        
        # Remove MongoDB _id field for clean backup
        for record in liquor_records:
            if '_id' in record:
                del record['_id']
        
        # Create backup record
        backup = StockBackup(
            total_records=len(liquor_records),
            backup_reason=reason,
            data_snapshot=liquor_records
        )
        
        # Store backup
        await collections.stock_backups.insert_one(backup.dict())
        
        logging.info(f"Created stock backup: {backup.id} with {len(liquor_records)} records")
        
        return {
            "backup_id": backup.id,
            "total_records": len(liquor_records),
            "backup_timestamp": backup.backup_timestamp,
            "message": "Backup created successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error creating backup: {e}")
        raise HTTPException(status_code=500, detail=f"Error creating backup: {str(e)}")

@api_router.get("/stock/backups")
async def list_stock_backups():
    """Get list of all stock backups"""
    try:
        backups = await collections.stock_backups.find().sort("backup_timestamp", -1).to_list(100)
        
        backup_list = []
        for backup in backups:
            # Ensure backup_timestamp is properly formatted with timezone information
            timestamp = backup.get("backup_timestamp")
            if isinstance(timestamp, str):
                # Parse string timestamp and ensure it has UTC timezone
                try:
                    timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                except:
                    timestamp = datetime.fromisoformat(timestamp)
                    if timestamp.tzinfo is None:
                        timestamp = timestamp.replace(tzinfo=timezone.utc)
            elif isinstance(timestamp, datetime) and timestamp.tzinfo is None:
                # Add UTC timezone if missing
                timestamp = timestamp.replace(tzinfo=timezone.utc)
            
            backup_list.append({
                "id": backup.get("id"),
                "backup_timestamp": timestamp.isoformat() if timestamp else None,
                "total_records": backup.get("total_records"),
                "backup_reason": backup.get("backup_reason"),
                "created_by": backup.get("created_by")
            })
        
        return backup_list
        
    except Exception as e:
        logging.error(f"Error fetching backups: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching backups: {str(e)}")

@api_router.get("/historical-periods")
async def get_historical_periods():
    """Get all available historical periods with D1/DL dates for calendar view"""
    try:
        periods = []
        
        # 1. Add current period
        current_data = await collections.liquor_data.find().to_list(1000)
        if current_data and len(current_data) > 0:
            # Extract D1 and DL dates from current data
            d1_dates = set()
            dl_dates = set()
            for record in current_data:
                if record.get('D1_date'):
                    d1_dates.add(str(record['D1_date']))
                if record.get('DL_date'):
                    dl_dates.add(str(record['DL_date']))
            
            if d1_dates and dl_dates:
                d1_date = min(d1_dates)
                dl_date = max(dl_dates)
                
                # Generate proper period name for current period
                try:
                    # Try ISO format first
                    d1_dt = datetime.fromisoformat(str(d1_date).replace(' ', 'T').split('.')[0])
                    dl_dt = datetime.fromisoformat(str(dl_date).replace(' ', 'T').split('.')[0])
                except:
                    # Try parsing "15-Nov-25" format
                    try:
                        d1_dt = datetime.strptime(str(d1_date), "%d-%b-%y")
                        dl_dt = datetime.strptime(str(dl_date), "%d-%b-%y")
                    except:
                        d1_dt = None
                        dl_dt = None
                
                # Generate period name in "Month-Month Year" format
                if d1_dt and dl_dt:
                    d1_month = d1_dt.strftime("%b")
                    dl_month = dl_dt.strftime("%b")
                    year = dl_dt.strftime("%Y")
                    
                    if d1_month == dl_month:
                        current_period_name = f"{d1_month} {year}"
                    else:
                        current_period_name = f"{d1_month}-{dl_month} {year}"
                else:
                    current_period_name = "Current Period"
                
                periods.append({
                    "id": "current",
                    "period_name": current_period_name,
                    "d1_date": d1_date,
                    "dl_date": dl_date,
                    "has_data": True,
                    "is_current": True,
                    "total_records": len(current_data)
                })
        
        # 2. Add historical periods from backups - ONLY pre_reset_backup types
        # These represent complete sales periods that were committed to history
        backups = await collections.stock_backups.find({
            "backup_reason": "pre_reset_backup"
        }).sort("backup_timestamp", -1).to_list(100)
        
        # Group backups by period (D1-DL combination) to avoid duplicates
        period_map = {}
        
        for backup in backups:
            data_snapshot = backup.get('data_snapshot', [])
            if not data_snapshot:
                continue
            
            # Extract D1 and DL dates from snapshot
            d1_dates = set()
            dl_dates = set()
            for record in data_snapshot:
                if record.get('D1_date'):
                    d1_dates.add(str(record['D1_date']))
                if record.get('DL_date'):
                    dl_dates.add(str(record['DL_date']))
            
            if d1_dates and dl_dates:
                d1_date = min(d1_dates)
                dl_date = max(dl_dates)
                period_key = f"{d1_date}_{dl_date}"
                
                # Only keep the most recent backup for each period
                if period_key not in period_map:
                    # Determine period name from D1 and DL dates - same format as sales trends
                    try:
                        # Try ISO format first
                        d1_dt = datetime.fromisoformat(d1_date.replace(' ', 'T'))
                        dl_dt = datetime.fromisoformat(dl_date.replace(' ', 'T'))
                    except:
                        # Try parsing "20-Sep-25" format
                        try:
                            d1_dt = datetime.strptime(d1_date, "%d-%b-%y")
                            dl_dt = datetime.strptime(dl_date, "%d-%b-%y")
                        except:
                            d1_dt = None
                            dl_dt = None
                    
                    # Generate period name in "Month-Month Year" format (same as trends)
                    if d1_dt and dl_dt:
                        d1_month = d1_dt.strftime("%b")
                        dl_month = dl_dt.strftime("%b")
                        year = dl_dt.strftime("%Y")
                        
                        if d1_month == dl_month:
                            period_name = f"{d1_month} {year}"
                        else:
                            period_name = f"{d1_month}-{dl_month} {year}"
                    else:
                        period_name = "Historical Period"
                    
                    period_map[period_key] = {
                        "id": backup.get('id') or backup.get('backup_id'),  # Try both field names
                        "period_name": period_name,
                        "d1_date": d1_date,
                        "dl_date": dl_date,
                        "has_data": True,
                        "is_current": False,
                        "total_records": len(data_snapshot),
                        "backup_timestamp": backup.get('backup_timestamp')
                    }
        
        # Add all historical periods
        periods.extend(list(period_map.values()))
        
        # Sort by D1 date (reverse chronological - newest first)
        periods.sort(key=lambda x: x['d1_date'], reverse=True)
        
        return periods
        
    except Exception as e:
        logging.error(f"Error fetching historical periods: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching historical periods: {str(e)}")

@api_router.post("/historical-data-view")
async def get_historical_data_view(period_ids: List[str]):
    """Get aggregated raw data for selected historical periods"""
    try:
        all_records = []
        period_labels = []
        
        # Fetch data for each selected period
        for period_id in period_ids:
            if period_id == "current":
                # Get current data
                current_data = await collections.liquor_data.find().to_list(1000)
                all_records.extend(current_data)
                period_labels.append("Current Period")
            else:
                # Get backup data (try both id field names)
                backup = await collections.stock_backups.find_one({
                    "$or": [{"id": period_id}, {"backup_id": period_id}]
                })
                if backup:
                    data_snapshot = backup.get('data_snapshot', [])
                    all_records.extend(data_snapshot)
                    
                    # Get period name from D1 date
                    if data_snapshot:
                        d1_date = data_snapshot[0].get('D1_date', '')
                        try:
                            d1_dt = datetime.fromisoformat(str(d1_date).replace(' ', 'T'))
                            period_name = d1_dt.strftime("%B %Y")
                        except:
                            period_name = "Historical Period"
                        period_labels.append(period_name)
        
        if not all_records:
            return {
                "data": [],
                "summary": {
                    "total_periods": 0,
                    "total_brands": 0,
                    "period_labels": []
                }
            }
        
        # Aggregate data by brand (index_number)
        brand_data = {}
        
        for record in all_records:
            index_number = record.get('index_number', 'N/A')
            brand_name = record.get('brand_name')
            
            if not brand_name:
                continue
            
            # Use index_number as primary key for aggregation
            key = f"{index_number}_{brand_name}"
            
            if key not in brand_data:
                brand_data[key] = {
                    'index_number': index_number,
                    'brand_name': brand_name,
                    'total_qty_procured': 0,
                    'total_qty_sold': 0,
                    'total_days': 0,
                    'selling_rates': [],
                    'wholesale_rates': [],
                    'total_revenue': 0,
                    'total_cost': 0,
                    'periods_data': []
                }
            
            # Get quantities
            d1_stock = record.get('D1_stock', 0)
            dl_stock = record.get('DL_stock', record.get('current_stock_qty', 0))
            # Try multiple field names for sales quantity
            monthly_sales = (record.get('monthly_sales_qty') or 
                           record.get('monthly_sale_qty') or 
                           record.get('total_sales_qty') or 
                           record.get('total_sale_qty') or 0)
            monthly_sale_value = record.get('monthly_sale_value', record.get('total_sale_value', 0))
            
            # Calculate qty procured (DL_stock + monthly_sales - D1_stock)
            qty_procured = dl_stock + monthly_sales - d1_stock
            
            brand_data[key]['total_qty_procured'] += max(0, qty_procured)
            brand_data[key]['total_qty_sold'] += monthly_sales
            brand_data[key]['total_revenue'] += monthly_sale_value
            
            # Collect rates
            selling_rate = record.get('selling_rate', record.get('rate', 0))
            wholesale_rate = record.get('wholesale_rate', 0)
            
            if selling_rate > 0:
                brand_data[key]['selling_rates'].append(selling_rate)
            if wholesale_rate > 0:
                brand_data[key]['wholesale_rates'].append(wholesale_rate)
            
            # Calculate cost
            brand_data[key]['total_cost'] += qty_procured * wholesale_rate if qty_procured > 0 and wholesale_rate > 0 else 0
            
            # Count days in period
            d1_date = record.get('D1_date')
            dl_date = record.get('DL_date')
            # Skip records with None, 'N/A', or empty dates
            if d1_date and dl_date and d1_date != 'N/A' and dl_date != 'N/A':
                try:
                    d1_dt = datetime.fromisoformat(str(d1_date).replace(' ', 'T'))
                    dl_dt = datetime.fromisoformat(str(dl_date).replace(' ', 'T'))
                    days = (dl_dt - d1_dt).days + 1
                    brand_data[key]['total_days'] += days
                except:
                    pass
            
            # Store period data
            brand_data[key]['periods_data'].append({
                'D1_date': str(d1_date) if d1_date else None,
                'DL_date': str(dl_date) if dl_date else None,
                'monthly_sales': monthly_sales
            })
        
        # Calculate aggregated data
        result_data = []
        total_revenue = 0
        total_profit = 0
        
        for key, data in brand_data.items():
            avg_selling_rate = sum(data['selling_rates']) / len(data['selling_rates']) if data['selling_rates'] else 0
            avg_wholesale_rate = sum(data['wholesale_rates']) / len(data['wholesale_rates']) if data['wholesale_rates'] else 0
            avg_daily_sales = data['total_qty_sold'] / data['total_days'] if data['total_days'] > 0 else 0
            
            # Use existing calculated revenue from records
            revenue = data['total_revenue']
            
            # Profit = (Avg Selling Rate - Avg Wholesale Rate) × Total Qty Sold
            per_unit_profit = avg_selling_rate - avg_wholesale_rate
            profit = per_unit_profit * data['total_qty_sold']
            
            total_revenue += revenue
            total_profit += profit
            
            result_data.append({
                'index_number': data['index_number'],
                'brand_name': data['brand_name'],
                'total_qty_procured': round(data['total_qty_procured'], 2),
                'total_qty_sold': round(data['total_qty_sold'], 2),
                'avg_daily_sales': round(avg_daily_sales, 2),
                'avg_selling_rate': round(avg_selling_rate, 2),
                'avg_wholesale_rate': round(avg_wholesale_rate, 2),
                'total_revenue': round(revenue, 2),
                'total_profit': round(profit, 2),
                'period_info': data['periods_data']
            })
        
        # Sort by index number
        result_data.sort(key=lambda x: x['index_number'] if isinstance(x['index_number'], (int, float)) else 999999)
        
        return {
            "data": result_data,
            "summary": {
                "total_periods": len(period_ids),
                "total_brands": len(result_data),
                "period_labels": period_labels,
                "total_revenue": round(total_revenue, 2),
                "total_profit": round(total_profit, 2)
            }
        }
        
    except Exception as e:
        logging.error(f"Error fetching historical data view: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching historical data view: {str(e)}")

@api_router.post("/historical-analysis")
async def analyze_historical_periods(period_ids: List[str]):
    """Analyze selected historical periods for trends, top brands, and forecast"""
    try:
        all_records = []
        period_labels = []
        
        # Fetch current data for index and current stock lookup
        current_liquor_data = await collections.liquor_data.find().to_list(1000)
        current_brand_lookup = {record.get('brand_name'): record for record in current_liquor_data}
        
        # Fetch data for each selected period
        for period_id in period_ids:
            if period_id == "current":
                # Get current data
                current_data = await collections.liquor_data.find().to_list(1000)
                all_records.extend(current_data)
                period_labels.append("Current Period")
            else:
                # Get backup data (try both id field names)
                backup = await collections.stock_backups.find_one({
                    "$or": [{"id": period_id}, {"backup_id": period_id}]
                })
                if backup:
                    data_snapshot = backup.get('data_snapshot', [])
                    all_records.extend(data_snapshot)
                    
                    # Get period name from D1 date
                    if data_snapshot:
                        d1_date = data_snapshot[0].get('D1_date', '')
                        try:
                            d1_dt = datetime.fromisoformat(str(d1_date).replace(' ', 'T'))
                            period_name = d1_dt.strftime("%B %Y")
                        except:
                            period_name = "Historical Period"
                        period_labels.append(period_name)
        
        if not all_records:
            return {
                "trends": [],
                "top_brands": [],
                "forecast": [],
                "summary": {
                    "total_periods": 0,
                    "total_brands": 0,
                    "message": "No data available for selected periods"
                }
            }
        
        # Calculate aggregate metrics
        brand_data = {}
        
        for record in all_records:
            brand_name = record.get('brand_name')
            if not brand_name:
                continue
            
            if brand_name not in brand_data:
                brand_data[brand_name] = {
                    'brand_name': brand_name,
                    'total_sales_qty': 0,
                    'total_sale_value': 0,
                    'periods_appeared': 0,
                    'selling_rate': 0,
                    'wholesale_rate': 0,
                    'monthly_sales_list': [],
                    'selling_rates': [],
                    'wholesale_rates': []
                }
            
            monthly_sales = record.get('monthly_sales_qty', record.get('monthly_sale_qty', 0))
            selling_rate = record.get('selling_rate', record.get('rate', 0))
            wholesale_rate = record.get('wholesale_rate', 0)
            
            brand_data[brand_name]['total_sales_qty'] += monthly_sales
            brand_data[brand_name]['total_sale_value'] += record.get('monthly_sale_value', 0)
            brand_data[brand_name]['monthly_sales_list'].append(monthly_sales)
            brand_data[brand_name]['periods_appeared'] += 1
            
            # Collect rates to calculate average later
            if selling_rate > 0:
                brand_data[brand_name]['selling_rates'].append(selling_rate)
            if wholesale_rate > 0:
                brand_data[brand_name]['wholesale_rates'].append(wholesale_rate)
        
        # Calculate trends and averages
        trends = []
        top_brands = []
        forecast = []
        
        for brand_name, data in brand_data.items():
            avg_monthly_sales = data['total_sales_qty'] / len(period_ids) if period_ids else 0
            
            # Calculate average rates
            avg_selling_rate = sum(data['selling_rates']) / len(data['selling_rates']) if data['selling_rates'] else 0
            avg_wholesale_rate = sum(data['wholesale_rates']) / len(data['wholesale_rates']) if data['wholesale_rates'] else 0
            
            # Calculate trend (simple: compare first half vs second half)
            sales_list = data['monthly_sales_list']
            if len(sales_list) >= 2:
                mid = len(sales_list) // 2
                first_half_avg = sum(sales_list[:mid]) / mid
                second_half_avg = sum(sales_list[mid:]) / (len(sales_list) - mid)
                
                if first_half_avg > 0:
                    growth_rate = ((second_half_avg - first_half_avg) / first_half_avg) * 100
                else:
                    growth_rate = 0
                
                if growth_rate > 10:
                    trend = "📈 Growing"
                elif growth_rate < -10:
                    trend = "📉 Declining"
                else:
                    trend = "➡️ Stable"
            else:
                growth_rate = 0
                trend = "➡️ Stable"
            
            trends.append({
                'brand_name': brand_name,
                'avg_monthly_sales': round(avg_monthly_sales, 2),
                'total_sales': data['total_sales_qty'],
                'growth_rate': round(growth_rate, 1),
                'trend': trend,
                'periods_appeared': data['periods_appeared']
            })
            
            # Forecast for next month
            # Formula: Average + (Average * Growth Rate)
            forecast_qty = avg_monthly_sales * (1 + growth_rate / 100)
            forecast_qty = max(0, round(forecast_qty))
            
            # Calculate cases needed (1 case = 12 units, round up)
            import math
            cases_needed = math.ceil(forecast_qty / 12) if forecast_qty > 0 else 0
            
            # Determine priority based on forecast
            if forecast_qty >= 50:
                priority = "HIGH"
            elif forecast_qty >= 20:
                priority = "MEDIUM"
            else:
                priority = "LOW"
            
            # Get index and current stock from current data
            current_brand_record = current_brand_lookup.get(brand_name, {})
            index_number = current_brand_record.get('index_number', 'N/A')
            current_stock = current_brand_record.get('current_stock_qty', 0)
            
            forecast.append({
                'index_number': index_number,
                'brand_name': brand_name,
                'historical_avg': round(avg_monthly_sales, 2),
                'forecast_qty': forecast_qty,
                'current_stock_qty': current_stock,
                'cases_to_buy': cases_needed,
                'priority': priority,
                'growth_rate': round(growth_rate, 1),
                'selling_rate': round(avg_selling_rate, 2),
                'wholesale_rate': round(avg_wholesale_rate, 2),
                'estimated_value': round(forecast_qty * avg_wholesale_rate, 2)
            })
        
        # Sort for top brands (by total sales)
        top_brands = sorted(trends, key=lambda x: x['total_sales'], reverse=True)[:20]
        
        # Sort forecast by priority and quantity
        priority_order = {"HIGH": 1, "MEDIUM": 2, "LOW": 3}
        forecast.sort(key=lambda x: (priority_order[x['priority']], -x['forecast_qty']))
        
        return {
            "trends": trends,
            "top_brands": top_brands,
            "forecast": forecast,
            "summary": {
                "total_periods": len(period_ids),
                "total_brands": len(brand_data),
                "period_labels": period_labels
            }
        }
        
    except Exception as e:
        logging.error(f"Error analyzing historical periods: {e}")
        raise HTTPException(status_code=500, detail=f"Error analyzing historical periods: {str(e)}")

@api_router.get("/stock/backup/{backup_id}/download")
async def download_backup(backup_id: str):
    """Download a specific backup as Excel file"""
    try:
        # Find backup
        backup = await collections.stock_backups.find_one({
            "$or": [{"id": backup_id}, {"backup_id": backup_id}]
        })
        
        if not backup:
            raise HTTPException(status_code=404, detail="Backup not found")
        
        # Create Excel file
        data_snapshot = backup['data_snapshot']
        
        # Convert timestamp fields to IST before creating DataFrame
        ist_timezone = pytz.timezone('Asia/Kolkata')
        
        for record in data_snapshot:
            if 'upload_timestamp' in record and record['upload_timestamp']:
                try:
                    # Parse UTC timestamp
                    utc_timestamp = record['upload_timestamp']
                    if isinstance(utc_timestamp, str):
                        utc_timestamp = datetime.fromisoformat(utc_timestamp.replace('Z', '+00:00'))
                        if utc_timestamp.tzinfo is None:
                            utc_timestamp = utc_timestamp.replace(tzinfo=timezone.utc)
                    
                    # Convert to IST and format as readable string
                    ist_timestamp = utc_timestamp.astimezone(ist_timezone)
                    record['upload_timestamp'] = ist_timestamp.strftime('%Y-%m-%d %H:%M:%S IST')
                except Exception as e:
                    logging.warning(f"Could not convert upload_timestamp for record {record.get('id', 'unknown')}: {e}")
        
        df = pd.DataFrame(data_snapshot)
        
        # Reorder columns: id, index_number, brand_name, then rest
        if 'id' in df.columns and 'index_number' in df.columns and 'brand_name' in df.columns:
            # Get all columns
            all_cols = df.columns.tolist()
            # Remove the three columns we want to reorder
            remaining_cols = [col for col in all_cols if col not in ['id', 'index_number', 'brand_name']]
            # Create new column order
            new_order = ['id', 'index_number', 'brand_name'] + remaining_cols
            df = df[new_order]
        
        # Create Excel in memory
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Stock Backup')
        
        output.seek(0)
        
        # Convert UTC timestamp to IST (India Standard Time, UTC+5:30)
        from datetime import timedelta
        
        # Get backup timestamp and ensure it's a datetime object
        backup_timestamp_utc = backup['backup_timestamp']
        
        # If it's a string, parse it to datetime
        if isinstance(backup_timestamp_utc, str):
            backup_timestamp_utc = datetime.fromisoformat(backup_timestamp_utc.replace('Z', '+00:00'))
        
        # Ensure it's timezone-aware UTC
        if backup_timestamp_utc.tzinfo is None:
            backup_timestamp_utc = backup_timestamp_utc.replace(tzinfo=timezone.utc)
        
        # Convert to IST timezone
        ist_timezone = pytz.timezone('Asia/Kolkata')
        backup_timestamp_ist = backup_timestamp_utc.astimezone(ist_timezone)
        backup_date = backup_timestamp_ist.strftime("%Y%m%d_%H%M%S")
        filename = f"stock_backup_{backup_date}.xlsx"
        
        return StreamingResponse(
            output,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error downloading backup: {e}")
        raise HTTPException(status_code=500, detail=f"Error downloading backup: {str(e)}")

@api_router.delete("/stock/backup/{backup_id}")
async def delete_backup(backup_id: str):
    """Delete a specific backup"""
    try:
        # Try both "id" and "backup_id" field names for compatibility
        result = await collections.stock_backups.delete_one({
            "$or": [
                {"id": backup_id},
                {"backup_id": backup_id}
            ]
        })
        
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Backup not found")
        
        logging.info(f"Deleted backup: {backup_id}")
        
        return {
            "success": True,
            "message": "Backup deleted successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error deleting backup: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/stock/backup/{backup_id}/restore")
async def restore_from_backup(backup_id: str, recalculate_historical: bool = True):
    """Restore data from a specific backup and optionally recalculate historical averages"""
    try:
        logging.info(f"🔄 Starting restore from backup: {backup_id}")
        
        # Find the backup
        backup = await collections.stock_backups.find_one({
            "$or": [{"id": backup_id}, {"backup_id": backup_id}]
        })
        
        if not backup:
            # Log available backups for debugging
            all_backups = await collections.stock_backups.find({}, {"id": 1, "backup_timestamp": 1}).to_list(10)
            available_ids = [b.get('id') for b in all_backups]
            logging.error(f"Backup {backup_id} not found. Available backup IDs: {available_ids}")
            raise HTTPException(
                status_code=404, 
                detail=f"Backup not found. Requested ID: {backup_id}. Available backups: {len(all_backups)}"
            )
        
        # Get the backup data
        backup_data = backup.get('data_snapshot', [])
        
        if not backup_data:
            raise HTTPException(status_code=400, detail="Backup contains no data")
        
        logging.info(f"📦 Found backup with {len(backup_data)} records from {backup.get('backup_timestamp')}")
        
        # STEP 1: Calculate historical averages FROM BACKUP DATA (before clearing current data)
        historical_records_created = 0
        historical_month = "N/A"
        if recalculate_historical:
            logging.info("📊 Calculating historical averages from backup data...")
            historical_result = await calculate_and_store_historical_averages(source_records=backup_data)
            historical_records_created = historical_result.get('historical_records_created', 0)
            historical_month = historical_result.get('month_year', 'N/A')
            if historical_records_created > 0:
                logging.info(f"✅ Created {historical_records_created} historical records for {historical_month}")
            else:
                logging.warning(f"⚠️ No historical records created: {historical_result.get('message', 'Unknown reason')}")
        
        # STEP 2: Clear current data
        current_count = await collections.liquor_data.count_documents({})
        await collections.liquor_data.delete_many({})
        logging.info(f"🗑️ Cleared {current_count} existing records before restore")
        
        # STEP 3: Restore data from backup
        # Convert backup data to proper format
        restored_records = []
        for record in backup_data:
            # Ensure all required fields exist
            if 'id' not in record:
                record['id'] = str(uuid.uuid4())
            if 'upload_timestamp' not in record:
                record['upload_timestamp'] = datetime.now(timezone.utc)
            restored_records.append(record)
        
        # Insert restored data
        if restored_records:
            await collections.liquor_data.insert_many(restored_records)
            logging.info(f"✅ Restored {len(restored_records)} records from backup")
        
        return {
            "success": True,
            "backup_id": backup_id,
            "backup_reason": backup.get('backup_reason', 'unknown'),
            "backup_date": backup.get('backup_timestamp'),
            "records_restored": len(restored_records),
            "current_records_cleared": current_count,
            "historical_records_created": historical_records_created,
            "historical_month": historical_month,
            "message": f"Successfully restored {len(restored_records)} records and created {historical_records_created} historical averages"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"❌ Error restoring from backup: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error restoring backup: {str(e)}")

# MODULE 5: Historical Sales Averages - Helper Functions

async def calculate_and_store_historical_averages(source_records=None):
    """
    Calculate historical sales averages from data before reset
    
    Args:
        source_records: Optional list of records to calculate from (for restore scenarios)
                       If None, fetches from current liquor_data collection
    """
    try:
        # Use provided records or fetch from database
        if source_records is None:
            liquor_records = await collections.liquor_data.find().to_list(10000)
        else:
            liquor_records = source_records
        
        if not liquor_records:
            logging.warning("No records available for historical calculation")
            return {"historical_records_created": 0, "message": "No data available"}
        
        logging.info(f"📊 Calculating historical averages from {len(liquor_records)} records")
        
        # Get month_year from first record's date fields
        sample_record = liquor_records[0]
        d1_date = sample_record.get('D1_date', '')
        
        # Parse month_year from date string
        try:
            if d1_date and d1_date != 'N/A':
                # Try to parse as datetime object first
                d1_dt = None
                if isinstance(d1_date, datetime):
                    d1_dt = d1_date
                else:
                    # Try ISO format (2025-10-19)
                    try:
                        d1_dt = datetime.fromisoformat(str(d1_date).replace(' ', 'T'))
                    except:
                        # Try parsing with different separators
                        parts = str(d1_date).split('-')
                        if len(parts) == 3:
                            # Check if it's already in short format (20-Sep-25)
                            if not parts[1].isdigit():  # Month is text
                                month = parts[1]  # Sep, Oct, etc.
                                year = f"20{parts[2]}" if len(parts[2]) == 2 else parts[2]
                                month_year = f"{month}-{year}"
                                d1_dt = None  # Already formatted
                
                if d1_dt:
                    month_year = d1_dt.strftime("%b-%Y")  # Format as "Oct-2025"
                elif 'month_year' not in locals():
                    month_year = datetime.now().strftime("%b-%Y")
            else:
                month_year = datetime.now().strftime("%b-%Y")
        except Exception as e:
            logging.warning(f"Error parsing month_year from D1_date '{d1_date}': {e}")
            month_year = datetime.now().strftime("%b-%Y")
        
        logging.info(f"📅 Historical data will be stored for period: {month_year}")
        
        historical_records = []
        brands_with_sales = 0
        brands_without_sales = 0
        
        for record in liquor_records:
            brand_name = record.get('brand_name', 'Unknown')
            avg_daily_sales_qty = record.get('avg_daily_sales_qty', 0.0)
            total_sales_qty = record.get('total_sales_qty', 0.0)
            days_analyzed = record.get('days_analyzed', 0)
            selling_rate = record.get('selling_rate', record.get('rate', 0))
            wholesale_rate = record.get('wholesale_rate', 0.0)
            
            # Calculate average daily sales value
            avg_daily_sales_value = avg_daily_sales_qty * selling_rate
            total_sales_value = total_sales_qty * selling_rate
            
            # RELAXED CONDITION: Store if there's any meaningful data
            # Changed from strict "days_analyzed > 0 and total_sales_qty > 0"
            # to allow records with at least 1 day analyzed OR any stock data
            if days_analyzed >= 1 or total_sales_qty > 0:
                historical_avg = HistoricalSalesAverage(
                    brand_name=brand_name,
                    month_year=month_year,
                    average_daily_sales_qty=float(avg_daily_sales_qty),
                    average_daily_sales_value=float(avg_daily_sales_value),
                    total_sales_quantity=float(total_sales_qty),
                    total_sales_value=float(total_sales_value),
                    total_sales_days=int(days_analyzed),
                    wholesale_rate=float(wholesale_rate),
                    selling_rate=float(selling_rate)
                )
                historical_records.append(historical_avg.dict())
                brands_with_sales += 1
            else:
                brands_without_sales += 1
                logging.debug(f"Skipping brand '{brand_name}': days_analyzed={days_analyzed}, total_sales_qty={total_sales_qty}")
        
        logging.info(f"✅ Brands with sales data: {brands_with_sales}, without: {brands_without_sales}")
        
        # Store in database (delete existing records for this month first to avoid duplicates)
        if historical_records:
            # Remove existing historical data for this month to avoid duplicates
            delete_result = await db.historical_sales_averages.delete_many({"month_year": month_year})
            if delete_result.deleted_count > 0:
                logging.info(f"Removed {delete_result.deleted_count} existing historical records for {month_year}")
            
            # Insert new historical records
            await db.historical_sales_averages.insert_many(historical_records)
            logging.info(f"✅ Successfully stored {len(historical_records)} historical sales averages for {month_year}")
            
            return {
                "historical_records_created": len(historical_records),
                "month_year": month_year,
                "brands_with_data": brands_with_sales,
                "brands_skipped": brands_without_sales,
                "message": f"Historical data saved for {month_year}"
            }
        else:
            logging.warning(f"⚠️ No historical records created - all brands had insufficient data")
            return {
                "historical_records_created": 0,
                "month_year": month_year,
                "brands_with_data": 0,
                "brands_skipped": brands_without_sales,
                "message": "No brands had sufficient sales data for historical calculation"
            }
        
    except Exception as e:
        logging.error(f"❌ Error calculating historical averages: {e}", exc_info=True)
        return {"historical_records_created": 0, "error": str(e), "message": f"Error: {str(e)}"}

async def get_days_of_current_data() -> int:
    """Count how many days of sales data we have in current month"""
    try:
        liquor_records = await collections.liquor_data.find().to_list(1)
        
        if not liquor_records:
            return 0
        
        # Get days_analyzed from first record
        days_analyzed = liquor_records[0].get('days_analyzed', 0)
        return days_analyzed
        
    except Exception as e:
        logging.error(f"Error getting days of current data: {e}")
        return 0

async def should_use_historical_data() -> tuple[bool, int]:
    """Determine if we should use historical data based on current data days"""
    days = await get_days_of_current_data()
    return (days < 5, days)

async def get_projected_data_from_historical():
    """Get projected liquor data based on historical sales averages (most recent month only)"""
    try:
        # Get ALL historical data first
        all_historical_records = await db.historical_sales_averages.find().to_list(1000)
        
        if not all_historical_records:
            return []
        
        # Group by brand_name and keep only the most recent month's data per brand
        # This prevents counting the same brand multiple times from different months
        brand_latest_data = {}
        for record in all_historical_records:
            brand_name = record.get('brand_name')
            month_year = record.get('month_year', '')
            
            if brand_name not in brand_latest_data:
                brand_latest_data[brand_name] = record
            else:
                # Compare months and keep the most recent
                existing_month = brand_latest_data[brand_name].get('month_year', '')
                if month_year > existing_month:  # Newer month (string comparison works for "Oct-2025" > "Sep-2025")
                    brand_latest_data[brand_name] = record
        
        # Convert back to list (now with unique brands only)
        historical_records = list(brand_latest_data.values())
        logging.info(f"Using {len(historical_records)} unique brands from historical data (filtered from {len(all_historical_records)} total records)")
        
        if not historical_records:
            return []
        
        # Get current stock data (if any exists from new month uploads)
        current_stock_dict = {}
        current_records = await collections.liquor_data.find().to_list(1000)
        for record in current_records:
            current_stock_dict[record['brand_name']] = {
                'current_stock_qty': record.get('current_stock_qty', 0),
                'stock_value_today': record.get('stock_value_today', 0),
                'D1_stock': record.get('D1_stock', 0),
                'DL_stock': record.get('DL_stock', 0),
                'D1_date': record.get('D1_date', 'N/A'),
                'DL_date': record.get('DL_date', 'N/A'),
                'daily_sales': record.get('daily_sales', {}),
                'selling_rate': record.get('selling_rate', record.get('rate', 0.0))
            }
        
        # Create projected records based on historical averages
        projected_records = []
        for hist_record in historical_records:
            brand_name = hist_record['brand_name']
            avg_daily_qty = hist_record['average_daily_sales_qty']
            selling_rate = hist_record['selling_rate']
            wholesale_rate = hist_record['wholesale_rate']
            
            # Project for 30 days (full month)
            projected_monthly_qty = avg_daily_qty * 30
            projected_monthly_value = projected_monthly_qty * selling_rate
            
            # Get current stock if available, otherwise default to 0
            current_stock_info = current_stock_dict.get(brand_name, {})
            current_stock_qty = current_stock_info.get('current_stock_qty', 0)
            # Use current stock value if available, otherwise calculate from historical rate
            stock_value_today = current_stock_info.get('stock_value_today', 0)
            if stock_value_today == 0 and current_stock_qty > 0:
                stock_value_today = current_stock_qty * selling_rate
            
            # Calculate stock ratios
            if avg_daily_qty > 0:
                stock_available_days = current_stock_qty / avg_daily_qty
                stock_ratio = stock_available_days / 30  # Days of stock / Days in month
            else:
                stock_available_days = 0
                stock_ratio = 0
            
            # Create daily_sales dict with projected values for visualization
            # Use current_stock_info to get actual dates if available
            daily_sales_dict = {}
            if current_stock_info.get('daily_sales'):
                # Use actual daily_sales from current stock data
                daily_sales_dict = current_stock_info.get('daily_sales', {})
            else:
                # Generate synthetic daily sales for historical projection visualization
                # Use D1 and DL dates if available to show trend
                d1_date = current_stock_info.get('D1_date', 'N/A')
                if d1_date != 'N/A' and avg_daily_qty > 0:
                    # Create a simulated daily sales trend based on historical average
                    daily_sales_dict[d1_date] = int(avg_daily_qty)
            
            # Create projected record in same format as liquor_data
            projected_record = {
                'id': str(uuid.uuid4()),
                'brand_name': brand_name,
                'rate': selling_rate,
                'daily_sales': daily_sales_dict,  # Populated with actual or projected daily data
                'monthly_sale_qty': int(projected_monthly_qty),
                'monthly_sale_value': projected_monthly_value,
                'avg_daily_sale': projected_monthly_value / 30,
                'stock_available_days': stock_available_days,
                'stock_value_before': stock_value_today,
                'stock_value_today': stock_value_today,
                'stock_ratio': stock_ratio,
                'index_number': 0,
                'wholesale_rate': wholesale_rate,
                'selling_rate': selling_rate,
                'D1_date': current_stock_info.get('D1_date', 'N/A'),
                'D1_stock': current_stock_info.get('D1_stock', 0),
                'DL_date': current_stock_info.get('DL_date', 'N/A'),
                'DL_stock': current_stock_info.get('DL_stock', 0),
                'total_sales_qty': projected_monthly_qty,
                'avg_daily_sales_qty': avg_daily_qty,
                'days_analyzed': 30,  # Projected for full month
                'current_stock_qty': current_stock_qty,
                'upload_timestamp': datetime.now(timezone.utc),
                '_data_source': 'historical'  # Mark as historical data
            }
            
            projected_records.append(projected_record)
        
        logging.info(f"Generated {len(projected_records)} projected records from historical data")
        return projected_records
        
    except Exception as e:
        logging.error(f"Error getting projected data from historical: {e}")
        return []

async def internal_reset_stock():
    """Internal helper to reset stock data, calculate averages, and create backup"""
    # 1. Calculate historical averages
    historical_result = await calculate_and_store_historical_averages()
    
    # 2. Create backup
    liquor_records = await collections.liquor_data.find().to_list(10000)
    if not liquor_records:
        return {"error": "No data to reset", "status": "failed"}
        
    backup_data = []
    for record in liquor_records:
        record_copy = record.copy()
        if '_id' in record_copy: del record_copy['_id']
        backup_data.append(record_copy)
        
    backup = StockBackup(
        total_records=len(backup_data),
        backup_reason="pre_reset_backup",
        data_snapshot=backup_data
    )
    await collections.stock_backups.insert_one(backup.dict())
    
    # 3. Clear current data
    await collections.liquor_data.delete_many({})
    
    return {
        "backup_id": backup.id,
        "records_backed_up": len(backup_data),
        "historical_records": historical_result.get('historical_records_created', 0),
        "status": "success"
    }

@api_router.post("/stock/reset")
async def reset_stock_data():
    """Reset all date-wise stock data after calculating historical averages and creating backup"""
    try:
        result = await internal_reset_stock()
        if result.get("status") == "failed":
            raise HTTPException(status_code=404, detail=result.get("error"))
            
        return {
            **result,
            "message": "Stock data reset successfully. Backup created.",
            "next_upload_becomes_d1": True
        }
    except HTTPException: raise
    except Exception as e:
        logging.error(f"Error resetting stock data: {e}")
        raise HTTPException(status_code=500, detail=f"Error resetting stock data: {str(e)}")
        
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error resetting stock data: {e}")
        raise HTTPException(status_code=500, detail=f"Error resetting stock data: {str(e)}")

# MODULE 5: Historical Sales Averages APIs

@api_router.get("/analytics-source")
async def get_analytics_source_info():
    """Get information about which data source is being used for analytics"""
    try:
        use_historical, days = await should_use_historical_data()
        
        # Get current month
        current_month = datetime.now().strftime("%b-%Y")
        
        # Determine confidence level
        if days == 0:
            confidence = "none"
        elif days < 3:
            confidence = "low"
        elif days < 5:
            confidence = "medium"
        else:
            confidence = "high"
        
        # Get the month we're using for analytics
        if use_historical:
            # Try to get the most recent historical month
            historical_record = await db.historical_sales_averages.find_one(
                {},
                sort=[("calculation_date", -1)]
            )
            using_month = historical_record.get('month_year', 'Previous Month') if historical_record else 'Previous Month'
        else:
            using_month = current_month
        
        return {
            "data_source": "historical" if use_historical else "current",
            "days_of_data": days,
            "using_month": using_month,
            "transition_threshold": 5,
            "is_transitioning": days > 0 and days < 5,
            "confidence_level": confidence
        }
        
    except Exception as e:
        logging.error(f"Error getting analytics source info: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/historical-averages")
async def get_historical_averages(month: Optional[str] = None):
    """Get historical sales averages, optionally filtered by month"""
    try:
        query = {}
        if month:
            query["month_year"] = month
        
        historical_records = await db.historical_sales_averages.find(query).sort("brand_name", 1).to_list(1000)
        
        # Remove _id for JSON serialization
        for record in historical_records:
            if '_id' in record:
                del record['_id']
        
        # Get unique months available
        all_months = await db.historical_sales_averages.distinct("month_year")
        
        return {
            "historical_averages": historical_records,
            "count": len(historical_records),
            "available_months": sorted(all_months, reverse=True),
            "filtered_by_month": month
        }
        
    except Exception as e:
        logging.error(f"Error fetching historical averages: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/calculate-historical-averages")
async def calculate_historical_averages_manual():
    """Manually trigger calculation of historical averages (for testing)"""
    try:
        result = await calculate_and_store_historical_averages()
        return {
            "success": True,
            "historical_records_created": result.get('historical_records_created', 0),
            "month_year": result.get('month_year', 'N/A'),
            "message": "Historical averages calculated and stored successfully"
        }
    except Exception as e:
        logging.error(f"Error manually calculating historical averages: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.delete("/historical-averages/cleanup")
async def cleanup_old_historical_data(months_to_keep: int = 36):
    """Delete historical data older than specified months (default 36 months)"""
    try:
        cutoff_date = datetime.now(timezone.utc) - pd.DateOffset(months=months_to_keep)
        
        delete_result = await db.historical_sales_averages.delete_many({
            "calculation_date": {"$lt": cutoff_date}
        })
        
        return {
            "deleted_count": delete_result.deleted_count,
            "months_kept": months_to_keep,
            "message": f"Deleted historical data older than {months_to_keep} months"
        }
        
    except Exception as e:
        logging.error(f"Error cleaning up historical data: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/clear-all-data")
async def clear_all_data():
    """Clear all data from the database (liquor_data, backups, historical_averages, upload_history)"""
    try:
        # Delete all collections
        liquor_deleted = await collections.liquor_data.delete_many({})
        backups_deleted = await collections.stock_backups.delete_many({})
        historical_deleted = await db.historical_sales_averages.delete_many({})
        history_deleted = await collections.upload_history.delete_many({})
        
        logging.info(f"Cleared all data - Liquor: {liquor_deleted.deleted_count}, Backups: {backups_deleted.deleted_count}, Historical: {historical_deleted.deleted_count}, Upload History: {history_deleted.deleted_count}")
        
        return {
            "success": True,
            "liquor_records_deleted": liquor_deleted.deleted_count,
            "backups_deleted": backups_deleted.deleted_count,
            "historical_records_deleted": historical_deleted.deleted_count,
            "upload_history_deleted": history_deleted.deleted_count,
            "message": "All data cleared successfully. You can now upload fresh data."
        }
        
    except Exception as e:
        logging.error(f"Error clearing all data: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# MODULE 4: Monthly Report Generation APIs

async def get_aggregated_period_data(period_ids: list) -> list:
    """
    Aggregate data from multiple selected historical periods
    Similar to the sales history tab aggregation logic
    """
    try:
        logging.info(f"🔍 Aggregating data for period IDs: {period_ids}")
        aggregated_data = {}
        
        for period_id in period_ids:
            logging.info(f"  Looking for backup with id: {period_id}")
            # Find the backup for this period
            backup = await collections.stock_backups.find_one({"id": period_id})
            if not backup:
                logging.warning(f"  ⚠️ No backup found for period_id: {period_id}")
                continue
            
            logging.info(f"  ✅ Found backup for period: {backup.get('period_name', 'Unknown')}")
            data_snapshot = backup.get('data_snapshot', [])
            logging.info(f"  Found {len(data_snapshot)} records in snapshot")
            
            for record in data_snapshot:
                brand_name = record.get('brand_name')
                if not brand_name:
                    continue
                
                if brand_name not in aggregated_data:
                    # Initialize aggregated record for this brand
                    aggregated_data[brand_name] = {
                        'brand_name': brand_name,
                        'wholesale_rate': record.get('wholesale_rate', 0),
                        'selling_rate': record.get('selling_rate', record.get('rate', 0)),
                        'rate': record.get('rate', record.get('selling_rate', 0)),
                        'total_sales_qty': 0,
                        'monthly_sale_value': 0,
                        'monthly_sales_qty': 0,
                        'stock_value_today': record.get('stock_value_today', 0),  # Use latest
                        'current_stock_qty': record.get('current_stock_qty', 0),  # Use latest
                        'stock_available_days': record.get('stock_available_days', 0),
                        'stock_ratio': record.get('stock_ratio', 0),
                        'avg_daily_sales_qty': 0
                    }
                
                # Aggregate sales quantities and values
                aggregated_data[brand_name]['total_sales_qty'] += record.get('total_sales_qty', 0)
                aggregated_data[brand_name]['monthly_sale_value'] += record.get('monthly_sale_value', 0)
                aggregated_data[brand_name]['monthly_sales_qty'] += record.get('monthly_sales_qty', 0)
                aggregated_data[brand_name]['avg_daily_sales_qty'] += record.get('avg_daily_sales_qty', 0)
                
                # Update latest stock position (from most recent period)
                aggregated_data[brand_name]['stock_value_today'] = record.get('stock_value_today', 0)
                aggregated_data[brand_name]['current_stock_qty'] = record.get('current_stock_qty', 0)
                aggregated_data[brand_name]['stock_available_days'] = record.get('stock_available_days', 0)
                aggregated_data[brand_name]['stock_ratio'] = record.get('stock_ratio', 0)
        
        # Convert dict to list
        return list(aggregated_data.values())
        
    except Exception as e:
        logging.error(f"Error aggregating period data: {e}")
        return []

async def generate_monthly_report_data(selected_periods: list = None) -> MonthlyReportData:
    """Generate comprehensive monthly report data - supports multi-period aggregation"""
    try:
        logging.info(f"Generating report data with selected_periods: {selected_periods}")
        
        # If periods are selected, get aggregated data from those periods
        if selected_periods and len(selected_periods) > 0:
            logging.info(f"Fetching aggregated data for {len(selected_periods)} periods")
            # Fetch data from selected historical periods
            liquor_records = await get_aggregated_period_data(selected_periods)
            logging.info(f"Got {len(liquor_records)} records from aggregation")
            
            # If aggregation returns empty, fall back to current data
            if not liquor_records:
                logging.warning("Aggregation returned no data, falling back to current data")
                liquor_records = await collections.liquor_data.find().to_list(1000)
        else:
            # Get current liquor data
            logging.info("No periods selected, using current data")
            liquor_records = await collections.liquor_data.find().to_list(1000)
        
        if not liquor_records:
            raise HTTPException(status_code=404, detail="No data found")
        
        # Extract date range for report period
        # If using aggregated periods, get dates from the backups
        if selected_periods and len(selected_periods) > 0:
            # Get D1 from first period, DL from last period
            first_backup = await collections.stock_backups.find_one({"id": selected_periods[0]})
            last_backup = await collections.stock_backups.find_one({"id": selected_periods[-1]})
            
            if first_backup and last_backup:
                d1_raw = first_backup.get('d1_date', 'N/A')
                dl_raw = last_backup.get('dl_date', 'N/A')
                
                # Convert datetime objects to string format if needed
                if isinstance(d1_raw, datetime):
                    d1_date = d1_raw.strftime("%d-%b-%y")
                else:
                    d1_date = str(d1_raw).split()[0] if ' ' in str(d1_raw) else str(d1_raw)
                
                if isinstance(dl_raw, datetime):
                    dl_date = dl_raw.strftime("%d-%b-%y")
                else:
                    dl_date = str(dl_raw).split()[0] if ' ' in str(dl_raw) else str(dl_raw)
            else:
                # Fallback: try to get from records
                sample_record = liquor_records[0]
                d1_date = sample_record.get('D1_date', 'N/A')
                dl_date = sample_record.get('DL_date', 'N/A')
        else:
            # Using current data - get from first record
            sample_record = liquor_records[0]
            d1_date = sample_record.get('D1_date', 'N/A')
            dl_date = sample_record.get('DL_date', 'N/A')
        
        logging.info(f"Report period dates: D1={d1_date}, DL={dl_date}")
        
        # Generate period label dynamically from D1 and DL dates
        try:
            from datetime import datetime
            import re
            
            # Parse D1 date
            match = re.search(r'(\d{1,2})[-/](\w{3})[-/]?(\d{0,4})', str(d1_date), re.IGNORECASE)
            if match:
                day, month_name, year_suffix = match.groups()
                year = '2025' if not year_suffix or len(year_suffix) < 2 else (f"20{year_suffix}" if len(year_suffix) == 2 else year_suffix[:4])
                d1_parsed = datetime.strptime(f"{day}-{month_name}-{year}", "%d-%b-%Y")
            else:
                d1_parsed = None
            
            # Parse DL date
            match = re.search(r'(\d{1,2})[-/](\w{3})[-/]?(\d{0,4})', str(dl_date), re.IGNORECASE)
            if match:
                day, month_name, year_suffix = match.groups()
                year = '2025' if not year_suffix or len(year_suffix) < 2 else (f"20{year_suffix}" if len(year_suffix) == 2 else year_suffix[:4])
                dl_parsed = datetime.strptime(f"{day}-{month_name}-{year}", "%d-%b-%Y")
            else:
                dl_parsed = None
            
            # Generate period name
            if d1_parsed and dl_parsed:
                d1_month = d1_parsed.strftime("%b")
                dl_month = dl_parsed.strftime("%b")
                year = dl_parsed.strftime("%Y")
                
                if d1_month == dl_month:
                    period_name = f"{d1_month} {year}"
                else:
                    period_name = f"{d1_month}-{dl_month} {year}"
                
                report_period = f"{period_name} Sales Period ({d1_date} to {dl_date})"
            else:
                report_period = f"Sales Period ({d1_date} to {dl_date})"
        except Exception as e:
            logging.warning(f"Error parsing dates for report period: {e}")
            report_period = f"Sales Period ({d1_date} to {dl_date})"
        
        # Convert to working format
        data_list = []
        for record in liquor_records:
            data_list.append({
                'brand_name': record['brand_name'],
                'wholesale_rate': record.get('wholesale_rate', 0),
                'selling_rate': record.get('selling_rate', record['rate']),
                'current_stock_qty': record.get('current_stock_qty', 0),
                'total_sales_qty': record.get('total_sales_qty', 0),
                'monthly_sale_value': record['monthly_sale_value'],
                'monthly_sales_qty': record.get('monthly_sales_qty', 0),
                'stock_value_today': record['stock_value_today'],
                'stock_available_days': record['stock_available_days'],
                'stock_ratio': record.get('stock_ratio', 0),
                'avg_daily_sales_qty': record.get('avg_daily_sales_qty', 0)
            })
        
        # 1. TOP SELLERS - Revenue and Volume
        # Revenue-wise top sellers
        revenue_sorted = sorted(data_list, key=lambda x: x['monthly_sale_value'], reverse=True)[:10]
        top_sellers_revenue = []
        for item in revenue_sorted:
            profit_per_unit = item['selling_rate'] - item['wholesale_rate']
            total_profit = profit_per_unit * item['total_sales_qty']
            profit_margin = (profit_per_unit / item['selling_rate'] * 100) if item['selling_rate'] > 0 else 0
            
            top_sellers_revenue.append(TopSeller(
                brand_name=item['brand_name'],
                revenue=item['monthly_sale_value'],
                volume=item['total_sales_qty'],
                profit=total_profit,
                profit_margin=profit_margin
            ))
        
        # Volume-wise top sellers
        volume_sorted = sorted(data_list, key=lambda x: x['total_sales_qty'], reverse=True)[:10]
        top_sellers_volume = []
        for item in volume_sorted:
            profit_per_unit = item['selling_rate'] - item['wholesale_rate']
            total_profit = profit_per_unit * item['total_sales_qty']
            profit_margin = (profit_per_unit / item['selling_rate'] * 100) if item['selling_rate'] > 0 else 0
            
            top_sellers_volume.append(TopSeller(
                brand_name=item['brand_name'],
                revenue=item['monthly_sale_value'],
                volume=item['total_sales_qty'],
                profit=total_profit,
                profit_margin=profit_margin
            ))
        
        # 2. SLOW SELLERS (low sales with high stock days)
        slow_sellers = []
        for item in data_list:
            if item['stock_available_days'] > 60 or item['monthly_sale_value'] < 1000:
                slow_sellers.append(SlowSeller(
                    brand_name=item['brand_name'],
                    revenue=item['monthly_sale_value'],
                    volume=item['total_sales_qty'],
                    stock_days=item['stock_available_days'],
                    stock_value=item['stock_value_today']
                ))
        
        slow_sellers = sorted(slow_sellers, key=lambda x: x.stock_days, reverse=True)[:15]
        
        # 3. CAPITAL BLOCKERS (overstocked items)
        capital_blockers = []
        for item in data_list:
            if item['stock_ratio'] > 3.0:  # More than 3 months of stock
                overstocked_ratio = item['stock_ratio']
                capital_blockers.append(CapitalBlocker(
                    brand_name=item['brand_name'],
                    stock_value=item['stock_value_today'],
                    stock_quantity=item['current_stock_qty'],
                    stock_days=item['stock_available_days'],
                    overstocked_ratio=overstocked_ratio
                ))
        
        capital_blockers = sorted(capital_blockers, key=lambda x: x.stock_value, reverse=True)[:15]
        
        # 4. DEMAND FORECAST WITH COSTS
        demand_forecast = []
        total_demand_cost = 0
        
        for item in data_list:
            monthly_sales_qty = item.get('monthly_sales_qty', 0)
            current_stock = item['current_stock_qty']
            
            if monthly_sales_qty > 0:
                recommended_qty = max(0, monthly_sales_qty - current_stock)
                if recommended_qty > 0:
                    total_cost = recommended_qty * item['wholesale_rate']
                    total_demand_cost += total_cost
                    
                    # Determine urgency
                    if item['stock_available_days'] < 10:
                        urgency = "HIGH"
                    elif item['stock_available_days'] < 20:
                        urgency = "MEDIUM"
                    else:
                        urgency = "LOW"
                    
                    demand_forecast.append(DemandForecastItem(
                        brand_name=item['brand_name'],
                        current_stock=current_stock,
                        recommended_qty=recommended_qty,
                        wholesale_rate=item['wholesale_rate'],
                        total_cost=total_cost,
                        urgency_level=urgency
                    ))
        
        # Sort by urgency and cost
        urgency_order = {"HIGH": 1, "MEDIUM": 2, "LOW": 3}
        demand_forecast = sorted(demand_forecast, key=lambda x: (urgency_order.get(x.urgency_level, 4), -x.total_cost))
        
        # 5. PROFIT ANALYSIS
        total_revenue = sum(item['monthly_sale_value'] for item in data_list)
        total_cost = sum((item['wholesale_rate'] * item['total_sales_qty']) for item in data_list)
        total_profit = total_revenue - total_cost
        avg_profit_margin = (total_profit / total_revenue * 100) if total_revenue > 0 else 0
        
        # Top profit generating brands
        profit_brands = []
        for item in data_list:
            brand_profit = (item['selling_rate'] - item['wholesale_rate']) * item['total_sales_qty']
            if brand_profit > 0:
                profit_brands.append({
                    'brand_name': item['brand_name'],
                    'profit': brand_profit,
                    'profit_margin': ((item['selling_rate'] - item['wholesale_rate']) / item['selling_rate'] * 100) if item['selling_rate'] > 0 else 0,
                    'sales_value': item['monthly_sale_value']
                })
        
        top_profit_brands = sorted(profit_brands, key=lambda x: x['profit'], reverse=True)[:10]
        
        profit_analysis = ProfitAnalysis(
            total_revenue=total_revenue,
            total_cost=total_cost,
            total_profit=total_profit,
            average_profit_margin=avg_profit_margin,
            top_profit_brands=top_profit_brands
        )
        
        # 6. EXECUTIVE SUMMARY DATA
        total_brands = len(data_list)
        overstocked_count = len(capital_blockers)
        slow_moving_count = len(slow_sellers)
        high_demand_count = len([f for f in demand_forecast if f.urgency_level == "HIGH"])
        
        executive_summary = {
            "total_brands_analyzed": total_brands,
            "report_period": report_period,
            "total_revenue": total_revenue,
            "total_profit": total_profit,
            "profit_margin": avg_profit_margin,
            "overstocked_brands": overstocked_count,
            "slow_moving_brands": slow_moving_count,
            "high_demand_brands": high_demand_count,
            "total_demand_investment": total_demand_cost,
            "key_insights": [
                f"Generated ₹{total_profit:,.0f} profit from ₹{total_revenue:,.0f} revenue",
                f"{overstocked_count} brands are overstocked, blocking capital",
                f"{slow_moving_count} brands are slow-moving and need attention",
                f"{high_demand_count} brands need urgent restocking"
            ]
        }
        
        # 7. RECOMMENDATIONS
        recommendations = [
            f"Focus on top revenue generators: {', '.join([b.brand_name for b in top_sellers_revenue[:3]])}",
            f"Address {overstocked_count} overstocked brands to free up ₹{sum(cb.stock_value for cb in capital_blockers):,.0f}",
            f"Implement promotion strategy for {slow_moving_count} slow-moving brands",
            f"Prioritize restocking of {high_demand_count} high-demand brands requiring ₹{total_demand_cost:,.0f} investment",
            f"Improve profit margin from current {avg_profit_margin:.1f}% through better wholesale negotiations"
        ]
        
        return MonthlyReportData(
            report_period=report_period,
            total_brands=total_brands,
            executive_summary=executive_summary,
            top_sellers_revenue=top_sellers_revenue,
            top_sellers_volume=top_sellers_volume,
            slow_sellers=slow_sellers,
            capital_blockers=capital_blockers,
            demand_forecast=demand_forecast,
            profit_analysis=profit_analysis,
            recommendations=recommendations
        )
        
    except Exception as e:
        logging.error(f"Error generating report data: {e}")
        raise HTTPException(status_code=500, detail=f"Error generating report data: {str(e)}")

@api_router.get("/reports/data", response_model=MonthlyReportData)
async def get_monthly_report_data():
    """Get structured monthly report data"""
    return await generate_monthly_report_data()

@api_router.post("/reports/generate-excel")
async def generate_excel_report(request_data: dict = None):
    """Generate comprehensive Excel report with all data - supports period selection"""
    try:
        # Extract selected periods if provided
        selected_periods = request_data.get('selected_periods', []) if request_data else []
        
        # Get report data (with period aggregation if multiple periods selected)
        report_data = await generate_monthly_report_data(selected_periods)
        
        # Create Excel file with multiple sheets
        output = io.BytesIO()
        
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            # Sheet 1: Executive Summary
            summary_data = {
                'Metric': [
                    'Report Period', 'Total Brands', 'Total Revenue', 'Total Profit', 
                    'Profit Margin %', 'Overstocked Brands', 'Slow Moving Brands', 'High Demand Brands'
                ],
                'Value': [
                    report_data.report_period,
                    report_data.total_brands,
                    f"₹{report_data.profit_analysis.total_revenue:,.0f}",
                    f"₹{report_data.profit_analysis.total_profit:,.0f}",
                    f"{report_data.profit_analysis.average_profit_margin:.1f}%",
                    len(report_data.capital_blockers),
                    len(report_data.slow_sellers),
                    len([f for f in report_data.demand_forecast if f.urgency_level == "HIGH"])
                ]
            }
            pd.DataFrame(summary_data).to_excel(writer, sheet_name='Executive Summary', index=False)
            
            # Sheet 2: Top Sellers Revenue
            if report_data.top_sellers_revenue:
                revenue_data = []
                for seller in report_data.top_sellers_revenue:
                    revenue_data.append({
                        'Brand Name': seller.brand_name,
                        'Revenue (₹)': seller.revenue,
                        'Volume Sold': seller.volume,
                        'Profit (₹)': seller.profit,
                        'Profit Margin (%)': seller.profit_margin
                    })
                pd.DataFrame(revenue_data).to_excel(writer, sheet_name='Top Revenue Generators', index=False)
            
            # Sheet 3: Top Sellers Volume
            if report_data.top_sellers_volume:
                volume_data = []
                for seller in report_data.top_sellers_volume:
                    volume_data.append({
                        'Brand Name': seller.brand_name,
                        'Volume Sold': seller.volume,
                        'Revenue (₹)': seller.revenue,
                        'Profit (₹)': seller.profit,
                        'Profit Margin (%)': seller.profit_margin
                    })
                pd.DataFrame(volume_data).to_excel(writer, sheet_name='Top Volume Movers', index=False)
            
            # Sheet 4: Slow Sellers
            if report_data.slow_sellers:
                slow_data = []
                for seller in report_data.slow_sellers:
                    slow_data.append({
                        'Brand Name': seller.brand_name,
                        'Revenue (₹)': seller.revenue,
                        'Volume Sold': seller.volume,
                        'Stock Days': seller.stock_days,
                        'Stock Value (₹)': seller.stock_value
                    })
                pd.DataFrame(slow_data).to_excel(writer, sheet_name='Slow Sellers', index=False)
            
            # Sheet 5: Capital Blockers
            if report_data.capital_blockers:
                capital_data = []
                for blocker in report_data.capital_blockers:
                    capital_data.append({
                        'Brand Name': blocker.brand_name,
                        'Stock Value (₹)': blocker.stock_value,
                        'Stock Quantity': blocker.stock_quantity,
                        'Stock Days': blocker.stock_days,
                        'Overstock Ratio': blocker.overstocked_ratio
                    })
                pd.DataFrame(capital_data).to_excel(writer, sheet_name='Capital Blockers', index=False)
            
            # Sheet 6: Demand Forecast
            if report_data.demand_forecast:
                demand_data = []
                for item in report_data.demand_forecast:
                    demand_data.append({
                        'Brand Name': item.brand_name,
                        'Current Stock': item.current_stock,
                        'Recommended Qty': item.recommended_qty,
                        'Wholesale Rate (₹)': item.wholesale_rate,
                        'Total Cost (₹)': item.total_cost,
                        'Urgency': item.urgency_level
                    })
                pd.DataFrame(demand_data).to_excel(writer, sheet_name='Demand Forecast', index=False)
            
            # Sheet 7: Profit Analysis
            profit_data = []
            for brand in report_data.profit_analysis.top_profit_brands:
                profit_data.append({
                    'Brand Name': brand['brand_name'],
                    'Profit (₹)': brand['profit'],
                    'Profit Margin (%)': brand['profit_margin'],
                    'Sales Value (₹)': brand['sales_value']
                })
            pd.DataFrame(profit_data).to_excel(writer, sheet_name='Profit Analysis', index=False)
            
            # Sheet 8: Date-wise Sales Analysis
            # Fetch liquor records for date-wise analysis
            liquor_records = await collections.liquor_data.find().to_list(1000)
            datewise_data = []
            
            # Define date parsing function for proper chronological sorting
            def parse_date_for_sorting_excel(date_str):
                """Parse various date formats for chronological sorting"""
                try:
                    import re
                    from datetime import datetime
                    
                    if not date_str:
                        return datetime.min
                    
                    date_str = str(date_str).strip()
                    
                    # Parse various date formats - handle dates with and without years
                    
                    # First try: dates with year (21-Sep-25, 01-Oct-25)
                    match = re.search(r'(\d{1,2})[-/](\w{3})[-/](\d{2,4})', date_str, re.IGNORECASE)
                    if match:
                        day, month_name, year = match.groups()
                        year = f"20{year}" if len(year) == 2 else year
                        full_date = f"{day}-{month_name}-{year}"
                        return datetime.strptime(full_date, "%d-%b-%Y")
                    
                    # Second try: dates without year (21-Sep, 22-Sep) - assume 2025
                    match = re.search(r'(\d{1,2})[-/](\w{3})$', date_str, re.IGNORECASE)
                    if match:
                        day, month_name = match.groups()
                        year = "2025"  # Default to 2025 for dates without year
                        full_date = f"{day}-{month_name}-{year}"
                        return datetime.strptime(full_date, "%d-%b-%Y")
                    
                    # Third try: ISO format (2025-10-04)
                    match = re.search(r'(\d{4})-(\d{1,2})-(\d{1,2})', date_str)
                    if match:
                        return datetime.strptime(match.group(0), "%Y-%m-%d")
                    
                    # Fourth try: numeric dates (04-10-25, 04/10/2025)
                    match = re.search(r'(\d{1,2})[-/](\d{1,2})[-/](\d{2,4})', date_str)
                    if match:
                        day, month, year = match.groups()
                        year = f"20{year}" if len(year) == 2 else year
                        return datetime(int(year), int(month), int(day))
                            
                except Exception as e:
                    print(f"Warning: Could not parse date '{date_str}': {e}")
                    return datetime.min
                
                return datetime.min
            
            # Extract actual date range from first record to create proper column headers
            date_columns = []
            if liquor_records:
                sample_record = liquor_records[0]
                d1_date = sample_record.get('D1_date', '20-Sep-25')
                dl_date = sample_record.get('DL_date', '03-Oct-25')
                
                # Create actual date columns based on daily_sales data structure
                daily_sales = sample_record.get('daily_sales', {}) or {}
                if daily_sales:
                    # Use actual dates as column headers, sorted chronologically using proper date parsing
                    sorted_dates = sorted(daily_sales.keys(), key=parse_date_for_sorting_excel)
                    date_columns = sorted_dates
                else:
                    # Fallback to static date range if daily_sales is not available, properly sorted
                    fallback_dates = ['20-Sep', '22-Sep', '26-Sep', '28-Sep-25', '29-Sep-25', '30-Sep-25', '01-Oct-25', '03-Oct-25']
                    date_columns = sorted(fallback_dates, key=parse_date_for_sorting_excel)
            
            for record in liquor_records:
                row_data = {
                    'Index': record.get('index_number', ''),
                    'Brand Name': record['brand_name'],
                    'Wholesale Rate (₹)': record.get('wholesale_rate', 0),
                    'Retail Rate (₹)': record.get('selling_rate', record.get('rate', 0))
                }
                
                # Add date-wise sales data with actual dates as column headers
                daily_sales = record.get('daily_sales', {})
                for date_col in date_columns:
                    sales_value = daily_sales.get(date_col, 0) if daily_sales else 0
                    row_data[date_col] = sales_value if sales_value is not None else 0
                
                datewise_data.append(row_data)
            
            pd.DataFrame(datewise_data).to_excel(writer, sheet_name='Date-wise Sales', index=False)
        
        output.seek(0)
        
        # Generate filename with IST timestamp
        ist_timezone = pytz.timezone('Asia/Kolkata')
        current_time = datetime.now(ist_timezone)
        filename = f"monthly_report_{current_time.strftime('%Y%m%d_%H%M%S')}.xlsx"
        
        return StreamingResponse(
            output,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
        
    except Exception as e:
        logging.error(f"Error generating Excel report: {e}")
        raise HTTPException(status_code=500, detail=f"Error generating Excel report: {str(e)}")

@api_router.post("/reports/generate-pdf")
async def generate_pdf_report(params: ReportParameters):
    """Generate beautified PDF report with selected sections - supports period selection"""
    try:
        # Extract selected periods if provided
        selected_periods = params.dict().get('selected_periods', []) if params else []
        
        # Get report data (with period aggregation if multiple periods selected)
        report_data = await generate_monthly_report_data(selected_periods)
        
        # Create PDF with A4 size (landscape for brand-wise analysis if requested)
        output = io.BytesIO()
        pagesize = landscape(A4) if params.include_datewise_analysis else A4
        doc = SimpleDocTemplate(output, pagesize=pagesize)
        styles = getSampleStyleSheet()
        
        # Custom styles matching dashboard theme
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            spaceAfter=30,
            textColor=HexColor('#1e40af'),
            alignment=1  # Center alignment
        )
        
        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontSize=16,
            spaceAfter=12,
            textColor=HexColor('#1e40af'),
            borderWidth=1,
            borderColor=HexColor('#3b82f6'),
            borderPadding=8,
            backColor=HexColor('#eff6ff')
        )
        
        normal_style = ParagraphStyle(
            'CustomNormal',
            parent=styles['Normal'],
            fontSize=10,
            spaceAfter=6
        )
        
        story = []
        
        # Title
        report_title = params.report_title or "Monthly Sales Analytics Report"
        story.append(Paragraph(report_title, title_style))
        story.append(Paragraph(f"<b>Period:</b> {report_data.report_period}", normal_style))
        story.append(Spacer(1, 20))
        
        # Executive Summary
        if params.include_executive_summary:
            story.append(Paragraph("📊 Executive Summary", heading_style))
            
            summary = report_data.executive_summary
            story.append(Paragraph(f"<b>Total Brands Analyzed:</b> {summary['total_brands_analyzed']}", normal_style))
            story.append(Paragraph(f"<b>Total Revenue:</b> ₹{summary['total_revenue']:,.0f}", normal_style))
            story.append(Paragraph(f"<b>Total Profit:</b> ₹{summary['total_profit']:,.0f}", normal_style))
            story.append(Paragraph(f"<b>Average Profit Margin:</b> {summary['profit_margin']:.1f}%", normal_style))
            
            story.append(Paragraph("<b>Key Insights:</b>", normal_style))
            for insight in summary['key_insights']:
                story.append(Paragraph(f"• {insight}", normal_style))
            
            story.append(Spacer(1, 15))
        
        # Top Revenue Sellers
        if params.include_top_sellers and report_data.top_sellers_revenue:
            story.append(Paragraph("🏆 Top Revenue Generators", heading_style))
            
            revenue_data = [['Brand Name', 'Revenue (₹)', 'Volume', 'Profit (₹)', 'Margin %']]
            for seller in report_data.top_sellers_revenue[:5]:
                revenue_data.append([
                    seller.brand_name,
                    f"₹{seller.revenue:,.0f}",
                    f"{seller.volume:.0f}",
                    f"₹{seller.profit:,.0f}",
                    f"{seller.profit_margin:.1f}%"
                ])
            
            table = Table(revenue_data)
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), HexColor('#3b82f6')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), HexColor('#f8fafc')),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            story.append(table)
            story.append(Spacer(1, 15))
        
        # Slow Sellers
        if params.include_slow_sellers and report_data.slow_sellers:
            story.append(Paragraph("🐌 Slow Moving Brands", heading_style))
            
            slow_data = [['Brand Name', 'Revenue (₹)', 'Stock Days', 'Stock Value (₹)']]
            for seller in report_data.slow_sellers[:5]:
                slow_data.append([
                    seller.brand_name,
                    f"₹{seller.revenue:,.0f}",
                    f"{seller.stock_days:.0f}",
                    f"₹{seller.stock_value:,.0f}"
                ])
            
            table = Table(slow_data)
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), HexColor('#dc2626')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), HexColor('#fef2f2')),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            story.append(table)
            story.append(Spacer(1, 15))
        
        # Capital Blockers
        if params.include_capital_blockers and report_data.capital_blockers:
            story.append(Paragraph("💰 Capital Blocking Brands", heading_style))
            
            capital_data = [['Brand Name', 'Stock Value (₹)', 'Stock Days', 'Overstock Ratio']]
            for blocker in report_data.capital_blockers[:5]:
                capital_data.append([
                    blocker.brand_name,
                    f"₹{blocker.stock_value:,.0f}",
                    f"{blocker.stock_days:.0f}",
                    f"{blocker.overstocked_ratio:.1f}x"
                ])
            
            table = Table(capital_data)
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), HexColor('#f59e0b')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), HexColor('#fffbeb')),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            story.append(table)
            story.append(Spacer(1, 15))
        
        # Profit Analysis
        if params.include_profit_analysis:
            story.append(Paragraph("💹 Profit Analysis", heading_style))
            
            profit = report_data.profit_analysis
            story.append(Paragraph(f"<b>Total Revenue:</b> ₹{profit.total_revenue:,.0f}", normal_style))
            story.append(Paragraph(f"<b>Total Profit:</b> ₹{profit.total_profit:,.0f}", normal_style))
            story.append(Paragraph(f"<b>Average Profit Margin:</b> {profit.average_profit_margin:.1f}%", normal_style))
            story.append(Spacer(1, 15))
        
        # Demand Forecast
        if params.include_demand_forecast and report_data.demand_forecast:
            story.append(PageBreak())  # New page for demand forecast
            story.append(Paragraph("📈 Demand Forecast & Investment Requirements", heading_style))
            
            total_investment = sum(item.total_cost for item in report_data.demand_forecast)
            story.append(Paragraph(f"<b>Total Investment Required:</b> ₹{total_investment:,.0f}", normal_style))
            story.append(Spacer(1, 10))
            
            demand_data = [['Brand Name', 'Current Stock', 'Recommended Qty', 'Cost (₹)', 'Urgency']]
            for item in report_data.demand_forecast[:10]:
                urgency_color = "🔴" if item.urgency_level == "HIGH" else "🟡" if item.urgency_level == "MEDIUM" else "🟢"
                demand_data.append([
                    item.brand_name,
                    f"{item.current_stock:.0f}",
                    f"{item.recommended_qty:.0f}",
                    f"₹{item.total_cost:,.0f}",
                    f"{urgency_color} {item.urgency_level}"
                ])
            
            table = Table(demand_data)
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), HexColor('#059669')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), HexColor('#f0fdf4')),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            story.append(table)
            story.append(Spacer(1, 15))
        
        # Recommendations
        if params.include_recommendations:
            story.append(Paragraph("💡 Strategic Recommendations", heading_style))
            
            for i, rec in enumerate(report_data.recommendations, 1):
                story.append(Paragraph(f"{i}. {rec}", normal_style))
            
            story.append(Spacer(1, 15))
        
        # Brand-wise Sale Analysis (if requested)
        if params.include_datewise_analysis:
            story.append(PageBreak())  # New page for brand-wise analysis
            story.append(Paragraph("📊 Brand-Wise Sale Analysis (All Brands - Landscape View)", heading_style))
            
            # Get ALL brands for complete analysis
            liquor_records = await collections.liquor_data.find().to_list(1000)  # Get all records
            
            if liquor_records:
                # Define table header
                brandwise_header = [
                    'Index', 'Brand Name', 'D1 Stock', 'DL Stock', 'Wholesale Rate (₹)', 
                    'Selling Rate (₹)', 'Monthly Sale Value (₹)', 'Monthly Profit (₹)',
                    'Retail Stock Value (₹)', 'Multiplier', 'Status'
                ]
                
                # Calculate compact landscape-optimized column widths for 3-page fit
                landscape_colwidths = [
                    0.4*inch,   # Index (more compact)
                    1.3*inch,   # Brand Name (more compact)
                    0.5*inch,   # D1 Stock (more compact)
                    0.5*inch,   # DL Stock (more compact)
                    0.7*inch,   # Wholesale Rate (more compact)
                    0.7*inch,   # Selling Rate (more compact)
                    0.9*inch,   # Monthly Sale Value (more compact)
                    0.8*inch,   # Monthly Profit (more compact)
                    1.0*inch,   # Retail Stock Value (more compact)
                    0.5*inch,   # Multiplier (more compact)
                    0.6*inch    # Status (more compact)
                ]
                
                # Prepare all brand data
                all_brand_data = []
                total_sale_value = 0
                total_profit = 0
                total_stock_value = 0
                
                for record in liquor_records:
                    # Calculate values
                    d1_stock = record.get('D1_stock', 0)
                    dl_stock = record.get('DL_stock', 0)
                    wholesale_rate = record.get('wholesale_rate', 0)
                    selling_rate = record.get('selling_rate', record.get('rate', 0))
                    monthly_sale_value = record.get('monthly_sale_value', 0)
                    
                    # Calculate monthly profit
                    total_sales_qty = record.get('total_sales_qty', 0)
                    monthly_profit = (selling_rate - wholesale_rate) * total_sales_qty
                    
                    current_stock_value = record.get('stock_value_today', 0)
                    multiplier_value = record.get('overstock_multiplier', 3.0)
                    
                    # Determine status based on stock ratio
                    stock_ratio = record.get('stock_ratio', 0)
                    if stock_ratio > multiplier_value:
                        status = "OVER"  # Shortened for space
                    elif stock_ratio < 0.5:
                        status = "LOW"
                    else:
                        status = "OK"
                    
                    # Add to totals
                    total_sale_value += monthly_sale_value
                    total_profit += monthly_profit
                    total_stock_value += current_stock_value
                    
                    row = [
                        str(record.get('index_number', '')),
                        record['brand_name'][:16],  # Slightly shorter to fit better
                        f"{d1_stock:.0f}",
                        f"{dl_stock:.0f}",
                        f"₹{wholesale_rate:.0f}",
                        f"₹{selling_rate:.0f}",
                        f"₹{monthly_sale_value:.0f}",
                        f"₹{monthly_profit:.0f}",
                        f"₹{current_stock_value:.0f}",
                        f"{multiplier_value:.1f}x",
                        status
                    ]
                    
                    all_brand_data.append(row)
                
                # Split data into chunks for multiple pages (20 rows per page to fit better in landscape)
                brands_per_page = 20
                total_pages = (len(all_brand_data) + brands_per_page - 1) // brands_per_page
                
                for page_num in range(total_pages):
                    # Add page break for subsequent pages
                    if page_num > 0:
                        story.append(PageBreak())
                    
                    # Add page indicator
                    if total_pages > 1:
                        story.append(Paragraph(f"<b>Brand-Wise Analysis - Page {page_num + 1} of {total_pages}</b>", normal_style))
                        story.append(Spacer(1, 10))
                    
                    # Get data for this page
                    start_idx = page_num * brands_per_page
                    end_idx = min(start_idx + brands_per_page, len(all_brand_data))
                    page_data = all_brand_data[start_idx:end_idx]
                    
                    # Create table data with header
                    table_data = [brandwise_header] + page_data
                    
                    # Create table for this page
                    table = Table(table_data, colWidths=landscape_colwidths, repeatRows=1)  # repeatRows=1 repeats header
                    table.setStyle(TableStyle([
                        ('BACKGROUND', (0, 0), (-1, 0), HexColor('#8b5cf6')),
                        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                        ('FONTSIZE', (0, 0), (-1, 0), 7),  # Further reduced header font
                        ('FONTSIZE', (0, 1), (-1, -1), 6),  # Further reduced data font
                        ('TOPPADDING', (0, 0), (-1, -1), 1),  # Minimal padding
                        ('BOTTOMPADDING', (0, 0), (-1, -1), 1),  # Minimal padding
                        ('LEFTPADDING', (0, 0), (-1, -1), 2),  # Minimal padding
                        ('RIGHTPADDING', (0, 0), (-1, -1), 2),  # Minimal padding
                        ('BACKGROUND', (0, 1), (-1, -1), HexColor('#f8fafc')),
                        ('GRID', (0, 0), (-1, -1), 0.25, colors.black),  # Very thin grid lines
                        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [HexColor('#ffffff'), HexColor('#f8fafc')])  # Alternating rows
                    ]))
                    
                    story.append(table)
                    story.append(Spacer(1, 10))
                
                # Add total row on last page only
                story.append(Paragraph("<b>Summary Totals:</b>", normal_style))
                
                # Create summary table
                summary_data = [
                    ['Metric', 'Total Amount'],
                    ['Total Sale Value', f"₹{total_sale_value:,.0f}"],
                    ['Total Profit', f"₹{total_profit:,.0f}"],
                    ['Total Retail Stock Value', f"₹{total_stock_value:,.0f}"],
                    ['Total Brands Analyzed', f"{len(all_brand_data)}"]
                ]
                
                summary_table = Table(summary_data, colWidths=[3*inch, 2*inch])
                summary_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), HexColor('#16a34a')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, -1), 9),
                    ('TOPPADDING', (0, 0), (-1, -1), 6),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                    ('BACKGROUND', (0, 1), (-1, -1), HexColor('#f0fdf4')),
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.black)
                ]))
                
                story.append(summary_table)
                story.append(Spacer(1, 10))
                story.append(Paragraph(f"<i>Complete Brand-Wise Sale Analysis across {total_pages} pages in landscape orientation. All {len(all_brand_data)} brands included with detailed financial metrics.</i>", normal_style))
            
            story.append(Spacer(1, 15))
        
        # Build PDF
        doc.build(story)
        output.seek(0)
        
        # Generate filename with IST timestamp
        ist_timezone = pytz.timezone('Asia/Kolkata')
        current_time = datetime.now(ist_timezone)
        filename = f"monthly_report_{current_time.strftime('%Y%m%d_%H%M%S')}.pdf"
        
        return StreamingResponse(
            output,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
        
    except Exception as e:
        logging.error(f"Error generating PDF report: {e}")
        raise HTTPException(status_code=500, detail=f"Error generating PDF report: {str(e)}")

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
