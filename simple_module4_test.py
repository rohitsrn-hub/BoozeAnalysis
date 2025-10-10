#!/usr/bin/env python3
"""
Simple Module 4 Test - Focus on the key requirements from the review request
"""

import requests
import pandas as pd
import io
import re

BACKEND_URL = "https://liquor-manager.preview.emergentagent.com/api"

def test_excel_actual_dates():
    """Test Excel Date-wise Sales sheet uses actual dates as headers"""
    print("🔍 Testing Excel Date-wise Sales with Actual Date Headers...")
    
    url = f"{BACKEND_URL}/reports/generate-excel"
    response = requests.post(url, timeout=60)
    
    if response.status_code != 200:
        print(f"❌ Excel generation failed: {response.status_code}")
        return False
    
    try:
        excel_data = pd.ExcelFile(io.BytesIO(response.content))
        
        if 'Date-wise Sales' not in excel_data.sheet_names:
            print(f"❌ Date-wise Sales sheet not found. Available: {excel_data.sheet_names}")
            return False
        
        df = pd.read_excel(io.BytesIO(response.content), sheet_name='Date-wise Sales')
        
        # Check for required base columns
        required_cols = ['Index', 'Brand Name', 'Wholesale Rate (₹)', 'Retail Rate (₹)']
        missing = [col for col in required_cols if col not in df.columns]
        
        if missing:
            print(f"❌ Missing required columns: {missing}")
            return False
        
        # Find date columns (should be actual dates, not D1, D2, D3)
        date_columns = []
        d_format_columns = []
        
        for col in df.columns:
            col_str = str(col).strip()
            if col in required_cols:
                continue
                
            # Check for old D1, D2, D3 format (should NOT exist)
            if re.match(r'^D\d+$', col_str):
                d_format_columns.append(col_str)
            # Check for actual date formats
            elif re.match(r'\d{1,2}-\w{3}(-\d{2,4})?$', col_str):
                date_columns.append(col_str)
        
        if d_format_columns:
            print(f"❌ Found old D1/D2/D3 format: {d_format_columns}")
            return False
        
        if not date_columns:
            print(f"❌ No actual date columns found. All columns: {list(df.columns)}")
            return False
        
        print(f"✅ Excel uses actual date headers: {date_columns[:5]}...")
        print(f"   Structure: {required_cols} + {len(date_columns)} date columns")
        return True
        
    except Exception as e:
        print(f"❌ Excel parsing error: {e}")
        return False

def test_pdf_brand_wise_analysis():
    """Test PDF Brand-Wise Sale Analysis section"""
    print("🔍 Testing PDF Brand-Wise Sale Analysis...")
    
    url = f"{BACKEND_URL}/reports/generate-pdf"
    params = {
        "include_datewise_analysis": True,
        "include_executive_summary": False,
        "include_top_sellers": False,
        "include_slow_sellers": False,
        "include_capital_blockers": False,
        "include_revenue_analysis": False,
        "include_demand_forecast": False,
        "include_profit_analysis": False,
        "include_recommendations": False,
        "report_title": "Brand-Wise Analysis Test"
    }
    
    response = requests.post(url, json=params, timeout=60)
    
    if response.status_code != 200:
        print(f"❌ PDF generation failed: {response.status_code}")
        return False
    
    if 'application/pdf' not in response.headers.get('Content-Type', ''):
        print(f"❌ Wrong content type: {response.headers.get('Content-Type')}")
        return False
    
    if len(response.content) < 2000:
        print(f"❌ PDF too small: {len(response.content)} bytes")
        return False
    
    if response.content[:4] != b'%PDF':
        print(f"❌ Invalid PDF signature")
        return False
    
    print(f"✅ PDF Brand-Wise Analysis generated successfully")
    print(f"   Size: {len(response.content)} bytes, Content-Type: PDF")
    return True

def test_profit_calculations():
    """Test profit calculations are reasonable"""
    print("🔍 Testing Profit Calculations...")
    
    url = f"{BACKEND_URL}/reports/data"
    response = requests.get(url, timeout=30)
    
    if response.status_code != 200:
        print(f"❌ Reports data failed: {response.status_code}")
        return False
    
    data = response.json()
    top_sellers = data.get('top_sellers_revenue', [])
    
    if not top_sellers:
        print("❌ No top sellers data")
        return False
    
    # Check if calculations are reasonable (not testing exact formula, just sanity)
    reasonable_count = 0
    for seller in top_sellers[:5]:
        revenue = seller.get('revenue', 0)
        profit = seller.get('profit', 0)
        margin = seller.get('profit_margin', 0)
        
        # Basic sanity checks
        if revenue > 0 and profit > 0 and 0 < margin < 50:  # Reasonable margin range
            reasonable_count += 1
    
    if reasonable_count >= 3:
        print(f"✅ Profit calculations appear reasonable for {reasonable_count} brands")
        return True
    else:
        print(f"❌ Only {reasonable_count} brands have reasonable calculations")
        return False

def main():
    print("🚀 Simple Module 4 Updated Features Test")
    print("=" * 60)
    
    tests = [
        ("Excel Actual Date Headers", test_excel_actual_dates),
        ("PDF Brand-Wise Analysis", test_pdf_brand_wise_analysis),
        ("Profit Calculations", test_profit_calculations),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n{test_name}:")
        try:
            if test_func():
                passed += 1
        except Exception as e:
            print(f"❌ Test error: {e}")
    
    print("\n" + "=" * 60)
    print(f"📊 RESULTS: {passed}/{total} tests passed ({(passed/total)*100:.1f}%)")
    
    if passed == total:
        print("🎉 All key features working!")
    else:
        print(f"⚠️ {total - passed} issues found")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)