# BoozeAnalysis - Liquor Sales Analysis Dashboard
## Comprehensive User Guide

---

## Table of Contents
1. [Introduction](#1-introduction)
2. [Dashboard Overview](#2-dashboard-overview)
3. [Getting Started](#3-getting-started)
4. [Header Section & Controls](#4-header-section--controls)
5. [Data Upload & Management](#5-data-upload--management)
6. [Key Performance Metrics](#6-key-performance-metrics)
7. [Main Dashboard Tabs](#7-main-dashboard-tabs)
8. [Period Selection for Reports](#8-period-selection-for-reports)
9. [Report Generation](#9-report-generation)
10. [Data Management Features](#10-data-management-features)
11. [Daily & Monthly Workflows](#11-daily--monthly-workflows)
12. [Tips & Best Practices](#12-tips--best-practices)
13. [Troubleshooting](#13-troubleshooting)

---

## 1. Introduction

### What is BoozeAnalysis?
BoozeAnalysis is an advanced analytics platform designed specifically for liquor retail businesses to manage inventory, analyze sales performance, forecast demand, and generate comprehensive reports. The system processes daily stock positions and automatically calculates sales, trends, and provides actionable insights.

### Key Capabilities
- **Real-time Sales Analytics**: Track daily sales performance across all brands
- **Multi-Period Analysis**: Compare performance across different sales periods
- **AI-Powered Forecasting**: Get intelligent demand predictions
- **Comprehensive Reporting**: Generate PDF and Excel reports for single or multiple periods
- **Historical Tracking**: Maintain and analyze data from previous sales cycles
- **Overstocking Alerts**: Identify slow-moving inventory automatically
- **Period-Based Sales Tracking**: Support for custom sales months that span calendar months

### System Requirements
- Modern web browser (Chrome, Firefox, Safari, Edge)
- Stable internet connection
- Excel or spreadsheet software for data preparation

---

## 2. Dashboard Overview

### Interface Layout
The dashboard features a clean, organized interface with the following main sections:

**Header Bar**
- Dashboard title
- Refresh button
- Help icon
- Overstock multiplier control
- Data upload buttons

**Key Metrics Cards**
- Total Brands
- Total Stock Value
- Overstocked Brands
- Overstocked Value

**Tab Navigation**
Seven main tabs provide access to different analytical views:
1. **Dashboard** - Visual charts and performance metrics
2. **Alerts** - Overstocking warnings
3. **Top Brands** - Best performers by revenue and velocity
4. **Sales History** - Historical period comparisons
5. **Forecast** - Demand predictions and recommendations
6. **Upload History** - Track all data uploads
7. **Database View** - Complete data records

---

## 3. Getting Started

### First-Time Setup

#### Step 1: Prepare Your Data
Your Excel file should contain:
- **Index/Serial Number column**
- **Brand Name column**
- **Wholesale Rate column** (cost price)
- **Retail/Selling Rate column**
- **Date columns** with daily stock positions (format: DD-MMM-YY, e.g., "14-Nov-25", "15-Nov-25")

#### Step 2: Initial Data Upload
1. Click the **"Upload Full Monthly Data"** button
2. Select your prepared Excel file
3. Wait for the upload progress bar to complete
4. System will automatically detect date columns and calculate:
   - D1 Date (First day of sales period)
   - DL Date (Last day of sales period)
   - Daily sales by subtracting consecutive day stocks
   - Total sales quantity per brand

#### Step 3: Review Initial Analytics
After first upload, verify:
- All brands are listed correctly
- Stock values are accurate
- Date range shows correct sales period
- Key metrics display properly

### Understanding Sales Periods
- **Sales Month**: Your business cycle that may span two calendar months
  - Example: 14-Nov-25 to 08-Dec-25 is displayed as "Nov-Dec 2025"
- **D1 (Day 1)**: First date in your sales period
- **DL (Day Last)**: Last date in your sales period
- System automatically identifies period names from D1 and DL dates

---

## 4. Header Section & Controls

### Dashboard Controls

#### Refresh Button (↻)
- Reloads all analytics data
- Use after making changes to ensure latest data is displayed
- Automatically fetches updated charts, metrics, and trends

#### Help Icon (?)
- Access quick help and feature explanations
- Context-sensitive guidance for current section

#### Overstock Multiplier
- **Purpose**: Controls the threshold for identifying overstocked items
- **Default**: 3.0x
- **Calculation**: Brand is flagged if current stock > (average daily sales × multiplier)
- **Adjustment**: Use the slider or input field to change sensitivity
  - Lower value (2x): More strict, flags items earlier
  - Higher value (4x): More lenient, only flags severely overstocked items

### Quick Action Buttons

**Upload Full Monthly Data**
- Replaces all existing data with new month's data
- Use when starting a new sales cycle
- Creates automatic backup of previous data
- Accepts Excel (.xlsx) or CSV files

**Upload Today's Data**
- Updates daily stock position for existing sales period
- Appends new date column to existing data
- Automatically recalculates all metrics

**Export Excel**
- Opens period selection modal
- Generates comprehensive Excel report
- Includes all brands with detailed metrics

**Generate PDF**
- Two-step process:
  1. Select period(s) for report
  2. Configure report sections and parameters

---

## 5. Data Upload & Management

### File Format Requirements

#### Full Monthly Data Format
```
Index | Brand Name      | W/Rate | S/Rate | 14-Nov-25 | 15-Nov-25 | 16-Nov-25 | ...
1     | Johnnie Walker  | 1200   | 1500   | 50        | 45        | 42        | ...
2     | Jack Daniels    | 1800   | 2200   | 30        | 28        | 25        | ...
```

**Key Points**:
- Column names can vary but should clearly identify: Index, Brand, Wholesale Rate, Selling Rate
- Date columns must contain month abbreviations (Jan, Feb, Mar, Apr, May, Jun, Jul, Aug, Sep, Oct, Nov, Dec)
- Stock quantities represent **closing stock** for each date
- System automatically detects date columns

#### Today's Data Format
```
Brand Name      | Stock Qty
Johnnie Walker  | 38
Jack Daniels    | 20
```

### Upload Process

#### Full Monthly Upload
1. Click **"Upload Full Monthly Data"**
2. Select your Excel file
3. System processes:
   - Detects all date columns (including those spanning two months)
   - Identifies D1 and DL dates
   - Calculates daily sales: `Sales = Previous Day Stock - Current Day Stock`
   - Computes total sales quantity and value per brand
   - Generates all analytics
4. Review success message showing period detected

#### Daily Update Upload
1. Click **"Upload Today's Data"**
2. Select file with current stock levels
3. System:
   - Adds new date column to existing data
   - Recalculates sales for the new day
   - Updates all metrics and trends
   - Preserves historical data

### Upload Validation
The system validates:
- File format compatibility
- Required columns presence
- Data type consistency
- Duplicate prevention
- Date format recognition

### Upload History
- Track all uploads in the **Upload History** tab
- View: Upload time, file size, type of upload
- Option to download uploaded files

---

## 6. Key Performance Metrics

### Metric Cards (Top of Dashboard)

#### Total Brands
- Count of all brands in your inventory
- Updated with each data upload
- Helps track catalog size

#### Total Stock Value
- **Calculation**: Sum of (Current Stock Qty × Wholesale Rate) for all brands
- Represents total capital invested in inventory
- Real-time update with each upload

#### Overstocked Brands
- Count of brands exceeding overstock threshold
- **Threshold**: Current Stock > (Avg Daily Sales × Overstock Multiplier)
- Color-coded alert (orange/red)

#### Overstocked Value
- **Calculation**: Sum of stock value for all overstocked brands
- Shows capital locked in slow-moving inventory
- Helps prioritize liquidation efforts

### Metric Interpretation
- **High Overstocked Value**: Review pricing or promotional strategies
- **Low Stock Value**: Consider restocking high-demand items
- **Increasing Overstock Count**: Adjust purchasing patterns

---

## 7. Main Dashboard Tabs

### Tab 1: Dashboard (Charts & Visualizations)

#### Available Charts

**1. Volume Leaders**
- Bar chart showing top brands by sales quantity
- Displays top 10 brands
- Useful for identifying best-moving items
- Color: Blue gradient

**2. Revenue Leaders**
- Horizontal bar chart of top revenue-generating brands
- Shows monetary contribution
- Helps prioritize valuable products
- Color: Green gradient

**3. Fastest Moving Brands**
- Identifies brands with highest sales velocity
- Based on days of stock remaining
- Critical for reordering decisions
- Color: Purple gradient

**4. Revenue Share Distribution**
- Pie chart showing percentage contribution
- Visualizes portfolio balance
- Identifies concentration risks
- Interactive hover tooltips

#### Sales Trends Section
- **Line chart** tracking daily sales performance
- **Period Selection**: Quarterly, Yearly, or Single Month
- **Features**:
  - Multiple period comparison
  - Hover to see exact daily values
  - Legend shows total units sold per period
  - Period summary cards with:
    - Total units sold
    - Days tracked
    - Average daily sales
    - Date range (D1 to DL)

### Tab 2: Alerts (Overstocking Analysis)

#### Overstock Table
Displays brands exceeding the overstock threshold:

**Columns**:
- Brand Name
- Current Stock (quantity)
- Stock Value (₹)
- Avg Daily Sales
- Stock Available (days)
- Overstock Ratio (e.g., "4.2x" means 4.2 times the threshold)

**Visual Indicators**:
- Red badges for high overstock ratios (>5x)
- Orange badges for moderate overstock (3-5x)

**Actions**:
- Sort by any column
- Export list to Excel
- Use for promotional planning

#### Risk Categories
- **High Risk**: >6x multiplier - Immediate action needed
- **Medium Risk**: 3-6x multiplier - Monitor and plan promotions
- **Watch List**: 2-3x multiplier - Track trends

### Tab 3: Top Brands

#### Performance Rankings

**Top Revenue Generators**
- Brands contributing most to total sales value
- Shows: Brand name, total revenue, percentage contribution
- Sorted by revenue (highest first)

**Fastest Moving Items**
- Based on sales velocity and stock turnover
- Shows: Brand name, daily sales rate, stock days
- Critical for inventory planning

**High Value Products**
- Premium items by wholesale cost
- Useful for security and insurance planning

**Use Cases**:
- Identify star performers for promotional support
- Ensure adequate stock of fast movers
- Review pricing strategies for underperformers

### Tab 4: Sales History (Multi-Period Analysis)

#### Historical Period Comparison
- **Purpose**: Compare performance across different sales months
- **Features**:
  - Select multiple historical periods
  - Aggregated sales data across brands
  - Side-by-side comparison
  - Export aggregated data

#### Data Display
**Table Columns**:
- Brand Name
- Total Sales Quantity (aggregated)
- Total Sales Value (aggregated)
- Average Daily Sales
- Stock Available (from most recent period)

**Period Selection**:
1. Available periods listed (e.g., "Sep-Oct 2025", "Oct-Nov 2025")
2. Select one or multiple periods
3. Click "Analyze" to aggregate data
4. View combined statistics

**Applications**:
- Seasonal trend identification
- Year-over-year growth analysis
- Portfolio performance review
- Quarterly reporting

### Tab 5: Forecast (Demand Planning)

#### AI-Powered Recommendations
The forecast engine analyzes historical sales patterns to provide intelligent reorder suggestions.

**Forecast Categories**:

**1. Critical Priority (Red)**
- Brands at risk of stockout
- Stock days < 5
- Immediate reorder required
- Recommended quantity displayed

**2. High Priority (Orange)**
- Stock days 5-10
- Order within 1-2 days
- Quantities based on consumption rate

**3. Medium Priority (Yellow)**
- Stock days 10-15
- Plan for next order
- Monitor consumption trends

**4. Low Priority (Green)**
- Stock days >15
- Well-stocked items
- Routine reorder cycle

**Forecast Table Columns**:
- Brand Name
- Current Stock
- Avg Daily Sales
- Stock Days Remaining
- Recommended Order Quantity
- Priority Level
- Wholesale Rate (for budgeting)

**Forecast Logic**:
```
Stock Days = Current Stock / Avg Daily Sales
Recommended Order = (Target Days × Avg Daily Sales) - Current Stock
Target Days = 15 (configurable)
```

**Export Options**:
- Download forecast as Excel
- Includes all recommendations
- Add to procurement system

### Tab 6: Upload History

#### Upload Tracking
- **Timeline**: Chronological list of all uploads
- **Details per Upload**:
  - Timestamp
  - File name
  - File size
  - Upload type (Full Monthly / Today's Data)
  - Status (Success/Failed)

**Features**:
- Download original uploaded file
- Track data changes over time
- Audit trail for compliance

### Tab 7: Database View

#### Complete Data Records
Raw database view of all liquor records:

**Displayed Information**:
- Brand Name
- Index Number
- Wholesale Rate
- Retail/Selling Rate
- D1 Date
- DL Date
- D1 Stock (opening stock)
- DL Stock (closing stock)
- Total Sales Quantity
- Total Sales Value
- Monthly Sale Value
- Average Daily Sales
- Current Stock
- Stock Value
- Stock Available Days
- Stock Ratio

**Use Cases**:
- Data verification
- Manual calculations
- Export to Excel for external analysis
- Troubleshooting discrepancies

**Features**:
- Sortable columns
- Search functionality
- Pagination for large datasets
- Export to Excel

---

## 8. Period Selection for Reports

### Multi-Period Report Feature

#### How It Works
When generating reports (Excel or PDF), you can select one or multiple sales periods to include:

**Single Period Selection**:
- Report contains data for that specific month
- D1 and DL dates from that period
- All metrics as they were during that cycle

**Multiple Period Selection**:
- Data is aggregated across selected periods
- Sales quantities summed
- Sales values combined
- Period shown as "First D1 to Last DL"
- Useful for quarterly or custom date range reports

#### Period Selection Modal

**Interface**:
- List of all available sales periods
- Each period card shows:
  - Period name (e.g., "Nov-Dec 2025")
  - Date range (14-Nov-25 to 08-Dec-25)
  - Number of brands tracked
- Checkboxes for selection
- Visual confirmation of selected periods

**Selection Process**:
1. Click "Export Excel" or "Generate PDF"
2. Period selection modal opens
3. Click on period cards to select (checkbox appears)
4. Multiple selections allowed
5. Summary shows count of selected periods
6. Click "Generate Excel/PDF Report" to proceed

**For Excel Reports**:
- Report generates immediately after period selection
- Downloads automatically

**For PDF Reports**:
- After period selection, report configuration modal opens
- Configure sections and title
- Then generate report

---

## 9. Report Generation

### Excel Report Generation

#### Process
1. Click **"Export Excel"** button
2. Select period(s) from modal
3. Click **"Generate Excel Report"**
4. File downloads automatically

#### Report Contents
**Sheets Included**:
1. **Summary Sheet**
   - Total brands
   - Total sales quantity and value
   - Date range
   - Top 10 performers

2. **Detailed Sales Data**
   - All brands with complete metrics
   - Sales quantities and values
   - Stock positions
   - Rates and margins

3. **Overstock Analysis**
   - Flagged brands
   - Stock ratios
   - Capital locked

4. **Demand Forecast**
   - Recommended orders
   - Priority levels
   - Estimated costs

**File Naming**: `monthly_report_YYYYMMDD_HHMMSS.xlsx`

### PDF Report Generation

#### Two-Step Process

**Step 1: Period Selection**
1. Click **"Generate PDF"** button
2. Period selection modal opens
3. Select one or more periods
4. Click **"Generate PDF Report"**

**Step 2: Report Configuration**
Configuration modal opens with options:

**Report Title**:
- Default: "Monthly Sales Analytics Report"
- Customize as needed
- Appears on cover page

**Report Sections** (toggle on/off):
- ☑ Executive Summary
- ☑ Top Sellers
- ☑ Slow Sellers
- ☑ Capital Blockers (Overstocked Items)
- ☑ Revenue Analysis
- ☑ Demand Forecast
- ☑ Profit Analysis
- ☑ Recommendations
- ☐ Date-wise Analysis (optional)

**Selected Periods Display**:
- Shows which periods will be included
- Indicates if data will be aggregated (multiple periods)

**Generate Report**:
- Click **"Generate PDF Report"**
- Report compiles (may take 10-30 seconds)
- Downloads automatically

#### PDF Report Structure

**Cover Page**:
- Report title
- Sales period (with date range)
- Generation date
- Company/business name (if configured)

**Executive Summary** (1 page):
- Key metrics overview
- Total sales, revenue, margins
- Brand count and portfolio value
- Period comparison (if multiple periods)

**Top Sellers Section** (1-2 pages):
- Top 15 brands by revenue
- Table with sales quantity, value, margin
- Percentage contribution to total sales

**Slow Sellers Section** (1-2 pages):
- Bottom 15 performers
- Brands requiring attention
- Stock value locked in slow movers

**Capital Blockers Section** (1-2 pages):
- Overstocked brands
- Stock ratios and days available
- Recommended actions (promotions, price adjustments)

**Revenue Analysis** (1 page):
- Category-wise breakdown (if applicable)
- Trend charts
- Period-over-period comparison

**Demand Forecast Section** (2-3 pages):
- Priority-wise recommendations
- Critical items for immediate order
- High priority items
- Quantities and estimated costs

**Profit Analysis** (1 page):
- Margin analysis by brand
- High-margin vs low-margin items
- Profitability insights

**Recommendations** (1-2 pages):
- Actionable insights
- Strategic suggestions
- Inventory optimization tips

**File Naming**: `monthly_report_YYYYMMDD_HHMMSS.pdf`

---

## 10. Data Management Features

### Brand Management

#### Adding New Brands

**Process**:
1. Click **"Add New Brand"** button
2. Fill in the form:
   - **Index Number**: Unique identifier (e.g., 101, 102)
   - **Brand Name**: Full product name
   - **Wholesale Rate**: Purchase cost per unit (₹)
   - **Selling Rate**: Retail price per unit (₹)
   - **Initial Stock Quantity**: Opening stock for new brand
3. Click **"Add Brand"**
4. Brand appears in all tabs and analytics

**Validation**:
- System checks for duplicate brand names
- Validates numeric fields
- Ensures index number uniqueness

#### Updating Brand Rates

**Individual Update**:
- Edit in Database View tab
- Modify wholesale or retail rate
- Save changes

**Bulk Rate Update**:
1. Prepare Excel file with columns:
   - Index
   - Brand Name
   - Wholesale Rate
   - Retail Rate
2. Click **"Update Rates"** button
3. Upload file
4. System matches by brand name or index
5. Updates rates for all matching brands

**Use Cases**:
- Seasonal price changes
- Vendor rate revisions
- Promotional pricing updates

### Backup & Restore

#### Creating Backups

**Manual Backup**:
1. Navigate to Backup section
2. Click **"Create Backup"**
3. Enter backup description (optional)
4. System saves current state with timestamp

**Automatic Backups**:
- Created automatically when:
  - Stock is reset for new cycle
  - Full monthly data is uploaded
  - Critical operations performed

**Backup Information**:
- Timestamp
- Number of records
- User/session ID
- Description/notes

#### Managing Backups

**View Backups**:
- List of all available backups
- Sorted by date (newest first)
- Shows record count and timestamp

**Restore Backup**:
1. Select backup from list
2. Click **"Restore"**
3. Confirm action
4. System replaces current data with backup
5. Creates safety backup of current state before restore

**Download Backup**:
- Export backup as Excel file
- Contains complete data snapshot
- Use for external archival

**Delete Backup**:
- Remove old or unnecessary backups
- Permanent deletion
- Confirmation required

### Stock Reset (New Cycle)

#### When to Reset
- Typically performed on the 3rd week of the month
- When starting a new sales period
- After monthly inventory count

#### Reset Process
1. **Backup Recommended**: Create manual backup first
2. Click **"Reset Stock"** button
3. System confirmation dialog:
   - Shows current data statistics
   - Warns about data deletion
   - Confirms automatic backup creation
4. Click **"Confirm Reset"**
5. System performs:
   - Creates automatic backup of current data
   - Transfers summary to historical averages
   - Clears all daily stock columns
   - Resets metrics to zero
   - Preserves brand master data (names, rates)
6. Next upload becomes new D1

**What is Preserved**:
- Brand names and index numbers
- Wholesale and retail rates
- Historical backups

**What is Cleared**:
- Daily stock positions
- Sales calculations
- Date range (D1/DL)
- Current metrics

---

## 11. Daily & Monthly Workflows

### Daily Routine (During Sales Period)

#### Morning/Opening
1. **Verify Previous Day's Upload**
   - Check Dashboard tab for correct metrics
   - Review Sales History to ensure data integrity

2. **Check Alerts**
   - Visit Alerts tab
   - Note overstocked brands
   - Review any critical stock situations

#### Evening/Closing
1. **Record Closing Stock**
   - Take physical inventory count
   - Update your Excel template
   - Include date column (format: DD-MMM-YY)

2. **Upload Today's Data**
   - Click **"Upload Today's Data"**
   - Select file with current stock levels
   - Wait for upload confirmation

3. **Verify Upload**
   - Check if new date column appears in Database View
   - Review Sales Trends for today's performance
   - Verify metrics update

4. **Review Forecast**
   - Check Forecast tab for reorder recommendations
   - Note critical and high-priority items
   - Plan next day's procurement

#### Weekly Tasks
- Review Top Brands performance
- Analyze overstocking alerts
- Plan promotions for slow movers
- Check Upload History for any missed days

### Monthly Routine

#### Month-End (Before Reset)
1. **Final Data Verification**
   - Ensure all days of the month are uploaded
   - Verify D1 and DL dates are correct
   - Check Database View for completeness

2. **Generate Reports**
   - Export Excel report for month
   - Generate PDF report for management
   - Save reports for record-keeping

3. **Backup Creation**
   - Create manual backup with clear description
   - Example: "Nov-Dec 2025 - End of Period Backup"
   - Download backup for external storage

4. **Performance Review**
   - Analyze Top Brands trends
   - Review overstock resolution
   - Compare with previous months (Sales History tab)

#### New Month Setup (After Reset)
1. **Stock Reset**
   - Click **"Reset Stock"** (typically around 20th)
   - Confirm automatic backup creation
   - Verify reset completion

2. **New Period Upload**
   - Prepare full monthly data file with new opening stock
   - Include all date columns for the new period
   - Click **"Upload Full Monthly Data"**
   - System establishes new D1 date

3. **Initial Verification**
   - Check that period name is correct (e.g., "Dec 2025-Jan 2026")
   - Verify D1 date matches your first day
   - Ensure all brands are listed

4. **Resume Daily Operations**
   - Continue with daily upload routine
   - Monitor trends from day 1

---

## 12. Tips & Best Practices

### Data Entry Best Practices

#### Excel File Preparation
- **Consistent Formatting**: Use the same template structure for all uploads
- **Date Format**: Always use DD-MMM-YY (e.g., 14-Nov-25)
- **No Blank Rows**: Remove empty rows between data
- **Header Row**: Ensure first row contains column names
- **Number Format**: Use plain numbers, avoid text formatting
- **Save As**: Use .xlsx format for best compatibility

#### Column Naming
The system is flexible but ensure clarity:
- **Good**: "Brand Name", "Wholesale Rate", "14-Nov-25"
- **Avoid**: Single letters, special characters, dates in other formats

### Optimal Overstock Multiplier Settings

#### By Business Type
- **High-Volume Retail**: 2.5x - 3.0x (strict control)
- **Mid-Size Store**: 3.0x - 3.5x (balanced)
- **Premium Boutique**: 3.5x - 4.0x (more inventory buffer)

#### Adjustment Strategy
- Start with default 3.0x
- Monitor Alerts tab for 1 week
- If too many false positives: Increase by 0.5x
- If missing slow movers: Decrease by 0.5x
- Review and adjust monthly

### Report Generation Tips

#### Excel Reports
- **Best For**: Data analysis, pivot tables, custom calculations
- **When to Use**: Internal analysis, detailed reviews, sharing with analysts

#### PDF Reports
- **Best For**: Management presentations, formal documentation
- **Customization**: Toggle off unnecessary sections for cleaner reports
- **Multiple Periods**: Use for quarterly or annual reviews

### Performance Optimization

#### For Faster Loading
- Keep active brands under 200 for optimal performance
- Archive old periods regularly
- Delete unnecessary backups (keep last 12 months)

#### For Accurate Analytics
- Upload data consistently every day
- Don't skip days (system calculates based on consecutive dates)
- Verify uploads immediately after submission

---

## 13. Troubleshooting

### Common Issues & Solutions

#### Issue: "No date columns detected"
**Cause**: Date columns don't contain recognizable month names
**Solution**: 
- Ensure column headers contain month abbreviations (Nov, Dec, Jan, etc.)
- Use format: "14-Nov-25" or "14-Nov-2025"
- Avoid pure numeric dates like "14/11/25"

#### Issue: "Duplicate upload detected"
**Cause**: Trying to upload same date again
**Solution**:
- System protects against overwriting
- If data needs correction: Delete last upload from Upload History
- Then re-upload corrected file

#### Issue: Period shows "N/A to N/A"
**Cause**: D1 or DL dates not properly detected
**Solution**:
- Check that date columns follow DD-MMM-YY format
- Ensure dates are in chronological order
- Verify dates span your intended sales period

#### Issue: Sales calculations seem wrong
**Cause**: Missing days or incorrect stock entries
**Solution**:
- Go to Database View tab
- Check daily_sales breakdown
- Verify: Sales = Previous Day Stock - Current Day Stock
- Look for negative values (indicates restocking)
- Ensure consecutive days have no gaps

#### Issue: Overstock alerts not showing
**Cause**: Multiplier set too high or insufficient sales history
**Solution**:
- Lower overstock multiplier to 2.5x or 2.0x
- Ensure at least 5 days of sales data
- Check Alerts tab for manual threshold override

#### Issue: Forecast recommendations empty
**Cause**: Insufficient data or all items well-stocked
**Solution**:
- Minimum 7 days of data needed for forecasting
- Check if all brands have adequate stock
- Review "Stock Available Days" in Database View

#### Issue: Report generation fails
**Cause**: No periods selected or data not available
**Solution**:
- Ensure at least one period is selected
- Verify selected periods have data (check Database View)
- Try generating report for current period first
- Check browser console for error messages

#### Issue: Upload takes too long
**Cause**: Large file size or slow connection
**Solution**:
- Ensure file size < 10MB
- Remove unnecessary columns (keep only required data)
- Check internet connection
- Try uploading during off-peak hours

#### Issue: Charts not displaying
**Cause**: No data or browser compatibility
**Solution**:
- Verify data is uploaded (check Database View)
- Refresh page (click Refresh button or F5)
- Try different browser (Chrome recommended)
- Clear browser cache

### Error Messages Explained

**"No data found"**
- Database is empty
- Upload full monthly data first

**"Invalid file format"**
- File is not .xlsx or .csv
- Convert file to Excel format

**"Missing required columns"**
- Essential columns not detected
- Ensure Index, Brand Name, Rates are present

**"Date parsing error"**
- Date format not recognized
- Use DD-MMM-YY format consistently

### Getting Help

#### Built-in Help
- Click **Help Icon (?)** in header
- Context-sensitive guidance for current section

#### Support Contacts
- Document your issue with screenshots
- Include: Date of occurrence, what you were trying to do, error message
- Note your browser type and version

---

## Appendix A: Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| Ctrl + R / F5 | Refresh dashboard |
| Tab | Navigate between input fields |
| Enter | Submit form/dialog |
| Esc | Close modal/dialog |

---

## Appendix B: Calculation Formulas

### Sales Calculations
```
Daily Sales = Previous Day Stock - Current Day Stock
Total Sales Qty = Sum of all daily sales
Total Sales Value = Total Sales Qty × Selling Rate
```

### Stock Metrics
```
Stock Value = Current Stock Qty × Wholesale Rate
Avg Daily Sales = Total Sales Qty / Number of Days
Stock Available Days = Current Stock / Avg Daily Sales
Stock Ratio = Current Stock / (Avg Daily Sales × Overstock Multiplier)
```

### Overstock Logic
```
Is Overstocked = Stock Ratio > 1.0
OR
Current Stock > (Avg Daily Sales × Overstock Multiplier)
```

### Forecast Recommendations
```
Stock Days Remaining = Current Stock / Avg Daily Sales
Recommended Order Qty = (Target Days × Avg Daily Sales) - Current Stock
Target Days = 15 (default)
Priority:
  - Critical: Stock Days < 5
  - High: Stock Days 5-10
  - Medium: Stock Days 10-15
  - Low: Stock Days > 15
```

---

## Appendix C: Glossary

| Term | Definition |
|------|------------|
| **D1 Date** | First day of the sales period (Day 1) |
| **DL Date** | Last day of the sales period (Day Last) |
| **Sales Period** | Custom business cycle, may span two calendar months |
| **Wholesale Rate** | Purchase cost per unit (your cost) |
| **Retail/Selling Rate** | Selling price per unit (customer price) |
| **Overstock Multiplier** | Threshold factor for identifying slow-moving inventory |
| **Stock Ratio** | Current stock relative to overstock threshold |
| **Stock Days** | Number of days current stock will last at current sales rate |
| **Aggregated Data** | Combined data from multiple sales periods |
| **Velocity** | Speed at which a brand sells (sales per day) |

---

## Version Information
**Document Version**: 2.0  
**Last Updated**: December 2025  
**Application Version**: Latest (with Multi-Period Selection Feature)

---

**End of User Guide**
