#!/usr/bin/env python3
"""
Critical Issues Testing for Liquor Sales Analytics Dashboard
Tests three specific production issues:
1. Duplicate Brands After Second Today's Data Upload
2. Sales Trends Empty
3. Datetime Error (Still Persisting)
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

class CriticalIssuesTester:
    def __init__(self):
        self.base_url = BACKEND_URL
        self.test_results = []
        self.session = requests.Session()
        
    def log_test(self, test_name, status, message, details=None):
        """Log test results"""
        result = {
            "test_name": test_name,
            "status": status,
            "message": message,
            "timestamp": datetime.now().isoformat(),
            "details": details
        }
        self.test_results.append(result)
        
        status_icon = "✅" if status == "PASS" else "❌" if status == "FAIL" else "⚠️"
        print(f"{status_icon} {test_name}: {message}")
        if details:
            print(f"   Details: {details}")
    
    def test_endpoint(self, method, endpoint, expected_status=200, data=None, files=None, description=""):
        """Generic endpoint testing method"""
        url = f"{self.base_url}{endpoint}"
        
        try:
            if method.upper() == "GET":
                response = self.session.get(url, timeout=30)
            elif method.upper() == "POST":
                if files:
                    response = self.session.post(url, files=files, data=data, timeout=30)
                else:
                    response = self.session.post(url, json=data, timeout=30)
            else:
                raise ValueError(f"Unsupported method: {method}")
            
            if response.status_code == expected_status:
                try:
                    response_data = response.json()
                    return True, response_data, None
                except:
                    return True, response.text, None
            else:
                try:
                    error_data = response.json()
                    return False, None, f"Status {response.status_code}: {error_data}"
                except:
                    return False, None, f"Status {response.status_code}: {response.text[:200]}"
                    
        except requests.exceptions.Timeout:
            return False, None, "Request timeout (30s)"
        except requests.exceptions.ConnectionError:
            return False, None, "Connection error - backend may be down"
        except Exception as e:
            return False, None, f"Request error: {str(e)}"

    def clear_database(self):
        """Clear the database to simulate reset"""
        print("\n🗑️ Clearing Database (Simulating Reset)")
        
        # Use stock reset endpoint to clear database
        success, data, error = self.test_endpoint("POST", "/stock/reset", 200)
        
        if success:
            self.log_test("Database Clear", "PASS", "Database cleared successfully", str(data))
            return True
        else:
            self.log_test("Database Clear", "FAIL", "Failed to clear database", error)
            return False

    def get_brand_count(self):
        """Get current brand count from database"""
        success, data, error = self.test_endpoint("GET", "/database-view", 200)
        
        if success and isinstance(data, dict):
            total_records = data.get('total_records', 0)
            return total_records
        else:
            return None

    def create_test_excel_file(self, date_str, brand_count=62):
        """Create a test Excel file for Today's Data upload"""
        import pandas as pd
        
        # Create test data with specified number of brands
        brands_data = []
        for i in range(1, brand_count + 1):
            brands_data.append({
                'Index': i,
                'Brand Name': f'Test Brand {i:02d}',
                date_str: 100 - i  # Stock quantity decreases with each brand
            })
        
        df = pd.DataFrame(brands_data)
        
        # Save to bytes
        excel_buffer = io.BytesIO()
        df.to_excel(excel_buffer, index=False)
        excel_buffer.seek(0)
        
        return excel_buffer.getvalue()

    def upload_todays_data(self, date_str, brand_count=62):
        """Upload Today's Data with specified date and brand count"""
        print(f"  📤 Uploading Today's Data for {date_str} ({brand_count} brands)")
        
        # Create test Excel file
        excel_content = self.create_test_excel_file(date_str, brand_count)
        
        # Upload the file
        files = {'file': (f'todays_data_{date_str}.xlsx', excel_content, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')}
        
        url = f"{self.base_url}/upload-todays-data"
        
        try:
            response = self.session.post(url, files=files, timeout=60)
            
            if response.status_code == 200:
                try:
                    response_data = response.json()
                    return True, response_data, None
                except:
                    return True, response.text, None
            else:
                try:
                    error_data = response.json()
                    return False, None, f"Status {response.status_code}: {error_data}"
                except:
                    return False, None, f"Status {response.status_code}: {response.text[:500]}"
                    
        except requests.exceptions.Timeout:
            return False, None, "Upload timeout (60s)"
        except requests.exceptions.ConnectionError:
            return False, None, "Connection error during upload"
        except Exception as e:
            return False, None, f"Upload error: {str(e)}"

    def test_issue_1_duplicate_brands(self):
        """
        ISSUE 1: Duplicate Brands After Second Today's Data Upload
        Test: Upload Today's Data twice on empty database and check brand count
        """
        print("\n🔍 TESTING ISSUE 1: Duplicate Brands After Second Today's Data Upload")
        
        # Step 1: Clear database
        if not self.clear_database():
            return False
        
        # Verify database is empty
        initial_count = self.get_brand_count()
        if initial_count != 0:
            self.log_test("Issue 1 - Initial State", "FAIL", f"Database not empty after reset", f"Found {initial_count} brands")
            return False
        
        self.log_test("Issue 1 - Initial State", "PASS", "Database is empty after reset", "Ready for testing")
        
        # Step 2: Upload Today's Data Day 1 (19-Oct-25)
        success1, data1, error1 = self.upload_todays_data("19-Oct-25", 62)
        
        if not success1:
            self.log_test("Issue 1 - First Upload", "FAIL", "First Today's Data upload failed", error1)
            return False
        
        # Check brand count after first upload
        count_after_first = self.get_brand_count()
        if count_after_first != 62:
            self.log_test("Issue 1 - First Upload Count", "FAIL", f"Expected 62 brands after first upload, got {count_after_first}", "Brand creation issue")
            return False
        
        self.log_test("Issue 1 - First Upload", "PASS", f"First upload successful: {count_after_first} brands created", str(data1))
        
        # Step 3: Upload Today's Data Day 2 (20-Oct-25) 
        success2, data2, error2 = self.upload_todays_data("20-Oct-25", 62)
        
        if not success2:
            self.log_test("Issue 1 - Second Upload", "FAIL", "Second Today's Data upload failed", error2)
            return False
        
        # Check brand count after second upload - THIS IS THE CRITICAL TEST
        count_after_second = self.get_brand_count()
        
        if count_after_second == 62:
            self.log_test("Issue 1 - Duplicate Brands Test", "PASS", f"Brand count remains correct: {count_after_second} brands", "No duplicate brands created ✅")
            return True
        elif count_after_second == 124:
            self.log_test("Issue 1 - Duplicate Brands Test", "FAIL", f"DUPLICATE BRANDS DETECTED: {count_after_second} brands (should be 62)", "Second upload created duplicate brands ❌")
            return False
        else:
            self.log_test("Issue 1 - Duplicate Brands Test", "FAIL", f"Unexpected brand count: {count_after_second} brands", f"Expected 62, got {count_after_second}")
            return False

    def test_issue_2_sales_trends_empty(self):
        """
        ISSUE 2: Sales Trends Empty
        Test: Check if daily_sales field is populated and /api/analytics returns sales_trends with data
        """
        print("\n🔍 TESTING ISSUE 2: Sales Trends Empty")
        
        # Step 1: Clear database and upload 3 days of data
        if not self.clear_database():
            return False
        
        # Upload 3 days of data
        dates = ["19-Oct-25", "20-Oct-25", "21-Oct-25"]
        
        for i, date in enumerate(dates):
            success, data, error = self.upload_todays_data(date, 62)
            if not success:
                self.log_test(f"Issue 2 - Upload Day {i+1}", "FAIL", f"Failed to upload data for {date}", error)
                return False
            
            self.log_test(f"Issue 2 - Upload Day {i+1}", "PASS", f"Successfully uploaded data for {date}", f"Response: {str(data)[:100]}")
        
        # Step 2: Check if daily_sales field is populated in liquor_data records
        success, db_data, error = self.test_endpoint("GET", "/database-view", 200)
        
        if not success:
            self.log_test("Issue 2 - Database Check", "FAIL", "Failed to get database data", error)
            return False
        
        if not isinstance(db_data, dict) or 'data' not in db_data:
            self.log_test("Issue 2 - Database Check", "FAIL", "Invalid database response format", f"Got: {type(db_data)}")
            return False
        
        records = db_data.get('data', [])
        if not records:
            self.log_test("Issue 2 - Database Check", "FAIL", "No records found in database", "Database appears empty")
            return False
        
        # Check first few records for daily_sales field
        daily_sales_populated = 0
        total_dates_found = set()
        
        for record in records[:5]:  # Check first 5 records
            daily_sales = record.get('daily_sales', {})
            if daily_sales and isinstance(daily_sales, dict):
                daily_sales_populated += 1
                total_dates_found.update(daily_sales.keys())
        
        if daily_sales_populated == 0:
            self.log_test("Issue 2 - Daily Sales Field", "FAIL", "daily_sales field is empty in all records", "Sales trends will be empty")
            return False
        
        self.log_test("Issue 2 - Daily Sales Field", "PASS", f"daily_sales field populated in {daily_sales_populated}/5 records", f"Found dates: {sorted(list(total_dates_found))}")
        
        # Step 3: Check if /api/analytics returns sales_trends with data
        success, analytics_data, error = self.test_endpoint("GET", "/analytics", 200)
        
        if not success:
            self.log_test("Issue 2 - Analytics Endpoint", "FAIL", "Failed to get analytics data", error)
            return False
        
        if not isinstance(analytics_data, dict):
            self.log_test("Issue 2 - Analytics Endpoint", "FAIL", "Invalid analytics response format", f"Got: {type(analytics_data)}")
            return False
        
        sales_trends = analytics_data.get('sales_trends', {})
        
        if not sales_trends:
            self.log_test("Issue 2 - Sales Trends Empty", "FAIL", "sales_trends is empty in analytics response", "Trends tab will show empty/placeholder")
            return False
        
        if not isinstance(sales_trends, dict):
            self.log_test("Issue 2 - Sales Trends Format", "FAIL", f"sales_trends has wrong format: {type(sales_trends)}", "Expected dict")
            return False
        
        trends_dates = list(sales_trends.keys())
        if len(trends_dates) < 3:
            self.log_test("Issue 2 - Sales Trends Data", "FAIL", f"Insufficient sales trends data: {len(trends_dates)} dates", f"Expected 3 dates, got: {trends_dates}")
            return False
        
        # Check if trends data has actual values
        sample_trend = sales_trends[trends_dates[0]]
        if not sample_trend or (isinstance(sample_trend, (int, float)) and sample_trend == 0):
            self.log_test("Issue 2 - Sales Trends Values", "FAIL", "Sales trends contains zero/empty values", f"Sample: {sample_trend}")
            return False
        
        self.log_test("Issue 2 - Sales Trends Populated", "PASS", f"sales_trends contains data for {len(trends_dates)} dates", f"Dates: {trends_dates}, Sample value: {sample_trend}")
        return True

    def test_issue_3_datetime_error(self):
        """
        ISSUE 3: Datetime Error (Still Persisting)
        Test: Try uploading Today's Data on empty database and catch datetime errors
        """
        print("\n🔍 TESTING ISSUE 3: Datetime Error (Still Persisting)")
        
        # Step 1: Clear database to simulate reset
        if not self.clear_database():
            return False
        
        # Step 2: Try uploading Today's Data and monitor for datetime errors
        print("  📤 Attempting Today's Data upload on empty database...")
        
        success, data, error = self.upload_todays_data("22-Oct-25", 62)
        
        if success:
            self.log_test("Issue 3 - Datetime Error Test", "PASS", "Today's Data upload successful - no datetime error", str(data))
            return True
        else:
            # Check if the error is related to datetime
            error_str = str(error).lower()
            
            if "datetime" in error_str and "cannot access local variable" in error_str:
                self.log_test("Issue 3 - Datetime Error Test", "FAIL", "DATETIME ERROR STILL PERSISTING", f"Error: {error}")
                return False
            elif "datetime" in error_str:
                self.log_test("Issue 3 - Datetime Error Test", "FAIL", "Datetime-related error detected", f"Error: {error}")
                return False
            else:
                self.log_test("Issue 3 - Datetime Error Test", "FAIL", "Upload failed with non-datetime error", f"Error: {error}")
                return False

    def run_all_critical_tests(self):
        """Run all critical issue tests"""
        print("🚨 STARTING CRITICAL ISSUES TESTING")
        print("=" * 60)
        
        all_passed = True
        
        # Test Issue 1: Duplicate Brands
        if not self.test_issue_1_duplicate_brands():
            all_passed = False
        
        # Test Issue 2: Sales Trends Empty  
        if not self.test_issue_2_sales_trends_empty():
            all_passed = False
        
        # Test Issue 3: Datetime Error
        if not self.test_issue_3_datetime_error():
            all_passed = False
        
        # Summary
        print("\n" + "=" * 60)
        print("🚨 CRITICAL ISSUES TEST SUMMARY")
        print("=" * 60)
        
        passed_tests = [result for result in self.test_results if result['status'] == 'PASS']
        failed_tests = [result for result in self.test_results if result['status'] == 'FAIL']
        
        print(f"✅ PASSED: {len(passed_tests)} tests")
        print(f"❌ FAILED: {len(failed_tests)} tests")
        
        if failed_tests:
            print("\n🔥 CRITICAL FAILURES:")
            for test in failed_tests:
                print(f"  ❌ {test['test_name']}: {test['message']}")
                if test['details']:
                    print(f"     Details: {test['details']}")
        
        return all_passed

if __name__ == "__main__":
    tester = CriticalIssuesTester()
    success = tester.run_all_critical_tests()
    
    if success:
        print("\n🎉 All critical issues tests PASSED!")
        sys.exit(0)
    else:
        print("\n💥 Some critical issues tests FAILED!")
        sys.exit(1)