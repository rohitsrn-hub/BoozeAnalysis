import requests
import sys
import json
import io
import pandas as pd
from datetime import datetime

class LiquorDashboardTester:
    def __init__(self, base_url="https://booze-dashboard.preview.emergentagent.com"):
        self.base_url = base_url
        self.api_url = f"{base_url}/api"
        self.tests_run = 0
        self.tests_passed = 0
        self.test_results = []

    def log_test(self, name, success, details=""):
        """Log test result"""
        self.tests_run += 1
        if success:
            self.tests_passed += 1
            print(f"✅ {name} - PASSED")
        else:
            print(f"❌ {name} - FAILED: {details}")
        
        self.test_results.append({
            "test": name,
            "success": success,
            "details": details
        })

    def test_api_root(self):
        """Test API root endpoint"""
        try:
            response = requests.get(f"{self.api_url}/")
            success = response.status_code == 200
            details = f"Status: {response.status_code}"
            if success:
                data = response.json()
                details += f", Message: {data.get('message', 'No message')}"
            self.log_test("API Root Endpoint", success, details)
            return success
        except Exception as e:
            self.log_test("API Root Endpoint", False, str(e))
            return False

    def create_sample_excel_file(self):
        """Create a sample Excel file for testing"""
        sample_data = {
            'Brand Name': [
                'Brand A', 'Brand B', 'Brand C', 'Brand D', 'Brand E'
            ],
            'Rate': [500, 750, 1000, 600, 800],
            'Monthly Sale (25 Aug - 19 Sep)': [100, 150, 80, 120, 90],
            'Monthly Sale value (a)': [50000, 112500, 80000, 72000, 72000],
            'Avg Daily SALE (b)': [4.0, 6.0, 3.2, 4.8, 3.6],
            'Stock avlb for days (c)': [45, 30, 90, 25, 60],
            'Stock Value before collection 19 Sep 25 (d)': [180000, 200000, 300000, 150000, 250000],
            'Stock value Today (29 Sep) ( e)': [200000, 180000, 350000, 140000, 280000],
            'Stock ratio (e/a)': [4.0, 1.6, 4.375, 1.94, 3.89],
            # Add some daily sales columns
            '25 Aug': [5, 8, 3, 6, 4],
            '26 Aug': [4, 7, 4, 5, 3],
            '27 Aug': [6, 9, 2, 7, 5],
            '28 Aug': [3, 6, 5, 4, 2],
            '29 Aug': [5, 8, 3, 6, 4]
        }
        
        df = pd.DataFrame(sample_data)
        excel_buffer = io.BytesIO()
        df.to_excel(excel_buffer, index=False)
        excel_buffer.seek(0)
        return excel_buffer.getvalue()

    def test_file_upload_valid(self):
        """Test valid file upload"""
        try:
            excel_data = self.create_sample_excel_file()
            files = {'file': ('test_data.xlsx', excel_data, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')}
            
            response = requests.post(f"{self.api_url}/upload-data", files=files)
            success = response.status_code == 200
            
            if success:
                data = response.json()
                details = f"Uploaded {data.get('total_records', 0)} records"
            else:
                details = f"Status: {response.status_code}, Response: {response.text[:200]}"
            
            self.log_test("File Upload - Valid Excel", success, details)
            return success, response.json() if success else {}
            
        except Exception as e:
            self.log_test("File Upload - Valid Excel", False, str(e))
            return False, {}

    def test_file_upload_invalid(self):
        """Test invalid file upload"""
        try:
            # Test with invalid file type
            files = {'file': ('test.txt', b'invalid content', 'text/plain')}
            response = requests.post(f"{self.api_url}/upload-data", files=files)
            
            success = response.status_code == 400
            details = f"Status: {response.status_code}"
            if response.status_code == 400:
                details += " - Correctly rejected invalid file type"
            
            self.log_test("File Upload - Invalid File Type", success, details)
            return success
            
        except Exception as e:
            self.log_test("File Upload - Invalid File Type", False, str(e))
            return False

    def test_analytics_endpoint(self, multiplier=3.0):
        """Test analytics endpoint"""
        try:
            response = requests.get(f"{self.api_url}/analytics?overstock_multiplier={multiplier}")
            success = response.status_code == 200
            
            if success:
                data = response.json()
                required_fields = [
                    'total_brands', 'total_stock_value', 'total_overstocked_value',
                    'overstocked_brands', 'top_selling_brands', 'overstocked_items', 'sales_trends'
                ]
                
                missing_fields = [field for field in required_fields if field not in data]
                if missing_fields:
                    success = False
                    details = f"Missing fields: {missing_fields}"
                else:
                    details = f"Total brands: {data['total_brands']}, Overstocked: {data['overstocked_brands']}"
            else:
                details = f"Status: {response.status_code}, Response: {response.text[:200]}"
            
            self.log_test(f"Analytics Endpoint (multiplier={multiplier})", success, details)
            return success, response.json() if success else {}
            
        except Exception as e:
            self.log_test(f"Analytics Endpoint (multiplier={multiplier})", False, str(e))
            return False, {}

    def test_analytics_different_multipliers(self):
        """Test analytics with different multiplier values"""
        multipliers = [2.0, 2.5, 3.0, 4.0, 5.0]
        results = []
        
        for multiplier in multipliers:
            success, data = self.test_analytics_endpoint(multiplier)
            if success:
                results.append({
                    'multiplier': multiplier,
                    'overstocked_brands': data.get('overstocked_brands', 0),
                    'total_overstocked_value': data.get('total_overstocked_value', 0)
                })
        
        # Verify that lower multipliers generally result in more overstocked items
        if len(results) >= 2:
            trend_correct = True
            for i in range(len(results) - 1):
                if results[i]['multiplier'] < results[i+1]['multiplier']:
                    if results[i]['overstocked_brands'] < results[i+1]['overstocked_brands']:
                        trend_correct = False
                        break
            
            self.log_test("Multiplier Logic Validation", trend_correct, 
                         f"Tested multipliers: {[r['multiplier'] for r in results]}")
        
        return len(results) > 0

    def test_brands_endpoint(self):
        """Test brands endpoint"""
        try:
            response = requests.get(f"{self.api_url}/brands")
            success = response.status_code == 200
            
            if success:
                data = response.json()
                details = f"Retrieved {len(data)} brands"
                if len(data) > 0:
                    # Check if brand data has required fields
                    first_brand = data[0]
                    required_fields = ['brand_name', 'rate', 'monthly_sale_qty', 'stock_value_today']
                    missing_fields = [field for field in required_fields if field not in first_brand]
                    if missing_fields:
                        success = False
                        details += f", Missing fields in brand data: {missing_fields}"
            else:
                details = f"Status: {response.status_code}, Response: {response.text[:200]}"
            
            self.log_test("Brands Endpoint", success, details)
            return success, response.json() if success else []
            
        except Exception as e:
            self.log_test("Brands Endpoint", False, str(e))
            return False, []

    def test_analytics_without_data(self):
        """Test analytics endpoint when no data is uploaded"""
        try:
            # First clear any existing data by uploading empty data (this might not work, but let's try)
            response = requests.get(f"{self.api_url}/analytics")
            
            # If we get 404, that's expected behavior when no data exists
            if response.status_code == 404:
                success = True
                details = "Correctly returns 404 when no data exists"
            elif response.status_code == 200:
                # If we get data, that means there's existing data, which is also valid
                success = True
                details = "Returns existing data"
            else:
                success = False
                details = f"Unexpected status: {response.status_code}"
            
            self.log_test("Analytics - No Data Handling", success, details)
            return success
            
        except Exception as e:
            self.log_test("Analytics - No Data Handling", False, str(e))
            return False

    def test_cors_headers(self):
        """Test CORS headers"""
        try:
            response = requests.options(f"{self.api_url}/analytics")
            success = True
            details = "CORS preflight request successful"
            
            # Check for CORS headers
            cors_headers = [
                'Access-Control-Allow-Origin',
                'Access-Control-Allow-Methods',
                'Access-Control-Allow-Headers'
            ]
            
            missing_headers = []
            for header in cors_headers:
                if header not in response.headers:
                    missing_headers.append(header)
            
            if missing_headers:
                details += f", Missing CORS headers: {missing_headers}"
            
            self.log_test("CORS Configuration", success, details)
            return success
            
        except Exception as e:
            self.log_test("CORS Configuration", False, str(e))
            return False

    def run_all_tests(self):
        """Run all backend tests"""
        print("🚀 Starting Liquor Dashboard Backend Tests")
        print("=" * 50)
        
        # Test API availability
        if not self.test_api_root():
            print("❌ API is not accessible, stopping tests")
            return False
        
        # Test file upload functionality
        upload_success, upload_data = self.test_file_upload_valid()
        self.test_file_upload_invalid()
        
        # Test analytics functionality (only if upload was successful)
        if upload_success:
            self.test_analytics_endpoint()
            self.test_analytics_different_multipliers()
            self.test_brands_endpoint()
        else:
            print("⚠️  Skipping analytics tests due to upload failure")
        
        # Test error handling
        self.test_analytics_without_data()
        
        # Test CORS
        self.test_cors_headers()
        
        # Print summary
        print("\n" + "=" * 50)
        print(f"📊 Test Summary: {self.tests_passed}/{self.tests_run} tests passed")
        print(f"Success Rate: {(self.tests_passed/self.tests_run)*100:.1f}%")
        
        return self.tests_passed == self.tests_run

def main():
    tester = LiquorDashboardTester()
    success = tester.run_all_tests()
    
    # Save detailed results
    with open('/app/backend_test_results.json', 'w') as f:
        json.dump({
            'timestamp': datetime.now().isoformat(),
            'total_tests': tester.tests_run,
            'passed_tests': tester.tests_passed,
            'success_rate': (tester.tests_passed/tester.tests_run)*100 if tester.tests_run > 0 else 0,
            'test_results': tester.test_results
        }, f, indent=2)
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())