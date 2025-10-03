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
    upload_type: str  # "full_monthly" or "daily_update"
    upload_timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    records_count: int
    file_size: int
    uploaded_by: str = Field(default="dashboard_user")

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
    recommended_qty: int
    urgency_level: str

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
            daily_sales = item.get('daily_sales', {})
            for date_key in daily_sales.keys():
                new_dates.add(date_key)
        
        if not new_dates:
            return  # No dates to check
        
        # Get existing data from database
        existing_records = await db.liquor_data.find({}, {"daily_sales": 1, "DL_date": 1}).to_list(1000)
        
        # Extract existing dates from database
        existing_dates = set()
        for record in existing_records:
            # Check DL_date
            dl_date = record.get('DL_date')
            if dl_date:
                existing_dates.add(dl_date)
            
            # Check daily_sales dates
            daily_sales = record.get('daily_sales', {})
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
        
        for col in df.columns:
            col_str = str(col)
            col_lower = col_str.lower().strip()
            
            if 'brand' in col_lower and 'name' in col_lower:
                brand_col = col
            elif any(term in col_lower for term in ['index', 'sl', 'sr', 'no', 'id']) and len(col_str) <= 10:
                index_col = col
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
        
        print(f"📊 Today's Data Column Detection:")
        print(f"  - Brand column: {brand_col}")
        print(f"  - Index column: {index_col}")
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
                
                todays_data['brands_data'][brand_name] = {
                    'index_number': index_num,
                    'stock_qty': stock_qty
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
        
        if 'brand' in col_lower and 'name' in col_lower:
            brand_col = col
        elif 'wholesale' in col_lower and 'rate' in col_lower:
            wholesale_rate_col = col
        elif ('selling' in col_lower or 'retail' in col_lower) and 'rate' in col_lower:
            selling_rate_col = col
        elif 'rate' in col_lower and not wholesale_rate_col and not selling_rate_col:
            selling_rate_col = col  # Default to selling rate if only one rate column
        elif any(term in col_lower for term in ['index', 'sl', 'sr', 'no', 'id']) and len(col_str) <= 10:
            index_col = col
        else:
            # Check if column represents a date (more flexible detection)
            is_date_column = False
            
            # Method 1: Check for month names (original logic)
            if any(date_part in col_lower for date_part in ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec']):
                is_date_column = True
            
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
    
    def parse_date_column(col_name):
        """Parse date from column name - return None if invalid"""
        try:
            import re
            from datetime import datetime
            
            col_clean = str(col_name).strip()
            
            # Primary pattern: day-month-year (20-Sep-25, 01-Oct-25, etc.)
            match = re.search(r'(\d{1,2})[-/](\w{3})[-/]?(\d{0,4})', col_clean, re.IGNORECASE)
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
                    print(f"Parsed valid date: '{col_name}' -> {parsed_date.strftime('%Y-%m-%d')}")
                    return parsed_date
                except ValueError as e:
                    print(f"Skipping unparseable date: '{col_name}' (error: {e})")
                    return None
            else:
                print(f"Skipping non-date column: '{col_name}' (no date pattern found)")
                return None
                
        except Exception as e:
            print(f"Exception parsing '{col_name}': {e}")
            return None
    
    # Filter out invalid date columns and sort the valid ones
    valid_date_columns = []
    for col in date_columns:
        parsed_date = parse_date_column(col)
        if parsed_date is not None:
            valid_date_columns.append((col, parsed_date))
    
    # Sort by parsed date
    valid_date_columns.sort(key=lambda x: x[1])
    
    # Extract just the column names in correct order
    date_columns = [col for col, date in valid_date_columns]
    
    print(f"Valid date columns AFTER filtering and sorting: {date_columns}")
    
    print(f"📊 Column Detection Summary:")
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
                col != index_col and not col_str.lower().strip() in ['brand name', 'brand_name', 'rate', 'index', 'sl', 'sr']):
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
            
            # Get rates
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
            
            # If wholesale rate not provided, calculate as 90% of selling rate
            if wholesale_rate == 0 and selling_rate > 0:
                wholesale_rate = selling_rate * 0.9
            elif selling_rate == 0 and wholesale_rate > 0:
                selling_rate = wholesale_rate / 0.9
            
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
                        
                except Exception as e:
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
        
        # Clear existing data and insert new data (full replacement)
        await db.liquor_data.delete_many({})
        
        # Convert to LiquorData models and insert
        liquor_objects = []
        for item_data in parsed_data:
            liquor_obj = LiquorData(**item_data)
            liquor_objects.append(liquor_obj.dict())
        
        if liquor_objects:
            await db.liquor_data.insert_many(liquor_objects)
        
        # Save upload history
        upload_history = UploadHistory(
            filename=file.filename,
            upload_type="full_monthly",
            records_count=len(liquor_objects),
            file_size=len(content)
        )
        await db.upload_history.insert_one(upload_history.dict())
        
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
        
        # Parse the data to extract date information for duplicate checking
        try:
            parsed_data = parse_excel_data(content, "daily_update")
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
        
        if not parsed_data:
            raise HTTPException(status_code=400, detail="No valid data found in the file")
        
        # Check for duplicate dates before processing
        await check_duplicate_dates_in_upload(parsed_data, file.filename)
        
        # Update existing data with today's stock positions
        updated_count = 0
        new_brands_count = 0
        
        for item_data in parsed_data:
            brand_name = item_data['brand_name']
            
            # Check if brand exists
            existing_brand = await db.liquor_data.find_one({"brand_name": brand_name})
            
            if existing_brand:
                # Update existing brand with new stock data
                update_data = {
                    "DL_stock": item_data['DL_stock'],
                    "current_stock_qty": item_data['current_stock_qty'],
                    "stock_value_today": item_data['stock_value_today'],
                    "DL_date": item_data['DL_date'],
                    "upload_timestamp": datetime.now(timezone.utc)
                }
                
                # Update daily_sales with new date data
                if 'daily_sales' in item_data:
                    update_data["daily_sales"] = {**existing_brand.get('daily_sales', {}), **item_data['daily_sales']}
                
                # Recalculate dependent values
                D1_stock = existing_brand.get('D1_stock', 0)
                new_DL_stock = item_data['DL_stock']
                days_analyzed = existing_brand.get('days_analyzed', 1)
                selling_rate = existing_brand.get('selling_rate', item_data.get('selling_rate', 0))
                
                total_sales_qty = max(0, D1_stock - new_DL_stock)
                avg_daily_sales_qty = total_sales_qty / max(1, days_analyzed)
                monthly_sales_qty = avg_daily_sales_qty * 24
                monthly_sales_value = monthly_sales_qty * selling_rate
                stock_ratio = (new_DL_stock * selling_rate) / max(1, monthly_sales_value)
                stock_available_days = (new_DL_stock / max(0.1, avg_daily_sales_qty)) if avg_daily_sales_qty > 0 else 999
                
                update_data.update({
                    "total_sales_qty": total_sales_qty,
                    "avg_daily_sales_qty": avg_daily_sales_qty,
                    "monthly_sales_qty": monthly_sales_qty,
                    "monthly_sale_qty": int(monthly_sales_qty),
                    "monthly_sale_value": monthly_sales_value,
                    "stock_ratio": stock_ratio,
                    "stock_available_days": min(999, max(0, stock_available_days))
                })
                
                await db.liquor_data.update_one(
                    {"brand_name": brand_name}, 
                    {"$set": update_data}
                )
                updated_count += 1
            else:
                # Add new brand
                liquor_obj = LiquorData(**item_data)
                await db.liquor_data.insert_one(liquor_obj.dict())
                new_brands_count += 1
        
        # Save upload history
        upload_history = UploadHistory(
            filename=file.filename,
            upload_type="daily_update",
            records_count=len(parsed_data),
            file_size=len(content)
        )
        await db.upload_history.insert_one(upload_history.dict())
        
        return JSONResponse(
            status_code=200,
            content={
                "message": f"Successfully updated today's data: {updated_count} brands updated, {new_brands_count} new brands added",
                "updated_brands": updated_count,
                "new_brands": new_brands_count,
                "total_records": len(parsed_data),
                "upload_type": "daily_update"
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
        upload_records = await db.upload_history.find().sort("upload_timestamp", -1).to_list(100)
        
        return [
            {
                "id": record["id"],
                "filename": record["filename"],
                "upload_type": record["upload_type"],
                "upload_timestamp": record["upload_timestamp"],
                "records_count": record["records_count"],
                "file_size": record["file_size"],
                "uploaded_by": record.get("uploaded_by", "dashboard_user")
            }
            for record in upload_records
        ]
        
    except Exception as e:
        logging.error(f"Error fetching upload history: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching upload history: {str(e)}")

# Keep existing endpoints for backward compatibility
@api_router.post("/upload-data")
async def upload_liquor_data(file: UploadFile = File(...)):
    """Legacy upload endpoint - redirects to full monthly data upload"""
    return await upload_full_monthly_data(file)

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

@api_router.get("/charts", response_model=ChartsResponse)
async def get_charts_data():
    """Get data for performance charts and visualizations"""
    try:
        liquor_records = await db.liquor_data.find().to_list(1000)
        
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
    """Get smart demand recommendations with wholesale rates and quantities"""
    try:
        liquor_records = await db.liquor_data.find().to_list(1000)
        
        if not liquor_records:
            raise HTTPException(status_code=404, detail="No data found")
        
        recommendations = []
        
        for record in liquor_records:
            brand_name = record['brand_name']
            selling_rate = record.get('selling_rate', record['rate'])
            wholesale_rate = record.get('wholesale_rate', selling_rate * 0.9)
            current_stock_qty = record.get('current_stock_qty', 0)
            avg_daily_sales_qty = record.get('avg_daily_sales_qty', 0)
            stock_days = record['stock_available_days']
            
            # Calculate recommended quantity based on monthly sales pattern for next 30 days
            monthly_sales_qty = record.get('monthly_sales_qty', record.get('monthly_sale_qty', 0))
            
            if monthly_sales_qty > 0:
                # For next 30 days, we need monthly_sales_qty amount
                # Calculate how much to order = Monthly requirement - Current stock
                recommended_qty = max(0, monthly_sales_qty - current_stock_qty)
                
                # Determine urgency level based on days of stock remaining
                if stock_days < 10:
                    urgency = "HIGH"
                elif stock_days < 20:
                    urgency = "MEDIUM"
                elif stock_days < 30:
                    urgency = "LOW"
                else:
                    urgency = "NONE"
                
                # Only include items that need restocking (when recommended_qty > 0)
                if recommended_qty > 0:
                    recommendations.append(DemandRecommendation(
                        brand_name=brand_name,
                        selling_rate=selling_rate,
                        wholesale_rate=round(wholesale_rate, 2),
                        current_stock_qty=current_stock_qty,
                        recommended_qty=recommended_qty,
                        urgency_level=urgency
                    ))
        
        # Sort by urgency (HIGH -> MEDIUM -> LOW) and then by recommended quantity
        urgency_order = {"HIGH": 1, "MEDIUM": 2, "LOW": 3}
        recommendations.sort(key=lambda x: (urgency_order.get(x.urgency_level, 4), -x.recommended_qty))
        
        return recommendations
        
    except Exception as e:
        logging.error(f"Error generating demand recommendations: {e}")
        raise HTTPException(status_code=500, detail=f"Error generating recommendations: {str(e)}")

@api_router.delete("/clear-data")
async def clear_all_data():
    """Clear all liquor data to force re-upload with corrected D1/DL logic"""
    try:
        result = await db.liquor_data.delete_many({})
        return {"message": f"Cleared {result.deleted_count} records. Please re-upload your data to apply corrected D1/DL calculations."}
    except Exception as e:
        logging.error(f"Error clearing data: {e}")
        raise HTTPException(status_code=500, detail=f"Error clearing data: {str(e)}")

@api_router.get("/calculation-details")
async def get_calculation_details():
    """Get detailed calculations for all brands for verification"""
    try:
        liquor_records = await db.liquor_data.find().to_list(1000)
        
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
        liquor_records = await db.liquor_data.find().to_list(1000)
        
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
            # Get the original brand record to find the correct index and monthly sales
            brand_record = brand_lookup.get(rec.brand_name)
            
            if brand_record:
                # Use the original index from the brand record
                original_index = brand_record.get('index_number', 'N/A')
                projected_monthly_sale_qty = brand_record.get('monthly_sales_qty', brand_record.get('monthly_sale_qty', 0))
            else:
                original_index = 'N/A'
                projected_monthly_sale_qty = 0
            
            # Calculate number of cases needed (1 case = 12 units, round up to get whole cases)
            import math
            cases_demanded = math.ceil(rec.recommended_qty / 12) if rec.recommended_qty > 0 else 0
            
            # Calculate totals for the summary row
            wholesale_cost_for_demand = rec.wholesale_rate * rec.recommended_qty
            total_wholesale_cost += wholesale_cost_for_demand
            total_quantity_in_stock += rec.current_stock_qty
            total_quantity_demanded += rec.recommended_qty
            total_projected_monthly_sale += projected_monthly_sale_qty
            total_cases_demanded += cases_demanded
            
            df_data.append({
                'Index': original_index,
                'Brand Name': rec.brand_name,
                'Wholesale Rate': rec.wholesale_rate,
                'Projected Monthly Sale (Qty)': int(round(projected_monthly_sale_qty, 0)),
                'Quantity held in Stock': rec.current_stock_qty,
                'Quantity to be Demanded': rec.recommended_qty,
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
