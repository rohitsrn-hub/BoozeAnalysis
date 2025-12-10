# Critical Fix: Sales Trends & Historical Data

## Issues Fixed

### 1. Ghost Trend Lines Appearing
**Problem**: After reset, trend lines for non-uploaded periods were appearing
**Root Cause**: Sales trends endpoint was fetching ALL backups from `stock_backups` collection, including:
- Manual backups
- Auto-backups from uploads
- Test backups
- Pre-reset backups

**Fix**: Modified `/backend/server.py` lines 2438-2442 to ONLY fetch `pre_reset_backup` type backups:
```python
# OLD CODE:
backups = await collections.stock_backups.find().sort("backup_timestamp", -1).to_list(100)

# NEW CODE:
backups = await collections.stock_backups.find({
    "backup_reason": "pre_reset_backup"
}).sort("backup_timestamp", -1).to_list(100)
```

### 2. Historical Periods Showing Wrong Data
**Problem**: Sales History tab showing unusual periods that weren't uploaded
**Root Cause**: Same issue - `get_historical_periods` endpoint was fetching ALL backups

**Fix**: Modified `/backend/server.py` lines 3589-3593 to ONLY fetch `pre_reset_backup` type backups:
```python
# OLD CODE:
backups = await collections.stock_backups.find().sort("backup_timestamp", -1).to_list(100)

# NEW CODE:
backups = await collections.stock_backups.find({
    "backup_reason": "pre_reset_backup"
}).sort("backup_timestamp", -1).to_list(100)
```

## How It Now Works

### Backup Types
1. **pre_reset_backup**: Created ONLY when you click "Reset Stock"
   - Represents a complete sales period
   - Used for historical trends and period reports
   - Never deleted automatically

2. **manual**: Created when you manually click "Create Backup"
   - For safety/archival purposes
   - NOT shown in trends or historical periods
   - Can be deleted manually

3. **auto**: Created before full monthly uploads
   - For undo functionality
   - NOT shown in trends or historical periods
   - Can be deleted after some time

### Data Flow After Fix

#### Reset Stock Flow:
1. You click "Reset Stock"
2. System creates backup with `backup_reason: "pre_reset_backup"`
3. This backup is saved with D1, DL, and period name
4. All data deleted from `liquor_data` collection
5. Next upload becomes new D1

#### Sales Trends Display:
1. Fetches current period from `liquor_data`
2. Fetches ONLY `pre_reset_backup` backups
3. Each backup = one complete sales period
4. Displays trend lines for: Current + All pre-reset periods

#### Upload History Delete:
1. For "Full Monthly" uploads: Restores from the auto-backup created before upload
2. For "Today's Data" uploads: Removes the date column and reverts calculations
3. Frontend should refresh after delete

## Testing Instructions

### Clean Slate Test
1. **Reset Stock**: Click "Reset Stock" button
   - Verify: All data cleared, dashboard empty
   
2. **Upload Period 1**: Upload Sep-Oct 2025 data
   - Verify: Only ONE trend line appears (Sep-Oct 2025)
   - Verify: Sales History shows "Current Period"
   
3. **Reset Stock Again**
   - Verify: Sep-Oct 2025 moves to history
   - Verify: Dashboard clears
   
4. **Upload Period 2**: Upload Oct-Nov 2025 data
   - Verify: TWO trend lines (Sep-Oct 2025 historical + Oct-Nov 2025 current)
   - Verify: Sales History shows both periods
   
5. **Upload Period 3**: Upload Nov-Dec 2025 data (without reset)
   - This should REPLACE Oct-Nov 2025 current data
   - Verify: Still TWO trend lines (Sep-Oct historical + Nov-Dec current)

### Upload History Delete Test
1. Upload a period
2. Note the trend lines shown
3. Go to Upload History tab
4. Delete the last upload
5. Refresh page (F5)
6. Verify: Trend line disappears and data reverts

## Important Notes

### When to Reset Stock
- Only when starting a NEW sales period (after stock collection)
- Typically around 3rd week of month
- This "commits" current period to history

### When NOT to Reset
- If uploading full monthly data to replace current period
- If correcting data for current period
- If adding missing dates to current period

### Stock Calculations
The system calculates:
```
Daily Sales = Previous Day Stock - Current Day Stock
Total Sales = Sum of all daily sales
```

If calculations seem wrong:
1. Check for missing dates (system needs consecutive days)
2. Verify stock quantities are correct
3. Check Database View tab for daily_sales breakdown

## Database Collections Structure

### liquor_data
- Contains ONLY current sales period data
- Cleared on reset
- One record per brand

### stock_backups
- Contains historical backups
- Three types: pre_reset_backup, manual, auto
- Only pre_reset_backup shown in trends

### upload_history
- Tracks all uploads
- Stores backup references for undo
- Can be used to reverse uploads

## Rollback Instructions

If you need to revert these changes:

1. In `/app/backend/server.py` line 2438, change:
```python
backups = await collections.stock_backups.find({
    "backup_reason": "pre_reset_backup"
}).sort("backup_timestamp", -1).to_list(100)
```
Back to:
```python
backups = await collections.stock_backups.find().sort("backup_timestamp", -1).to_list(100)
```

2. Make the same change at line 3589

3. Restart backend: `sudo supervisorctl restart backend`

## Summary

**What Was Wrong**: System was showing ALL backups as separate sales periods in trends

**What Was Fixed**: System now shows ONLY complete sales periods (created via reset)

**Result**: 
- Clean trend lines showing only actual sales periods
- Historical periods correctly show only reset-committed data
- No ghost periods appearing
- Upload delete properly removes data

**Next Steps**:
1. Test the fixed system with your actual data
2. Verify trend lines match uploaded periods
3. Confirm delete from upload history works
4. Check period labels are correct (e.g., "Nov-Dec 2025")
