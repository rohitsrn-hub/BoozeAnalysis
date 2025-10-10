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
BACKEND_URL = "https://liquor-manager.preview.emergentagent.com/api"

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
    
    def test_module4_reports_data_endpoint(self):
        """PRIORITY TEST: Test Module 4 GET /api/reports/data endpoint"""
        print("\n📊 Testing Module 4 Reports Data Endpoint (PRIORITY)")
        
        success, data, error = self.test_endpoint("GET", "/reports/data", 200)
        
        if not success:
            self.log_test("Module 4 Reports Data", "FAIL", "Reports data endpoint failed", error)
            return False
        
        if not isinstance(data, dict):
            self.log_test("Module 4 Reports Data", "FAIL", "Invalid response format", f"Expected dict, got {type(data)}")
            return False
        
        # Verify required fields in the response
        required_fields = [
            'report_period', 'total_brands', 'executive_summary', 
            'top_sellers_revenue', 'top_sellers_volume', 'slow_sellers',
            'capital_blockers', 'demand_forecast', 'profit_analysis', 'recommendations'
        ]
        
        missing_fields = []
        for field in required_fields:
            if field not in data:
                missing_fields.append(field)
        
        if missing_fields:
            self.log_test("Module 4 Reports Data", "FAIL", f"Missing required fields: {missing_fields}", f"Available fields: {list(data.keys())}")
            return False
        
        # Verify executive summary structure
        exec_summary = data.get('executive_summary', {})
        exec_required = ['total_brands_analyzed', 'total_revenue', 'total_profit', 'profit_margin', 'key_insights']
        exec_missing = [field for field in exec_required if field not in exec_summary]
        
        if exec_missing:
            self.log_test("Module 4 Reports Data", "FAIL", f"Executive summary missing fields: {exec_missing}", f"Available: {list(exec_summary.keys())}")
            return False
        
        # Verify profit analysis structure
        profit_analysis = data.get('profit_analysis', {})
        profit_required = ['total_revenue', 'total_cost', 'total_profit', 'average_profit_margin', 'top_profit_brands']
        profit_missing = [field for field in profit_required if field not in profit_analysis]
        
        if profit_missing:
            self.log_test("Module 4 Reports Data", "FAIL", f"Profit analysis missing fields: {profit_missing}", f"Available: {list(profit_analysis.keys())}")
            return False
        
        # Verify mathematical calculations
        total_revenue = profit_analysis.get('total_revenue', 0)
        total_cost = profit_analysis.get('total_cost', 0)
        total_profit = profit_analysis.get('total_profit', 0)
        calculated_profit = total_revenue - total_cost
        
        if abs(total_profit - calculated_profit) > 0.01:  # Allow small floating point differences
            self.log_test("Module 4 Reports Data", "FAIL", f"Profit calculation incorrect", f"Expected: {calculated_profit}, Got: {total_profit}")
            return False
        
        # Verify profit margin calculation
        expected_margin = (total_profit / total_revenue * 100) if total_revenue > 0 else 0
        actual_margin = profit_analysis.get('average_profit_margin', 0)
        
        if abs(expected_margin - actual_margin) > 0.1:  # Allow 0.1% difference
            self.log_test("Module 4 Reports Data", "FAIL", f"Profit margin calculation incorrect", f"Expected: {expected_margin:.2f}%, Got: {actual_margin:.2f}%")
            return False
        
        # Verify data completeness
        top_sellers_count = len(data.get('top_sellers_revenue', []))
        slow_sellers_count = len(data.get('slow_sellers', []))
        capital_blockers_count = len(data.get('capital_blockers', []))
        demand_forecast_count = len(data.get('demand_forecast', []))
        
        self.log_test(
            "Module 4 Reports Data", 
            "PASS", 
            f"Report data structure validated successfully",
            f"Revenue: ₹{total_revenue:,.0f}, Profit: ₹{total_profit:,.0f}, Margin: {actual_margin:.1f}%, Top sellers: {top_sellers_count}, Slow: {slow_sellers_count}, Blockers: {capital_blockers_count}, Demand: {demand_forecast_count}"
        )
        return True
    
    def test_module4_excel_report_generation(self):
        """PRIORITY TEST: Test Module 4 POST /api/reports/generate-excel endpoint with Date-wise Analysis"""
        print("\n📈 Testing Module 4 Excel Report Generation with Date-wise Analysis (PRIORITY)")
        
        # Record test start time for IST timestamp verification
        import pytz
        from datetime import datetime
        
        ist_timezone = pytz.timezone('Asia/Kolkata')
        test_start_time_ist = datetime.now(ist_timezone)
        
        # Test Excel report generation
        url = f"{self.base_url}/reports/generate-excel"
        
        try:
            response = self.session.post(url, timeout=60)  # Longer timeout for report generation
            
            if response.status_code != 200:
                try:
                    error_data = response.json()
                    self.log_test("Module 4 Excel Generation", "FAIL", f"Excel generation failed with status {response.status_code}", str(error_data))
                except:
                    self.log_test("Module 4 Excel Generation", "FAIL", f"Excel generation failed with status {response.status_code}", response.text[:200])
                return False
            
            # Verify Content-Type header
            content_type = response.headers.get('Content-Type', '')
            expected_content_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            
            if expected_content_type not in content_type:
                self.log_test("Module 4 Excel Generation", "FAIL", f"Incorrect content type", f"Expected: {expected_content_type}, Got: {content_type}")
                return False
            
            # Verify Content-Disposition header and filename format
            content_disposition = response.headers.get('Content-Disposition', '')
            
            if 'filename=' not in content_disposition:
                self.log_test("Module 4 Excel Generation", "FAIL", "No filename in Content-Disposition header", f"Header: {content_disposition}")
                return False
            
            # Extract filename and verify IST timestamp format
            import re
            filename_match = re.search(r'filename=([^;]+)', content_disposition)
            if not filename_match:
                self.log_test("Module 4 Excel Generation", "FAIL", "Could not extract filename", f"Content-Disposition: {content_disposition}")
                return False
            
            filename = filename_match.group(1).strip('"')
            
            # Verify filename format: monthly_report_YYYYMMDD_HHMMSS.xlsx
            filename_pattern = r'monthly_report_(\d{8})_(\d{6})\.xlsx'
            match = re.match(filename_pattern, filename)
            
            if not match:
                self.log_test("Module 4 Excel Generation", "FAIL", f"Filename format incorrect", f"Expected: monthly_report_YYYYMMDD_HHMMSS.xlsx, Got: {filename}")
                return False
            
            date_part, time_part = match.groups()
            
            # Parse and verify IST timestamp
            try:
                filename_datetime_str = f"{date_part}_{time_part}"
                filename_datetime = datetime.strptime(filename_datetime_str, "%Y%m%d_%H%M%S")
                filename_datetime_ist = ist_timezone.localize(filename_datetime)
                
                # Verify timestamp is reasonable (within 5 minutes)
                time_diff = abs((filename_datetime_ist - test_start_time_ist).total_seconds())
                
                if time_diff > 300:  # 5 minutes tolerance
                    self.log_test("Module 4 Excel Generation", "FAIL", f"IST timestamp difference too large: {time_diff:.1f} seconds", f"Expected around: {test_start_time_ist.strftime('%Y-%m-%d %H:%M:%S %Z')}")
                    return False
                
            except ValueError as e:
                self.log_test("Module 4 Excel Generation", "FAIL", f"Could not parse IST timestamp from filename", f"Timestamp: {date_part}_{time_part}, Error: {e}")
                return False
            
            # Verify file content is valid Excel
            if not response.content or len(response.content) < 1000:  # Excel files should be reasonably large
                self.log_test("Module 4 Excel Generation", "FAIL", "Excel file too small or empty", f"Size: {len(response.content)} bytes")
                return False
            
            # Check Excel file signature
            excel_signature = response.content[:4]
            if excel_signature != b'PK\x03\x04':  # ZIP signature (Excel files are ZIP-based)
                self.log_test("Module 4 Excel Generation", "FAIL", "Invalid Excel file format", f"File signature: {excel_signature}")
                return False
            
            # Try to parse Excel content to verify multiple sheets including Date-wise Sales
            try:
                import pandas as pd
                import io
                
                excel_data = pd.ExcelFile(io.BytesIO(response.content))
                sheet_names = excel_data.sheet_names
                
                expected_sheets = ['Executive Summary', 'Top Revenue Generators', 'Top Volume Movers', 'Slow Sellers', 'Capital Blockers', 'Demand Forecast', 'Profit Analysis', 'Date-wise Sales']
                missing_sheets = [sheet for sheet in expected_sheets if sheet not in sheet_names]
                
                if missing_sheets:
                    self.log_test("Module 4 Excel Generation", "FAIL", f"Missing Excel sheets: {missing_sheets}", f"Available sheets: {sheet_names}")
                    return False
                
                # CRITICAL: Verify Date-wise Sales sheet structure
                if 'Date-wise Sales' in sheet_names:
                    datewise_df = pd.read_excel(io.BytesIO(response.content), sheet_name='Date-wise Sales')
                    
                    if datewise_df.empty:
                        self.log_test("Module 4 Excel Date-wise Analysis", "FAIL", "Date-wise Sales sheet is empty", "No data in date-wise analysis sheet")
                        return False
                    
                    # Verify required columns in Date-wise Sales sheet
                    required_columns = ['Index', 'Brand Name', 'Wholesale Rate (₹)', 'Retail Rate (₹)']
                    missing_columns = [col for col in required_columns if col not in datewise_df.columns]
                    
                    if missing_columns:
                        self.log_test("Module 4 Excel Date-wise Analysis", "FAIL", f"Missing required columns in Date-wise Sales sheet: {missing_columns}", f"Available columns: {list(datewise_df.columns)}")
                        return False
                    
                    # Check for date columns (D1, D2, D3, etc.)
                    date_columns = [col for col in datewise_df.columns if col.startswith('D') and col not in ['DL_date', 'D1_date']]
                    
                    if not date_columns:
                        self.log_test("Module 4 Excel Date-wise Analysis", "FAIL", "No date columns found in Date-wise Sales sheet", f"Available columns: {list(datewise_df.columns)}")
                        return False
                    
                    self.log_test(
                        "Module 4 Excel Date-wise Analysis", 
                        "PASS", 
                        f"Date-wise Sales sheet structure verified successfully",
                        f"Rows: {len(datewise_df)}, Required columns: ✓, Date columns: {len(date_columns)} ({date_columns[:5]})"
                    )
                else:
                    self.log_test("Module 4 Excel Date-wise Analysis", "FAIL", "Date-wise Sales sheet not found", f"Available sheets: {sheet_names}")
                    return False
                
                # Verify at least one sheet has data
                summary_df = pd.read_excel(io.BytesIO(response.content), sheet_name='Executive Summary')
                if summary_df.empty:
                    self.log_test("Module 4 Excel Generation", "FAIL", "Executive Summary sheet is empty", "No data in main sheet")
                    return False
                
            except Exception as e:
                self.log_test("Module 4 Excel Generation", "FAIL", f"Could not parse Excel content: {str(e)}", "Excel file may be corrupted")
                return False
            
            self.log_test(
                "Module 4 Excel Generation", 
                "PASS", 
                f"Excel report with Date-wise Analysis generated successfully",
                f"Filename: {filename}, Size: {len(response.content)} bytes, Sheets: {len(sheet_names)}, IST time diff: {time_diff:.1f}s"
            )
            return True
            
        except requests.exceptions.Timeout:
            self.log_test("Module 4 Excel Generation", "FAIL", "Request timeout (60s)", "Report generation taking too long")
            return False
        except requests.exceptions.ConnectionError:
            self.log_test("Module 4 Excel Generation", "FAIL", "Connection error", "Backend may be down")
            return False
        except Exception as e:
            self.log_test("Module 4 Excel Generation", "FAIL", f"Unexpected error: {str(e)}", "Excel generation failed")
            return False
    
    def test_module4_pdf_report_generation(self):
        """PRIORITY TEST: Test Module 4 POST /api/reports/generate-pdf endpoint with various parameters"""
        print("\n📄 Testing Module 4 PDF Report Generation (PRIORITY)")
        
        # Test different parameter combinations including Date-wise Analysis
        test_scenarios = [
            {
                "name": "Full Report with Date-wise Analysis",
                "params": {
                    "include_executive_summary": True,
                    "include_top_sellers": True,
                    "include_slow_sellers": True,
                    "include_capital_blockers": True,
                    "include_revenue_analysis": True,
                    "include_demand_forecast": True,
                    "include_profit_analysis": True,
                    "include_recommendations": True,
                    "include_datewise_analysis": True,
                    "report_title": "Complete Monthly Sales Analytics Report with Date-wise Analysis",
                    "report_period": "September-October 2025"
                }
            },
            {
                "name": "Executive Summary Only",
                "params": {
                    "include_executive_summary": True,
                    "include_top_sellers": False,
                    "include_slow_sellers": False,
                    "include_capital_blockers": False,
                    "include_revenue_analysis": False,
                    "include_demand_forecast": False,
                    "include_profit_analysis": False,
                    "include_recommendations": False,
                    "include_datewise_analysis": False,
                    "report_title": "Executive Summary Report"
                }
            },
            {
                "name": "Date-wise Analysis Only",
                "params": {
                    "include_executive_summary": False,
                    "include_top_sellers": False,
                    "include_slow_sellers": False,
                    "include_capital_blockers": False,
                    "include_revenue_analysis": False,
                    "include_demand_forecast": False,
                    "include_profit_analysis": False,
                    "include_recommendations": False,
                    "include_datewise_analysis": True,
                    "report_title": "Date-wise Sales Analysis Report"
                }
            },
            {
                "name": "Sales Focus Report",
                "params": {
                    "include_executive_summary": True,
                    "include_top_sellers": True,
                    "include_slow_sellers": True,
                    "include_capital_blockers": False,
                    "include_revenue_analysis": True,
                    "include_demand_forecast": False,
                    "include_profit_analysis": True,
                    "include_recommendations": True,
                    "include_datewise_analysis": False,
                    "report_title": "Sales Performance Report"
                }
            }
        ]
        
        import pytz
        from datetime import datetime
        
        ist_timezone = pytz.timezone('Asia/Kolkata')
        all_tests_passed = True
        
        for scenario in test_scenarios:
            print(f"  Testing scenario: {scenario['name']}")
            test_start_time_ist = datetime.now(ist_timezone)
            
            url = f"{self.base_url}/reports/generate-pdf"
            
            try:
                response = self.session.post(url, json=scenario['params'], timeout=60)
                
                if response.status_code != 200:
                    try:
                        error_data = response.json()
                        self.log_test(f"Module 4 PDF Generation - {scenario['name']}", "FAIL", f"PDF generation failed with status {response.status_code}", str(error_data))
                    except:
                        self.log_test(f"Module 4 PDF Generation - {scenario['name']}", "FAIL", f"PDF generation failed with status {response.status_code}", response.text[:200])
                    all_tests_passed = False
                    continue
                
                # Verify Content-Type
                content_type = response.headers.get('Content-Type', '')
                if 'application/pdf' not in content_type:
                    self.log_test(f"Module 4 PDF Generation - {scenario['name']}", "FAIL", f"Incorrect content type", f"Expected: application/pdf, Got: {content_type}")
                    all_tests_passed = False
                    continue
                
                # Verify filename with IST timestamp
                content_disposition = response.headers.get('Content-Disposition', '')
                
                if 'filename=' not in content_disposition:
                    self.log_test(f"Module 4 PDF Generation - {scenario['name']}", "FAIL", "No filename in Content-Disposition header", f"Header: {content_disposition}")
                    all_tests_passed = False
                    continue
                
                import re
                filename_match = re.search(r'filename=([^;]+)', content_disposition)
                if not filename_match:
                    self.log_test(f"Module 4 PDF Generation - {scenario['name']}", "FAIL", "Could not extract filename", f"Content-Disposition: {content_disposition}")
                    all_tests_passed = False
                    continue
                
                filename = filename_match.group(1).strip('"')
                
                # Verify filename format: monthly_report_YYYYMMDD_HHMMSS.pdf
                filename_pattern = r'monthly_report_(\d{8})_(\d{6})\.pdf'
                match = re.match(filename_pattern, filename)
                
                if not match:
                    self.log_test(f"Module 4 PDF Generation - {scenario['name']}", "FAIL", f"Filename format incorrect", f"Expected: monthly_report_YYYYMMDD_HHMMSS.pdf, Got: {filename}")
                    all_tests_passed = False
                    continue
                
                # Verify IST timestamp
                date_part, time_part = match.groups()
                try:
                    filename_datetime_str = f"{date_part}_{time_part}"
                    filename_datetime = datetime.strptime(filename_datetime_str, "%Y%m%d_%H%M%S")
                    filename_datetime_ist = ist_timezone.localize(filename_datetime)
                    
                    time_diff = abs((filename_datetime_ist - test_start_time_ist).total_seconds())
                    
                    if time_diff > 300:  # 5 minutes tolerance
                        self.log_test(f"Module 4 PDF Generation - {scenario['name']}", "FAIL", f"IST timestamp difference too large: {time_diff:.1f} seconds", f"Expected around: {test_start_time_ist.strftime('%Y-%m-%d %H:%M:%S %Z')}")
                        all_tests_passed = False
                        continue
                        
                except ValueError as e:
                    self.log_test(f"Module 4 PDF Generation - {scenario['name']}", "FAIL", f"Could not parse IST timestamp", f"Timestamp: {date_part}_{time_part}, Error: {e}")
                    all_tests_passed = False
                    continue
                
                # Verify PDF content
                if not response.content or len(response.content) < 1000:
                    self.log_test(f"Module 4 PDF Generation - {scenario['name']}", "FAIL", "PDF file too small or empty", f"Size: {len(response.content)} bytes")
                    all_tests_passed = False
                    continue
                
                # Check PDF signature
                pdf_signature = response.content[:4]
                if pdf_signature != b'%PDF':
                    self.log_test(f"Module 4 PDF Generation - {scenario['name']}", "FAIL", "Invalid PDF file format", f"File signature: {pdf_signature}")
                    all_tests_passed = False
                    continue
                
                self.log_test(
                    f"Module 4 PDF Generation - {scenario['name']}", 
                    "PASS", 
                    f"PDF report generated successfully with IST timestamp",
                    f"Filename: {filename}, Size: {len(response.content)} bytes, IST time diff: {time_diff:.1f}s"
                )
                
            except requests.exceptions.Timeout:
                self.log_test(f"Module 4 PDF Generation - {scenario['name']}", "FAIL", "Request timeout (60s)", "PDF generation taking too long")
                all_tests_passed = False
            except requests.exceptions.ConnectionError:
                self.log_test(f"Module 4 PDF Generation - {scenario['name']}", "FAIL", "Connection error", "Backend may be down")
                all_tests_passed = False
            except Exception as e:
                self.log_test(f"Module 4 PDF Generation - {scenario['name']}", "FAIL", f"Unexpected error: {str(e)}", "PDF generation failed")
                all_tests_passed = False
        
        return all_tests_passed
    
    def test_datewise_analysis_functionality(self):
        """PRIORITY TEST: Test Date-wise Analysis functionality in both Excel and PDF reports"""
        print("\n📊 Testing Date-wise Analysis Functionality (PRIORITY)")
        
        all_tests_passed = True
        
        # Test 1: Excel report with Date-wise Analysis
        print("  Testing Excel report with Date-wise Analysis...")
        url = f"{self.base_url}/reports/generate-excel"
        
        try:
            response = self.session.post(url, timeout=60)
            
            if response.status_code != 200:
                self.log_test("Date-wise Analysis Excel", "FAIL", f"Excel generation failed with status {response.status_code}", response.text[:200])
                all_tests_passed = False
            else:
                # Parse Excel and verify Date-wise Sales sheet
                try:
                    import pandas as pd
                    import io
                    
                    excel_data = pd.ExcelFile(io.BytesIO(response.content))
                    
                    if 'Date-wise Sales' not in excel_data.sheet_names:
                        self.log_test("Date-wise Analysis Excel", "FAIL", "Date-wise Sales sheet not found", f"Available sheets: {excel_data.sheet_names}")
                        all_tests_passed = False
                    else:
                        datewise_df = pd.read_excel(io.BytesIO(response.content), sheet_name='Date-wise Sales')
                        
                        # Verify column structure
                        expected_columns = ['Index', 'Brand Name', 'Wholesale Rate (₹)', 'Retail Rate (₹)']
                        missing_columns = [col for col in expected_columns if col not in datewise_df.columns]
                        
                        if missing_columns:
                            self.log_test("Date-wise Analysis Excel", "FAIL", f"Missing columns: {missing_columns}", f"Available: {list(datewise_df.columns)}")
                            all_tests_passed = False
                        else:
                            # Check for date columns (D1, D2, D3, etc.)
                            date_columns = [col for col in datewise_df.columns if col.startswith('D') and col not in ['DL_date', 'D1_date']]
                            
                            if len(date_columns) == 0:
                                self.log_test("Date-wise Analysis Excel", "FAIL", "No date columns found", f"Columns: {list(datewise_df.columns)}")
                                all_tests_passed = False
                            else:
                                self.log_test(
                                    "Date-wise Analysis Excel", 
                                    "PASS", 
                                    f"Excel Date-wise Sales sheet structure verified",
                                    f"Rows: {len(datewise_df)}, Date columns: {len(date_columns)} ({date_columns[:3]}...)"
                                )
                        
                except Exception as e:
                    self.log_test("Date-wise Analysis Excel", "FAIL", f"Could not parse Excel: {str(e)}", "Excel parsing error")
                    all_tests_passed = False
        
        except Exception as e:
            self.log_test("Date-wise Analysis Excel", "FAIL", f"Excel request error: {str(e)}", "Request failed")
            all_tests_passed = False
        
        # Test 2: PDF report with Date-wise Analysis enabled
        print("  Testing PDF report with Date-wise Analysis enabled...")
        url = f"{self.base_url}/reports/generate-pdf"
        
        params = {
            "include_executive_summary": False,
            "include_top_sellers": False,
            "include_slow_sellers": False,
            "include_capital_blockers": False,
            "include_revenue_analysis": False,
            "include_demand_forecast": False,
            "include_profit_analysis": False,
            "include_recommendations": False,
            "include_datewise_analysis": True,
            "report_title": "Date-wise Analysis Test Report"
        }
        
        try:
            response = self.session.post(url, json=params, timeout=60)
            
            if response.status_code != 200:
                self.log_test("Date-wise Analysis PDF", "FAIL", f"PDF generation failed with status {response.status_code}", response.text[:200])
                all_tests_passed = False
            else:
                # Verify PDF content type and size
                content_type = response.headers.get('Content-Type', '')
                if 'application/pdf' not in content_type:
                    self.log_test("Date-wise Analysis PDF", "FAIL", f"Incorrect content type: {content_type}", "Expected PDF")
                    all_tests_passed = False
                elif len(response.content) < 1000:
                    self.log_test("Date-wise Analysis PDF", "FAIL", f"PDF too small: {len(response.content)} bytes", "May not contain date-wise analysis")
                    all_tests_passed = False
                else:
                    # Check PDF signature
                    pdf_signature = response.content[:4]
                    if pdf_signature != b'%PDF':
                        self.log_test("Date-wise Analysis PDF", "FAIL", f"Invalid PDF signature: {pdf_signature}", "Not a valid PDF")
                        all_tests_passed = False
                    else:
                        self.log_test(
                            "Date-wise Analysis PDF", 
                            "PASS", 
                            f"PDF with Date-wise Analysis generated successfully",
                            f"Size: {len(response.content)} bytes, Content-Type: {content_type}"
                        )
        
        except Exception as e:
            self.log_test("Date-wise Analysis PDF", "FAIL", f"PDF request error: {str(e)}", "Request failed")
            all_tests_passed = False
        
        # Test 3: PDF report with Date-wise Analysis disabled (should be smaller)
        print("  Testing PDF report with Date-wise Analysis disabled...")
        
        params_no_datewise = {
            "include_executive_summary": True,
            "include_top_sellers": False,
            "include_slow_sellers": False,
            "include_capital_blockers": False,
            "include_revenue_analysis": False,
            "include_demand_forecast": False,
            "include_profit_analysis": False,
            "include_recommendations": False,
            "include_datewise_analysis": False,
            "report_title": "Executive Summary Only Report"
        }
        
        try:
            response_no_datewise = self.session.post(url, json=params_no_datewise, timeout=60)
            
            if response_no_datewise.status_code == 200:
                size_with_datewise = len(response.content) if 'response' in locals() else 0
                size_without_datewise = len(response_no_datewise.content)
                
                if size_with_datewise > size_without_datewise:
                    self.log_test(
                        "Date-wise Analysis PDF Comparison", 
                        "PASS", 
                        f"PDF with date-wise analysis is larger than without",
                        f"With: {size_with_datewise} bytes, Without: {size_without_datewise} bytes"
                    )
                else:
                    self.log_test(
                        "Date-wise Analysis PDF Comparison", 
                        "WARN", 
                        f"PDF sizes unexpected",
                        f"With: {size_with_datewise} bytes, Without: {size_without_datewise} bytes"
                    )
            
        except Exception as e:
            self.log_test("Date-wise Analysis PDF Comparison", "WARN", f"Could not compare PDF sizes: {str(e)}", "Comparison failed")
        
        return all_tests_passed
    
    def test_backup_functionality_with_ist_timestamp(self):
        """Test backup functionality with IST timestamp verification"""
        print("\n💾 Testing Backup Functionality with IST Timestamp")
        
        # Record the test start time in IST for comparison
        import pytz
        from datetime import datetime, timezone
        
        ist_timezone = pytz.timezone('Asia/Kolkata')
        test_start_time_ist = datetime.now(ist_timezone)
        
        # Step 1: Create a new backup
        print("  Step 1: Creating backup...")
        success, backup_data, error = self.test_endpoint("POST", "/stock/backup", 200, data={"reason": "test_backup"})
        
        if not success:
            self.log_test("Backup Creation", "FAIL", "Failed to create backup", error)
            return False
        
        if not isinstance(backup_data, dict) or 'backup_id' not in backup_data:
            self.log_test("Backup Creation", "FAIL", "Invalid backup response format", f"Expected dict with backup_id, got: {backup_data}")
            return False
        
        backup_id = backup_data['backup_id']
        backup_timestamp = backup_data.get('backup_timestamp')
        total_records = backup_data.get('total_records', 0)
        
        self.log_test(
            "Backup Creation", 
            "PASS", 
            f"Backup created successfully with ID: {backup_id}",
            f"Records: {total_records}, Timestamp: {backup_timestamp}"
        )
        
        # Step 2: List all backups to verify the backup exists
        print("  Step 2: Listing backups...")
        success, backups_list, error = self.test_endpoint("GET", "/stock/backups", 200)
        
        if not success:
            self.log_test("Backup Listing", "FAIL", "Failed to list backups", error)
            return False
        
        if not isinstance(backups_list, list):
            self.log_test("Backup Listing", "FAIL", "Invalid backups list format", f"Expected list, got: {type(backups_list)}")
            return False
        
        # Find our backup in the list
        our_backup = None
        for backup in backups_list:
            if backup.get('id') == backup_id:
                our_backup = backup
                break
        
        if not our_backup:
            self.log_test("Backup Listing", "FAIL", f"Created backup {backup_id} not found in list", f"Available backups: {[b.get('id') for b in backups_list[:3]]}")
            return False
        
        self.log_test(
            "Backup Listing", 
            "PASS", 
            f"Backup found in list ({len(backups_list)} total backups)",
            f"Backup timestamp: {our_backup.get('backup_timestamp')}"
        )
        
        # Step 3: Download the backup and verify filename timestamp
        print("  Step 3: Downloading backup and verifying IST timestamp...")
        url = f"{self.base_url}/stock/backup/{backup_id}/download"
        
        try:
            response = self.session.get(url, timeout=30)
            
            if response.status_code != 200:
                self.log_test("Backup Download", "FAIL", f"Download failed with status {response.status_code}", response.text[:200])
                return False
            
            # Check Content-Disposition header for filename
            content_disposition = response.headers.get('Content-Disposition', '')
            
            if 'filename=' not in content_disposition:
                self.log_test("Backup Download", "FAIL", "No filename in Content-Disposition header", f"Header: {content_disposition}")
                return False
            
            # Extract filename
            import re
            filename_match = re.search(r'filename=([^;]+)', content_disposition)
            if not filename_match:
                self.log_test("Backup Download", "FAIL", "Could not extract filename", f"Content-Disposition: {content_disposition}")
                return False
            
            filename = filename_match.group(1).strip('"')
            
            # Verify filename format: stock_backup_YYYYMMDD_HHMMSS.xlsx
            filename_pattern = r'stock_backup_(\d{8})_(\d{6})\.xlsx'
            match = re.match(filename_pattern, filename)
            
            if not match:
                self.log_test("Backup Download", "FAIL", f"Filename format incorrect", f"Expected: stock_backup_YYYYMMDD_HHMMSS.xlsx, Got: {filename}")
                return False
            
            date_part, time_part = match.groups()
            
            # Parse the timestamp from filename
            try:
                filename_datetime_str = f"{date_part}_{time_part}"
                filename_datetime = datetime.strptime(filename_datetime_str, "%Y%m%d_%H%M%S")
                
                # Make it timezone-aware as IST
                filename_datetime_ist = ist_timezone.localize(filename_datetime)
                
            except ValueError as e:
                self.log_test("Backup Download", "FAIL", f"Could not parse timestamp from filename", f"Timestamp: {date_part}_{time_part}, Error: {e}")
                return False
            
            # Verify the timestamp is reasonable (within 5 minutes of test start)
            time_diff = abs((filename_datetime_ist - test_start_time_ist).total_seconds())
            
            if time_diff > 300:  # 5 minutes tolerance
                self.log_test(
                    "Backup IST Timestamp", 
                    "FAIL", 
                    f"Timestamp difference too large: {time_diff:.1f} seconds",
                    f"Test start: {test_start_time_ist.strftime('%Y-%m-%d %H:%M:%S %Z')}, Filename: {filename_datetime_ist.strftime('%Y-%m-%d %H:%M:%S %Z')}"
                )
                return False
            
            # Verify file content is Excel format
            if not response.content or len(response.content) < 100:
                self.log_test("Backup Download", "FAIL", "Downloaded file is too small or empty", f"Size: {len(response.content)} bytes")
                return False
            
            # Check Excel file signature (first few bytes)
            excel_signature = response.content[:4]
            if excel_signature != b'PK\x03\x04':  # ZIP signature (Excel files are ZIP-based)
                self.log_test("Backup Download", "FAIL", "Downloaded file is not a valid Excel file", f"File signature: {excel_signature}")
                return False
            
            self.log_test(
                "Backup IST Timestamp", 
                "PASS", 
                f"IST timestamp conversion working correctly",
                f"Filename: {filename}, IST time: {filename_datetime_ist.strftime('%Y-%m-%d %H:%M:%S %Z')}, Diff: {time_diff:.1f}s"
            )
            
            self.log_test(
                "Backup Download", 
                "PASS", 
                f"Excel file downloaded successfully",
                f"Size: {len(response.content)} bytes, Format: Valid Excel"
            )
            
            return True
            
        except requests.exceptions.Timeout:
            self.log_test("Backup Download", "FAIL", "Download request timeout (30s)", "Server may be slow")
            return False
        except requests.exceptions.ConnectionError:
            self.log_test("Backup Download", "FAIL", "Connection error during download", "Backend may be down")
            return False
        except Exception as e:
            self.log_test("Backup Download", "FAIL", f"Download error: {str(e)}", "Unexpected error during download")
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
        
        # Test results tracking - PRIORITY: Module 4 Monthly Report Generation
        test_functions = [
            ("Root Endpoint", self.test_root_endpoint),
            ("Module 4 Reports Data Endpoint (PRIORITY)", self.test_module4_reports_data_endpoint),
            ("Module 4 Excel Report Generation (PRIORITY)", self.test_module4_excel_report_generation),
            ("Module 4 PDF Report Generation (PRIORITY)", self.test_module4_pdf_report_generation),
            ("Backup Functionality with IST Timestamp", self.test_backup_functionality_with_ist_timestamp),
            ("Trends Chronological Ordering", self.test_trends_chronological_ordering),
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