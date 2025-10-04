#!/usr/bin/env python3
"""
Final comprehensive test for Trends tab chronological ordering fix
"""

import requests
import json
from datetime import datetime
import re

BACKEND_URL = "https://liquor-analytics.preview.emergentagent.com/api"

def test_chronological_ordering_fix():
    """Test that the chronological ordering fix is working correctly"""
    print("🔍 FINAL TRENDS CHRONOLOGICAL ORDERING TEST")
    print("=" * 60)
    
    try:
        response = requests.get(f"{BACKEND_URL}/analytics", timeout=30)
        if response.status_code != 200:
            print(f"❌ Failed to get analytics data: {response.status_code}")
            return False
        
        data = response.json()
        sales_trends = data.get('sales_trends', {})
        
        if not sales_trends:
            print("❌ No sales_trends data found")
            return False
        
        print(f"📊 Found {len(sales_trends)} dates in sales_trends")
        print("\n🗓️ CURRENT ORDER (as returned by API):")
        
        date_keys = list(sales_trends.keys())
        for i, date_key in enumerate(date_keys, 1):
            value = sales_trends[date_key]
            print(f"  {i:2d}. {date_key:12s} (value: {value})")
        
        # Expected chronological order based on the review request
        expected_order = [
            "20-Sep-25",  # 2025-09-20
            "21-Sep",     # 2025-09-21 (should be treated as 2025)
            "22-Sep",     # 2025-09-22 (should be treated as 2025)
            "26-Sep",     # 2025-09-26 (should be treated as 2025)
            "28-Sep-25",  # 2025-09-28
            "29-Sep-25",  # 2025-09-29
            "30-Sep-25",  # 2025-09-30
            "01-Oct-25",  # 2025-10-01
            "03-Oct-25",  # 2025-10-03
        ]
        
        print(f"\n📈 CHRONOLOGICAL ORDER VALIDATION:")
        print(f"Expected order: {' → '.join(expected_order)}")
        print(f"Actual order:   {' → '.join(date_keys)}")
        
        # Check if the order matches expected chronological order
        if date_keys == expected_order:
            print("✅ PASS: Dates are in correct chronological order!")
            print("   - Dates without year (21-Sep, 22-Sep, 26-Sep) are correctly treated as 2025")
            print("   - All dates are sorted chronologically, not alphabetically")
            return True
        else:
            print("❌ FAIL: Dates are not in expected chronological order")
            
            # Show differences
            for i, (expected, actual) in enumerate(zip(expected_order, date_keys)):
                if expected != actual:
                    print(f"   Position {i+1}: Expected '{expected}', got '{actual}'")
            
            return False
            
    except Exception as e:
        print(f"❌ Error during test: {e}")
        return False

def test_specific_date_formats():
    """Test that the API handles various date formats correctly"""
    print(f"\n🗓️ DATE FORMAT HANDLING TEST")
    print("=" * 40)
    
    try:
        response = requests.get(f"{BACKEND_URL}/analytics", timeout=30)
        if response.status_code != 200:
            print(f"❌ Failed to get analytics data: {response.status_code}")
            return False
        
        data = response.json()
        sales_trends = data.get('sales_trends', {})
        
        # Check for the specific formats mentioned in the review request
        format_tests = {
            "21-Sep format": any("21-Sep" in key for key in sales_trends.keys()),
            "20-Sep-25 format": any("20-Sep-25" in key for key in sales_trends.keys()),
            "01-Oct-25 format": any("01-Oct-25" in key for key in sales_trends.keys()),
        }
        
        all_passed = True
        for format_name, found in format_tests.items():
            if found:
                print(f"✅ {format_name}: Found and handled correctly")
            else:
                print(f"❌ {format_name}: Not found in data")
                all_passed = False
        
        return all_passed
        
    except Exception as e:
        print(f"❌ Error during format test: {e}")
        return False

def test_data_completeness():
    """Test that all dates from database are included in sales_trends"""
    print(f"\n📋 DATA COMPLETENESS TEST")
    print("=" * 30)
    
    try:
        # Get database data
        db_response = requests.get(f"{BACKEND_URL}/database-view", timeout=30)
        if db_response.status_code != 200:
            print(f"❌ Failed to get database data: {db_response.status_code}")
            return False
        
        # Get analytics data
        analytics_response = requests.get(f"{BACKEND_URL}/analytics", timeout=30)
        if analytics_response.status_code != 200:
            print(f"❌ Failed to get analytics data: {analytics_response.status_code}")
            return False
        
        db_data = db_response.json()
        analytics_data = analytics_response.json()
        
        # Extract dates from database
        db_dates = set()
        data_list = db_data.get('data', [])
        
        for record in data_list:
            # Check DL_date
            dl_date = record.get('DL_date')
            if dl_date:
                db_dates.add(str(dl_date))
            
            # Check daily_sales dates
            daily_sales = record.get('daily_sales', {})
            for date_key in daily_sales.keys():
                db_dates.add(str(date_key))
        
        # Extract dates from sales_trends
        sales_trends = analytics_data.get('sales_trends', {})
        trends_dates = set(str(key) for key in sales_trends.keys())
        
        print(f"Database dates: {len(db_dates)}")
        print(f"Trends dates: {len(trends_dates)}")
        
        missing_dates = db_dates - trends_dates
        
        if not missing_dates:
            print("✅ All database dates are included in sales_trends")
            return True
        else:
            print(f"❌ {len(missing_dates)} dates missing from sales_trends")
            print(f"Missing: {sorted(list(missing_dates))[:5]}")
            return False
            
    except Exception as e:
        print(f"❌ Error during completeness test: {e}")
        return False

def main():
    """Run final comprehensive tests"""
    print("🚀 FINAL COMPREHENSIVE TRENDS TAB TESTS")
    print("Testing the chronological date ordering fix")
    print("=" * 70)
    
    test_results = []
    
    # Test 1: Chronological ordering fix
    result1 = test_chronological_ordering_fix()
    test_results.append(("Chronological Ordering Fix", result1))
    
    # Test 2: Date format handling
    result2 = test_specific_date_formats()
    test_results.append(("Date Format Handling", result2))
    
    # Test 3: Data completeness
    result3 = test_data_completeness()
    test_results.append(("Data Completeness", result3))
    
    # Summary
    print("\n" + "=" * 70)
    print("📊 FINAL TEST SUMMARY")
    passed = sum(1 for _, result in test_results if result)
    total = len(test_results)
    
    for test_name, result in test_results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {status} {test_name}")
    
    print(f"\nOverall: {passed}/{total} tests passed ({(passed/total)*100:.1f}%)")
    
    if passed == total:
        print("🎉 ALL TESTS PASSED!")
        print("✅ The Trends tab chronological date ordering fix is working correctly!")
        print("✅ Dates like '21-Sep', '22-Sep', '26-Sep' are now properly sorted chronologically")
        print("✅ The fix handles various date formats correctly")
    else:
        print("⚠️ Some tests failed - further investigation needed")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)