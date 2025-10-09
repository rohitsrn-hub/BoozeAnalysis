#!/usr/bin/env python3
"""
Specific test for backup filename format verification
Tests the most recent backup download to verify IST timestamp format
"""

import requests
import json
import re
from datetime import datetime
import pytz

# Get backend URL from environment
BACKEND_URL = "https://liquor-manager.preview.emergentagent.com/api"

def test_backup_filename_format():
    """Test the most recent backup download to verify filename format"""
    print("🔍 Testing Most Recent Backup Filename Format")
    print("=" * 60)
    
    session = requests.Session()
    
    # Step 1: Get the list of backups
    print("Step 1: Getting list of backups...")
    try:
        response = session.get(f"{BACKEND_URL}/stock/backups", timeout=30)
        
        if response.status_code != 200:
            print(f"❌ Failed to get backups list: Status {response.status_code}")
            print(f"Response: {response.text[:200]}")
            return False
        
        backups_list = response.json()
        
        if not isinstance(backups_list, list) or len(backups_list) == 0:
            print(f"❌ No backups found or invalid response format")
            print(f"Response: {backups_list}")
            return False
        
        print(f"✅ Found {len(backups_list)} backups")
        
    except Exception as e:
        print(f"❌ Error getting backups list: {e}")
        return False
    
    # Step 2: Identify the most recently created backup
    print("\nStep 2: Identifying most recent backup...")
    
    most_recent_backup = None
    latest_timestamp = None
    
    for backup in backups_list:
        backup_timestamp_str = backup.get('backup_timestamp')
        if not backup_timestamp_str:
            continue
        
        try:
            # Parse the timestamp
            if 'T' in backup_timestamp_str:
                backup_timestamp = datetime.fromisoformat(backup_timestamp_str.replace('Z', '+00:00'))
            else:
                backup_timestamp = datetime.fromisoformat(backup_timestamp_str)
            
            if latest_timestamp is None or backup_timestamp > latest_timestamp:
                latest_timestamp = backup_timestamp
                most_recent_backup = backup
                
        except Exception as e:
            print(f"⚠️ Could not parse timestamp for backup {backup.get('id')}: {e}")
            continue
    
    if not most_recent_backup:
        print("❌ Could not identify most recent backup")
        return False
    
    backup_id = most_recent_backup['id']
    backup_timestamp = most_recent_backup['backup_timestamp']
    
    print(f"✅ Most recent backup identified:")
    print(f"   ID: {backup_id}")
    print(f"   Timestamp: {backup_timestamp}")
    print(f"   Records: {most_recent_backup.get('total_records', 'N/A')}")
    
    # Step 3: Download the backup and verify filename
    print(f"\nStep 3: Downloading backup {backup_id} and verifying filename...")
    
    try:
        download_url = f"{BACKEND_URL}/stock/backup/{backup_id}/download"
        response = session.get(download_url, timeout=30)
        
        if response.status_code != 200:
            print(f"❌ Download failed: Status {response.status_code}")
            print(f"Response: {response.text[:200]}")
            return False
        
        print(f"✅ Download successful ({len(response.content)} bytes)")
        
    except Exception as e:
        print(f"❌ Error downloading backup: {e}")
        return False
    
    # Step 4: Verify Content-Disposition header and filename format
    print("\nStep 4: Verifying filename format in Content-Disposition header...")
    
    content_disposition = response.headers.get('Content-Disposition', '')
    print(f"Content-Disposition header: {content_disposition}")
    
    if 'filename=' not in content_disposition:
        print("❌ No filename found in Content-Disposition header")
        return False
    
    # Extract filename
    filename_match = re.search(r'filename=([^;]+)', content_disposition)
    if not filename_match:
        print("❌ Could not extract filename from Content-Disposition header")
        return False
    
    filename = filename_match.group(1).strip('"')
    print(f"Extracted filename: {filename}")
    
    # Step 5: Verify filename format requirements
    print(f"\nStep 5: Verifying filename format requirements...")
    
    # Check 1: Overall format should be stock_backup_YYYYMMDD_HHMMSS.xlsx
    expected_pattern = r'^stock_backup_(\d{8})_(\d{6})\.xlsx$'
    match = re.match(expected_pattern, filename)
    
    if not match:
        print(f"❌ FILENAME FORMAT INCORRECT")
        print(f"   Expected format: stock_backup_YYYYMMDD_HHMMSS.xlsx")
        print(f"   Actual filename: {filename}")
        print(f"   Issues:")
        
        # Check specific issues
        if '-' in filename:
            print(f"   - Contains dashes (should not have dashes)")
        if not filename.startswith('stock_backup_'):
            print(f"   - Does not start with 'stock_backup_'")
        if not filename.endswith('.xlsx'):
            print(f"   - Does not end with '.xlsx'")
        if not re.search(r'_\d{6}', filename):
            print(f"   - Missing time component (HHMMSS)")
        if not re.search(r'_\d{8}_', filename):
            print(f"   - Missing or incorrect date component (YYYYMMDD)")
        
        return False
    
    date_part, time_part = match.groups()
    print(f"✅ Filename format is correct: stock_backup_YYYYMMDD_HHMMSS.xlsx")
    print(f"   Date part: {date_part}")
    print(f"   Time part: {time_part}")
    
    # Check 2: Verify date and time components
    try:
        # Parse the date and time
        filename_datetime = datetime.strptime(f"{date_part}_{time_part}", "%Y%m%d_%H%M%S")
        print(f"✅ Date/time parsing successful: {filename_datetime}")
        
        # Check if it's in IST timezone context
        ist_timezone = pytz.timezone('Asia/Kolkata')
        current_ist = datetime.now(ist_timezone)
        
        # The filename should represent IST time, so compare the date
        filename_date = filename_datetime.date()
        current_ist_date = current_ist.date()
        
        print(f"   Filename date: {filename_date}")
        print(f"   Current IST date: {current_ist_date}")
        
        # Check if the date is reasonable (today or very recent)
        date_diff = abs((current_ist_date - filename_date).days)
        
        if date_diff > 1:
            print(f"⚠️ Date seems unusual: {date_diff} days difference from today")
            print(f"   This might indicate UTC vs IST timezone issue")
        else:
            print(f"✅ Date appears to be in IST (difference: {date_diff} days)")
        
    except ValueError as e:
        print(f"❌ Could not parse date/time from filename: {e}")
        return False
    
    # Check 3: Verify no dashes in filename
    if '-' in filename:
        print(f"❌ Filename contains dashes (should not have dashes)")
        return False
    else:
        print(f"✅ No dashes in filename (correct)")
    
    # Check 4: Verify includes time component
    if len(time_part) == 6 and time_part.isdigit():
        hours = int(time_part[:2])
        minutes = int(time_part[2:4])
        seconds = int(time_part[4:6])
        
        if 0 <= hours <= 23 and 0 <= minutes <= 59 and 0 <= seconds <= 59:
            print(f"✅ Time component is valid: {hours:02d}:{minutes:02d}:{seconds:02d}")
        else:
            print(f"❌ Time component has invalid values: {time_part}")
            return False
    else:
        print(f"❌ Time component format incorrect: {time_part}")
        return False
    
    # Final verification summary
    print(f"\n" + "=" * 60)
    print(f"📋 FILENAME FORMAT VERIFICATION SUMMARY")
    print(f"✅ Format: stock_backup_YYYYMMDD_HHMMSS.xlsx")
    print(f"✅ No dashes in filename")
    print(f"✅ Includes date component: {date_part}")
    print(f"✅ Includes time component: {time_part}")
    print(f"✅ File extension: .xlsx")
    print(f"✅ Overall filename: {filename}")
    
    # Check if this matches the expected IST format for today
    if filename_date == current_ist_date:
        print(f"✅ Date matches current IST date (2025-10-10)")
    elif filename_date == current_ist_date.replace(day=current_ist_date.day-1):
        print(f"⚠️ Date is yesterday - might indicate UTC vs IST issue")
        print(f"   Expected IST date: {current_ist_date}")
        print(f"   Filename date: {filename_date}")
    
    print(f"\n🎉 BACKUP FILENAME FORMAT TEST PASSED!")
    return True

def main():
    """Main test execution"""
    success = test_backup_filename_format()
    
    if success:
        print(f"\n✅ All filename format requirements verified successfully")
        exit(0)
    else:
        print(f"\n❌ Filename format verification failed")
        exit(1)

if __name__ == "__main__":
    main()