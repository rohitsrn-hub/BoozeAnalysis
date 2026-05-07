# COMPLETE AUDIT REPORT: Liquor Sales Analysis App

## A. System Overview
### Architecture
- **Frontend**: React (Tailwind CSS, Recharts).
- **Backend**: FastAPI (Python) with Motor (Async MongoDB driver).
- **Database**: MongoDB (Collections: `liquor_data`, `upload_history`, `stock_backups`, `brands_master`).

### Stock → Sales Data Flow
1. **Reporting**: Users upload Excel files containing periodic stock snapshots.
2. **Derivation**: The system calculates sales by summing all **decreases** in stock between sequential reporting dates ("Sum of Decreases" algorithm).
3. **Purchases**: Stock **increases** are correctly identified as purchases/procurements and do not negate calculated sales.
4. **Aggregation**: Daily sales are aggregated across all brands and projected for a 30-day "Sales Period" for trend analysis and forecasting.

---

## B. Critical Logic Issues

### 1. Opening Stock Erasure on Reset
- **Issue**: The `stock/reset` endpoint deletes all records in `liquor_data`. When a new month starts, the first upload becomes the "D1" (Opening Stock). However, because the previous month's final stock was deleted, the sales occurring *between* the last day of the old month and the first report of the new month are lost (effectively recorded as 0).
- **Location**: `backend/server.py` -> `reset_stock_data` and `upload-todays-data`.
- **Real-world impact**: If stock was 100 on April 30 and 80 on May 1 (20 units sold), the system records 0 sales because it has no record of the 100-unit starting point after the reset.
- **Fix**: The reset logic should preserve the last known stock level as a "ghost" starting point for the new period, or the new month's D1 should be initialized from the latest backup's DL.
- **Existing data affected?**: YES. All historical "Day 1" sales are likely underreported.

### 2. "Fake Zero" Data Corruption
- **Issue**: The Excel parser (`parse_tabular_format`) treats empty cells or unparseable stock values as `0`.
- **Location**: `backend/server.py` -> `parse_tabular_format` (Line 990-1010).
- **Real-world impact**: If a brand is missing from one daily report (empty cell), the system thinks it "Sold Out" (Stock 100 -> 0), recording 100 sales. When it reappears with 90 units, it records a purchase of 90. This creates massive false spikes in revenue and sales volume.
- **Fix**: Skip brands with missing values or use linear interpolation/last-known-value instead of defaulting to 0.
- **Existing data affected?**: YES. Any inconsistent Excel uploads have corrupted the historical trends.

### 3. Signature Mismatch Regressions
- **Issue**: Several call sites of `calculate_movements_logic` were found attempting to unpack 3 values when the function returns 4, leading to internal server errors (500) that crash the dashboard.
- **Location**: `backend/server.py` lines 1066, 1661, etc.
- **Fix**: Ensure all 6+ call sites use the `total_sales, total_purchases, attributed_sales, reporting_dates` 4-tuple signature. (Applied in this audit).

---

## C. Data Integrity Risks

### 1. Historical Error Compounding
- **Risk**: Because `monthly_sale_value` is derived from `avg_daily_sales_qty`, any "Fake Zero" spike (Issue B2) permanently inflates the brand's performance metrics and overstocking calculations for the rest of the period.
- **Correction Strategy**: Implement a "Sanity Check" layer that flags sales exceeding 500% of historical averages for manual review.

### 2. Time-Boundary "Ghost" Dates
- **Risk**: Test data or incorrect manual entries (e.g., year 2027) can move the "DL_date" far into the future, causing the clustering algorithm to hide all legitimate current data.
- **Correction**: Filter `daily_sales` keys against a rolling 31-day window relative to the current server time.

---

## D. Bugs

### 1. Hardcoded Year Logic
- **Severity**: CRITICAL.
- **Issue**: Multiple functions (`parse_date_string`, `parse_date_for_sorting_excel`) were hardcoded to default to year "2025" or "25".
- **Impact**: Since current production time is May 2026, any date without a year (e.g., "05-May") was being parsed as May 2025, causing it to disappear from "Current Period" views or fail comparison logic.
- **Fix**: Replaced all hardcoded "2025" strings with `datetime.now().year`. (Applied in this audit).

### 2. Blocking IO in Async Routes
- **Severity**: MEDIUM.
- **Issue**: Large Excel parsing (`pandas.read_excel`) and PDF generation (`reportlab`) are CPU-bound and blocking. In a production environment with multiple users, the entire API becomes unresponsive during report generation.
- **Fix**: Wrap these calls in `run_in_threadpool` or offload to a Celery worker.

---

## E. Performance Improvements

| Problem | Optimization | Benefit |
|---------|--------------|---------|
| No MongoDB Indexes | Add unique index on `brand_name` and `index_number` | 10x faster lookups for daily updates. |
| In-memory aggregation | Use MongoDB `$group` and `$sum` operators | Reduces RAM usage and allows scaling to thousands of brands. |
| Redundant parsing | Cache `sales-trends` results for 1 hour | Instant dashboard loading for repeated views. |

---

## F. Inventory Edge Case Gaps

| Scenario | Risk | Fix |
|----------|------|-----|
| Negative Stock | Database corruption or math errors | Add `max(0, qty)` constraint in all update paths. |
| Mid-day Purchases | Sales underestimation (Stock 10 -> Sale 5 -> Purchase 5 -> Stock 10 looks like 0 sales) | Document that system tracks "Net Movement" between reports. |
| Multiple Uploads/Date | Data overwriting | Enforce single-upload-per-day policy or append with timestamp. |

---

## G. Security Issues
- **Public Data**: Authentication has been disabled ("AUTH REMOVED"). This makes sensitive business revenue data public.
- **CORS Policy**: Currently uses wildcard fallback. Should be restricted to the production frontend domain.

---

## H. Safe Refactoring Plan
1. **Phase 1 (Immediate)**: Run `/api/refresh-analytics` to re-sync all current data with the fixed year logic and 4-tuple signature.
2. **Phase 2 (Data Integrity)**: Update `parse_tabular_format` to ignore empty cells instead of defaulting to 0.
3. **Phase 3 (Transition)**: Modify `stock/reset` to store the final stock of the closing month as the "Opening" value for the new month's first calculation.
4. **Phase 4 (Security)**: Restore the Auth module and restrict CORS.
