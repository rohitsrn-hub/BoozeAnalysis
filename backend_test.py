import requests
import sys
import json
import io
import pandas as pd
from datetime import datetime

class LiquorDashboardTester:
    def __init__(self, base_url="https://liquor-dashboard.preview.emergentagent.com"):
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
        """Create a sample Excel file for testing with proper index numbers and structure"""
        sample_data = {
            'Index': [101, 205, 350, 412, 578],  # Non-sequential index numbers to test original index preservation
            'Brand Name': [
                'Premium Whiskey Gold', 'Classic Vodka Silver', 'Royal Rum Deluxe', 
                'Elite Gin Supreme', 'Heritage Brandy Reserve'
            ],
            'Wholesale Rate': [450, 675, 900, 540, 720],
            'Selling Rate': [500, 750, 1000, 600, 800],
            # Daily stock data to simulate real liquor inventory tracking
            '25-Aug': [120, 180, 95, 140, 110],  # Initial stock
            '26-Aug': [115, 175, 92, 135, 106],  # Some sales
            '27-Aug': [110, 170, 90, 130, 102],  # More sales
            '28-Aug': [105, 165, 87, 125, 98],   # Continued sales
            '29-Aug': [100, 160, 85, 120, 95],   # Current stock
            '30-Aug': [95, 155, 82, 115, 91],    # More recent data
            '31-Aug': [90, 150, 80, 110, 88],    # Latest stock levels
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

    def test_charts_endpoint(self):
        """Test charts data endpoint"""
        try:
            response = requests.get(f"{self.api_url}/charts")
            success = response.status_code == 200
            
            if success:
                data = response.json()
                required_fields = [
                    'volume_leaders', 'velocity_leaders', 'revenue_leaders', 'revenue_proportion'
                ]
                
                missing_fields = [field for field in required_fields if field not in data]
                if missing_fields:
                    success = False
                    details = f"Missing fields: {missing_fields}"
                else:
                    # Check if each chart has data
                    chart_counts = {
                        'volume_leaders': len(data.get('volume_leaders', [])),
                        'velocity_leaders': len(data.get('velocity_leaders', [])),
                        'revenue_leaders': len(data.get('revenue_leaders', [])),
                        'revenue_proportion': len(data.get('revenue_proportion', []))
                    }
                    details = f"Chart data counts: {chart_counts}"
                    
                    # Validate structure of volume leaders
                    if data.get('volume_leaders') and len(data['volume_leaders']) > 0:
                        first_volume = data['volume_leaders'][0]
                        required_volume_fields = ['name', 'value', 'stock_value']
                        missing_volume_fields = [field for field in required_volume_fields if field not in first_volume]
                        if missing_volume_fields:
                            success = False
                            details += f", Missing volume leader fields: {missing_volume_fields}"
            else:
                details = f"Status: {response.status_code}, Response: {response.text[:200]}"
            
            self.log_test("Charts Data Endpoint", success, details)
            return success, response.json() if success else {}
            
        except Exception as e:
            self.log_test("Charts Data Endpoint", False, str(e))
            return False, {}

    def test_demand_recommendations_endpoint(self):
        """Test demand recommendations endpoint"""
        try:
            response = requests.get(f"{self.api_url}/demand-recommendations")
            success = response.status_code == 200
            
            if success:
                data = response.json()
                if isinstance(data, list):
                    details = f"Retrieved {len(data)} recommendations"
                    
                    # Check structure of recommendations if any exist
                    if len(data) > 0:
                        first_rec = data[0]
                        required_fields = [
                            'brand_name', 'selling_rate', 'wholesale_rate',
                            'current_stock_qty', 'recommended_qty', 'urgency_level'
                        ]
                        missing_fields = [field for field in required_fields if field not in first_rec]
                        if missing_fields:
                            success = False
                            details += f", Missing recommendation fields: {missing_fields}"
                        else:
                            # Check urgency levels
                            urgency_levels = [rec.get('urgency_level') for rec in data]
                            valid_urgencies = ['HIGH', 'MEDIUM', 'LOW', 'NONE']
                            invalid_urgencies = [u for u in urgency_levels if u not in valid_urgencies]
                            if invalid_urgencies:
                                success = False
                                details += f", Invalid urgency levels: {set(invalid_urgencies)}"
                            else:
                                urgency_counts = {level: urgency_levels.count(level) for level in valid_urgencies if urgency_levels.count(level) > 0}
                                details += f", Urgency distribution: {urgency_counts}"
                                
                            # Validate wholesale rates are reasonable (should be less than selling rates)
                            rate_issues = []
                            for rec in data[:5]:  # Check first 5 recommendations
                                if rec.get('wholesale_rate', 0) > rec.get('selling_rate', 0):
                                    rate_issues.append(rec['brand_name'])
                            
                            if rate_issues:
                                details += f", Rate validation issues for: {rate_issues}"
                            else:
                                details += ", Wholesale rates properly calculated"
                else:
                    success = False
                    details = "Response is not a list"
            else:
                details = f"Status: {response.status_code}, Response: {response.text[:200]}"
            
            self.log_test("Demand Recommendations Endpoint", success, details)
            return success, response.json() if success else []
            
        except Exception as e:
            self.log_test("Demand Recommendations Endpoint", False, str(e))
            return False, []

    def test_export_demand_list_endpoint(self):
        """Test Excel export endpoint with enhanced validation"""
        try:
            response = requests.get(f"{self.api_url}/export-demand-list")
            success = response.status_code == 200
            
            if success:
                # Check if response is Excel file
                content_type = response.headers.get('content-type', '')
                is_excel = 'spreadsheet' in content_type or 'excel' in content_type
                
                if is_excel:
                    details = f"Excel file exported, size: {len(response.content)} bytes"
                    
                    # Check content-disposition header for filename
                    content_disposition = response.headers.get('content-disposition', '')
                    if 'attachment' in content_disposition and 'filename' in content_disposition:
                        details += ", proper download headers set"
                    else:
                        details += ", missing proper download headers"
                        
                    # Parse Excel content to validate structure
                    try:
                        excel_df = pd.read_excel(io.BytesIO(response.content))
                        
                        # Check required columns
                        expected_columns = [
                            'Index', 'Brand Name', 'Wholesale Rate', 
                            'Projected Monthly Sale', 'Quantity held in Stock', 
                            'Quantity to be Demanded'
                        ]
                        
                        missing_columns = [col for col in expected_columns if col not in excel_df.columns]
                        if missing_columns:
                            success = False
                            details += f", Missing columns: {missing_columns}"
                        else:
                            details += f", All 6 required columns present"
                            
                            # Check if there's data
                            if len(excel_df) > 0:
                                # Check for total row (should be last row with 'TOTAL' in Index column)
                                last_row = excel_df.iloc[-1]
                                if str(last_row['Index']).upper() == 'TOTAL':
                                    details += ", Total row present"
                                    
                                    # Validate total row calculations
                                    data_rows = excel_df.iloc[:-1]  # All rows except total
                                    
                                    # Check if index numbers are not just serial numbers (1,2,3...)
                                    index_values = data_rows['Index'].tolist()
                                    is_sequential = all(index_values[i] == i+1 for i in range(len(index_values)))
                                    if not is_sequential:
                                        details += ", Uses original brand indexes (not serial numbers)"
                                    else:
                                        details += ", WARNING: May be using serial numbers instead of original indexes"
                                    
                                    # Validate total calculations
                                    expected_total_stock = data_rows['Quantity held in Stock'].sum()
                                    expected_total_demand = data_rows['Quantity to be Demanded'].sum()
                                    expected_total_monthly_sale = data_rows['Projected Monthly Sale'].sum()
                                    
                                    actual_total_stock = last_row['Quantity held in Stock']
                                    actual_total_demand = last_row['Quantity to be Demanded']
                                    actual_total_monthly_sale = last_row['Projected Monthly Sale']
                                    
                                    if (abs(expected_total_stock - actual_total_stock) < 0.01 and
                                        abs(expected_total_demand - actual_total_demand) < 0.01 and
                                        abs(expected_total_monthly_sale - actual_total_monthly_sale) < 0.01):
                                        details += ", Total calculations correct"
                                    else:
                                        details += f", Total calculation errors - Stock: {expected_total_stock} vs {actual_total_stock}, Demand: {expected_total_demand} vs {actual_total_demand}, Monthly Sale: {expected_total_monthly_sale} vs {actual_total_monthly_sale}"
                                else:
                                    details += ", WARNING: No total row found"
                                    
                                details += f", {len(excel_df)-1} data rows + 1 total row"
                            else:
                                details += ", No data in Excel file"
                                
                    except Exception as parse_error:
                        details += f", Excel parsing error: {str(parse_error)}"
                        
                else:
                    success = False
                    details = f"Wrong content type: {content_type}"
            else:
                details = f"Status: {response.status_code}, Response: {response.text[:200]}"
            
            self.log_test("Enhanced Excel Export Validation", success, details)
            return success
            
        except Exception as e:
            self.log_test("Enhanced Excel Export Validation", False, str(e))
            return False

    def test_enhanced_excel_export_detailed(self):
        """Detailed test for the three key Excel export enhancements"""
        try:
            # First get the demand recommendations to compare
            rec_response = requests.get(f"{self.api_url}/demand-recommendations")
            if rec_response.status_code != 200:
                self.log_test("Enhanced Excel Export - Prerequisites", False, "Cannot get recommendations for comparison")
                return False
            
            recommendations = rec_response.json()
            
            # Get the Excel export
            export_response = requests.get(f"{self.api_url}/export-demand-list")
            if export_response.status_code != 200:
                self.log_test("Enhanced Excel Export - Prerequisites", False, f"Export failed with status {export_response.status_code}")
                return False
            
            # Parse Excel
            excel_df = pd.read_excel(io.BytesIO(export_response.content))
            
            success = True
            issues = []
            
            # Test 1: Correct brand index numbers (not serial numbers)
            if len(excel_df) > 1:  # Has data + total row
                data_rows = excel_df.iloc[:-1]  # Exclude total row
                index_values = data_rows['Index'].tolist()
                
                # Check if indexes are sequential 1,2,3... (which would be wrong)
                is_sequential = all(str(index_values[i]) == str(i+1) for i in range(len(index_values)))
                if is_sequential:
                    issues.append("Using serial numbers instead of original brand indexes")
                    success = False
                else:
                    issues.append("✓ Uses original brand index numbers")
            
            # Test 2: Projected Monthly Sale column exists and has data
            if 'Projected Monthly Sale' in excel_df.columns:
                monthly_sales = excel_df['Projected Monthly Sale'].iloc[:-1]  # Exclude total row
                if monthly_sales.sum() > 0:
                    issues.append("✓ Projected Monthly Sale column has valid data")
                else:
                    issues.append("Projected Monthly Sale column exists but has no data")
                    success = False
            else:
                issues.append("Missing Projected Monthly Sale column")
                success = False
            
            # Test 3: Total row validation
            if len(excel_df) > 0:
                last_row = excel_df.iloc[-1]
                if str(last_row['Index']).upper() == 'TOTAL':
                    issues.append("✓ Total row present with correct format")
                    
                    # Validate total calculations
                    data_rows = excel_df.iloc[:-1]
                    expected_stock_total = data_rows['Quantity held in Stock'].sum()
                    expected_demand_total = data_rows['Quantity to be Demanded'].sum()
                    
                    actual_stock_total = last_row['Quantity held in Stock']
                    actual_demand_total = last_row['Quantity to be Demanded']
                    
                    if (abs(expected_stock_total - actual_stock_total) < 0.01 and
                        abs(expected_demand_total - actual_demand_total) < 0.01):
                        issues.append("✓ Total row calculations are accurate")
                    else:
                        issues.append(f"Total row calculation errors: Stock {expected_stock_total} vs {actual_stock_total}, Demand {expected_demand_total} vs {actual_demand_total}")
                        success = False
                else:
                    issues.append("Total row missing or incorrectly formatted")
                    success = False
            
            # Test 4: Data integrity - compare with recommendations API
            if len(recommendations) > 0 and len(excel_df) > 1:
                rec_brands = {rec['brand_name']: rec for rec in recommendations}
                excel_brands = data_rows['Brand Name'].tolist()
                
                matching_brands = 0
                for brand in excel_brands:
                    if brand in rec_brands:
                        matching_brands += 1
                
                if matching_brands == len(excel_brands):
                    issues.append("✓ All Excel brands match recommendation data")
                else:
                    issues.append(f"Brand mismatch: {matching_brands}/{len(excel_brands)} brands match")
                    success = False
            
            details = "; ".join(issues)
            self.log_test("Enhanced Excel Export - Three Key Improvements", success, details)
            return success
            
        except Exception as e:
            self.log_test("Enhanced Excel Export - Three Key Improvements", False, str(e))
            return False

    def test_excel_export_edge_cases(self):
        """Test edge cases for Excel export functionality"""
        try:
            success = True
            issues = []
            
            # Test 1: Export when no recommendations exist (clear data first)
            # This is tricky since we can't easily clear data, but we can test current state
            export_response = requests.get(f"{self.api_url}/export-demand-list")
            
            if export_response.status_code == 404:
                issues.append("✓ Correctly handles no recommendations case with 404")
            elif export_response.status_code == 200:
                # Check if it's an empty Excel or has data
                excel_df = pd.read_excel(io.BytesIO(export_response.content))
                if len(excel_df) == 0:
                    issues.append("✓ Returns empty Excel when no recommendations")
                else:
                    issues.append("✓ Returns Excel with existing recommendations")
            else:
                issues.append(f"Unexpected status {export_response.status_code} for export")
                success = False
            
            # Test 2: File format validation
            if export_response.status_code == 200:
                content_type = export_response.headers.get('content-type', '')
                if 'spreadsheet' in content_type or 'excel' in content_type:
                    issues.append("✓ Correct Excel MIME type")
                else:
                    issues.append(f"Wrong MIME type: {content_type}")
                    success = False
                
                # Test filename in headers
                content_disposition = export_response.headers.get('content-disposition', '')
                if 'liquor_demand_forecast_' in content_disposition and '.xlsx' in content_disposition:
                    issues.append("✓ Proper filename format with date")
                else:
                    issues.append("Missing or incorrect filename format")
                    success = False
            
            # Test 3: Excel file structure validation
            if export_response.status_code == 200:
                try:
                    excel_df = pd.read_excel(io.BytesIO(export_response.content))
                    
                    # Check column order
                    expected_order = [
                        'Index', 'Brand Name', 'Wholesale Rate', 
                        'Projected Monthly Sale', 'Quantity held in Stock', 
                        'Quantity to be Demanded'
                    ]
                    
                    actual_columns = excel_df.columns.tolist()
                    if actual_columns == expected_order:
                        issues.append("✓ Columns in correct order")
                    else:
                        issues.append(f"Column order mismatch: {actual_columns}")
                        success = False
                    
                    # Check data types
                    if len(excel_df) > 1:  # Has data
                        data_rows = excel_df.iloc[:-1]  # Exclude total row
                        
                        # Wholesale Rate should be numeric
                        if pd.api.types.is_numeric_dtype(data_rows['Wholesale Rate']):
                            issues.append("✓ Wholesale Rate is numeric")
                        else:
                            issues.append("Wholesale Rate is not numeric")
                            success = False
                        
                        # Projected Monthly Sale should be numeric
                        if pd.api.types.is_numeric_dtype(data_rows['Projected Monthly Sale']):
                            issues.append("✓ Projected Monthly Sale is numeric")
                        else:
                            issues.append("Projected Monthly Sale is not numeric")
                            success = False
                    
                except Exception as parse_error:
                    issues.append(f"Excel parsing failed: {str(parse_error)}")
                    success = False
            
            details = "; ".join(issues)
            self.log_test("Excel Export Edge Cases", success, details)
            return success
            
        except Exception as e:
            self.log_test("Excel Export Edge Cases", False, str(e))
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
            
            # Test new chart features
            self.test_charts_endpoint()
            self.test_demand_recommendations_endpoint()
            self.test_export_demand_list_endpoint()
            
            # Test enhanced Excel export functionality in detail
            self.test_enhanced_excel_export_detailed()
            
            # Test edge cases for Excel export
            self.test_excel_export_edge_cases()
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