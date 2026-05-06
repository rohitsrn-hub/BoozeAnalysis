# COMPLETE AUDIT REPORT: Liquor Sales Analysis App

## A. System Overview
### Architecture
- **Frontend**: React (Tailwind CSS, Recharts).
- **Backend**: FastAPI (Python) with Motor (Async MongoDB driver).
- **Database**: MongoDB (using prefixes for data separation).

### Stock → Sales Data Flow
1. **Upload**: User uploads periodic stock reports via Excel.
2. **Logic**: The system derives sales by tracking **decreases in stock** between reporting dates.
3. **Trends**: Sales are attributed to the "closing" date of a reporting interval. If a gap exists, the system waits for the next update to calculate the delta.

---

## B. Critical Logic Fixes

### 1. The "Sum of Decreases" Logic
- **Fixed**: Replaced flawed `D1 - DL` formula with a robust movement tracker.
- **Impact**: Correctly identifies sales mid-period and treats stock increases as purchases, rather than subtracting them from sales.
- **Attribution**: Sales are only attributed when a stock update occurs. If data is missing for a day, the sales are calculated upon the next update.

### 2. Contiguous Period Clustering
- **Fixed**: Implemented a clustering algorithm to identify the "Current Period".
- **Benefit**: Prevents future "ghost" dates (outliers from tests or errors) from pruning legitimate current data like **Apr 26 and 27**. The system now looks for the most recent contiguous block of data.

---

## C. Chart & Visual Fixes

### 1. Sparse Data Aggregation
- **Issue**: Gaps in brand reporting caused the trendline to break or show only single dots.
- **Fix**: The backend now aggregates sales at the brand level first, then sums them up across all reporting dates found in the period.
- **Frontend**: Enabled `connectNulls` to ensure visual continuity.

### 2. Date Format Consolidation
- **Issue**: Disparate formats like "25-Apr" and "25-Apr-25" were splitting data points.
- **Fix**: Implemented a global normalization layer (`DD-MMM-YY`) for all trend calculations.

---

## D. Recommended Migration
Run the provided `/api/admin/migrate-historical-data` endpoint to retroactively apply the accurate math to your production backups. This ensures your past trends and future restocking recommendations are based on consistent logic.
