# COMPLETE AUDIT REPORT: Liquor Sales Analysis App

## A. System Overview
### Architecture
- **Frontend**: React (Tailwind CSS, Lucide icons, Recharts).
- **Backend**: FastAPI (Python) with Motor (Async MongoDB driver).
- **Database**: MongoDB (using prefixes for liquor data, upload history, and backups).
- **Data Ingestion**: Excel/CSV uploads (Full Monthly or Daily Update).

### Stock → Sales Data Flow
1. **Upload**: User uploads an Excel sheet with multiple date columns representing stock quantities on those days.
2. **Parsing**: `parse_tabular_format` extracts the first valid date column as `D1` and the last as `DL`.
3. **Sales Derivation**: The app calculates sales by subtracting the closing stock (`DL_stock`) from the opening stock (`D1_stock`).
4. **Daily Trends**: Daily sales are derived by comparing consecutive stock levels: `max(0, previous_day_stock - current_day_stock)`.
5. **Persistence**: Derived metrics (avg daily sales, monthly projected qty, etc.) are stored in the `liquor_data` collection.

---

## B. Critical Logic Issues

### 1. The "Missing Purchases" Flaw
- **Issue**: The core sales formula `total_sales_qty = max(0, D1_stock - DL_stock)` and daily trend logic `max(0, prev_stock - current_stock)` completely ignore stock replenishments (purchases).
- **Location**: `backend/server.py` lines 951, 1532, 2687, and 3072.
- **Real-world impact**: If a brand starts with 10 units, the owner buys 50 units mid-month, and ends with 5 units, the actual sales are **55 units**. The current app calculates sales as `max(0, 10 - 5) = 5 units`. This results in a **1,000% underestimation** of sales, leading to catastrophic restocking failures.
- **Fix (code)**:
  The system needs to detect stock increases between date columns and treat them as purchases, OR support a dedicated "Purchases" column.

```python
# In backend/server.py - within sales calculation loops
# REPLACING: total_sales_qty = max(0, D1_stock - DL_stock)
# WITH logic that accounts for all movements:

def calculate_accurate_sales(daily_stock_data, sorted_dates):
    total_sales = 0
    for i in range(1, len(sorted_dates)):
        prev_stock = daily_stock_data.get(sorted_dates[i-1], 0)
        curr_stock = daily_stock_data.get(sorted_dates[i], 0)
        # If curr > prev, it's a purchase/restock.
        # We assume Sales = max(0, prev_stock + purchases - curr_stock)
        # Without a purchase column, we must assume any increase is a purchase
        # and that sales occurred only when stock decreased.
        # BUT a better way if we only have daily snapshots:
        if curr_stock < prev_stock:
            total_sales += (prev_stock - curr_stock)
    return total_sales
```

- **Existing data impact**: **YES**. All historical analytics and demand forecasts generated in periods where restocks occurred are mathematically incorrect.

---

## C. Data Integrity Risks
- **Historical impact**: High. The `historical_sales_averages` collection contains corrupted data because it was derived from the flawed `D1 - DL` formula.
- **Correction strategy**:
  1. **DO NOT** delete historical data yet.
  2. Implement a migration script that iterates through `liquor_stock_backups` (which contains the full `daily_sales` snapshots), recalculates the sales using the "Sum of Decreases" method (or supports a new Purchase column), and updates the `historical_sales_averages`.

---

## D. Bugs
### 1. Blocking Synchronous I/O in Async Endpoints
- **Issue**: Heavy pandas `read_excel` and processing operations are running directly inside `async def` routes.
- **Severity**: Medium/High (can cause API timeouts during concurrent uploads).
- **Fix**: Use `run_in_threadpool` or `anyio.to_thread.run_sync` to offload pandas processing.

### 2. Date Format Ambiguity
- **Issue**: The logic in `detect_date_format` defaults to `DD/MM` (Indian standard) but might still fail on specific ambiguous Excel serial numbers.
- **Severity**: Medium.
- **Fix**: Force the user to select the date format in the UI during upload.

---

## E. Performance Improvements
- **Problem**: The system recalculates *everything* for all brands on every "Refresh Analytics" or upload.
- **Optimization**: Use **vectorized pandas operations** instead of row-by-row iteration in `parse_tabular_format`.
- **Benefit**: Reductions in processing time from seconds to milliseconds for large inventories (>1000 brands).

---

## F. Inventory Edge Case Gaps
- **Scenario**: Missing stock entry for a mid-period day.
- **Risk**: The current logic `prev_total - current_total` in `get_sales_trends` (line 3072) will treat a missing day (0 stock) as a massive sales spike, then the next day as a massive purchase.
- **Fix**: Implement linear interpolation for missing daily stock values or skip gaps in the trendline rather than assuming 0.

---

## G. Security Issues
- **Risk**: `pd.read_excel` is vulnerable to Excel External Entity (XXE) attacks if `lxml` is used under the hood with older versions.
- **Fix**: Ensure `defusedxml` is used or strictly validate the file header bytes before passing to pandas.

### 2. Automated Sales Period Reset on Purchase
- **Scenario**: User uploads new stock data where a brand's quantity has increased (indicating a purchase).
- **Previous Behavior**: User had to manually press "Reset Stock" before uploading to ensure the purchase day became D1. Failure to do so would lead to negative sales calculations or messy trendlines.
- **New Behavior**: The system automatically detects the purchase, prompts the user for confirmation via a dialog, and if confirmed, triggers a backup/reset of the previous period. The current upload then becomes D1 for the new period.
- **Safety Feature**: If the user identifies the detected purchase as an error, the upload is cancelled, and they are prompted to check their data.
- **Identical Data Guard**: Added a check to prevent consecutive uploads of the exact same data file, ensuring data progression.
- **Fix (code)**: Implemented `execute_stock_reset` helper and integrated it into `upload_todays_data` with confirmation parameters. Updated React frontend with a `Purchase Confirmation Dialog`.

---

## H. Safe Refactoring Plan
1. **Step 1: Backup Database**: Perform a full MongoDB dump.
2. **Step 2: Update Schema**: Modify `LiquorData` model to include a `total_purchases` field.
3. **Step 3: Fix Backend Calculation**: Deploy the "Sum of Decreases" logic to `parse_tabular_format` and `upload_todays_data`.
4. **Step 4: Recalculation Script**: Run a one-time script to fix `historical_sales_averages` using stored daily snapshots in backups.
5. **Step 5: Frontend Update**: Add a "Purchases Detected" badge in the UI to explain sales derivation to the user.
