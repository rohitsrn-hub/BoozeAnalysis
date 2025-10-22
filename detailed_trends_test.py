#!/usr/bin/env python3
"""
Detailed test for Trends tab chronological ordering issue
This test specifically validates the fix for the date ordering problem
"""

import requests
import json
from datetime import datetime
import re

BACKEND_URL = "https://liquor-dashboard-1.preview.emergentagent.com/api"

def parse_date_for_sorting(date_str):
    """Parse various date formats for chronological sorting - matches backend logic"""
    try:
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
                    # Handle missing year - assume current year (2025)
                    if not year or len(year) < 2:
                        year = '2025'
                    elif len(year) == 2:
                        year = f"20{year}"
                    full_date = f"{day}-{month_name}-{year}"
                    return datetime.strptime(full_date, fmt)
                elif fmt == "%Y-%m-%d":
                    return datetime.strptime(match.group(0), fmt)
                elif fmt == "%d-%m-%Y":
                    day, month, year = match.groups()
                    year = f"20{year}" if len(year) == 2 else year
                    return datetime(int(year), int(month), int(day))
                    
    except Exception as e:
        print(f"Warning: Could not parse date '{date_str}': {e}")
        return datetime.min
    
    return datetime.min

def test_chronological_ordering():
    """Test the specific chronological ordering issue"""
    print("🔍 DETAILED TRENDS CHRONOLOGICAL ORDERING TEST")
    print("=" * 60)
    
    # Get analytics data
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
        
        # Show current order
        for i, (date_key, value) in enumerate(sales_trends.items(), 1):
            parsed_date = parse_date_for_sorting(date_key)
            print(f"  {i:2d}. {date_key:12s} → {parsed_date.strftime('%Y-%m-%d')} (value: {value})")
        
        # Test if current order is chronological
        date_keys = list(sales_trends.keys())
        parsed_dates = [(key, parse_date_for_sorting(key)) for key in date_keys]
        
        # Check chronological order
        is_chronological = True
        problem_indices = []
        
        for i in range(1, len(parsed_dates)):
            current_date = parsed_dates[i][1]
            previous_date = parsed_dates[i-1][1]
            
            if current_date < previous_date:
                is_chronological = False
                problem_indices.append(i)
        
        print(f"\n📈 CHRONOLOGICAL ORDER TEST:")
        if is_chronological:
            print("✅ PASS: Dates are in correct chronological order")
            return True
        else:
            print("❌ FAIL: Dates are NOT in chronological order")
            print(f"   Problem at positions: {problem_indices}")
            
            # Show what the correct order should be
            print("\n🔧 CORRECT CHRONOLOGICAL ORDER should be:")
            sorted_dates = sorted(parsed_dates, key=lambda x: x[1])
            
            for i, (date_key, parsed_date) in enumerate(sorted_dates, 1):
                value = sales_trends[date_key]
                print(f"  {i:2d}. {date_key:12s} → {parsed_date.strftime('%Y-%m-%d')} (value: {value})")
            
            # Show the specific issue
            print(f"\n🚨 SPECIFIC ISSUE IDENTIFIED:")
            print(f"   The problem mentioned in the review request:")
            print(f"   - Dates like '21-Sep', '22-Sep', '26-Sep' (missing year) are being sorted alphabetically")
            print(f"   - They should be treated as '21-Sep-25', '22-Sep-25', '26-Sep-25' for proper chronological sorting")
            print(f"   - Current: {' → '.join(date_keys[:5])}")
            print(f"   - Should be: {' → '.join([key for key, _ in sorted_dates[:5]])}")
            
            return False
            
    except Exception as e:
        print(f"❌ Error during test: {e}")
        return False

def test_today_data_upload_impact():
    """Test if Today's Data upload would maintain chronological ordering"""
    print(f"\n📤 TODAY'S DATA UPLOAD IMPACT TEST")
    print("=" * 40)
    
    # This test simulates what would happen if new data was uploaded
    # We can't actually upload without a file, but we can verify the current state
    
    try:
        response = requests.get(f"{BACKEND_URL}/database-view", timeout=30)
        if response.status_code != 200:
            print(f"❌ Failed to get database data: {response.status_code}")
            return False
        
        db_data = response.json()
        data_list = db_data.get('data', [])
        
        if not data_list:
            print("❌ No database records found")
            return False
        
        # Check the latest DL_date to see what would happen with new uploads
        latest_dl_dates = set()
        for record in data_list[:5]:  # Check first 5 records
            dl_date = record.get('DL_date')
            if dl_date:
                latest_dl_dates.add(dl_date)
        
        print(f"📅 Current DL dates in database: {sorted(latest_dl_dates)}")
        
        # Simulate what would happen if we uploaded "04-Oct-25" data
        simulated_new_date = "04-Oct-25"
        
        # Get current sales trends
        response2 = requests.get(f"{BACKEND_URL}/analytics", timeout=30)
        if response2.status_code == 200:
            analytics_data = response2.json()
            current_trends = list(analytics_data.get('sales_trends', {}).keys())
            
            # Add simulated new date and test ordering
            test_dates = current_trends + [simulated_new_date]
            parsed_test_dates = [(key, parse_date_for_sorting(key)) for key in test_dates]
            sorted_test_dates = sorted(parsed_test_dates, key=lambda x: x[1])
            
            print(f"\n🧪 SIMULATION: If '{simulated_new_date}' was uploaded:")
            print(f"   Current order: {' → '.join(current_trends)}")
            print(f"   After upload: {' → '.join([key for key, _ in sorted_test_dates])}")
            
            # Check if new date would be in correct position
            new_date_position = [key for key, _ in sorted_test_dates].index(simulated_new_date)
            expected_position = len(current_trends)  # Should be at the end since it's the latest date
            
            if new_date_position == expected_position:
                print(f"✅ PASS: New date would be correctly positioned at end (position {new_date_position + 1})")
                return True
            else:
                print(f"❌ FAIL: New date would be at position {new_date_position + 1}, expected {expected_position + 1}")
                return False
        else:
            print("❌ Could not get analytics data for simulation")
            return False
            
    except Exception as e:
        print(f"❌ Error during simulation test: {e}")
        return False

def main():
    """Run detailed trends tests"""
    print("🚀 DETAILED TRENDS TAB CHRONOLOGICAL ORDERING TESTS")
    print("=" * 70)
    
    test_results = []
    
    # Test 1: Current chronological ordering
    result1 = test_chronological_ordering()
    test_results.append(("Chronological Ordering", result1))
    
    # Test 2: Today's data upload impact
    result2 = test_today_data_upload_impact()
    test_results.append(("Today's Data Upload Impact", result2))
    
    # Summary
    print("\n" + "=" * 70)
    print("📊 DETAILED TEST SUMMARY")
    passed = sum(1 for _, result in test_results if result)
    total = len(test_results)
    
    for test_name, result in test_results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {status} {test_name}")
    
    print(f"\nOverall: {passed}/{total} tests passed ({(passed/total)*100:.1f}%)")
    
    if passed == total:
        print("🎉 All detailed tests passed!")
    else:
        print("⚠️ Some tests failed - chronological ordering fix needs attention")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)