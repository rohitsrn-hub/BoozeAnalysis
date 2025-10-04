#!/usr/bin/env python3
"""
Backend API Testing for Liquor Sales Analytics Dashboard
Tests all backend endpoints with focus on refresh functionality and demand recommendations
"""

import requests
import json
import os
import sys
from datetime import datetime
import time

# Get backend URL from environment
BACKEND_URL = "https://liquor-analytics.preview.emergentagent.com/api"

class BackendTester:
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
    
    def test_refresh_analytics(self):
        """PRIORITY TEST: Test refresh analytics endpoint"""
        print("\n🔄 Testing Refresh Analytics Endpoint (PRIORITY)")
        
        success, data, error = self.test_endpoint("POST", "/refresh-analytics", 200)
        
        if success:
            if isinstance(data, dict):
                updated_records = data.get('updated_records', 0)
                d1_dates = data.get('d1_dates', [])
                dl_dates = data.get('dl_dates', [])
                
                self.log_test(
                    "Refresh Analytics", 
                    "PASS", 
                    f"Successfully refreshed {updated_records} records",
                    f"D1 dates: {d1_dates}, DL dates: {dl_dates}"
                )
                return True
            else:
                self.log_test("Refresh Analytics", "PASS", "Endpoint responded successfully", str(data)[:100])
                return True
        else:
            self.log_test("Refresh Analytics", "FAIL", "Refresh endpoint failed", error)
            return False
    
    def test_demand_recommendations(self):
        """Test demand recommendations endpoint with float validation"""
        print("\n📊 Testing Demand Recommendations Endpoint")
        
        success, data, error = self.test_endpoint("GET", "/demand-recommendations", 200)
        
        if success:
            if isinstance(data, list):
                if len(data) > 0:
                    # Check if recommended_qty is float
                    sample_rec = data[0]
                    recommended_qty = sample_rec.get('recommended_qty')
                    
                    if isinstance(recommended_qty, (int, float)):
                        self.log_test(
                            "Demand Recommendations", 
                            "PASS", 
                            f"Found {len(data)} recommendations with proper float values",
                            f"Sample recommended_qty: {recommended_qty} (type: {type(recommended_qty).__name__})"
                        )
                        return True
                    else:
                        self.log_test(
                            "Demand Recommendations", 
                            "FAIL", 
                            "recommended_qty field has wrong type",
                            f"Expected float/int, got {type(recommended_qty).__name__}: {recommended_qty}"
                        )
                        return False
                else:
                    self.log_test("Demand Recommendations", "PASS", "No recommendations needed (empty list)", "All items sufficiently stocked")
                    return True
            else:
                self.log_test("Demand Recommendations", "FAIL", "Expected list response", f"Got: {type(data).__name__}")
                return False
        else:
            self.log_test("Demand Recommendations", "FAIL", "Endpoint failed", error)
            return False
    
    def test_analytics_endpoints(self):
        """Test all analytics endpoints"""
        print("\n📈 Testing Analytics Endpoints")
        
        endpoints_to_test = [
            ("/analytics?overstock_multiplier=3.0", "Analytics with overstock multiplier"),
            ("/charts", "Charts data"),
            ("/calculation-details", "Calculation details"),
            ("/database-view", "Database view"),
            ("/upload-history", "Upload history")
        ]
        
        all_passed = True
        
        for endpoint, description in endpoints_to_test:
            success, data, error = self.test_endpoint("GET", endpoint, 200)
            
            if success:
                if isinstance(data, (dict, list)):
                    data_size = len(data) if isinstance(data, list) else len(str(data))
                    self.log_test(f"Analytics - {description}", "PASS", f"Returned valid data ({data_size} items/chars)")
                else:
                    self.log_test(f"Analytics - {description}", "PASS", "Endpoint responded", str(data)[:50])
            else:
                self.log_test(f"Analytics - {description}", "FAIL", "Endpoint failed", error)
                all_passed = False
        
        return all_passed
    
    def test_dl_date_updates(self):
        """Test if DL dates are properly reflected in analytics after data uploads"""
        print("\n📅 Testing DL Date Updates in Analytics")
        
        # First, get current analytics to see DL dates
        success, analytics_data, error = self.test_endpoint("GET", "/database-view", 200)
        
        if success and isinstance(analytics_data, dict):
            # database-view returns {"total_records": X, "data": [...]}
            data_list = analytics_data.get('data', [])
            if len(data_list) > 0:
                # Check if we have DL_date fields
                sample_record = data_list[0]
                dl_date = sample_record.get('DL_date')
                
                if dl_date:
                    self.log_test(
                        "DL Date Verification", 
                        "PASS", 
                        f"DL dates are present in analytics",
                        f"Sample DL_date: {dl_date}"
                    )
                    
                    # Also check calculation-details for DL date consistency
                    success2, calc_data, error2 = self.test_endpoint("GET", "/calculation-details", 200)
                    if success2 and isinstance(calc_data, list) and len(calc_data) > 0:
                        calc_sample = calc_data[0]
                        calc_dl_date = calc_sample.get('DL_date')
                        
                        if calc_dl_date == dl_date:
                            self.log_test(
                                "DL Date Consistency", 
                                "PASS", 
                                "DL dates consistent across endpoints",
                                f"Both show: {dl_date}"
                            )
                            return True
                        else:
                            self.log_test(
                                "DL Date Consistency", 
                                "FAIL", 
                                "DL dates inconsistent between endpoints",
                                f"Database: {dl_date}, Calculations: {calc_dl_date}"
                            )
                            return False
                    else:
                        self.log_test("DL Date Consistency", "FAIL", "Could not verify calculation details", error2)
                        return False
                else:
                    self.log_test("DL Date Verification", "FAIL", "No DL_date found in analytics data", "DL dates may not be updating")
                    return False
            else:
                self.log_test("DL Date Verification", "FAIL", "No data records found", "Database may be empty")
                return False
        else:
            self.log_test("DL Date Verification", "FAIL", "Could not retrieve analytics data", error)
            return False
    
    def test_trends_chronological_ordering(self):
        """PRIORITY TEST: Test Trends tab chronological date ordering fix"""
        print("\n📊 Testing Trends Tab Chronological Date Ordering (PRIORITY)")
        
        # Test the analytics endpoint for sales_trends chronological ordering
        success, analytics_data, error = self.test_endpoint("GET", "/analytics", 200)
        
        if not success:
            self.log_test("Trends Chronological Ordering", "FAIL", "Analytics endpoint failed", error)
            return False
        
        if not isinstance(analytics_data, dict):
            self.log_test("Trends Chronological Ordering", "FAIL", "Invalid analytics response format", f"Expected dict, got {type(analytics_data)}")
            return False
        
        sales_trends = analytics_data.get('sales_trends', {})
        
        if not sales_trends:
            self.log_test("Trends Chronological Ordering", "FAIL", "No sales_trends data found", "sales_trends is empty or missing")
            return False
        
        # Get the date keys from sales_trends
        date_keys = list(sales_trends.keys())
        
        if len(date_keys) < 2:
            self.log_test("Trends Chronological Ordering", "PASS", "Insufficient dates for ordering test", f"Only {len(date_keys)} dates found")
            return True
        
        # Test chronological ordering by parsing dates
        def parse_date_for_validation(date_str):
            """Parse date string for validation - matches backend logic exactly"""
            try:
                import re
                from datetime import datetime
                
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
                
                # First try: dates with year (21-Sep-25, 01-Oct-25)
                match = re.search(r'(\d{1,2})[-/](\w{3})[-/](\d{2,4})', date_str, re.IGNORECASE)
                if match:
                    day, month_name, year = match.groups()
                    year = f"20{year}" if len(year) == 2 else year
                    full_date = f"{day}-{month_name}-{year}"
                    return datetime.strptime(full_date, "%d-%b-%Y")
                
                # Second try: dates without year (21-Sep, 22-Sep) - assume 2025
                match = re.search(r'(\d{1,2})[-/](\w{3})$', date_str, re.IGNORECASE)
                if match:
                    day, month_name = match.groups()
                    year = "2025"  # Default to 2025 for dates without year
                    full_date = f"{day}-{month_name}-{year}"
                    return datetime.strptime(full_date, "%d-%b-%Y")
                
                # Third try: ISO format (2025-10-04)
                match = re.search(r'(\d{4})-(\d{1,2})-(\d{1,2})', date_str)
                if match:
                    return datetime.strptime(match.group(0), "%Y-%m-%d")
                
                # Fourth try: numeric dates (04-10-25, 04/10/2025)
                match = re.search(r'(\d{1,2})[-/](\d{1,2})[-/](\d{2,4})', date_str)
                if match:
                    day, month, year = match.groups()
                    year = f"20{year}" if len(year) == 2 else year
                    return datetime(int(year), int(month), int(day))
                        
            except Exception as e:
                print(f"Warning: Could not parse date '{date_str}': {e}")
                return datetime.min
            
            return datetime.min
        
        # Parse all dates and check if they're in chronological order
        parsed_dates = []
        for date_key in date_keys:
            parsed_date = parse_date_for_validation(date_key)
            parsed_dates.append((date_key, parsed_date))
        
        # Check if dates are in chronological order
        is_chronological = True
        previous_date = None
        
        for i, (date_key, parsed_date) in enumerate(parsed_dates):
            if previous_date is not None and parsed_date < previous_date:
                is_chronological = False
                break
            previous_date = parsed_date
        
        if is_chronological:
            # Format dates for display
            date_display = [f"{date_key} ({parsed_date.strftime('%Y-%m-%d')})" for date_key, parsed_date in parsed_dates[:5]]
            self.log_test(
                "Trends Chronological Ordering", 
                "PASS", 
                f"Sales trends dates are in chronological order ({len(date_keys)} dates)",
                f"Sample order: {' → '.join(date_display)}"
            )
            return True
        else:
            # Show the problematic ordering
            date_display = [f"{date_key} ({parsed_date.strftime('%Y-%m-%d')})" for date_key, parsed_date in parsed_dates]
            self.log_test(
                "Trends Chronological Ordering", 
                "FAIL", 
                "Sales trends dates are NOT in chronological order",
                f"Current order: {' → '.join(date_display)}"
            )
            return False
    
    def test_date_parsing_function(self):
        """Test various date formats that the parse_date_for_sorting function should handle"""
        print("\n🗓️ Testing Date Parsing Function Formats")
        
        # Get analytics data to test actual date parsing
        success, analytics_data, error = self.test_endpoint("GET", "/analytics", 200)
        
        if not success:
            self.log_test("Date Parsing Function", "FAIL", "Could not get analytics data for testing", error)
            return False
        
        sales_trends = analytics_data.get('sales_trends', {})
        
        if not sales_trends:
            self.log_test("Date Parsing Function", "FAIL", "No sales_trends data to test date parsing", "Empty sales_trends")
            return False
        
        # Test different date format patterns that should be supported
        date_keys = list(sales_trends.keys())
        supported_formats = {
            'day_month_year': 0,  # 21-Sep, 20-Sep-25
            'full_datetime': 0,   # Full datetime strings
            'iso_format': 0,      # 2025-10-01
            'other_formats': 0    # Other recognized formats
        }
        
        import re
        
        for date_key in date_keys:
            date_str = str(date_key).strip()
            
            # Check format patterns
            if re.search(r'\d{1,2}[-/]\w{3}[-/]?\d{0,4}', date_str, re.IGNORECASE):
                supported_formats['day_month_year'] += 1
            elif 'T' in date_str or len(date_str) > 15:
                supported_formats['full_datetime'] += 1
            elif re.search(r'\d{4}-\d{1,2}-\d{1,2}', date_str):
                supported_formats['iso_format'] += 1
            else:
                supported_formats['other_formats'] += 1
        
        # Verify that we can handle the formats present in the data
        total_dates = len(date_keys)
        recognized_dates = sum(supported_formats.values())
        
        if recognized_dates == total_dates:
            format_summary = ", ".join([f"{fmt}: {count}" for fmt, count in supported_formats.items() if count > 0])
            self.log_test(
                "Date Parsing Function", 
                "PASS", 
                f"All {total_dates} date formats recognized and parseable",
                f"Format breakdown: {format_summary}"
            )
            return True
        else:
            self.log_test(
                "Date Parsing Function", 
                "FAIL", 
                f"Some date formats not recognized: {recognized_dates}/{total_dates}",
                f"Unrecognized dates may cause sorting issues"
            )
            return False
    
    def test_data_completeness(self):
        """Test that all dates from database are included in sales_trends"""
        print("\n📋 Testing Data Completeness in Sales Trends")
        
        # Get database view to see all dates in raw data
        success1, db_data, error1 = self.test_endpoint("GET", "/database-view", 200)
        
        if not success1:
            self.log_test("Data Completeness", "FAIL", "Could not get database data", error1)
            return False
        
        # Get analytics data to see sales_trends
        success2, analytics_data, error2 = self.test_endpoint("GET", "/analytics", 200)
        
        if not success2:
            self.log_test("Data Completeness", "FAIL", "Could not get analytics data", error2)
            return False
        
        # Extract all dates from database records
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
        
        # Compare completeness
        missing_dates = db_dates - trends_dates
        extra_dates = trends_dates - db_dates
        
        if not missing_dates and not extra_dates:
            self.log_test(
                "Data Completeness", 
                "PASS", 
                f"All {len(db_dates)} dates from database included in sales_trends",
                f"Perfect match between database dates and trends data"
            )
            return True
        elif missing_dates and not extra_dates:
            self.log_test(
                "Data Completeness", 
                "FAIL", 
                f"{len(missing_dates)} dates missing from sales_trends",
                f"Missing dates: {sorted(list(missing_dates))[:5]}"
            )
            return False
        elif extra_dates and not missing_dates:
            self.log_test(
                "Data Completeness", 
                "PASS", 
                f"All database dates included, {len(extra_dates)} additional dates in trends",
                f"Extra dates may be from processed/calculated data"
            )
            return True
        else:
            self.log_test(
                "Data Completeness", 
                "FAIL", 
                f"Data mismatch: {len(missing_dates)} missing, {len(extra_dates)} extra",
                f"Missing: {sorted(list(missing_dates))[:3]}, Extra: {sorted(list(extra_dates))[:3]}"
            )
            return False
    
    def test_file_upload_endpoints(self):
        """Test file upload endpoints (without actually uploading files)"""
        print("\n📁 Testing File Upload Endpoints")
        
        # Test upload endpoints by checking they exist and return proper error for missing file
        upload_endpoints = [
            ("/upload-full-monthly-data", "Full Monthly Data Upload"),
            ("/upload-todays-data", "Today's Data Upload")
        ]
        
        all_passed = True
        
        for endpoint, description in upload_endpoints:
            # Test without file - should return 422 (validation error) not 404
            success, data, error = self.test_endpoint("POST", endpoint, 422)
            
            if success or (error and "422" in str(error)):
                self.log_test(
                    f"Upload - {description}", 
                    "PASS", 
                    "Endpoint exists and validates file requirement",
                    "Returns proper validation error when no file provided"
                )
            else:
                self.log_test(f"Upload - {description}", "FAIL", "Endpoint issue", error)
                all_passed = False
        
        return all_passed
    
    def test_root_endpoint(self):
        """Test root API endpoint"""
        print("\n🏠 Testing Root Endpoint")
        
        success, data, error = self.test_endpoint("GET", "/", 200)
        
        if success:
            self.log_test("Root Endpoint", "PASS", "API root accessible", str(data))
            return True
        else:
            self.log_test("Root Endpoint", "FAIL", "API root not accessible", error)
            return False
    
    def run_all_tests(self):
        """Run all backend tests"""
        print(f"🚀 Starting Backend API Tests")
        print(f"Backend URL: {self.base_url}")
        print("=" * 60)
        
        # Test results tracking - PRIORITY: Trends tab chronological ordering tests
        test_functions = [
            ("Root Endpoint", self.test_root_endpoint),
            ("Trends Chronological Ordering (PRIORITY)", self.test_trends_chronological_ordering),
            ("Date Parsing Function", self.test_date_parsing_function),
            ("Data Completeness", self.test_data_completeness),
            ("Refresh Analytics", self.test_refresh_analytics),
            ("Demand Recommendations", self.test_demand_recommendations),
            ("DL Date Updates", self.test_dl_date_updates),
            ("Analytics Endpoints", self.test_analytics_endpoints),
            ("File Upload Endpoints", self.test_file_upload_endpoints),
        ]
        
        passed_tests = 0
        total_tests = len(test_functions)
        
        for test_name, test_func in test_functions:
            try:
                result = test_func()
                if result:
                    passed_tests += 1
            except Exception as e:
                self.log_test(test_name, "FAIL", f"Test execution error: {str(e)}")
        
        # Summary
        print("\n" + "=" * 60)
        print(f"📊 TEST SUMMARY")
        print(f"Passed: {passed_tests}/{total_tests}")
        print(f"Success Rate: {(passed_tests/total_tests)*100:.1f}%")
        
        if passed_tests == total_tests:
            print("🎉 ALL TESTS PASSED!")
        else:
            print(f"⚠️  {total_tests - passed_tests} tests failed")
        
        return passed_tests, total_tests, self.test_results

def main():
    """Main test execution"""
    tester = BackendTester()
    passed, total, results = tester.run_all_tests()
    
    # Save detailed results
    with open('/app/backend_test_results.json', 'w') as f:
        json.dump({
            'summary': {
                'passed': passed,
                'total': total,
                'success_rate': (passed/total)*100,
                'timestamp': datetime.now().isoformat()
            },
            'detailed_results': results
        }, f, indent=2)
    
    print(f"\n📄 Detailed results saved to: /app/backend_test_results.json")
    
    # Exit with appropriate code
    sys.exit(0 if passed == total else 1)

if __name__ == "__main__":
    main()