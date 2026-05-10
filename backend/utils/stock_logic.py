from typing import List, Dict, Tuple
from .date_helper import parse_date, normalize_date_key
from datetime import datetime

def calculate_movements(daily_stock: Dict[str, float], d1_date: str, dl_date: str) -> Tuple[float, float, List[str]]:
    """
    Calculates total sales and restocks by analyzing stock movements between dates.
    Returns (total_sales, total_restocks, brands_with_increase)
    """
    d1_dt = parse_date(d1_date)
    dl_dt = parse_date(dl_date)
    
    # Sort dates to ensure chronological processing
    date_points = []
    for date_str, qty in daily_stock.items():
        dt = parse_date(date_str)
        if dt != datetime.min and d1_dt <= dt <= dl_dt:
            date_points.append((dt, qty))
    
    date_points.sort(key=lambda x: x[0])
    
    total_sales = 0.0
    total_restocks = 0.0
    
    if len(date_points) < 2:
        return 0.0, 0.0, []

    for i in range(1, len(date_points)):
        prev_qty = date_points[i-1][1]
        curr_qty = date_points[i][1]
        
        if curr_qty < prev_qty:
            total_sales += (prev_qty - curr_qty)
        elif curr_qty > prev_qty:
            total_restocks += (curr_qty - prev_qty)
            
    return total_sales, total_restocks, []

def detect_monthly_restock(parsed_data: List[Dict], existing_data: Dict[str, float]) -> Tuple[bool, int, List[str]]:
    """
    Analyzes if the current upload indicates a monthly restock.
    Monthly restock is triggered if >= 5 brands show a stock increase compared to existing DB data.
    """
    increases_count = 0
    increased_brands = []
    
    for item in parsed_data:
        brand_name = item['brand_name']
        new_stock = item['DL_stock']
        
        # Compare with existing stock in database if available
        old_stock = existing_data.get(brand_name)
        
        if old_stock is not None and new_stock is not None and new_stock > old_stock:
            increases_count += 1
            increased_brands.append(brand_name)
            
    is_restock = increases_count >= 5
    return is_restock, increases_count, increased_brands
