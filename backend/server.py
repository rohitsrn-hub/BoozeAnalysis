from fastapi import FastAPI, APIRouter, File, UploadFile, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
import traceback
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
import uuid
from datetime import datetime, timezone, timedelta
import pandas as pd
import io

# Import authentication routes factory
# AUTH REMOVED - Backup in /BACKUP_AUTH_CODE/
# from auth.routes import create_auth_router
import json
import pytz
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
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Collection name prefixes for data separation
LIQUOR_PREFIX = "liquor_"  # Prefix for all liquor app collections

# Collection references with proper prefixing
class Collections:
    """Centralized collection references for the Liquor app"""
    @property
    def liquor_data(self):
        return db[f"{LIQUOR_PREFIX}data"]
    
    @property
    def upload_history(self):
        return db[f"{LIQUOR_PREFIX}upload_history"]
    
    @property
    def stock_backups(self):
        return db[f"{LIQUOR_PREFIX}stock_backups"]
    
    @property
    def brands_master(self):
        return db[f"{LIQUOR_PREFIX}brands_master"]

# Initialize collections
collections = Collections()

# Create the main app without a prefix
app = FastAPI()

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# AUTH REMOVED - Backup in /BACKUP_AUTH_CODE/
# auth_router = create_auth_router(db.users)
# api_router.include_router(auth_router, tags=["authentication"])

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
    # New fields for enhanced analysis
    index_number: int = Field(default=0)
    wholesale_rate: float = Field(default=0.0)
    selling_rate: float = Field(default=0.0)
    D1_date: str = Field(default="N/A")
    D1_stock: float = Field(default=0.0)
    DL_date: str = Field(default="N/A")
    DL_stock: float = Field(default=0.0)
    total_sales_qty: float = Field(default=0.0)
    avg_daily_sales_qty: float = Field(default=0.0)
    days_analyzed: int = Field(default=0)
    current_stock_qty: int = Field(default=0)
    upload_timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class UploadHistory(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    filename: str
    upload_type: str  # "full_monthly", "daily_update", or "rate_update"
    upload_timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    records_count: int
    file_size: int
    uploaded_by: str = Field(default="dashboard_user")
    can_undo: bool = Field(default=True)  # Whether this upload can be undone
    undone_at: Optional[datetime] = None  # When was this upload undone
    changes_snapshot: Optional[Dict[str, Any]] = None  # Detailed changes for granular undo

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

class ChartsResponse(BaseModel):
    volume_leaders: List[Dict[str, Any]]
    velocity_leaders: List[Dict[str, Any]]
    revenue_leaders: List[Dict[str, Any]]
    revenue_proportion: List[Dict[str, Any]]

class DemandRecommendation(BaseModel):
    brand_name: str
    selling_rate: float
    wholesale_rate: float
    current_stock_qty: int
    recommended_qty: float
    urgency_level: str

# Module 1: Brand & Rate Management Models
class AddBrandRequest(BaseModel):
    """Request model for adding a new brand manually"""
    index_number: int
    brand_name: str
    wholesale_rate: float
    selling_rate: float
    initial_stock_qty: int = Field(default=0)

class BrandRateInfo(BaseModel):
    """Response model for brand rate information"""
    id: str
    index_number: int
    brand_name: str
    wholesale_rate: float
    selling_rate: float
    current_stock_qty: int
    stock_value_today: float
    last_updated: datetime

class UpdateRatesResponse(BaseModel):
    """Response for bulk rate update operations"""
    updated_count: int
    not_found_count: int
    updated_brands: List[str]
    not_found_brands: List[str]

# Module 3: Stock Reset & Backup Models
class StockBackup(BaseModel):
    """Model for stock backup records"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    backup_timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    total_records: int
    backup_reason: str = Field(default="manual_backup")
    created_by: str = Field(default="dashboard_user")
    data_snapshot: List[Dict[str, Any]]

class BackupListResponse(BaseModel):
    """Response for listing backups"""
    id: str
    backup_timestamp: datetime
    total_records: int
    backup_reason: str
    created_by: str

# Module 4: Monthly Report Generation Models
class ReportParameters(BaseModel):
    """Parameters for PDF report generation"""
    include_executive_summary: bool = True
    include_top_sellers: bool = True
    include_slow_sellers: bool = True
    include_capital_blockers: bool = True
    include_revenue_analysis: bool = True
    include_demand_forecast: bool = True
    include_profit_analysis: bool = True
    include_recommendations: bool = True
    include_datewise_analysis: bool = False
    report_title: str = "Monthly Sales Analytics Report"
    report_period: str = ""

# Module 5: Historical Sales Averages Models
class HistoricalSalesAverage(BaseModel):
    """Model for storing historical sales averages before reset"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    brand_name: str
    month_year: str  # Format: "Sep-2025"
    average_daily_sales_qty: float  # Average bottles sold per day
    average_daily_sales_value: float  # Average revenue per day
    total_sales_quantity: float  # Total bottles sold in the month
    total_sales_value: float  # Total revenue in the month
    total_sales_days: int  # Number of days with sales data
    wholesale_rate: float = Field(default=0.0)
    selling_rate: float = Field(default=0.0)
    calculation_date: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class BrandMaster(BaseModel):
    """Master collection for brand rates that persist across stock resets"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    brand_name: str
    wholesale_rate: float = Field(default=0.0)
    selling_rate: float = Field(default=0.0)
    index_number: int = Field(default=0)
    last_updated: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class AnalyticsSourceInfo(BaseModel):
    """Information about data source used for analytics"""
    data_source: str  # "historical" or "current"
    days_of_data: int
    using_month: str
    transition_threshold: int = 5
    is_transitioning: bool
    confidence_level: str  # "low", "medium", "high"

class TopSeller(BaseModel):
    brand_name: str
    revenue: float
    volume: float
    profit: float
    profit_margin: float

class SlowSeller(BaseModel):
    brand_name: str
    revenue: float
    volume: float
    stock_days: float
    stock_value: float

class CapitalBlocker(BaseModel):
    brand_name: str
    stock_value: float
    stock_quantity: float
    stock_days: float
    overstocked_ratio: float

class DemandForecastItem(BaseModel):
    brand_name: str
    current_stock: float
    recommended_qty: float
    wholesale_rate: float
    total_cost: float
    urgency_level: str

class ProfitAnalysis(BaseModel):
    total_revenue: float
    total_cost: float
    total_profit: float
    average_profit_margin: float
    top_profit_brands: List[Dict[str, Any]]

class MonthlyReportData(BaseModel):
    """Complete monthly report data structure"""
    report_period: str
    total_brands: int
    executive_summary: Dict[str, Any]
    top_sellers_revenue: List[TopSeller]
    top_sellers_volume: List[TopSeller]
    slow_sellers: List[SlowSeller]
    capital_blockers: List[CapitalBlocker]
    demand_forecast: List[DemandForecastItem]
    profit_analysis: ProfitAnalysis
    recommendations: List[str]

# Helper functions
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
    """Parse today's stock data - extract new date column and stock values for appending"""
    try:
        # Read the Excel file
        df = pd.read_excel(io.BytesIO(file_content))
        
        if df.empty:
            raise HTTPException(status_code=400, detail="The uploaded file is empty or contains no data")
        
        # Clean column names - handle non-string column names
        df.columns = [str(col).strip() if col is not None else f"Unnamed_{i}" for i, col in enumerate(df.columns)]
        
        # Find key columns
        brand_col = None
        index_col = None
        new_date_col = None
        rate_col = None
        
        for col in df.columns:
            col_str = str(col)
            col_lower = col_str.lower().strip()
            
            if 'brand' in col_lower and 'name' in col_lower:
                brand_col = col
            elif any(term in col_lower for term in ['index', 'sl', 'sr', 'no', 'id']) and len(col_str) <= 10:
                index_col = col
            elif 'rate' in col_lower and 'wholesale' not in col_lower:
                # Found rate column (but not wholesale rate)
                rate_col = col
                print(f"✅ Detected rate column: '{col}'")
            else:
                # Check if this is the new date column (should be only one date column in today's data)
                is_date_column = False
                
                # Method 1: Check for month names
                if any(date_part in col_lower for date_part in ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec']):
                    is_date_column = True
                
                # Method 2: Check for date patterns
                import re
                date_patterns = [
                    r'\d{1,2}[-/]\d{1,2}[-/]\d{2,4}',
                    r'\d{1,2}[-/]\w{3}[-/]?\d{0,4}',
                    r'\w{3}[-/]\d{1,2}[-/]?\d{0,4}',
                    r'\d{4}[-/]\d{1,2}[-/]\d{1,2}',
                ]
                
                for pattern in date_patterns:
                    if re.search(pattern, col_str, re.IGNORECASE):
                        is_date_column = True
                        break
                
                if is_date_column and new_date_col is None:
                    new_date_col = col
                    print(f"✅ Detected today's date column: '{col}'")
        
        if not brand_col:
            raise HTTPException(status_code=400, detail="Could not find 'Brand Name' column in today's data file")
        
        if not new_date_col:
            raise HTTPException(status_code=400, detail="Could not find date column in today's data file")
        
        print("📊 Today's Data Column Detection:")
        print(f"  - Brand column: {brand_col}")
        print(f"  - Index column: {index_col}")
        print(f"  - Rate column: {rate_col}")
        print(f"  - New date column: {new_date_col}")
        
        # Extract data for each brand
        todays_data = {
            'new_date_column': str(new_date_col),
            'brands_data': {}
        }
        
        # Filter out header rows
        df = df[df[brand_col].notna()]
        df = df[~df[brand_col].astype(str).str.contains('total|sum|^brand name$|^name$|^brand$', na=False, case=False)]
        
        for idx, row in df.iterrows():
            try:
                brand_name = str(row[brand_col]).strip()
                if not brand_name or brand_name.lower() in ['nan', 'none', '']:
                    continue
                
                # Get index number for matching
                index_num = idx + 1
                if index_col and pd.notna(row[index_col]):
                    try:
                        index_val = str(row[index_col]).strip()
                        import re
                        numeric_match = re.search(r'\d+', index_val)
                        if numeric_match:
                            index_num = int(numeric_match.group())
                    except:
                        pass
                
                # Get stock quantity for the new date
                stock_qty = 0
                try:
                    if pd.notna(row[new_date_col]):
                        stock_qty = float(row[new_date_col])
                except:
                    stock_qty = 0
                
                # Get rate if available
                rate = 0.0
                if rate_col is not None:
                    try:
                        if pd.notna(row[rate_col]):
                            rate = float(row[rate_col])
                    except:
                        rate = 0.0
                
                todays_data['brands_data'][brand_name] = {
                    'index_number': index_num,
                    'stock_qty': stock_qty,
                    'rate': rate  # Include rate from Excel
                }
                
                print(f"  {brand_name} (Index: {index_num}): {stock_qty} units on {new_date_col}")
                
            except Exception as e:
                print(f"Warning: Error parsing row for {brand_name}: {e}")
                continue
        
        if not todays_data['brands_data']:
            raise HTTPException(status_code=400, detail="No valid brand data found in today's file")
        
        print(f"✅ Successfully parsed today's data for {len(todays_data['brands_data'])} brands")
        return todays_data
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error parsing today's data: {str(e)}")

def parse_excel_data(file_content: bytes, upload_type: str = "full_monthly") -> List[Dict[str, Any]]:
    """Parse Excel file and return structured data - supports both tabular and list formats"""
    try:
        # Try to read as Excel with headers first (tabular format)
        try:
            df = pd.read_excel(io.BytesIO(file_content))
            
            # Check if it looks like a tabular format (has typical column names)
            if len(df.columns) >= 3 and any(str(col).lower().strip() in ['brand name', 'brand_name', 'product', 'name'] for col in df.columns):
                return parse_tabular_format(df, upload_type)
            else:
                # Try headerless format
                df_headerless = pd.read_excel(io.BytesIO(file_content), header=None)
                return parse_list_format(df_headerless)
                
        except Exception as excel_error:
            # If Excel fails, try CSV only if it's likely a CSV file (not binary Excel)
            try:
                # Try to decode as text first to check if it's a CSV
                file_content_str = file_content.decode('utf-8')
                
                # If decoding succeeds, it might be a CSV file
                df = pd.read_csv(io.StringIO(file_content_str))
                if len(df.columns) >= 3 and any(str(col).lower().strip() in ['brand name', 'brand_name', 'product', 'name'] for col in df.columns):
                    return parse_tabular_format(df, upload_type)
                else:
                    df_headerless = pd.read_csv(io.StringIO(file_content_str), header=None)
                    return parse_list_format(df_headerless)
                    
            except UnicodeDecodeError:
                # If it can't be decoded as UTF-8, it's likely a binary Excel file with encoding issues
                # Try different Excel reading approaches
                try:
                    # Try reading Excel without specifying engine
                    df = pd.read_excel(io.BytesIO(file_content), engine='openpyxl')
                    return parse_tabular_format(df, upload_type)
                except:
                    try:
                        # Try with xlrd engine for older Excel files
                        df = pd.read_excel(io.BytesIO(file_content), engine='xlrd')
                        return parse_tabular_format(df, upload_type)
                    except:
                        pass
                        
                raise HTTPException(
                    status_code=400, 
                    detail=f"Unable to parse Excel file. The file may be corrupted or in an unsupported format. Original error: {str(excel_error)}"
                )
            except Exception as csv_error:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Unable to parse file. Please ensure it's a valid Excel or CSV file. Error: {str(csv_error)}"
                )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error parsing file: {str(e)}")

def parse_tabular_format(df: pd.DataFrame, upload_type: str = "full_monthly") -> List[Dict[str, Any]]:
    """Parse liquor stock data with FIXED D1 and DL calculation"""
    if df.empty:
        raise HTTPException(status_code=400, detail="The uploaded file is empty or contains no data")
    
    try:
        # Clean column names - handle non-string column names
        df.columns = [str(col).strip() if col is not None else f"Unnamed_{i}" for i, col in enumerate(df.columns)]
    except Exception as e:
        print(f"Warning: Error cleaning column names: {e}")
        # Fallback: create simple column names
        df.columns = [f"Column_{i}" for i in range(len(df.columns))]
    
    # DEBUG: Print all columns to see what pandas is reading
    print(f"🔍 DEBUG: Total columns found by pandas: {len(df.columns)}")
    print(f"🔍 DEBUG: All column headers: {list(df.columns)}")
    
    # Find key columns
    brand_col = None
    wholesale_rate_col = None
    selling_rate_col = None
    index_col = None
    date_columns = []
    
    for col in df.columns:
        # Convert column name to string and handle potential NaN/float values
        col_str = str(col) if col is not None else ""
        col_lower = col_str.lower().strip()
        
        print(f"🔍 Processing column: '{col}' (lower: '{col_lower}')")
        
        if 'brand' in col_lower and 'name' in col_lower:
            brand_col = col
            print(f"  ➜ Identified as BRAND column")
        elif ('wholesale' in col_lower or 'w/' in col_lower or col_lower == 'w/rate') and 'rate' in col_lower:
            wholesale_rate_col = col
            print(f"  ➜ Identified as WHOLESALE RATE column")
        elif ('selling' in col_lower or 'retail' in col_lower or col_lower == 'rate' or col_lower == 's/rate') and 'rate' in col_lower:
            selling_rate_col = col
            print(f"  ➜ Identified as SELLING RATE column")
        elif 'rate' in col_lower and '/' not in col_lower and not wholesale_rate_col and not selling_rate_col:
            selling_rate_col = col  # Default to selling rate if only one rate column (but not W/RATE or S/RATE)
            print(f"  ➜ Identified as RATE column (default to selling)")
        elif any(term in col_lower for term in ['index', 'sl', 'sr', 'no', 'id']) and len(col_str) <= 10:
            index_col = col
            print(f"  ➜ Identified as INDEX column")
        else:
            # Check if column represents a date (more flexible detection)
            is_date_column = False
            
            # DEBUG: Print all non-standard columns
            print(f"🔍 Checking column: '{col}' (lower: '{col_lower}')")
            
            # IMPORTANT: Skip columns that are clearly rate-related (even if not captured above)
            if ('rate' in col_lower or 'price' in col_lower or 'cost' in col_lower or 'value' in col_lower) and '/' in col_str:
                # This is likely W/RATE, S/RATE, or similar - NOT a date column
                is_date_column = False
                print(f"⛔ Skipping rate column: '{col}' (contains rate/price with slash)")
            # Method 1: Check for month names (original logic)
            elif any(date_part in col_lower for date_part in ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec']):
                is_date_column = True
                print(f"✓ Month name found in: '{col}'")
            
            # Method 2: Check for date patterns using regex
            import re
            date_patterns = [
                r'\d{1,2}[-/]\d{1,2}[-/]\d{2,4}',     # 20/09/25, 03-10-25
                r'\d{1,2}[-/]\w{3}[-/]?\d{0,4}',      # 20-Sep-25, 03-Oct-25  
                r'\w{3}[-/]\d{1,2}[-/]?\d{0,4}',      # Sep-20-25, Oct-03-25
                r'\d{4}[-/]\d{1,2}[-/]\d{1,2}',       # 2025-09-20, 2025-10-03
                r'\d{1,2}\s+\w+\s+\d{2,4}',          # 20 Sep 25, 03 Oct 25
            ]
            
            for pattern in date_patterns:
                if re.search(pattern, col_str, re.IGNORECASE):
                    is_date_column = True
                    break
            
            # Method 3: Check for date-like keywords
            date_keywords = ['date', 'day', 'month', 'year', 'time', 'period']
            if any(keyword in col_lower for keyword in date_keywords):
                is_date_column = True
            
            # Method 4: If column contains only numbers, it might be dates
            # Try to parse the first non-empty cell to see if it's a date-like number
            if not is_date_column and col in df.columns:
                try:
                    first_values = df[col].dropna().head(3)
                    for val in first_values:
                        val_str = str(val).strip()
                        # Check if it looks like a date number (e.g., 44520 for Excel date serial)
                        if val_str.replace('.', '').isdigit() and len(val_str) >= 4:
                            # Might be Excel date serial number or similar
                            is_date_column = True
                            break
                except:
                    pass
            
            if is_date_column:
                date_columns.append(col)
                print(f"✅ Detected date column: '{col}'")
    
    # Filter and sort date columns properly 
    print(f"Date columns BEFORE filtering: {date_columns}")
    
    # Smart two-pass parsing system to handle ambiguous DD/MM vs MM/DD formats
    def detect_date_format(date_columns_list):
        """
        Intelligently detect whether numeric dates are DD/MM or MM/DD format.
        Returns: 'DD/MM' or 'MM/DD' or 'AMBIGUOUS'
        """
        import re
        
        numeric_dates = []
        for col in date_columns_list:
            col_str = str(col).strip()
            # Only check numeric dates (not month-name dates like "20-Sep-25")
            match = re.search(r'(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})', col_str)
            if match:
                first_num = int(match.group(1))
                second_num = int(match.group(2))
                numeric_dates.append((first_num, second_num, col_str))
        
        if not numeric_dates:
            return 'DD/MM'  # Default if no numeric dates found
        
        # Smart detection logic:
        # 1. If any first number > 12, it MUST be DD/MM format (days can be 13-31)
        # 2. If any second number > 12, it MUST be DD/MM format (month can't be > 12)
        # 3. If both are always <= 12, it's ambiguous - default to DD/MM (Indian standard)
        
        has_first_gt_12 = any(first > 12 for first, second, _ in numeric_dates)
        has_second_gt_12 = any(second > 12 for first, second, _ in numeric_dates)
        
        if has_first_gt_12:
            print("📍 Date format detected: DD/MM (found day > 12 in first position)")
            return 'DD/MM'
        
        if has_second_gt_12:
            print("📍 Date format detected: MM/DD (found value > 12 in second position)")
            return 'MM/DD'
        
        # All values <= 12 in both positions - ambiguous
        print("📍 Date format ambiguous (all values ≤ 12), defaulting to DD/MM (Indian standard)")
        return 'DD/MM'
    
    # Detect the date format before parsing
    detected_format = detect_date_format(date_columns)
    print(f"🎯 Using date format: {detected_format}")
    
    def parse_date_column(col_name, date_format='DD/MM'):
        """Parse date from column name using specified format - return None if invalid"""
        try:
            import re
            from datetime import datetime
            
            col_clean = str(col_name).strip()
            
            # Pattern 1: day-month-year with month name (20-Sep-25, 01-Oct-25, etc.)
            # Use [A-Za-z] instead of \w to ensure we match letters only (not digits)
            match = re.search(r'(\d{1,2})[-/]([A-Za-z]{3})[-/]?(\d{0,4})', col_clean, re.IGNORECASE)
            if match:
                day, month_name, year_suffix = match.groups()
                
                # Handle year - be strict about valid years
                if not year_suffix:
                    year = '2025'
                elif len(year_suffix) == 2 and year_suffix.isdigit():
                    year = f"20{year_suffix}"  # 25 -> 2025
                elif len(year_suffix) == 4 and year_suffix.isdigit():
                    year = year_suffix
                else:
                    # Invalid year format, skip this column
                    print(f"Skipping invalid date column: '{col_name}' (bad year: '{year_suffix}')")
                    return None
                
                try:
                    parsed_date = datetime.strptime(f"{day}-{month_name}-{year}", "%d-%b-%Y")
                    print(f"✓ Parsed date (month-name format): '{col_name}' -> {parsed_date.strftime('%Y-%m-%d')}")
                    return parsed_date
                except ValueError as e:
                    print(f"Skipping unparseable date: '{col_name}' (error: {e})")
                    return None
            
            # Pattern 2: Numeric date formats with intelligent format detection
            # Check YYYY-MM-DD first (unambiguous ISO format)
            match = re.search(r'(\d{4})[/-](\d{1,2})[/-](\d{1,2})', col_clean)
            if match:
                year, month, day = match.groups()
                date_str = f"{year}/{month}/{day}"
                try:
                    parsed_date = datetime.strptime(date_str, '%Y/%m/%d')
                    print(f"✓ Parsed date (YYYY/MM/DD): '{col_name}' -> {parsed_date.strftime('%Y-%m-%d')}")
                    return parsed_date
                except ValueError:
                    pass
            
            # Check numeric dates DD/MM or MM/DD based on detected format
            match = re.search(r'(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})', col_clean)
            if match:
                first_num, second_num, year_part = match.groups()
                
                # Apply detected format
                if date_format == 'DD/MM':
                    day, month = first_num, second_num
                    format_name = 'DD/MM'
                else:  # MM/DD
                    month, day = first_num, second_num
                    format_name = 'MM/DD'
                
                # Handle year
                if len(year_part) == 2:
                    year = f"20{year_part}"
                    date_str = f"{day}/{month}/{year}"
                    date_format_str = '%d/%m/%Y'
                else:
                    year = year_part
                    date_str = f"{day}/{month}/{year}"
                    date_format_str = '%d/%m/%Y'
                
                try:
                    parsed_date = datetime.strptime(date_str, date_format_str)
                    print(f"✓ Parsed date ({format_name}): '{col_name}' -> {parsed_date.strftime('%Y-%m-%d')}")
                    return parsed_date
                except ValueError as e:
                    print(f"⚠ Failed to parse '{col_name}' as {format_name}: {e}")
                    return None
            
            # If no pattern matched
            print(f"⚠ Skipping column (no recognizable date format): '{col_name}'")
            return None
                
        except Exception as e:
            print(f"❌ Exception parsing '{col_name}': {e}")
            return None
    
    # Filter out invalid date columns and sort the valid ones
    valid_date_columns = []
    for col in date_columns:
        parsed_date = parse_date_column(col, date_format=detected_format)
        if parsed_date is not None:
            valid_date_columns.append((col, parsed_date))
    
    # Sort by parsed date
    valid_date_columns.sort(key=lambda x: x[1])
    
    # Extract just the column names in correct order
    date_columns = [col for col, date in valid_date_columns]
    
    print(f"Valid date columns AFTER filtering and sorting: {date_columns}")
    
    print("📊 Column Detection Summary:")
    print(f"  - Brand column: {brand_col}")
    print(f"  - Index column: {index_col}")
    print(f"  - Wholesale rate: {wholesale_rate_col}")
    print(f"  - Selling rate: {selling_rate_col}")
    print(f"  - Date columns found: {date_columns}")
    print(f"  - All available columns: {list(df.columns)}")
    
    if not brand_col:
        raise HTTPException(status_code=400, detail="Could not find 'Brand Name' column in the file")
    
    if not date_columns:
        # Try one more fallback - use any remaining columns that aren't brand/rate columns
        potential_date_cols = []
        for col in df.columns:
            col_str = str(col)
            if (col != brand_col and col != wholesale_rate_col and col != selling_rate_col and 
                col != index_col and col_str.lower().strip() not in ['brand name', 'brand_name', 'rate', 'index', 'sl', 'sr']):
                potential_date_cols.append(col)
        
        if potential_date_cols:
            print(f"🔄 Fallback: Using potential date columns: {potential_date_cols}")
            date_columns = potential_date_cols[:10]  # Limit to first 10 columns
        else:
            # Show detailed error with column information
            available_columns = [str(col) for col in df.columns]
            raise HTTPException(
                status_code=400, 
                detail={
                    "error": "No date columns detected",
                    "message": "Could not identify date columns in your Excel file. Please ensure your file has columns with dates (like '20-Sep-25', '03-Oct-25', etc.)",
                    "available_columns": available_columns,
                    "suggestions": [
                        "Ensure date columns contain recognizable date formats (20-Sep-25, 03/10/25, etc.)",
                        "Check that date columns have month names or date patterns",
                        "Verify your Excel file structure matches the expected format"
                    ]
                }
            )
    
    # Filter out only obvious header rows, be more lenient
    df = df[df[brand_col].notna()]
    df = df[~df[brand_col].astype(str).str.contains('total|sum|^brand name$|^name$|^brand$', na=False, case=False)]
    
    print(f"After filtering, found {len(df)} potential brand rows")
    
    if df.empty:
        raise HTTPException(status_code=400, detail="No valid brand data found after filtering")
    
    # CORRECTED D1 and DL CALCULATION - SIMPLE AND ACCURATE
    # D1: ALWAYS First date column in Excel sheet
    # DL: ALWAYS Last date column in Excel sheet
    
    if not date_columns:
        raise HTTPException(status_code=400, detail="No valid date columns found in the Excel file")
    
    # D1 = First valid date column (e.g., 20-Sep)
    global_D1_date = date_columns[0]
    print(f"*** D1 (First Valid Date Column): {global_D1_date} ***")
    
    # DL = Last valid date column (e.g., 03-Oct) 
    global_DL_date = date_columns[-1]
    print(f"*** DL (Last Valid Date Column): {global_DL_date} ***")
    
    # STEP 2: Process each brand with the SIMPLE D1 and DL logic
    liquor_data = []
    
    for idx, row in df.iterrows():
        try:
            brand_name = str(row[brand_col]).strip()
            if not brand_name or brand_name.lower() in ['nan', 'none', '']:
                continue
            
            # Get index - preserve original index from Excel file
            index_num = idx + 1
            if index_col and pd.notna(row[index_col]):
                try:
                    # Try to extract integer from the index value
                    index_val = str(row[index_col]).strip()
                    # Handle cases where index might have extra characters
                    import re
                    numeric_match = re.search(r'\d+', index_val)
                    if numeric_match:
                        index_num = int(numeric_match.group())
                    else:
                        index_num = int(float(row[index_col]))
                except:
                    index_num = idx + 1
            
            # Get rates from Excel file
            wholesale_rate = 0.0
            selling_rate = 0.0
            
            if wholesale_rate_col and pd.notna(row[wholesale_rate_col]):
                try:
                    wholesale_rate = float(row[wholesale_rate_col])
                except:
                    pass
            
            if selling_rate_col and pd.notna(row[selling_rate_col]):
                try:
                    selling_rate = float(row[selling_rate_col])
                except:
                    pass
            
            # Note: If rates not in Excel, they will be filled from database in the upload endpoint
            # Store flags to indicate if rates need to be fetched from DB
            needs_wholesale_from_db = (wholesale_rate == 0)
            needs_selling_from_db = (selling_rate == 0)
            
            # Get daily stock data
            daily_stock_data = {}
            valid_stock_values = []
            
            for date_col in date_columns:
                try:
                    raw_value = row[date_col]
                    if pd.notna(raw_value) and str(raw_value).strip() != '':
                        stock_qty = 0
                        try:
                            stock_qty = float(raw_value)
                        except (ValueError, TypeError):
                            try:
                                stock_qty = float(str(raw_value).replace(',', ''))
                            except:
                                stock_qty = 0
                        
                        daily_stock_data[date_col] = stock_qty
                        
                        if stock_qty >= 0:
                            valid_stock_values.append((date_col, stock_qty))
                    else:
                        daily_stock_data[date_col] = 0
                        
                except Exception:
                    daily_stock_data[date_col] = 0
            
            if not valid_stock_values:
                print(f"WARNING: No valid stock data found for {brand_name}")
                continue
            
            # Use corrected D1 and DL dates
            D1_date = global_D1_date
            D1_stock = daily_stock_data.get(global_D1_date, 0)
            
            DL_date = global_DL_date
            DL_stock = daily_stock_data.get(global_DL_date, 0)
            
            # If brand has no data on D1/DL dates, find closest dates
            sorted_stock_values = sorted(valid_stock_values, key=lambda x: x[0])
            
            if D1_stock == 0:
                for date_col, stock_val in sorted_stock_values:
                    if date_col <= global_D1_date:
                        D1_stock = stock_val
                    else:
                        break
            
            if DL_stock == 0:
                for date_col, stock_val in reversed(sorted_stock_values):
                    if date_col <= global_DL_date:
                        DL_stock = stock_val
                        break
            
            print(f"  {brand_name}: D1={D1_date}({D1_stock}), DL={DL_date}({DL_stock})")
            
            # Calculate total sales between D1 and DL
            total_sales_qty = max(0, D1_stock - DL_stock)
            
            # Calculate number of days between D1 and DL using actual date arithmetic
            try:
                from datetime import datetime
                
                def parse_date_string(date_str):
                    """Parse date string like '20-Sep-25' to datetime object"""
                    import re
                    match = re.search(r'(\d{1,2})[-/](\w{3})[-/]?(\d{0,4})', date_str, re.IGNORECASE)
                    if match:
                        day, month_name, year_suffix = match.groups()
                        year = '2025' if not year_suffix or len(year_suffix) < 2 else (f"20{year_suffix}" if len(year_suffix) == 2 else year_suffix[:4])
                        return datetime.strptime(f"{day}-{month_name}-{year}", "%d-%b-%Y")
                    return None
                
                d1_datetime = parse_date_string(D1_date)
                dl_datetime = parse_date_string(DL_date)
                
                if d1_datetime and dl_datetime:
                    # Calculate actual days difference (inclusive of both start and end dates)
                    days_between = (dl_datetime - d1_datetime).days + 1
                    print(f"  {brand_name}: Date arithmetic: {D1_date} to {DL_date} = {days_between} days")
                else:
                    # Fallback to index-based calculation if date parsing fails
                    d1_idx = date_columns.index(D1_date) if D1_date in date_columns else 0
                    dl_idx = date_columns.index(DL_date) if DL_date in date_columns else len(date_columns) - 1
                    days_between = max(1, dl_idx - d1_idx + 1)
                    print(f"  {brand_name}: Fallback calculation: {days_between} days (index-based)")
                
                # Ensure minimum of 1 day
                days_between = max(1, days_between)
                
            except Exception as e:
                print(f"  {brand_name}: Error calculating days - using default: {e}")
                days_between = max(1, len(sorted_stock_values) - 1)
            
            # Calculate average daily sales
            avg_daily_sales_qty = total_sales_qty / days_between if days_between > 0 else 0
            
            # Calculate monthly sales (24 days as requested)
            monthly_sales_qty = avg_daily_sales_qty * 24
            monthly_sales_value = monthly_sales_qty * selling_rate
            
            # Current stock value (on DL date)
            current_stock_value = DL_stock * selling_rate
            
            # Calculate stock ratio (stock value / monthly sales value)
            stock_ratio = current_stock_value / max(1, monthly_sales_value) if monthly_sales_value > 0 else 0
            
            # Stock availability in days
            stock_available_days = (DL_stock / max(0.1, avg_daily_sales_qty)) if avg_daily_sales_qty > 0 else 999
            
            brand_data = {
                'brand_name': brand_name,
                'product_id': f"ID_{index_num}",
                'index_number': int(index_num),
                'wholesale_rate': float(wholesale_rate),
                'selling_rate': float(selling_rate),
                'rate': float(selling_rate),
                'D1_date': str(D1_date),
                'D1_stock': float(D1_stock),
                'DL_date': str(DL_date),
                'DL_stock': float(DL_stock),
                'current_stock_qty': int(max(0, DL_stock)),
                'total_sales_qty': float(total_sales_qty),
                'avg_daily_sales_qty': float(avg_daily_sales_qty),
                'monthly_sales_qty': float(monthly_sales_qty),
                'monthly_sale_value': float(monthly_sales_value),
                'monthly_sale_qty': int(max(0, monthly_sales_qty)),
                'stock_value_today': float(current_stock_value),
                'stock_ratio': float(stock_ratio),
                'stock_available_days': float(min(999, max(0, stock_available_days))),
                'avg_daily_sale': float(monthly_sales_value / 30),
                'stock_value_before': float(D1_stock * selling_rate),
                'daily_sales': daily_stock_data,
                'days_analyzed': int(max(1, days_between)),
            }
            
            liquor_data.append(brand_data)
            
        except Exception as e:
            logging.error(f"Error parsing row {idx} ({brand_name}): {e}")
            continue
    
    if not liquor_data:
        raise HTTPException(status_code=400, detail="No valid liquor data could be extracted from the file")
    
    print(f"Successfully parsed {len(liquor_data)} out of {len(df)} potential brands")
    logging.info(f"Successfully parsed {len(liquor_data)} liquor brands with corrected D1/DL analysis")
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
    """Upload and process Excel/CSV file with complete monthly liquor data - replaces existing data"""
    try:
        # Validate file type
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
        parsed_data = parse_excel_data(content, "full_monthly")
        
        if not parsed_data:
            raise HTTPException(status_code=400, detail="No valid data found in the file")
        
        # For full monthly data, we don't need to check duplicates since it replaces everything
        # But we can log the dates being processed for reference
        new_dates = set()
        for item in parsed_data[:3]:  # Just check first few items for logging
            dl_date = item.get('DL_date')
            if dl_date:
                new_dates.add(dl_date)
        if new_dates:
            print(f"📅 Full monthly upload processing dates: {sorted(list(new_dates))}")
        
        # Before clearing, get existing brands to preserve their rates if not in new file
        existing_brands_dict = {}
        existing_brands = await collections.liquor_data.find({}, {"brand_name": 1, "wholesale_rate": 1, "selling_rate": 1}).to_list(1000)
        for brand in existing_brands:
            existing_brands_dict[brand['brand_name']] = {
                'wholesale_rate': brand.get('wholesale_rate', 0.0),
                'selling_rate': brand.get('selling_rate', brand.get('rate', 0.0))
            }
        
        # Fill in missing rates from existing database records
        for item_data in parsed_data:
            brand_name = item_data['brand_name']
            if brand_name in existing_brands_dict:
                # If wholesale_rate is 0 in new data, use existing
                if item_data.get('wholesale_rate', 0) == 0:
                    item_data['wholesale_rate'] = existing_brands_dict[brand_name]['wholesale_rate']
                # If selling_rate is 0 in new data, use existing
                if item_data.get('selling_rate', 0) == 0:
                    item_data['selling_rate'] = existing_brands_dict[brand_name]['selling_rate']
                    item_data['rate'] = existing_brands_dict[brand_name]['selling_rate']
                # Recalculate stock value with correct rates
                item_data['stock_value_today'] = item_data['current_stock_qty'] * item_data['selling_rate']
                item_data['monthly_sale_value'] = item_data.get('total_sales_qty', 0) * item_data['selling_rate']
        
        # CRITICAL: Create backup before deleting data (for undo functionality)
        backup_id = None
        all_existing_records = await collections.liquor_data.find({}, {"_id": 0}).to_list(1000)
        if all_existing_records:
            backup = StockBackup(
                data_snapshot=all_existing_records,
                total_records=len(all_existing_records),
                backup_reason="pre_full_monthly_upload"
            )
            backup_result = await collections.stock_backups.insert_one(backup.dict())
            backup_id = backup.id
            logging.info(f"Created backup {backup_id} with {len(all_existing_records)} records before full monthly upload")
        
        # Clear existing data and insert new data (full replacement)
        await collections.liquor_data.delete_many({})
        
        # Convert to LiquorData models and insert
        liquor_objects = []
        brands_added_ids = []
        for item_data in parsed_data:
            liquor_obj = LiquorData(**item_data)
            liquor_obj_dict = liquor_obj.dict()
            liquor_objects.append(liquor_obj_dict)
            brands_added_ids.append(liquor_obj_dict['id'])
        
        if liquor_objects:
            await collections.liquor_data.insert_many(liquor_objects)
        
        # Save upload history with changes snapshot
        upload_history = UploadHistory(
            filename=file.filename,
            upload_type="full_monthly",
            records_count=len(liquor_objects),
            file_size=len(content),
            can_undo=True,  # Enable undo for this upload
            changes_snapshot={
                "brands_added": brands_added_ids,
                "replaced_all": True,
                "backup_id": backup_id  # Store backup ID for restoration
            }
        )
        await collections.upload_history.insert_one(upload_history.dict())
        
        return JSONResponse(
            status_code=200,
            content={
                "message": f"Successfully uploaded full monthly data with {len(liquor_objects)} liquor records",
                "total_records": len(liquor_objects),
                "upload_type": "full_monthly"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error uploading full monthly data: {e}")
        raise HTTPException(status_code=500, detail=f"Error processing file: {str(e)}")

@api_router.post("/upload-todays-data")
async def upload_todays_data(file: UploadFile = File(...)):
    """Upload today's stock data - appends to existing data by updating stock positions"""
    try:
        # Validate file type
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
        
        # Parse today's data (different from full monthly data parsing)
        try:
            todays_data = parse_todays_data(content)
        except HTTPException as parse_error:
            # Add specific guidance for Today's Data upload errors
            if "utf-8" in str(parse_error.detail).lower() or "codec" in str(parse_error.detail).lower():
                raise HTTPException(
                    status_code=400, 
                    detail={
                        "error": "File encoding issue",
                        "message": "Unable to read the Excel file. This may be due to file corruption or an unsupported Excel format.",
                        "suggestions": [
                            "Try saving the file as a new Excel file (.xlsx format)",
                            "Ensure the file is not corrupted",
                            "Check that the file contains proper date columns for today's data"
                        ]
                    }
                )
            else:
                raise parse_error
        
        if not todays_data or not todays_data.get('brands_data'):
            raise HTTPException(status_code=400, detail="No valid brand data found in today's file")
        
        new_date_column = todays_data['new_date_column']
        brands_data = todays_data['brands_data']
        
        # Check for duplicate dates with proper date format comparison
        def normalize_date_for_comparison(date_str):
            """Convert various date formats to a standard format for comparison"""
            try:
                from datetime import datetime
                import re
                
                if not date_str:
                    return None
                
                date_str = str(date_str).strip()
                
                # If it's already a datetime string, parse it
                if 'T' in date_str or len(date_str) > 15:
                    try:
                        dt = datetime.fromisoformat(date_str.replace('T', ' ').replace('Z', ''))
                        return dt.strftime("%Y-%m-%d")
                    except:
                        pass
                
                # Parse various date formats
                patterns = [
                    (r'(\d{1,2})[-/](\w{3})[-/]?(\d{2,4})', "%d-%b-%Y"),  # 04-Oct-25, 04-Oct-2025
                    (r'(\d{4})-(\d{1,2})-(\d{1,2})', "%Y-%m-%d"),         # 2025-10-04
                    (r'(\d{1,2})[-/](\d{1,2})[-/](\d{2,4})', "%d-%m-%Y"), # 04-10-25, 04/10/2025
                ]
                
                for pattern, fmt in patterns:
                    match = re.search(pattern, date_str, re.IGNORECASE)
                    if match:
                        if fmt == "%d-%b-%Y":
                            day, month_name, year = match.groups()
                            year = f"20{year}" if len(year) == 2 else year
                            full_date = f"{day}-{month_name}-{year}"
                            dt = datetime.strptime(full_date, fmt)
                        elif fmt == "%Y-%m-%d":
                            dt = datetime.strptime(match.group(0), fmt)
                        elif fmt == "%d-%m-%Y":
                            day, month, year = match.groups()
                            year = f"20{year}" if len(year) == 2 else year
                            dt = datetime(int(year), int(month), int(day))
                        
                        return dt.strftime("%Y-%m-%d")
                        
            except Exception as e:
                print(f"Warning: Could not normalize date '{date_str}': {e}")
                return str(date_str)
            
            return str(date_str)
        
        # Normalize the new date for comparison
        normalized_new_date = normalize_date_for_comparison(new_date_column)
        print(f"📅 New date to upload: '{new_date_column}' -> normalized: '{normalized_new_date}'")
        
        # Get existing dates and normalize them (check ALL records, not just first 10)
        existing_records = await collections.liquor_data.find({}, {"daily_sales": 1, "DL_date": 1}).to_list(1000)
        existing_dates = set()
        existing_dates_raw = []
        
        for record in existing_records:
            # Check DL_date
            if record.get('DL_date'):
                raw_dl_date = record['DL_date']
                normalized_dl_date = normalize_date_for_comparison(raw_dl_date)
                existing_dates.add(normalized_dl_date)
                existing_dates_raw.append(f"DL_date: {raw_dl_date}")
            
            # Check daily_sales dates  
            daily_sales = record.get('daily_sales', {}) or {}
            if daily_sales:
                for date_key in daily_sales.keys():
                    normalized_daily_date = normalize_date_for_comparison(date_key)
                    existing_dates.add(normalized_daily_date)
                    existing_dates_raw.append(f"daily_sales: {date_key}")
        
        print(f"📅 Existing dates in database: {sorted(list(existing_dates))}")
        print(f"📅 Raw existing dates: {existing_dates_raw[:5]}")  # Show first 5
        
        if normalized_new_date in existing_dates:
            # Show detailed information about the conflict
            matching_dates = []
            for record in existing_records[:3]:  # Show details for first 3 records
                if record.get('DL_date'):
                    raw_date = record['DL_date']
                    if normalize_date_for_comparison(raw_date) == normalized_new_date:
                        matching_dates.append(f"DL_date: {raw_date}")
                
                daily_sales = record.get('daily_sales', {}) or {}
                for date_key in daily_sales.keys():
                    if normalize_date_for_comparison(date_key) == normalized_new_date:
                        matching_dates.append(f"daily_sales: {date_key}")
            
            raise HTTPException(
                status_code=409,
                detail={
                    "error": "Duplicate dates detected",
                    "message": f"The date '{new_date_column}' (normalized: {normalized_new_date}) already exists in the database",
                    "duplicate_dates": [new_date_column],
                    "existing_dates_found": matching_dates[:3],
                    "filename": file.filename,
                    "suggestion": "This date already exists in your data. Please upload data for a newer date or use 'Upload Full Monthly Data' to replace all existing data"
                }
            )
        
        # Check if database is empty (after stock reset scenario)
        db_record_count = await collections.liquor_data.count_documents({})
        is_fresh_start = (db_record_count == 0)
        
        if is_fresh_start:
            print("🆕 Database is empty - treating Today's Data as initial D1 upload")
        
        # Track changes for undo functionality
        brands_updated = {}  # {brand_id: previous_state}
        brands_added = []    # [brand_id, brand_id, ...]
        
        # Append today's data to existing monthly data OR create fresh D1 data
        updated_count = 0
        new_brands_count = 0
        
        for brand_name, brand_info in brands_data.items():
            new_stock_qty = brand_info['stock_qty']
            index_number = brand_info['index_number']
            
            # Try to find existing brand by name first, then by index
            existing_brand = await collections.liquor_data.find_one({"brand_name": brand_name})
            if not existing_brand and index_number:
                existing_brand = await collections.liquor_data.find_one({"index_number": index_number})
            
            if existing_brand:
                # Store previous state for undo (including daily_sales BEFORE the new date is added)
                brands_updated[existing_brand['id']] = {
                    "DL_date": existing_brand.get('DL_date'),
                    "DL_stock": existing_brand.get('DL_stock'),
                    "current_stock_qty": existing_brand.get('current_stock_qty'),
                    "total_sales_qty": existing_brand.get('total_sales_qty'),
                    "avg_daily_sales_qty": existing_brand.get('avg_daily_sales_qty'),
                    "days_analyzed": existing_brand.get('days_analyzed'),
                    "monthly_sale_value": existing_brand.get('monthly_sale_value'),
                    "avg_daily_sale": existing_brand.get('avg_daily_sale'),
                    "stock_value_today": existing_brand.get('stock_value_today'),
                    "stock_available_days": existing_brand.get('stock_available_days'),
                    "stock_ratio": existing_brand.get('stock_ratio'),
                    "daily_sales": existing_brand.get('daily_sales', {})  # CRITICAL: Store daily_sales before update
                }
                
                # Normalize the date format before storing
                def normalize_date_key(date_str):
                    """Normalize date to DD-MMM-YY format for consistent storage"""
                    import re
                    from datetime import datetime
                    
                    try:
                        date_str = str(date_str).strip()
                        
                        # Method 1: Handle datetime strings (YYYY-MM-DD HH:MM:SS or YYYY-MM-DD)
                        if re.match(r'\d{4}-\d{2}-\d{2}', date_str):
                            try:
                                dt = datetime.strptime(date_str.split()[0], "%Y-%m-%d")
                                return dt.strftime("%d-%b-%y")  # Format: 16-Nov-25
                            except:
                                pass
                        
                        # Method 2: Handle DD-MMM-YY or DD-MMM-YYYY format
                        match = re.search(r'(\d{1,2})[-/](\w{3})[-/]?(\d{0,4})', date_str, re.IGNORECASE)
                        if match:
                            day, month_name, year_suffix = match.groups()
                            # Normalize to 2-digit year
                            if not year_suffix or len(year_suffix) < 2:
                                year_suffix = '25'  # Default to 2025
                            elif len(year_suffix) == 4:
                                year_suffix = year_suffix[2:]  # Convert 2025 to 25
                            # Ensure 2-digit day with leading zero
                            day = day.zfill(2)
                            # Capitalize month name properly
                            month_name = month_name.capitalize()
                            return f"{day}-{month_name}-{year_suffix}"
                        
                    except Exception as e:
                        logging.warning(f"Could not normalize date '{date_str}': {e}")
                    
                    return str(date_str)
                
                # Normalize existing daily_sales keys to consistent format
                current_daily_sales = existing_brand.get('daily_sales', {}) or {}
                normalized_daily_sales = {}
                for old_date_key, value in current_daily_sales.items():
                    normalized_key = normalize_date_key(old_date_key)
                    normalized_daily_sales[normalized_key] = value
                
                # Normalize the new date column and add it
                normalized_new_date = normalize_date_key(new_date_column)
                normalized_daily_sales[normalized_new_date] = new_stock_qty
                
                # Use the normalized dictionary
                current_daily_sales = normalized_daily_sales
                
                # Update DL to the new date
                old_DL_date = existing_brand.get('DL_date')
                old_D1_date = existing_brand.get('D1_date')
                
                # Recalculate analytics with the new data point
                D1_stock = existing_brand.get('D1_stock', 0)
                selling_rate = existing_brand.get('selling_rate', existing_brand.get('rate', 0))
                
                # Calculate new number of days with updated date range
                try:
                    def parse_date_string(date_str):
                        import re
                        match = re.search(r'(\d{1,2})[-/](\w{3})[-/]?(\d{0,4})', date_str, re.IGNORECASE)
                        if match:
                            day, month_name, year_suffix = match.groups()
                            year = '2025' if not year_suffix or len(year_suffix) < 2 else (f"20{year_suffix}" if len(year_suffix) == 2 else year_suffix[:4])
                            return datetime.strptime(f"{day}-{month_name}-{year}", "%d-%b-%Y")
                        return None
                    
                    d1_datetime = parse_date_string(old_D1_date) if old_D1_date else None
                    new_dl_datetime = parse_date_string(new_date_column)
                    
                    if d1_datetime and new_dl_datetime:
                        days_analyzed = (new_dl_datetime - d1_datetime).days + 1
                    else:
                        days_analyzed = existing_brand.get('days_analyzed', 1) + 1
                        
                    days_analyzed = max(1, days_analyzed)
                    
                except:
                    days_analyzed = existing_brand.get('days_analyzed', 1) + 1
                
                # Recalculate all dependent values
                total_sales_qty = max(0, D1_stock - new_stock_qty)
                avg_daily_sales_qty = total_sales_qty / days_analyzed if days_analyzed > 0 else 0
                monthly_sales_qty = avg_daily_sales_qty * 24
                monthly_sales_value = monthly_sales_qty * selling_rate
                current_stock_value = new_stock_qty * selling_rate
                stock_ratio = current_stock_value / max(1, monthly_sales_value) if monthly_sales_value > 0 else 0
                stock_available_days = (new_stock_qty / max(0.1, avg_daily_sales_qty)) if avg_daily_sales_qty > 0 else 999
                
                # Update the brand in database (daily uploads always extend existing period)
                update_data = {
                    "daily_sales": current_daily_sales,
                    "DL_date": new_date_column,
                    "DL_stock": float(new_stock_qty),
                    "current_stock_qty": int(new_stock_qty),
                    "days_analyzed": int(days_analyzed),
                    "total_sales_qty": float(total_sales_qty),
                    "avg_daily_sales_qty": float(avg_daily_sales_qty),
                    "monthly_sales_qty": float(monthly_sales_qty),
                    "monthly_sale_qty": int(monthly_sales_qty),
                    "monthly_sale_value": float(monthly_sales_value),
                    "stock_value_today": float(current_stock_value),
                    "stock_ratio": float(stock_ratio),
                    "stock_available_days": float(min(999, max(0, stock_available_days))),
                    "upload_timestamp": datetime.now(timezone.utc)
                }
                
                await collections.liquor_data.update_one(
                    {"_id": existing_brand["_id"]}, 
                    {"$set": update_data}
                )
                updated_count += 1
                
                print(f"✅ Updated {brand_name}: {old_DL_date}({existing_brand.get('DL_stock', 0)}) -> {new_date_column}({new_stock_qty})")
                
            else:
                # If database is empty (fresh start after reset), create brand as D1
                if is_fresh_start:
                    print(f"🆕 Creating fresh D1 record for brand '{brand_name}'")
                    
                    # First, try to get rate from uploaded Excel file
                    excel_rate = brand_info.get('rate', 0.0)
                    
                    if excel_rate > 0:
                        selling_rate = excel_rate
                        wholesale_rate = excel_rate * 0.7  # Estimate wholesale as 70% of selling
                        print(f"✅ Using rate from Excel for '{brand_name}': S={selling_rate}, W={wholesale_rate}")
                    else:
                        # Fallback: Fetch rates from brands_master if available
                        master_brand = await collections.brands_master.find_one({"brand_name": brand_name})
                        
                        if master_brand:
                            wholesale_rate = master_brand.get('wholesale_rate', 0.0)
                            selling_rate = master_brand.get('selling_rate', 0.0)
                            print(f"✅ Found persisted rates for '{brand_name}': W={wholesale_rate}, S={selling_rate}")
                        else:
                            wholesale_rate = 0.0
                            selling_rate = 0.0
                            print(f"⚠️ No rate in Excel or brands_master for '{brand_name}', using 0.0")
                    
                    # Create fresh brand record with this date as D1 and DL
                    new_brand_data = {
                        'id': str(uuid.uuid4()),
                        'brand_name': brand_name,
                        'index_number': index_number,
                        'product_id': f"ID_{index_number}",
                        'wholesale_rate': wholesale_rate,  # Loaded from brands_master
                        'selling_rate': selling_rate,      # Loaded from brands_master
                        'rate': selling_rate,
                        'D1_date': new_date_column,
                        'D1_stock': new_stock_qty,
                        'DL_date': new_date_column,
                        'DL_stock': new_stock_qty,
                        'current_stock_qty': int(new_stock_qty),
                        'total_sales_qty': 0.0,  # No sales yet (only one day)
                        'avg_daily_sales_qty': 0.0,
                        'monthly_sales_qty': 0.0,
                        'monthly_sale_value': 0.0,
                        'monthly_sale_qty': 0,
                        'stock_value_today': selling_rate * new_stock_qty,  # Calculated with loaded rate
                        'stock_ratio': 0.0,
                        'stock_available_days': 999,
                        'avg_daily_sale': 0.0,
                        'stock_value_before': selling_rate * new_stock_qty,  # Same as today for D1

                        'daily_sales': {new_date_column: new_stock_qty},
                        'days_analyzed': 1,
                        'upload_timestamp': datetime.now(timezone.utc)
                    }
                    
                    await collections.liquor_data.insert_one(new_brand_data)
                    brands_added.append(new_brand_data['id'])  # Track for undo
                    new_brands_count += 1
                    print(f"✅ Created fresh brand '{brand_name}' with D1={new_date_column}, stock={new_stock_qty}")
                else:
                    print(f"⚠️ Brand '{brand_name}' (Index: {index_number}) not found in existing data - skipping")
                    # Note: We don't add new brands for today's data uploads when data exists
        
        # Save upload history with changes snapshot for granular undo
        upload_history = UploadHistory(
            filename=file.filename,
            upload_type="daily_update",
            records_count=len(brands_data),
            file_size=len(content),
            can_undo=True,  # Enable undo for this upload
            changes_snapshot={
                "brands_updated": brands_updated,
                "brands_added": brands_added,
                "date_added": new_date_column
            }
        )
        await collections.upload_history.insert_one(upload_history.dict())
        
        # Determine appropriate success message
        if is_fresh_start:
            message = f"✅ Fresh start: Created {new_brands_count} brands with D1 date '{new_date_column}'. Upload more daily data or update rates next."
        elif new_brands_count > 0:
            message = f"✅ Successfully updated {updated_count} brands and added {new_brands_count} new brands for date '{new_date_column}'"
        else:
            message = f"✅ Successfully updated {updated_count} brands for date '{new_date_column}'"
        
        return JSONResponse(
            status_code=200,
            content={
                "message": message,
                "updated_brands": updated_count,
                "new_brands": new_brands_count,
                "total_records": len(brands_data),
                "upload_type": "fresh_start" if is_fresh_start else "daily_update",
                "new_date": new_date_column,
                "is_fresh_start": is_fresh_start
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error uploading today's data: {e}")
        raise HTTPException(status_code=500, detail=f"Error processing file: {str(e)}")

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
        if upload_type == "daily_update":
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
                'brand_name': record['brand_name'],
                'rate': record['rate'],
                'current_stock_qty': record.get('current_stock_qty', 0),
                'monthly_sale_value': record['monthly_sale_value'],
                'stock_value_today': record['stock_value_today'],
                'stock_available_days': record['stock_available_days'],
                'stock_ratio': record['stock_ratio']
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
    Get sales trends with D1-DL sales periods from current AND historical data
    period: 'quarterly' (last 3 sales periods), 'yearly' (last 12 periods), 'single' (specific period)
    sales_month: Format 'Sep-Oct 2025' - required when period='single'
    Returns: dict with 'series' (list of sales periods with daily data from current + history)
    """
    try:
        from collections import defaultdict
        import re
        
        def parse_date_for_sorting(date_str):
            """Parse various date formats for chronological sorting"""
            try:
                if not date_str:
                    return datetime.min
                
                date_str = str(date_str).strip()
                
                # Handle full datetime strings (YYYY-MM-DD HH:MM:SS format)
                if 'T' in date_str or len(date_str) > 15:
                    try:
                        dt = datetime.fromisoformat(date_str.replace('T', ' ').replace('Z', ''))
                        # Validate year is reasonable (2020-2030)
                        if dt.year < 2020 or dt.year > 2030:
                            logging.warning(f"Invalid year {dt.year} in date '{date_str}', attempting correction")
                            # Try to fix common issues (2052 -> 2025)
                            if dt.year > 2030:
                                dt = dt.replace(year=2025)
                        return dt
                    except Exception as e:
                        logging.warning(f"Failed to parse datetime '{date_str}': {e}")
                
                # Parse various date formats
                match = re.search(r'(\d{1,2})[-/](\w{3})[-/](\d{2,4})', date_str, re.IGNORECASE)
                if match:
                    day, month_name, year = match.groups()
                    year = f"20{year}" if len(year) == 2 else year
                    full_date = f"{day}-{month_name}-{year}"
                    dt = datetime.strptime(full_date, "%d-%b-%Y")
                    # Validate year
                    if dt.year < 2020 or dt.year > 2030:
                        dt = dt.replace(year=2025)
                    return dt
                
                match = re.search(r'(\d{1,2})[-/](\w{3})$', date_str, re.IGNORECASE)
                if match:
                    day, month_name = match.groups()
                    year = "2025"
                    full_date = f"{day}-{month_name}-{year}"
                    return datetime.strptime(full_date, "%d-%b-%Y")
                
                logging.warning(f"Could not parse date '{date_str}'")
                return datetime.min
                
            except Exception as e:
                logging.warning(f"Could not parse date '{date_str}': {e}")
                return datetime.min
        
        # 1. Get CURRENT month data from liquor_data
        current_data = await collections.liquor_data.find().to_list(10000)
        
        # 2. Get HISTORICAL data from stock_backups (most recent only per period)
        backups = await collections.stock_backups.find().sort("backup_timestamp", -1).to_list(100)
        
        # Create a dict to store data by period - use most recent backup only
        period_to_data = {}
        period_info = {}
        
        # First, process current data (highest priority)
        if current_data:
            for record in current_data:
                d1_date = record.get('D1_date')
                dl_date = record.get('DL_date')
                
                # Skip records with None, 'N/A', or empty dates
                if d1_date and dl_date and d1_date != 'N/A' and dl_date != 'N/A':
                    d1_parsed = parse_date_for_sorting(d1_date)
                    dl_parsed = parse_date_for_sorting(dl_date)
                    
                    if d1_parsed != datetime.min and dl_parsed != datetime.min:
                        d1_month = d1_parsed.strftime("%b")
                        dl_month = dl_parsed.strftime("%b")
                        year = dl_parsed.strftime("%Y")
                        
                        if d1_month == dl_month:
                            period_label = f"{d1_month} {year}"
                        else:
                            period_label = f"{d1_month}-{dl_month} {year}"
                        
                        if period_label not in period_to_data:
                            period_to_data[period_label] = []
                            period_info[period_label] = {
                                'd1': d1_parsed,
                                'dl': dl_parsed,
                                'd1_str': d1_date,
                                'dl_str': dl_date,
                                'source': 'current'
                            }
                        
                        period_to_data[period_label].append(record)
        
        # Then, process historical backups (only if period not already in current data)
        periods_seen_in_backups = set()
        
        for backup in backups:
            data_snapshot = backup.get('data_snapshot', [])
            
            # Group this backup's records by period first
            backup_periods = defaultdict(list)
            
            for record in data_snapshot:
                d1_date = record.get('D1_date')
                dl_date = record.get('DL_date')
                
                # Skip records with None, 'N/A', or empty dates
                if d1_date and dl_date and d1_date != 'N/A' and dl_date != 'N/A':
                    d1_parsed = parse_date_for_sorting(d1_date)
                    dl_parsed = parse_date_for_sorting(dl_date)
                    
                    if d1_parsed != datetime.min and dl_parsed != datetime.min:
                        d1_month = d1_parsed.strftime("%b")
                        dl_month = dl_parsed.strftime("%b")
                        year = dl_parsed.strftime("%Y")
                        
                        if d1_month == dl_month:
                            period_label = f"{d1_month} {year}"
                        else:
                            period_label = f"{d1_month}-{dl_month} {year}"
                        
                        backup_periods[period_label].append(record)
                        
                        if period_label not in period_info:
                            period_info[period_label] = {
                                'd1': d1_parsed,
                                'dl': dl_parsed,
                                'd1_str': d1_date,
                                'dl_str': dl_date,
                                'source': 'historical'
                            }
            
            # Now add periods from this backup, but only if not already seen
            for period_label, records in backup_periods.items():
                # Skip if period already exists in current data
                if period_label in period_to_data and period_info[period_label]['source'] == 'current':
                    continue
                
                # Skip if we've already processed this period from a more recent backup
                if period_label in periods_seen_in_backups:
                    continue
                
                # Add all records for this period from this backup
                period_to_data[period_label] = records
                periods_seen_in_backups.add(period_label)
        
        # Collect daily sales for each period (now deduplicated)
        period_trends = {}
        
        for period_label, records in period_to_data.items():
            # OPTION 1: Use pre-calculated total_sales_qty if available (most accurate)
            # This is the value shown in History tab
            has_totals = all('total_sales_qty' in r for r in records)
            
            if has_totals:
                # Use the stored total_sales_qty values (already calculated correctly)
                # Distribute sales across days proportionally based on stock decreases
                
                all_daily_sales = {}
                for record in records:
                    daily_sales = record.get('daily_sales', {}) or {}
                    for date_str, stock_qty in daily_sales.items():
                        if date_str not in all_daily_sales:
                            all_daily_sales[date_str] = []
                        all_daily_sales[date_str].append(stock_qty)
                
                # Sort dates
                sorted_dates = sorted(all_daily_sales.keys(), key=lambda d: parse_date_for_sorting(d))
                
                # Get the correct total from total_sales_qty
                correct_total = sum(r.get('total_sales_qty', 0) for r in records)
                
                # Calculate stock changes (can be negative if restocking happened)
                stock_changes = []
                for i, date in enumerate(sorted_dates):
                    if i == 0:
                        stock_changes.append(0)
                    else:
                        prev_total = sum(all_daily_sales[sorted_dates[i-1]])
                        current_total = sum(all_daily_sales[date])
                        change = prev_total - current_total
                        stock_changes.append(change)
                
                # If all changes are non-positive (restocking happened), 
                # distribute total sales proportionally across days based on stock levels
                total_positive_changes = sum(c for c in stock_changes if c > 0)
                
                if total_positive_changes == 0 or correct_total > total_positive_changes * 1.5:
                    # Restocking likely happened or calculation is very off
                    # Distribute total_sales_qty evenly across days (excluding first day)
                    num_days = len(sorted_dates) - 1
                    if num_days > 0:
                        sales_per_day = correct_total / num_days
                        daily_sales_qty = {sorted_dates[0]: 0}
                        for date in sorted_dates[1:]:
                            daily_sales_qty[date] = sales_per_day
                    else:
                        daily_sales_qty = {sorted_dates[0]: correct_total}
                else:
                    # Normal calculation with adjustment
                    daily_sales_qty = {}
                    for i, date in enumerate(sorted_dates):
                        daily_sales_qty[date] = max(0, stock_changes[i])
                    
                    # Adjust to match correct total
                    calculated_total = sum(daily_sales_qty.values())
                    if calculated_total > 0:
                        adjustment_factor = correct_total / calculated_total
                        for date in daily_sales_qty:
                            daily_sales_qty[date] = daily_sales_qty[date] * adjustment_factor
                
                # Create sequential day numbers
                day_data = []
                for day_num, date_str in enumerate(sorted_dates, start=1):
                    date_obj = parse_date_for_sorting(date_str)
                    day_data.append({
                        "day": day_num,
                        "date": date_obj.strftime("%d-%b") if date_obj != datetime.min else date_str,
                        "sales": round(daily_sales_qty.get(date_str, 0), 2)
                    })
                
                period_trends[period_label] = day_data
                
            else:
                # OPTION 2: Fallback to calculating from daily_sales (for current month)
                all_daily_sales = {}
                
                for record in records:
                    daily_sales = record.get('daily_sales', {}) or {}
                    for date_str, stock_qty in daily_sales.items():
                        if date_str not in all_daily_sales:
                            all_daily_sales[date_str] = []
                        all_daily_sales[date_str].append(stock_qty)
                
                # Calculate daily sales quantities
                daily_sales_qty = {}
                sorted_dates = sorted(all_daily_sales.keys(), key=lambda d: parse_date_for_sorting(d))
                
                for i, date in enumerate(sorted_dates):
                    if i == 0:
                        daily_sales_qty[date] = 0
                    else:
                        prev_date = sorted_dates[i-1]
                        prev_total = sum(all_daily_sales[prev_date])
                        current_total = sum(all_daily_sales[date])
                        daily_sales_qty[date] = max(0, prev_total - current_total)
                
                # Create sequential day numbers
                day_data = []
                for day_num, date_str in enumerate(sorted_dates, start=1):
                    date_obj = parse_date_for_sorting(date_str)
                    day_data.append({
                        "day": day_num,
                        "date": date_obj.strftime("%d-%b") if date_obj != datetime.min else date_str,
                        "sales": daily_sales_qty.get(date_str, 0)
                    })
                
                period_trends[period_label] = day_data
        
        # Sort periods chronologically
        sorted_periods = sorted(
            period_trends.keys(),
            key=lambda p: period_info[p]['d1'] if p in period_info else datetime.min
        )
        
        # Select periods based on request
        series_data = []
        
        if period == "quarterly":
            selected_periods = sorted_periods[-3:] if len(sorted_periods) >= 3 else sorted_periods
            for period_label in selected_periods:
                # Safely access period_info to avoid KeyError
                if period_label in period_info and period_label in period_trends:
                    series_data.append({
                        "month": period_label,
                        "data": period_trends[period_label],
                        "d1_date": period_info[period_label]['d1_str'],
                        "dl_date": period_info[period_label]['dl_str']
                    })
        
        elif period == "yearly":
            selected_periods = sorted_periods[-12:] if len(sorted_periods) >= 12 else sorted_periods
            for period_label in selected_periods:
                # Safely access period_info to avoid KeyError
                if period_label in period_info and period_label in period_trends:
                    series_data.append({
                        "month": period_label,
                        "data": period_trends[period_label],
                        "d1_date": period_info[period_label]['d1_str'],
                        "dl_date": period_info[period_label]['dl_str']
                    })
        
        elif period == "single" and sales_month:
            # Safely access period_info to avoid KeyError
            if sales_month in period_trends and sales_month in period_info:
                series_data.append({
                    "month": sales_month,
                    "data": period_trends[sales_month],
                    "d1_date": period_info[sales_month]['d1_str'],
                    "dl_date": period_info[sales_month]['dl_str']
                })
        
        # Calculate summary
        total_sales = sum(
            sum(day_data["sales"] for day_data in series["data"])
            for series in series_data
        )
        
        return {
            "period": period,
            "selected_month": sales_month,
            "available_months": sorted_periods,
            "series": series_data,
            "summary": {
                "total_sales": total_sales,
                "periods_count": len(series_data)
            }
        }
        
    except Exception as e:
        logging.error(f"Error getting sales trends: {e}")
        raise HTTPException(status_code=500, detail=f"Error calculating sales trends: {str(e)}")

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
            
            if upload_type == "daily_update":
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
                
                # FAILSAFE: If snapshot is incomplete, remove the date from ALL brands
                # This handles cases where the snapshot didn't capture all brands
                if date_added and len(brands_updated) < total_brands_in_db:
                    logging.warning(f"Snapshot incomplete ({len(brands_updated)} < {total_brands_in_db}). Running failsafe cleanup...")
                    
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
                    
                    # Remove the date key from ALL brands using $unset
                    result = await collections.liquor_data.update_many(
                        {},  # Update ALL documents
                        {"$unset": {f"daily_sales.{normalized_date}": ""}}
                    )
                    logging.info(f"Failsafe cleanup: Removed '{normalized_date}' from {result.modified_count} additional brands")
                
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

@api_router.post("/admin/fix-database-integrity")
async def fix_database_integrity():
    """
    Administrative utility to fix database integrity issues.
    This endpoint will:
    1. Fix any records where daily_sales is null (set to empty dict)
    2. Ensure all numeric fields have valid values
    3. Return a summary of fixes applied
    """
    try:
        issues_found = []
        fixes_applied = []
        
        # Get all records
        all_records = await collections.liquor_data.find().to_list(10000)
        
        if not all_records:
            return {
                "status": "success",
                "message": "Database is empty, nothing to fix",
                "issues_found": [],
                "fixes_applied": []
            }
        
        for record in all_records:
            brand_id = record.get('id')
            brand_name = record.get('brand_name', 'Unknown')
            record_updated = False
            update_data = {}
            
            # Fix 1: Ensure daily_sales is a dict, not null
            daily_sales = record.get('daily_sales')
            if daily_sales is None:
                issues_found.append(f"Brand '{brand_name}': daily_sales was null")
                update_data['daily_sales'] = {}
                record_updated = True
            
            # Fix 2: Ensure numeric fields are not None
            numeric_fields = {
                'current_stock_qty': 0,
                'total_sales_qty': 0.0,
                'avg_daily_sales_qty': 0.0,
                'monthly_sales_qty': 0.0,
                'monthly_sale_qty': 0,
                'monthly_sale_value': 0.0,
                'stock_available_days': 0.0,
                'stock_ratio': 0.0,
                'D1_stock': 0.0,
                'DL_stock': 0.0,
                'days_analyzed': 1
            }
            
            for field, default_value in numeric_fields.items():
                if record.get(field) is None:
                    issues_found.append(f"Brand '{brand_name}': {field} was None")
                    update_data[field] = default_value
                    record_updated = True
            
            # Apply updates if any
            if record_updated and brand_id:
                await collections.liquor_data.update_one(
                    {"id": brand_id},
                    {"$set": update_data}
                )
                fixes_applied.append(f"Fixed {len(update_data)} fields for brand '{brand_name}'")
        
        return {
            "status": "success",
            "message": f"Database integrity check complete. Fixed {len(fixes_applied)} records.",
            "total_records_checked": len(all_records),
            "issues_found": len(issues_found),
            "fixes_applied": len(fixes_applied),
            "details": {
                "issues": issues_found[:10],  # Show first 10 issues
                "fixes": fixes_applied[:10]   # Show first 10 fixes
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
                
                periods.append({
                    "id": "current",
                    "period_name": "Current Period",
                    "d1_date": d1_date,
                    "dl_date": dl_date,
                    "has_data": True,
                    "is_current": True,
                    "total_records": len(current_data)
                })
        
        # 2. Add historical periods from backups
        backups = await collections.stock_backups.find().sort("backup_timestamp", -1).to_list(100)
        
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
                    # Determine period name from D1 and DL dates
                    try:
                        # Try ISO format first
                        d1_dt = datetime.fromisoformat(d1_date.replace(' ', 'T'))
                        dl_dt = datetime.fromisoformat(dl_date.replace(' ', 'T'))
                        period_name = f"{d1_dt.day} {d1_dt.strftime('%b')} - {dl_dt.day} {dl_dt.strftime('%b')} {dl_dt.year}"
                    except:
                        # Try parsing "20-Sep-25" format
                        try:
                            d1_dt = datetime.strptime(d1_date, "%d-%b-%y")
                            dl_dt = datetime.strptime(dl_date, "%d-%b-%y")
                            period_name = f"{d1_dt.day} {d1_dt.strftime('%b')} - {dl_dt.day} {dl_dt.strftime('%b')} {d1_dt.year}"
                        except:
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
                'daily_sales': record.get('daily_sales', {}),  # Include daily_sales for trends
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
            stock_value_today = current_stock_info.get('stock_value_today', 0)
            
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

@api_router.post("/stock/reset")
async def reset_stock_data():
    """Reset all date-wise stock data after calculating historical averages and creating backup"""
    try:
        # STEP 1: Calculate and store historical sales averages
        historical_result = await calculate_and_store_historical_averages()
        
        # STEP 2: Create automatic backup
        liquor_records = await collections.liquor_data.find().to_list(10000)
        
        if not liquor_records:
            raise HTTPException(status_code=404, detail="No data to reset")
        
        # Remove MongoDB _id for backup
        backup_data = []
        for record in liquor_records:
            record_copy = record.copy()
            if '_id' in record_copy:
                del record_copy['_id']
            backup_data.append(record_copy)
        
        # Create backup
        backup = StockBackup(
            total_records=len(backup_data),
            backup_reason="pre_reset_backup",
            data_snapshot=backup_data
        )
        
        await collections.stock_backups.insert_one(backup.dict())
        
        # STEP 3: Delete all liquor data (brands_master is preserved for rate persistence)
        delete_result = await collections.liquor_data.delete_many({})
        
        historical_count = historical_result.get('historical_records_created', 0)
        historical_month = historical_result.get('month_year', 'N/A')
        
        logging.info(f"Reset completed: Stored {historical_count} historical averages for {historical_month}, backed up and deleted {delete_result.deleted_count} records")
        
        # Create detailed message based on historical data creation
        if historical_count > 0:
            hist_message = f"✅ Saved {historical_count} brands' sales history for {historical_month}"
        else:
            hist_message = f"⚠️ No historical data saved - brands need at least 1 day of sales data"
        
        return {
            "backup_id": backup.id,
            "records_backed_up": len(backup_data),
            "records_deleted": delete_result.deleted_count,
            "historical_records_created": historical_count,
            "historical_month": historical_month,
            "historical_message": hist_message,
            "message": f"Stock data reset successfully. {hist_message}. Backup created.",
            "next_upload_becomes_d1": True
        }
        
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

async def generate_monthly_report_data() -> MonthlyReportData:
    """Generate comprehensive monthly report data"""
    try:
        # Get all liquor data
        liquor_records = await collections.liquor_data.find().to_list(1000)
        
        if not liquor_records:
            raise HTTPException(status_code=404, detail="No data found")
        
        # Extract date range from first record for report period
        sample_record = liquor_records[0]
        d1_date = sample_record.get('D1_date', 'N/A')
        dl_date = sample_record.get('DL_date', 'N/A') 
        report_period = f"Sep-Oct 2025 Sales Period ({d1_date} to {dl_date})"
        
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
async def generate_excel_report():
    """Generate comprehensive Excel report with all data"""
    try:
        # Get report data
        report_data = await generate_monthly_report_data()
        
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
    """Generate beautified PDF report with selected sections"""
    try:
        # Get report data
        report_data = await generate_monthly_report_data()
        
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
