#!/usr/bin/env python3
"""
Detailed Demand Recommendations Analysis
"""

import requests
import json
import os

# Get backend URL from environment
BACKEND_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://stocktracker-debug.preview.emergentagent.com')
API_BASE = f"{BACKEND_URL}/api"

def analyze_demand_recommendations():
    """Detailed analysis of demand recommendations response"""
    try:
        url = f"{API_BASE}/demand-recommendations"
        response = requests.get(url, timeout=30)
        
        if response.status_code != 200:
            print(f"❌ API Error: {response.status_code}")
            print(f"Response: {response.text}")
            return
        
        data = response.json()
        
        print("🔍 DETAILED DEMAND RECOMMENDATIONS ANALYSIS")
        print("=" * 60)
        print(f"📊 Total recommendations: {len(data)}")
        
        # Analyze zero-D1-stock items
        zero_d1_items = [item for item in data if item.get('d1_stock') == 0]
        non_zero_d1_items = [item for item in data if item.get('d1_stock', 0) > 0]
        
        print(f"🎯 Zero-D1-stock items: {len(zero_d1_items)}")
        print(f"📈 Non-zero-D1-stock items: {len(non_zero_d1_items)}")
        
        if zero_d1_items:
            print("\n🔍 ZERO-D1-STOCK ITEMS ANALYSIS:")
            print("-" * 40)
            
            # Group by urgency level
            urgency_groups = {'HIGH': [], 'MEDIUM': [], 'LOW': [], 'NONE': []}
            for item in zero_d1_items:
                urgency = item.get('urgency_level', 'NONE')
                urgency_groups[urgency].append(item)
            
            for urgency, items in urgency_groups.items():
                if items:
                    print(f"\n{urgency} PRIORITY ({len(items)} items):")
                    for i, item in enumerate(items[:3]):  # Show first 3 of each priority
                        print(f"  {i+1}. {item['brand_name']}")
                        print(f"     - D1 Stock: {item.get('d1_stock', 0)}")
                        print(f"     - Current Stock: {item.get('current_stock_qty', 0)}")
                        print(f"     - Recommended Qty: {item.get('recommended_qty', 0)}")
                        print(f"     - Data Source: {item.get('data_source', 'N/A')}")
                        print(f"     - Urgency Level: {item.get('urgency_level', 'N/A')}")
                        
                        remarks = item.get('remarks', [])
                        if remarks:
                            print(f"     - Remarks ({len(remarks)}):")
                            for remark in remarks[:3]:  # Show first 3 remarks
                                print(f"       • {remark}")
                        else:
                            print(f"     - Remarks: None")
                        print()
                    
                    if len(items) > 3:
                        print(f"     ... and {len(items) - 3} more {urgency} priority items")
        
        # Check sorting - zero-D1 items should appear first
        print("\n🔄 SORTING VERIFICATION:")
        print("-" * 30)
        
        first_10_items = data[:10]
        zero_d1_in_first_10 = sum(1 for item in first_10_items if item.get('d1_stock') == 0)
        
        print(f"First 10 items: {zero_d1_in_first_10} are zero-D1-stock")
        
        # Show first few items to verify sorting
        print("\nFirst 5 recommendations:")
        for i, item in enumerate(data[:5]):
            d1_stock = item.get('d1_stock', 0)
            urgency = item.get('urgency_level', 'N/A')
            print(f"  {i+1}. {item['brand_name']} (D1: {d1_stock}, Urgency: {urgency})")
        
        # Verify all required fields are present
        print("\n✅ FIELD VERIFICATION:")
        print("-" * 25)
        
        required_fields = [
            'brand_name', 'selling_rate', 'wholesale_rate', 'current_stock_qty',
            'recommended_qty', 'urgency_level', 'remarks', 'data_source', 'd1_stock'
        ]
        
        if data:
            sample_item = data[0]
            missing_fields = [field for field in required_fields if field not in sample_item]
            
            if missing_fields:
                print(f"❌ Missing fields: {missing_fields}")
            else:
                print("✅ All required fields present")
                
            # Show sample item structure
            print(f"\nSample item structure ({sample_item['brand_name']}):")
            for field in required_fields:
                value = sample_item.get(field)
                if field == 'remarks' and isinstance(value, list):
                    print(f"  {field}: {len(value)} remarks")
                else:
                    print(f"  {field}: {value}")
        
        print("\n" + "=" * 60)
        print("✅ ANALYSIS COMPLETE")
        
    except Exception as e:
        print(f"❌ Error analyzing demand recommendations: {e}")

if __name__ == "__main__":
    analyze_demand_recommendations()