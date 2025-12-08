#!/usr/bin/env python3
"""
Check for historical data in the system
"""

import requests
import json
import os

# Get backend URL from environment
BACKEND_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://stocktracker-debug.preview.emergentagent.com')
API_BASE = f"{BACKEND_URL}/api"

def check_system_data():
    """Check what data exists in the system"""
    try:
        print("🔍 CHECKING SYSTEM DATA")
        print("=" * 40)
        
        # Check analytics endpoint to see current data
        print("📊 Checking analytics data...")
        response = requests.get(f"{API_BASE}/analytics", timeout=30)
        if response.status_code == 200:
            analytics = response.json()
            print(f"✅ Analytics accessible")
            print(f"   Total brands: {analytics.get('total_brands', 'N/A')}")
            print(f"   Total stock value: ${analytics.get('total_stock_value', 'N/A'):,.2f}" if analytics.get('total_stock_value') else "   Total stock value: N/A")
        else:
            print(f"❌ Analytics error: {response.status_code}")
        
        # Check if there are any backups (historical data source)
        print("\n📦 Checking backup data...")
        response = requests.get(f"{API_BASE}/backups", timeout=30)
        if response.status_code == 200:
            backups = response.json()
            print(f"✅ Found {len(backups)} backups")
            if backups:
                latest_backup = backups[0]
                print(f"   Latest backup: {latest_backup.get('backup_timestamp', 'N/A')}")
                print(f"   Records in backup: {latest_backup.get('total_records', 'N/A')}")
        else:
            print(f"❌ Backups error: {response.status_code}")
        
        # Check current liquor data
        print("\n🍺 Checking current liquor data...")
        response = requests.get(f"{API_BASE}/data", timeout=30)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Found {len(data)} current liquor records")
            
            # Check for D1 stock patterns
            zero_d1_count = sum(1 for item in data if item.get('D1_stock', 0) == 0)
            non_zero_d1_count = len(data) - zero_d1_count
            
            print(f"   Zero D1 stock: {zero_d1_count} items")
            print(f"   Non-zero D1 stock: {non_zero_d1_count} items")
            
            # Show a few examples
            if zero_d1_count > 0:
                print("\n   Examples of zero-D1-stock items:")
                zero_d1_items = [item for item in data if item.get('D1_stock', 0) == 0][:3]
                for item in zero_d1_items:
                    print(f"     - {item['brand_name']}: D1={item.get('D1_stock', 0)}, Current={item.get('current_stock_qty', 0)}")
            
            if non_zero_d1_count > 0:
                print("\n   Examples of non-zero-D1-stock items:")
                non_zero_d1_items = [item for item in data if item.get('D1_stock', 0) > 0][:3]
                for item in non_zero_d1_items:
                    print(f"     - {item['brand_name']}: D1={item.get('D1_stock', 0)}, Current={item.get('current_stock_qty', 0)}")
        else:
            print(f"❌ Data error: {response.status_code}")
        
        print("\n" + "=" * 40)
        
    except Exception as e:
        print(f"❌ Error checking system data: {e}")

if __name__ == "__main__":
    check_system_data()