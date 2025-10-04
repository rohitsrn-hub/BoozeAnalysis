#!/usr/bin/env python3
"""
Debug the date parsing function to understand why it's failing
"""

import re
from datetime import datetime

def parse_date_for_sorting(date_str):
    """Parse various date formats for chronological sorting - matches backend logic"""
    try:
        if not date_str:
            return datetime.min
        
        date_str = str(date_str).strip()
        print(f"Parsing: '{date_str}'")
        
        # Handle full datetime strings
        if 'T' in date_str or len(date_str) > 15:
            try:
                dt = datetime.fromisoformat(date_str.replace('T', ' ').replace('Z', ''))
                print(f"  → Parsed as full datetime: {dt}")
                return dt
            except:
                pass
        
        # First try: dates with year (21-Sep-25, 01-Oct-25)
        match = re.search(r'(\d{1,2})[-/](\w{3})[-/](\d{2,4})', date_str, re.IGNORECASE)
        if match:
            day, month_name, year = match.groups()
            year = f"20{year}" if len(year) == 2 else year
            full_date = f"{day}-{month_name}-{year}"
            dt = datetime.strptime(full_date, "%d-%b-%Y")
            print(f"  → Parsed as date with year: {dt} (groups: {match.groups()})")
            return dt
        
        # Second try: dates without year (21-Sep, 22-Sep) - assume 2025
        match = re.search(r'(\d{1,2})[-/](\w{3})$', date_str, re.IGNORECASE)
        if match:
            day, month_name = match.groups()
            year = "2025"  # Default to 2025 for dates without year
            full_date = f"{day}-{month_name}-{year}"
            dt = datetime.strptime(full_date, "%d-%b-%Y")
            print(f"  → Parsed as date without year: {dt} (groups: {match.groups()})")
            return dt
        
        # Third try: ISO format (2025-10-04)
        match = re.search(r'(\d{4})-(\d{1,2})-(\d{1,2})', date_str)
        if match:
            dt = datetime.strptime(match.group(0), "%Y-%m-%d")
            print(f"  → Parsed as ISO format: {dt}")
            return dt
        
        # Fourth try: numeric dates (04-10-25, 04/10/2025)
        match = re.search(r'(\d{1,2})[-/](\d{1,2})[-/](\d{2,4})', date_str)
        if match:
            day, month, year = match.groups()
            year = f"20{year}" if len(year) == 2 else year
            dt = datetime(int(year), int(month), int(day))
            print(f"  → Parsed as numeric date: {dt}")
            return dt
            
        print(f"  → No pattern matched, returning datetime.min")
        return datetime.min
        
    except Exception as e:
        print(f"  → Exception: {e}")
        return datetime.min

def main():
    """Test the date parsing function with problematic dates"""
    print("🔍 DEBUGGING DATE PARSING FUNCTION")
    print("=" * 50)
    
    # Test dates from the actual data
    test_dates = [
        "21-Sep",      # Should parse as 2025-09-21
        "22-Sep",      # Should parse as 2025-09-22
        "26-Sep",      # Should parse as 2025-09-26
        "20-Sep-25",   # Should parse as 2025-09-20
        "28-Sep-25",   # Should parse as 2025-09-28
        "01-Oct-25",   # Should parse as 2025-10-01
        "03-Oct-25",   # Should parse as 2025-10-03
    ]
    
    parsed_results = []
    
    for date_str in test_dates:
        print(f"\nTesting: {date_str}")
        parsed_date = parse_date_for_sorting(date_str)
        parsed_results.append((date_str, parsed_date))
        print(f"Result: {parsed_date.strftime('%Y-%m-%d %H:%M:%S')}")
    
    print(f"\n" + "=" * 50)
    print("📊 CHRONOLOGICAL SORTING TEST")
    
    # Sort by parsed dates
    sorted_results = sorted(parsed_results, key=lambda x: x[1])
    
    print("\nCorrect chronological order should be:")
    for i, (date_str, parsed_date) in enumerate(sorted_results, 1):
        print(f"  {i:2d}. {date_str:12s} → {parsed_date.strftime('%Y-%m-%d')}")
    
    # Check if the problematic dates are being parsed correctly
    problematic_dates = ["21-Sep", "22-Sep", "26-Sep"]
    print(f"\n🚨 CHECKING PROBLEMATIC DATES:")
    
    for date_str in problematic_dates:
        parsed_date = next(parsed for orig, parsed in parsed_results if orig == date_str)
        if parsed_date == datetime.min:
            print(f"  ❌ {date_str} → FAILED (datetime.min)")
        else:
            print(f"  ✅ {date_str} → {parsed_date.strftime('%Y-%m-%d')}")

if __name__ == "__main__":
    main()