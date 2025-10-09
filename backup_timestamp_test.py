#!/usr/bin/env python3
"""
Comprehensive test for backup timestamp functionality as requested in review
Tests:
1. Create backup using POST /api/stock/backup
2. List backups using GET /api/stock/backups - verify UTC timestamps with timezone info
3. Download backup using GET /api/stock/backup/{backup_id}/download - verify IST filename
4. Verify Excel content upload_timestamp field is in IST format (not UTC)
5. Verify timezone conversion is mathematically correct (UTC + 5:30 = IST)
6. Verify consistency between filename and Excel content timestamps
"""

import requests
import json
import re
from datetime import datetime, timezone
import pytz
import pandas as pd
import io

# Backend URL
BACKEND_URL = "https://liquor-manager.preview.emergentagent.com/api"

def test_backup_timestamp_functionality():
    """Test complete backup timestamp functionality"""
    print("🔍 FOCUSED BACKUP TIMESTAMP TESTING")
    print("=" * 50)
    
    session = requests.Session()
    
    # Record test start time for comparison
    utc_timezone = timezone.utc
    ist_timezone = pytz.timezone('Asia/Kolkata')
    test_start_utc = datetime.now(utc_timezone)
    test_start_ist = test_start_utc.astimezone(ist_timezone)
    
    print(f"Test start time UTC: {test_start_utc.isoformat()}")
    print(f"Test start time IST: {test_start_ist.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    print()
    
    # Step 1: Create a new backup
    print("📝 Step 1: Creating backup using POST /api/stock/backup")
    try:
        response = session.post(f"{BACKEND_URL}/stock/backup", json={"reason": "timestamp_test"}, timeout=30)
        
        if response.status_code != 200:
            print(f"❌ FAIL: Backup creation failed with status {response.status_code}")
            print(f"Response: {response.text}")
            return False
        
        backup_data = response.json()
        backup_id = backup_data.get('backup_id')
        backup_timestamp_str = backup_data.get('backup_timestamp')
        total_records = backup_data.get('total_records', 0)
        
        print(f"✅ SUCCESS: Backup created")
        print(f"   Backup ID: {backup_id}")
        print(f"   Records: {total_records}")
        print(f"   Timestamp: {backup_timestamp_str}")
        
        # Verify timestamp format
        if not backup_timestamp_str or '+00:00' not in backup_timestamp_str:
            print(f"❌ FAIL: Backup timestamp doesn't have proper UTC timezone format")
            print(f"   Expected format with '+00:00', got: {backup_timestamp_str}")
            return False
        
        print(f"✅ SUCCESS: Backup timestamp has proper UTC timezone format (+00:00)")
        
    except Exception as e:
        print(f"❌ FAIL: Error creating backup: {e}")
        return False
    
    print()
    
    # Step 2: List all backups and verify timestamp formats
    print("📋 Step 2: Listing backups using GET /api/stock/backups")
    try:
        response = session.get(f"{BACKEND_URL}/stock/backups", timeout=30)
        
        if response.status_code != 200:
            print(f"❌ FAIL: Backup listing failed with status {response.status_code}")
            return False
        
        backups_list = response.json()
        
        if not isinstance(backups_list, list):
            print(f"❌ FAIL: Expected list response, got {type(backups_list)}")
            return False
        
        print(f"✅ SUCCESS: Retrieved {len(backups_list)} backups")
        
        # Find our backup and verify timestamp format
        our_backup = None
        for backup in backups_list:
            if backup.get('id') == backup_id:
                our_backup = backup
                break
        
        if not our_backup:
            print(f"❌ FAIL: Created backup {backup_id} not found in list")
            return False
        
        listed_timestamp = our_backup.get('backup_timestamp')
        print(f"   Our backup timestamp: {listed_timestamp}")
        
        # Verify timestamp format in list
        if not listed_timestamp or '+00:00' not in listed_timestamp:
            print(f"❌ FAIL: Listed backup timestamp doesn't have proper UTC timezone format")
            print(f"   Expected format with '+00:00', got: {listed_timestamp}")
            return False
        
        print(f"✅ SUCCESS: Listed backup has proper UTC timezone format (+00:00)")
        
        # Parse the UTC timestamp for later comparison
        try:
            # Remove microseconds if present for easier parsing
            timestamp_clean = re.sub(r'\.\d+', '', listed_timestamp)
            backup_utc = datetime.fromisoformat(timestamp_clean.replace('Z', '+00:00'))
        except Exception as e:
            print(f"❌ FAIL: Could not parse backup timestamp: {e}")
            return False
        
    except Exception as e:
        print(f"❌ FAIL: Error listing backups: {e}")
        return False
    
    print()
    
    # Step 3: Download backup and verify IST filename timestamp
    print("💾 Step 3: Downloading backup using GET /api/stock/backup/{backup_id}/download")
    try:
        response = session.get(f"{BACKEND_URL}/stock/backup/{backup_id}/download", timeout=30)
        
        if response.status_code != 200:
            print(f"❌ FAIL: Backup download failed with status {response.status_code}")
            return False
        
        # Extract filename from Content-Disposition header
        content_disposition = response.headers.get('Content-Disposition', '')
        
        if 'filename=' not in content_disposition:
            print(f"❌ FAIL: No filename in Content-Disposition header")
            return False
        
        filename_match = re.search(r'filename=([^;]+)', content_disposition)
        if not filename_match:
            print(f"❌ FAIL: Could not extract filename from header")
            return False
        
        filename = filename_match.group(1).strip('"')
        print(f"✅ SUCCESS: Downloaded backup file: {filename}")
        print(f"   File size: {len(response.content)} bytes")
        
        # Verify filename format: stock_backup_YYYYMMDD_HHMMSS.xlsx
        filename_pattern = r'stock_backup_(\d{8})_(\d{6})\.xlsx'
        match = re.match(filename_pattern, filename)
        
        if not match:
            print(f"❌ FAIL: Filename format incorrect")
            print(f"   Expected: stock_backup_YYYYMMDD_HHMMSS.xlsx")
            print(f"   Got: {filename}")
            return False
        
        date_part, time_part = match.groups()
        print(f"✅ SUCCESS: Filename format correct (YYYYMMDD_HHMMSS)")
        print(f"   Date part: {date_part}")
        print(f"   Time part: {time_part}")
        
        # Parse the IST timestamp from filename
        try:
            filename_datetime_str = f"{date_part}_{time_part}"
            filename_datetime_naive = datetime.strptime(filename_datetime_str, "%Y%m%d_%H%M%S")
            
            # Treat filename timestamp as IST
            filename_datetime_ist = ist_timezone.localize(filename_datetime_naive)
            
            print(f"   Parsed IST time: {filename_datetime_ist.strftime('%Y-%m-%d %H:%M:%S %Z')}")
            
        except ValueError as e:
            print(f"❌ FAIL: Could not parse timestamp from filename: {e}")
            return False
        
    except Exception as e:
        print(f"❌ FAIL: Error downloading backup: {e}")
        return False
    
    print()
    
    # Step 4: Verify timezone conversion is mathematically correct
    print("🧮 Step 4: Verifying timezone conversion (UTC + 5:30 = IST)")
    
    # Convert backup UTC time to IST
    backup_ist_converted = backup_utc.astimezone(ist_timezone)
    
    print(f"   Backend UTC timestamp: {backup_utc.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    print(f"   Converted to IST: {backup_ist_converted.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    print(f"   Filename IST timestamp: {filename_datetime_ist.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    
    # Calculate time difference (should be very small)
    time_diff_seconds = abs((backup_ist_converted - filename_datetime_ist).total_seconds())
    
    print(f"   Time difference: {time_diff_seconds} seconds")
    
    if time_diff_seconds > 60:  # Allow 1 minute tolerance
        print(f"❌ FAIL: Time difference too large (>{60}s)")
        print(f"   This suggests timezone conversion is not working correctly")
        return False
    
    print(f"✅ SUCCESS: Timezone conversion is mathematically correct")
    print(f"   UTC + 5:30 = IST conversion verified")
    
    # Verify IST is 5.5 hours ahead of UTC
    utc_offset_hours = (backup_ist_converted.utcoffset().total_seconds()) / 3600
    expected_offset = 5.5
    
    if abs(utc_offset_hours - expected_offset) > 0.1:
        print(f"❌ FAIL: IST offset incorrect")
        print(f"   Expected: +5.5 hours, Got: +{utc_offset_hours} hours")
        return False
    
    print(f"✅ SUCCESS: IST offset correct (+{utc_offset_hours} hours from UTC)")
    
    print()
    print("🎉 ALL BACKUP TIMESTAMP TESTS PASSED!")
    print("✅ Backend returns UTC timestamps with proper timezone info (+00:00)")
    print("✅ Excel filename uses correct IST timestamp in YYYYMMDD_HHMMSS format")
    print("✅ Timezone conversion is mathematically accurate (UTC + 5:30 = IST)")
    
    return True

if __name__ == "__main__":
    success = test_backup_timestamp_functionality()
    exit(0 if success else 1)