#!/usr/bin/env python3
"""
Sales Trends Debug Test
Detailed investigation of the sales trends empty issue
"""

import requests
import json
import os
import sys
from datetime import datetime
import time
import io

# Get backend URL from environment
BACKEND_URL = "https://liquor-dashboard-1.preview.emergentagent.com/api"

def test_sales_trends_issue():
    """Debug the sales trends empty issue"""
    print("🔍 DEBUGGING SALES TRENDS EMPTY ISSUE")
    print("=" * 50)
    
    session = requests.Session()
    
    # Step 1: Check analytics-source to see data source
    print("1. Checking data source...")
    response = session.get(f"{BACKEND_URL}/analytics-source")
    if response.status_code == 200:
        source_data = response.json()
        print(f"   Data source: {source_data.get('data_source')}")
        print(f"   Days of data: {source_data.get('days_of_data')}")
        print(f"   Using month: {source_data.get('using_month')}")
        print(f"   Is transitioning: {source_data.get('is_transitioning')}")
    
    # Step 2: Check database records for daily_sales
    print("\n2. Checking database records...")
    response = session.get(f"{BACKEND_URL}/database-view")
    if response.status_code == 200:
        db_data = response.json()
        records = db_data.get('data', [])
        print(f"   Total records: {len(records)}")
        
        if records:
            sample_record = records[0]
            daily_sales = sample_record.get('daily_sales', {})
            print(f"   Sample daily_sales: {daily_sales}")
            print(f"   Sample brand: {sample_record.get('brand_name')}")
            print(f"   Sample D1_date: {sample_record.get('D1_date')}")
            print(f"   Sample DL_date: {sample_record.get('DL_date')}")
    
    # Step 3: Check analytics response
    print("\n3. Checking analytics response...")
    response = session.get(f"{BACKEND_URL}/analytics")
    if response.status_code == 200:
        analytics_data = response.json()
        sales_trends = analytics_data.get('sales_trends', {})
        print(f"   Sales trends: {sales_trends}")
        print(f"   Total brands in analytics: {analytics_data.get('total_brands')}")
        
        # Check if any records have daily_sales in the analytics data
        # This would require looking at the raw data being processed
        
    # Step 4: Test with multiple days of data
    print("\n4. Testing with multiple days of data...")
    
    # Clear database first
    response = session.post(f"{BACKEND_URL}/stock/reset")
    if response.status_code == 200:
        print("   Database cleared successfully")
    
    # Upload 6 days of data (above the 5-day threshold)
    dates = ["19-Oct-25", "20-Oct-25", "21-Oct-25", "22-Oct-25", "23-Oct-25", "24-Oct-25"]
    
    for i, date in enumerate(dates):
        # Create test Excel file
        import pandas as pd
        
        brands_data = []
        for j in range(1, 11):  # Just 10 brands for faster testing
            brands_data.append({
                'Index': j,
                'Brand Name': f'Test Brand {j:02d}',
                date: 100 - j - i  # Stock decreases over time
            })
        
        df = pd.DataFrame(brands_data)
        excel_buffer = io.BytesIO()
        df.to_excel(excel_buffer, index=False)
        excel_buffer.seek(0)
        
        files = {'file': (f'todays_data_{date}.xlsx', excel_buffer.getvalue(), 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')}
        
        response = session.post(f"{BACKEND_URL}/upload-todays-data", files=files)
        if response.status_code == 200:
            print(f"   ✅ Uploaded data for {date}")
        else:
            print(f"   ❌ Failed to upload data for {date}: {response.text[:100]}")
    
    # Check analytics-source again
    print("\n5. Checking data source after 6 days...")
    response = session.get(f"{BACKEND_URL}/analytics-source")
    if response.status_code == 200:
        source_data = response.json()
        print(f"   Data source: {source_data.get('data_source')}")
        print(f"   Days of data: {source_data.get('days_of_data')}")
    
    # Check analytics again
    print("\n6. Checking analytics after 6 days...")
    response = session.get(f"{BACKEND_URL}/analytics")
    if response.status_code == 200:
        analytics_data = response.json()
        sales_trends = analytics_data.get('sales_trends', {})
        print(f"   Sales trends: {sales_trends}")
        print(f"   Number of trend dates: {len(sales_trends)}")
        
        if sales_trends:
            print("   ✅ Sales trends now populated!")
            return True
        else:
            print("   ❌ Sales trends still empty")
            return False
    
    return False

if __name__ == "__main__":
    success = test_sales_trends_issue()
    if success:
        print("\n🎉 Sales trends issue resolved with sufficient data!")
    else:
        print("\n💥 Sales trends issue persists!")