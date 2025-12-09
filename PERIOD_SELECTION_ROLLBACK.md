# Period Selection Feature - Rollback Instructions

This document contains instructions to rollback the period selection feature for report generation.

## Feature Added
- Period selection modal before generating reports
- Multi-period aggregation for reports
- User can select one or more sales periods to include in reports

## Files Modified/Created

### New Files (DELETE to rollback):
1. `/app/frontend/src/components/PeriodSelectionModal.js`

### Modified Files (REVERT changes):
1. `/app/frontend/src/App.js`
2. `/app/backend/server.py`

## Rollback Steps

### Step 1: Delete New Component
```bash
rm -f /app/frontend/src/components/PeriodSelectionModal.js
```

### Step 2: Revert App.js Changes

Remove the import:
```javascript
// REMOVE THIS LINE:
import PeriodSelectionModal from "./components/PeriodSelectionModal";
```

Remove the state variables:
```javascript
// REMOVE THESE:
const [showPeriodSelectionModal, setShowPeriodSelectionModal] = useState(false);
const [selectedReportType, setSelectedReportType] = useState('pdf');
const [selectedReportPeriods, setSelectedReportPeriods] = useState([]);
```

Remove new handlers and revert to original:
```javascript
// REMOVE THESE FUNCTIONS:
// - handlePeriodSelectionComplete
// - generateReport

// REVERT TO ORIGINAL:
const handleGenerateExcelReport = async () => {
  try {
    setGeneratingReport(true);
    
    const response = await axios.post(`${API}/reports/generate-excel`, {}, {
      responseType: 'blob'
    });
    
    // ... rest of original code (create download link, etc.)
  }
};

const handleGeneratePDFReport = async () => {
  try {
    setGeneratingReport(true);
    
    const response = await axios.post(`${API}/reports/generate-pdf`, reportParameters, {
      responseType: 'blob'
    });
    
    // ... rest of original code (create download link, etc.)
  }
};
```

Revert the PDF button:
```javascript
// CHANGE BACK TO:
<Button 
  size="sm"
  onClick={() => setShowReportModal(true)}
  disabled={loading || !hasData || generatingReport}
  className="bg-blue-600 hover:bg-blue-700 text-white text-xs h-9 whitespace-nowrap disabled:opacity-50"
>
  <FileText className="w-4 h-4 mr-2" />
  Generate PDF
</Button>
```

Remove the PeriodSelectionModal component from JSX (near end of file):
```javascript
// REMOVE THIS ENTIRE BLOCK:
<PeriodSelectionModal
  isOpen={showPeriodSelectionModal}
  onClose={() => setShowPeriodSelectionModal(false)}
  onGenerateReport={handlePeriodSelectionComplete}
  periods={historicalPeriods}
  reportType={selectedReportType}
  isGenerating={false}
/>
```

Remove the selected periods display from report modal:
```javascript
// REMOVE THIS BLOCK from inside the PDF Report Modal:
{selectedReportPeriods.length > 0 && (
  <div className="p-4 bg-blue-50 rounded-lg border border-blue-200">
    // ... period display code
  </div>
)}
```

### Step 3: Revert Backend Changes

In `/app/backend/server.py`:

1. Remove the `get_aggregated_period_data` function (entire function before `generate_monthly_report_data`)

2. Revert `generate_monthly_report_data` signature:
```python
# CHANGE BACK TO:
async def generate_monthly_report_data() -> MonthlyReportData:
    """Generate comprehensive monthly report data"""
    try:
        # Get all liquor data
        liquor_records = await collections.liquor_data.find().to_list(1000)
```

3. Revert Excel endpoint:
```python
# CHANGE BACK TO:
@api_router.post("/reports/generate-excel")
async def generate_excel_report():
    """Generate comprehensive Excel report with all data"""
    try:
        report_data = await generate_monthly_report_data()
```

4. Revert PDF endpoint:
```python
# CHANGE BACK TO:
@api_router.post("/reports/generate-pdf")
async def generate_pdf_report(params: ReportParameters):
    """Generate beautified PDF report with selected sections"""
    try:
        report_data = await generate_monthly_report_data()
```

5. Remove `selected_periods` field from ReportParameters model:
```python
# REMOVE THIS LINE:
selected_periods: list = []  # List of period IDs for multi-period reports
```

### Step 4: Restart Services
```bash
sudo supervisorctl restart backend
sudo supervisorctl restart frontend
```

## Quick Rollback Command
Run this single command to execute all rollback steps:
```bash
rm -f /app/frontend/src/components/PeriodSelectionModal.js && \
echo "Deleted PeriodSelectionModal.js - Now manually revert App.js and server.py changes as per instructions above" && \
echo "Then restart services with: sudo supervisorctl restart all"
```
