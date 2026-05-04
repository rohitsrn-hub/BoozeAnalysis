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
- **Location**: `backend/server.py` (Lines 951, 1532, 2687, 3072 in original code).
- **Real-world impact**: If a brand starts with 10 units, the owner buys 50 units mid-month, and ends with 5 units, the actual sales are **55 units**. The current app calculates sales as `max(0, 10 - 5) = 5 units`. This results in a **1,000% underestimation** of sales.
- **FIX WITH CODE**:
  Replace the D1-DL subtraction with a "Sum of Decreases" algorithm.

```python
def calculate_movements_logic(daily_sales_dict, d1_dt, dl_dt):
    # Sort dates chronologically
    sorted_dates = sorted(
        [k for k in daily_sales_dict.keys()],
        key=lambda x: parse_date_for_comparison_global(x)
    )

    total_sales = 0
    total_purchases = 0

    for i in range(1, len(sorted_dates)):
        prev_qty = daily_sales_dict[sorted_dates[i-1]]
        curr_qty = daily_sales_dict[sorted_dates[i]]
        if curr_qty > prev_qty:
            total_purchases += (curr_qty - prev_qty)
        elif curr_qty < prev_qty:
            total_sales += (prev_qty - curr_qty)

    return float(total_sales), float(total_purchases)
```

- **Existing data impact**: **YES**. Past reports underestimate sales for any item restocked mid-period.

---

## C. Data Integrity Risks
- **Historical impact**: Data in `historical_sales_averages` is derived from the flawed formula and is incorrect for items with mid-period purchases.
- **Correction strategy**: Run a recalculation script on all historical backups.
- **RECALCULATION SCRIPT**:

```python
# Migration script to fix historical data
import motor.motor_asyncio
import asyncio

async def migrate():
    client = motor.motor_asyncio.AsyncIOMotorClient("mongodb://localhost:27017")
    db = client["your_db_name"]

    # Process all backups
    backups = await db.liquor_stock_backups.find().to_list(None)
    for backup in backups:
        data = backup["data_snapshot"]
        for record in data:
            sales, purchases = calculate_movements_logic(
                record["daily_sales"],
                parse(record["D1_date"]),
                parse(record["DL_date"])
            )
            record["total_sales_qty"] = sales
            record["total_purchases_qty"] = purchases
            # ... update derived fields (monthly_sale_value etc.)

        await db.liquor_stock_backups.update_one(
            {"_id": backup["_id"]}, {"$set": {"data_snapshot": data}}
        )
    print("Migration complete")
```

---

## D. Bugs
### 1. Blocking Synchronous I/O
- **Issue**: Pandas operations block the async event loop.
- **Severity**: Medium.
- **Fix**: Wrap `pd.read_excel` in `run_in_threadpool`.

### 2. Trendline Discontinuity
- **Issue**: Recharts stops drawing lines if a brand is missing a data point for a specific date.
- **Severity**: Low (Visual).
- **Fix**: Set `connectNulls={true}` on the `LineChart` components in `frontend/src/App.js`.

---

## E. Performance Improvements
- **Problem**: Row-by-row iteration on large Excel files.
- **Optimization**: Use Vectorization.
- **Benefit**: Faster uploads.

---

## F. Inventory Edge Case Gaps
- **Scenario**: Missing stock entries for a day.
- **Risk**: Spikes in sales trends.
- **Fix**: Data validation to detect and interpolate 0-stock gaps that aren't actual sales (e.g., if stock goes 100 -> 0 -> 98).

---

## G. Security Issues
- **Risk**: Malicious Excel files (XXE).
- **Fix**: Use `defusedxml` and strictly enforce `.xlsx` extension.

---

## H. Safe Refactoring Plan
1. **Infrastructure**: Implement `calculate_movements_logic` as a shared utility.
2. **Backend Update**: Inject the logic into `upload-todays-data` to detect purchases.
3. **Database Guard**: Add a trigger to prevent duplicate daily uploads for the same date.
4. **Historical Correction**: Execute the migration script provided in Section C.
5. **Frontend Enhancement**: Update charts to handle sparse data gracefully using null-connection.
