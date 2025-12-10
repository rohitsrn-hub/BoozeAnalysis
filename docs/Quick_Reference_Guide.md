# BoozeAnalysis - Quick Reference Guide
## Essential Instructions for New Users

---

## Getting Started in 5 Minutes

### 1. First-Time Data Upload

**Prepare Your Excel File**
```
Index | Brand Name      | W/Rate | S/Rate | 14-Nov-25 | 15-Nov-25 | ...
1     | Johnnie Walker  | 1200   | 1500   | 50        | 45        | ...
2     | Jack Daniels    | 1800   | 2200   | 30        | 28        | ...
```

**Upload Steps**
1. Click **"Upload Full Monthly Data"** button (top of dashboard)
2. Select your Excel file
3. Wait for success message
4. Dashboard populates automatically

---

## Daily Operations

### Every Day at Close
1. **Take Stock Count** - Record closing inventory
2. **Update Excel** - Add today's date and quantities
3. **Upload** - Click "Upload Today's Data"
4. **Verify** - Check metrics updated correctly

### Morning Review
- Check **Dashboard** tab for yesterday's sales
- Review **Alerts** for overstocked items
- Note **Forecast** recommendations for reordering

---

## Understanding Your Dashboard

### Key Metrics (Top Cards)
| Metric | What It Shows |
|--------|---------------|
| **Total Brands** | Number of products in catalog |
| **Total Stock Value** | Capital invested in inventory (₹) |
| **Overstocked Brands** | Items with excess inventory |
| **Overstocked Value** | Capital locked in slow movers (₹) |

### Main Tabs (Quick Reference)

| Tab | Purpose | When to Use |
|-----|---------|-------------|
| **Dashboard** | Charts & trends | Daily performance review |
| **Alerts** | Overstock warnings | Identify slow movers for promotions |
| **Top Brands** | Best performers | Understand what's selling well |
| **Sales History** | Past periods comparison | Monthly/quarterly analysis |
| **Forecast** | Reorder recommendations | Procurement planning |
| **Upload History** | Track uploads | Verify data integrity |
| **Database View** | Raw data | Detailed verification |

---

## Common Tasks

### Generate Monthly Report

**For Excel Report**
1. Click "Export Excel"
2. Select period(s) from the list
3. Click "Generate Excel Report"
4. File downloads automatically

**For PDF Report**
1. Click "Generate PDF"
2. Select period(s)
3. Click "Generate PDF Report"
4. Choose report sections
5. Click "Generate PDF Report" again
6. File downloads

### Adjust Overstock Sensitivity
- Find **Overstock Multiplier** slider (top right)
- Default: 3.0x
- **Lower** (2.0x): More strict - flags items earlier
- **Higher** (4.0x): More lenient - only severe cases

### Add New Brand
1. Click "Add New Brand" button
2. Fill in: Index, Name, Wholesale Rate, Retail Rate, Initial Stock
3. Click "Add Brand"
4. Brand appears in all analytics

### Update Prices
1. Prepare Excel with: Index, Brand Name, New Wholesale Rate, New Retail Rate
2. Click "Update Rates"
3. Upload file
4. All brands update automatically

---

## Monthly Cycle

### End of Month (Before Reset)
✓ Generate reports (Excel & PDF)  
✓ Create manual backup ("Create Backup" button)  
✓ Download backup for external storage  
✓ Review performance vs targets

### Start New Month (After Reset)
1. Click **"Reset Stock"** (around 20th of month)
2. Confirm reset (automatic backup created)
3. Upload new full monthly data with opening stock
4. Resume daily uploads

---

## Quick Troubleshooting

| Problem | Quick Fix |
|---------|-----------|
| **Date not detected** | Use format: 14-Nov-25 (not 14/11/25) |
| **Duplicate error** | Delete last upload from Upload History first |
| **No forecast** | Need minimum 7 days of data |
| **Charts not showing** | Click Refresh button or press F5 |
| **Upload slow** | Keep file size under 10MB, remove extra columns |

---

## Understanding Sales Calculations

### How System Calculates Sales
```
Daily Sales = Yesterday's Stock - Today's Stock
Example:
- 15-Nov: 50 units
- 16-Nov: 45 units
- Sales on 16-Nov = 50 - 45 = 5 units
```

### Your Sales Period
- **May Span 2 Calendar Months**
  - Example: 14-Nov-25 to 08-Dec-25 = "Nov-Dec 2025"
- **D1**: First date in your file = Period start
- **DL**: Last date in your file = Period end

### Overstock Logic
```
Brand is OVERSTOCKED when:
Current Stock > (Average Daily Sales × Multiplier)

Example (Multiplier = 3.0):
- Current Stock: 60 units
- Avg Daily Sales: 15 units
- Threshold: 15 × 3.0 = 45 units
- Result: 60 > 45 = OVERSTOCKED ⚠️
```

---

## File Format Requirements

### Full Monthly Data
✓ Must include: Index, Brand Name, Wholesale Rate, Retail Rate  
✓ Date columns: Use month abbreviations (Jan, Feb, Mar, Apr, May, Jun, Jul, Aug, Sep, Oct, Nov, Dec)  
✓ Format dates: DD-MMM-YY (e.g., 14-Nov-25)  
✓ Stock values: Plain numbers only  
✓ File type: .xlsx or .csv  
✗ Avoid: Blank rows, merged cells, formulas in data area

### Today's Data Upload
```
Brand Name      | Stock Qty
Johnnie Walker  | 38
Jack Daniels    | 20
```
Simple two-column format: Brand Name and Current Stock

---

## Top 5 Tips for Success

1. **Upload Daily Without Gaps**
   - Missing days cause incorrect calculations
   - Set a reminder for end-of-day upload

2. **Verify After Every Upload**
   - Check Database View for new date column
   - Review metrics for anomalies

3. **Backup Before Reset**
   - Always create manual backup before monthly reset
   - Download and store externally

4. **Use Consistent Date Format**
   - Stick to DD-MMM-YY throughout
   - System auto-detects columns with month names

5. **Review Forecast Weekly**
   - Don't wait for stockouts
   - Critical items need immediate action
   - High priority items: order within 1-2 days

---

## Multi-Period Reports Feature

### When to Use
- **Quarterly Reviews**: Select 3 consecutive periods
- **Half-Yearly Analysis**: Select 6 periods
- **Custom Date Range**: Select any combination

### How It Works
1. Click "Export Excel" or "Generate PDF"
2. **Period Selection Modal Opens**
3. Click on periods to select (checkboxes appear)
4. Multiple selections combine data automatically
5. Report shows aggregated totals across all selected periods

**Example**:
- Select: Sep-Oct 2025 + Oct-Nov 2025 + Nov-Dec 2025
- Report shows: Combined Q4 2025 performance
- Sales totals: Sum of all three months
- Period label: "Sep-Oct 2025 to Nov-Dec 2025"

---

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| **F5** or **Ctrl+R** | Refresh dashboard |
| **Tab** | Move between fields |
| **Enter** | Submit/Confirm |
| **Esc** | Close dialog |

---

## Need Help?

**During Work**
- Click **? (Help Icon)** in top right corner
- Context-sensitive guidance for current section

**For Issues**
- Check troubleshooting table above
- Take screenshot of error
- Note: What were you doing, what was the error message

---

## Key Definitions

| Term | Meaning |
|------|---------|
| **D1** | First day of your sales period |
| **DL** | Last day of your sales period |
| **W/Rate** | Wholesale Rate (your cost) |
| **S/Rate** | Selling/Retail Rate (customer price) |
| **Stock Days** | How many days current stock will last |
| **Multiplier** | Threshold for overstock alerts (default 3x) |

---

## Important Reminders

⚠️ **Never Skip Daily Uploads** - Breaks sales calculations  
⚠️ **Backup Before Reset** - Data loss otherwise  
⚠️ **Use Correct Date Format** - DD-MMM-YY only  
⚠️ **Check Forecasts Regularly** - Avoid stockouts  
⚠️ **Reset Around 20th** - After stock replenishment

---

## Quick Start Checklist

Day 1:
- [ ] Prepare Excel file with all columns
- [ ] Upload Full Monthly Data
- [ ] Verify data in Database View
- [ ] Set Overstock Multiplier to 3.0
- [ ] Review Dashboard charts

Daily:
- [ ] Record closing stock
- [ ] Upload Today's Data
- [ ] Check Alerts tab
- [ ] Review Forecast for reorders

Weekly:
- [ ] Compare performance in Sales History
- [ ] Plan promotions for overstocked items
- [ ] Verify Upload History for completeness

Monthly:
- [ ] Generate Excel and PDF reports
- [ ] Create manual backup
- [ ] Reset stock around 20th
- [ ] Upload new period's opening data

---

**Quick Reference Guide v2.0**  
**For Comprehensive Guide**: See Full User Manual  
**Last Updated**: December 2025

---

**Print this page and keep handy for daily reference!**
