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
def parse_excel_data(file_content: bytes) -> List[Dict[str, Any]]:
    """Parse Excel file and return structured data for the new format"""
    try:
        # Try to read as Excel first
        try:
            df = pd.read_excel(io.BytesIO(file_content), header=None)
        except Exception:
            # If Excel fails, try CSV
            try:
                df = pd.read_csv(io.BytesIO(file_content), header=None)
            except Exception as csv_error:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Unable to parse file. Please ensure it's a valid Excel or CSV file. Error: {str(csv_error)}"
                )
        
        if df.empty:
            raise HTTPException(status_code=400, detail="The uploaded file is empty or contains no data")
        
        # Parse the new format: brand names in first part, then numerical data
        all_data = df.values.flatten()
        all_data = [str(x).strip() for x in all_data if pd.notna(x) and str(x).strip()]
        
        # Separate brand names from numerical data
        brand_names = []
        numerical_data = []
        
        for item in all_data:
            try:
                # Try to convert to float - if successful, it's numerical data
                float(item)
                numerical_data.append(item)
            except (ValueError, TypeError):
                # If conversion fails, it's a brand name
                if item and not item.replace('.', '').isdigit():
                    brand_names.append(item)
        
        if not brand_names:
            raise HTTPException(status_code=400, detail="No brand names found in the file")
        
        if len(numerical_data) < len(brand_names) * 3:
            raise HTTPException(
                status_code=400, 
                detail=f"Insufficient numerical data. Expected {len(brand_names) * 3} values (ID, Rate, Quantity for each brand), found {len(numerical_data)}"
            )
        
        liquor_data = []
        
        # Parse numerical data in groups of 3 (ID, Rate, Quantity)
        for i in range(len(brand_names)):
            try:
                if i * 3 + 2 < len(numerical_data):
                    product_id = numerical_data[i * 3]
                    rate = float(numerical_data[i * 3 + 1])
                    quantity = int(float(numerical_data[i * 3 + 2])) if i * 3 + 2 < len(numerical_data) else 0
                    
                    # Create synthetic monthly sales based on current stock (for demo purposes)
                    # In real scenario, this would come from historical data
                    estimated_monthly_sales = max(1, quantity // 4) * rate  # Rough estimate
                    
                    brand_data = {
                        'brand_name': brand_names[i],
                        'product_id': product_id,
                        'rate': rate,
                        'current_stock_qty': quantity,
                        'stock_value_today': rate * quantity,
                        'monthly_sale_value': estimated_monthly_sales,
                        'stock_available_days': max(1, quantity // max(1, quantity // 30)) if quantity > 0 else 0,
                        'stock_ratio': (rate * quantity) / max(1, estimated_monthly_sales),
                        # For compatibility with existing code
                        'daily_sales': {},
                        'monthly_sale_qty': max(1, quantity // 4),
                        'avg_daily_sale': estimated_monthly_sales / 30,
                        'stock_value_before': rate * quantity * 1.1,  # Slightly higher before
                    }
                    
                    liquor_data.append(brand_data)
                    
            except Exception as e:
                logging.warning(f"Error parsing data for {brand_names[i] if i < len(brand_names) else 'Unknown'}: {e}")
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
        volume_leaders = sorted(data_dicts, key=lambda x: x['current_stock_qty'], reverse=True)[:10]
        volume_chart = [
            {
                'name': item['brand_name'],
                'value': item['current_stock_qty'],
                'stock_value': item['stock_value_today']
            }
            for item in volume_leaders if item['current_stock_qty'] > 0
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
            selling_rate = record['rate']
            wholesale_rate = selling_rate * 0.9  # 10% lower than selling rate
            current_stock_qty = record.get('current_stock_qty', 0)
            monthly_sale_value = record['monthly_sale_value']
            stock_days = record['stock_available_days']
            
            # Calculate recommended quantity based on sales velocity and stock position
            if monthly_sale_value > 0 and selling_rate > 0:
                # Estimate monthly quantity sold
                estimated_monthly_qty = max(1, int(monthly_sale_value / selling_rate))
                
                # Target: maintain 45-60 days of stock
                target_qty = int(estimated_monthly_qty * 1.5)  # 45 days worth
                
                # Calculate recommended order quantity
                recommended_qty = max(0, target_qty - current_stock_qty)
                
                # Determine urgency level based on days of stock remaining
                if stock_days < 15:
                    urgency = "HIGH"
                elif stock_days < 30:
                    urgency = "MEDIUM"
                elif stock_days < 45:
                    urgency = "LOW"
                else:
                    urgency = "NONE"
                
                # Only include items that need restocking
                if urgency != "NONE" or recommended_qty > 0:
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

@api_router.get("/export-demand-list")
async def export_demand_list():
    """Export demand recommendations with updated format: Index, Brand Name, Wholesale Rate, Quantity in Stock, Quantity to be Demanded"""
    try:
        # Get recommendations
        recommendations_data = await get_demand_recommendations()
        
        if not recommendations_data:
            raise HTTPException(status_code=404, detail="No recommendations to export")
        
        # Convert to updated DataFrame format
        df_data = []
        for index, rec in enumerate(recommendations_data, 1):
            df_data.append({
                'Index': index,
                'Brand Name': rec.brand_name,
                'Wholesale Rate': rec.wholesale_rate,
                'Quantity held in Stock': rec.current_stock_qty,
                'Quantity to be Demanded': rec.recommended_qty
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
            
            # Auto-adjust column widths
            column_widths = {'A': 10, 'B': 40, 'C': 18, 'D': 22, 'E': 25}
            for column_letter, width in column_widths.items():
                worksheet.column_dimensions[column_letter].width = width
            
            # Style headers
            from openpyxl.styles import Font, PatternFill, Alignment
            header_font = Font(bold=True, color="FFFFFF")
            header_fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
            
            for col in range(1, 6):  # 5 columns
                cell = worksheet.cell(row=1, column=col)
                cell.font = header_font
                cell.fill = header_fill
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