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
        
        if success and isinstance(analytics_data, list) and len(analytics_data) > 0:
            # Check if we have DL_date fields
            sample_record = analytics_data[0]
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
            self.log_test("DL Date Verification", "FAIL", "Could not retrieve analytics data", error)
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
        
        # Test results tracking
        test_functions = [
            ("Root Endpoint", self.test_root_endpoint),
            ("Refresh Analytics (PRIORITY)", self.test_refresh_analytics),
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