import { useState, useEffect } from "react";
import "./App.css";
import axios from "axios";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "./components/ui/card";
import { Button } from "./components/ui/button";
import { Input } from "./components/ui/input";
import { Label } from "./components/ui/label";
import { Alert, AlertDescription } from "./components/ui/alert";
import { Badge } from "./components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "./components/ui/tabs";
import { Progress } from "./components/ui/progress";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from "./components/ui/dialog";
import { Upload, TrendingUp, AlertTriangle, BarChart3, Package, DollarSign, Calendar, FileSpreadsheet, HelpCircle, Play, CheckCircle, ArrowRight, Download, Zap, Target, Crown, History, Database, RefreshCw } from "lucide-react";
import { toast } from "sonner";
import { Toaster } from "./components/ui/sonner";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell, LineChart, Line } from "recharts";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

function App() {
  const [analyticsData, setAnalyticsData] = useState(null);
  const [chartsData, setChartsData] = useState(null);
  const [demandData, setDemandData] = useState(null);
  const [calculationData, setCalculationData] = useState(null);
  const [uploadHistory, setUploadHistory] = useState([]);
  const [loading, setLoading] = useState(false);
  const [overstockMultiplier, setOverstockMultiplier] = useState(3.0);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [hasData, setHasData] = useState(false);
  const [showOnboarding, setShowOnboarding] = useState(false);
  const [showUploadHistory, setShowUploadHistory] = useState(false);
  const [showDuplicateDialog, setShowDuplicateDialog] = useState(false);
  const [duplicateError, setDuplicateError] = useState(null);
  const [databaseView, setDatabaseView] = useState(null);
  const [currentDateRange, setCurrentDateRange] = useState(null);
  const [onboardingStep, setOnboardingStep] = useState(0);

  // Module 1: Brand Management state
  const [showBrandModal, setShowBrandModal] = useState(false);
  const [showRatesModal, setShowRatesModal] = useState(false);
  const [brandFormData, setBrandFormData] = useState({
    index_number: '',
    brand_name: '',
    wholesale_rate: '',
    selling_rate: '',
    initial_stock_qty: 0
  });
  const [ratesFile, setRatesFile] = useState(null);

  // Module 3: Stock Reset & Backup state
  const [showResetDialog, setShowResetDialog] = useState(false);
  const [showBackupsDialog, setShowBackupsDialog] = useState(false);
  const [backupsList, setBackupsList] = useState([]);
  const [resetting, setResetting] = useState(false);

  // Module 4: Monthly Report Generation state
  const [showReportModal, setShowReportModal] = useState(false);
  const [reportParameters, setReportParameters] = useState({
    include_executive_summary: true,
    include_top_sellers: true,
    include_slow_sellers: true,
    include_capital_blockers: true,
    include_revenue_analysis: true,
    include_demand_forecast: true,
    include_profit_analysis: true,
    include_recommendations: true,
    include_datewise_analysis: false,
    report_title: "Monthly Sales Analytics Report",
    report_period: ""
  });
  const [generatingReport, setGeneratingReport] = useState(false);

  // Fetch all data
  const fetchAnalytics = async (multiplier = 3.0) => {
    try {
      setLoading(true);
      
      // Fetch analytics data
      const analyticsResponse = await axios.get(`${API}/analytics?overstock_multiplier=${multiplier}`);
      setAnalyticsData(analyticsResponse.data);
      
      // Fetch charts data
      const chartsResponse = await axios.get(`${API}/charts`);
      setChartsData(chartsResponse.data);
      
      // Fetch demand recommendations
      const demandResponse = await axios.get(`${API}/demand-recommendations`);
      setDemandData(demandResponse.data);
      
      // Fetch calculation details
      const calculationResponse = await axios.get(`${API}/calculation-details`);
      setCalculationData(calculationResponse.data);
      
      // Fetch database view
      const databaseResponse = await axios.get(`${API}/database-view`);
      setDatabaseView(databaseResponse.data);
      
      // Extract current D1/DL dates for header display from calculation data
      try {
        if (calculationResponse.data && calculationResponse.data.length > 0) {
          const firstRecord = calculationResponse.data[0];
          if (firstRecord.D1_date && firstRecord.DL_date) {
            // Format dates for display
            const formatDateForDisplay = (dateStr) => {
              try {
                if (!dateStr) return 'N/A';
                
                // Handle different date formats
                if (dateStr.includes('T') || dateStr.includes('00:00:00')) {
                  // It's a full datetime string like "2025-10-04 00:00:00"
                  const date = new Date(dateStr);
                  if (isNaN(date.getTime())) return dateStr; // Invalid date
                  
                  const day = date.getDate().toString().padStart(2, '0');
                  const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
                  const month = months[date.getMonth()];
                  const year = date.getFullYear().toString().slice(-2);
                  return `${day}-${month}-${year}`;
                } else {
                  // It's already in format like "20-Sep-25"
                  return dateStr;
                }
              } catch (e) {
                console.warn('Error formatting date:', dateStr, e);
                return dateStr; // Return as-is if parsing fails
              }
            };

            setCurrentDateRange({
              d1_date: formatDateForDisplay(firstRecord.D1_date),
              dl_date: formatDateForDisplay(firstRecord.DL_date)
            });
          }
        }
      } catch (e) {
        console.warn('Error extracting date range:', e);
      }
      
      setHasData(true);
      toast.success("Analytics updated successfully");
    } catch (error) {
      console.error("Error fetching data:", error);
      if (error.response?.status === 404) {
        setHasData(false);
        toast.error("No data found. Please upload liquor data first.");
      } else {
        toast.error(`Failed to fetch data: ${error.message}`);
      }
    } finally {
      setLoading(false);
    }
  };

  // Fetch upload history
  const fetchUploadHistory = async () => {
    try {
      const response = await axios.get(`${API}/upload-history`);
      setUploadHistory(response.data);
    } catch (error) {
      console.error("Error fetching upload history:", error);
      toast.error("Failed to fetch upload history");
    }
  };

  // Handle full monthly data upload
  const handleFullMonthlyUpload = async (event) => {
    const file = event.target.files[0];
    if (!file) return;

    const formData = new FormData();
    formData.append("file", file);

    try {
      setLoading(true);
      setUploadProgress(10);
      
      const response = await axios.post(`${API}/upload-full-monthly-data`, formData, {
        headers: {
          "Content-Type": "multipart/form-data",
        },
        onUploadProgress: (progressEvent) => {
          const progress = Math.round((progressEvent.loaded * 100) / progressEvent.total);
          setUploadProgress(progress);
        },
      });

      setUploadProgress(100);
      toast.success(`Successfully uploaded full monthly data: ${response.data.total_records} records`);
      
      // Fetch analytics and upload history after successful upload
      await fetchAnalytics(overstockMultiplier);
      await fetchUploadHistory();
      
    } catch (error) {
      console.error("Error uploading full monthly data:", error);
      
      let errorMessage = "Failed to upload file";
      
      if (error.response?.data?.detail) {
        if (typeof error.response.data.detail === 'object') {
          errorMessage = error.response.data.detail.message || errorMessage;
        } else {
          errorMessage = error.response.data.detail;
        }
      }
      
      if (errorMessage.includes("Invalid file type")) {
        toast.error("Please upload an Excel file (.xlsx, .xls) or CSV file");
      } else {
        toast.error(errorMessage);
      }
    } finally {
      setLoading(false);
      setUploadProgress(0);
      event.target.value = "";
    }
  };

  // Handle today's data upload
  const handleTodaysDataUpload = async (event) => {
    const file = event.target.files[0];
    if (!file) return;

    const formData = new FormData();
    formData.append("file", file);

    try {
      setLoading(true);
      setUploadProgress(10);
      
      const response = await axios.post(`${API}/upload-todays-data`, formData, {
        headers: {
          "Content-Type": "multipart/form-data",
        },
        onUploadProgress: (progressEvent) => {
          const progress = Math.round((progressEvent.loaded * 100) / progressEvent.total);
          setUploadProgress(progress);
        },
      });

      setUploadProgress(100);
      toast.success(`Today's data updated: ${response.data.updated_brands} brands updated, ${response.data.new_brands} new brands added`);
      
      // Fetch analytics and upload history after successful upload
      await fetchAnalytics(overstockMultiplier);
      await fetchUploadHistory();
      
    } catch (error) {
      console.error("Error uploading today's data:", error);
      
      let errorMessage = "Failed to upload today's data";
      
      if (error.response?.data?.detail) {
        const detail = error.response.data.detail;
        
        // Handle duplicate date error specially
        if (error.response.status === 409 && typeof detail === 'object' && detail.error === "Duplicate dates detected") {
          setDuplicateError({
            duplicateDates: detail.duplicate_dates,
            filename: detail.filename,
            suggestion: detail.suggestion,
            existing_dates_found: detail.existing_dates_found || []
          });
          setShowDuplicateDialog(true);
          return; // Exit early for duplicate date error
        }
        
        // Handle other errors
        if (typeof detail === 'object') {
          errorMessage = detail.message || errorMessage;
          
          // Show available columns if provided
          if (detail.available_columns && Array.isArray(detail.available_columns)) {
            const columns = detail.available_columns.join(', ');
            errorMessage += `\n\nColumns found in your file: ${columns}`;
          }
          
          // Show additional suggestions if available
          if (detail.suggestions && Array.isArray(detail.suggestions)) {
            const suggestions = detail.suggestions.map(s => `• ${s}`).join('\n');
            errorMessage += `\n\nSuggestions:\n${suggestions}`;
          }
        } else {
          errorMessage = detail;
        }
      }
      
      toast.error(errorMessage);
    } finally {
      setLoading(false);
      setUploadProgress(0);
      event.target.value = "";
    }
  };

  // Handle file upload (legacy - keeping for backward compatibility)
  const handleFileUpload = async (event) => {
    const file = event.target.files[0];
    if (!file) return;

    const formData = new FormData();
    formData.append("file", file);

    try {
      setLoading(true);
      setUploadProgress(10);
      
      const response = await axios.post(`${API}/upload-data`, formData, {
        headers: {
          "Content-Type": "multipart/form-data",
        },
        onUploadProgress: (progressEvent) => {
          const progress = Math.round((progressEvent.loaded * 100) / progressEvent.total);
          setUploadProgress(progress);
        },
      });

      setUploadProgress(100);
      toast.success(`Successfully uploaded ${response.data.total_records} records`);
      
      // Fetch analytics and upload history after successful upload
      await fetchAnalytics(overstockMultiplier);
      await fetchUploadHistory();
      
    } catch (error) {
      console.error("Error uploading file:", error);
      
      // Better error handling for file upload
      let errorMessage = "Failed to upload file";
      
      if (error.response?.data?.detail) {
        if (typeof error.response.data.detail === 'object') {
          errorMessage = error.response.data.detail.message || errorMessage;
        } else {
          errorMessage = error.response.data.detail;
        }
      }
      
      // Show helpful error messages
      if (errorMessage.includes("Invalid file type")) {
        toast.error("Please upload an Excel file (.xlsx, .xls) or CSV file");
      } else if (errorMessage.includes("Insufficient numerical data")) {
        toast.error("File format incorrect. Please check the data structure in your Excel file");
      } else {
        toast.error(errorMessage);
      }
    } finally {
      setLoading(false);
      setUploadProgress(0);
      // Clear file input
      event.target.value = "";
    }
  };

  // Handle multiplier change
  const handleMultiplierChange = async () => {
    if (hasData) {
      await fetchAnalytics(overstockMultiplier);
    }
  };

  // Handle manual refresh
  const handleManualRefresh = async () => {
    try {
      setLoading(true);
      toast.info("Refreshing all data...");
      
      // Call backend refresh endpoint first
      await axios.post(`${API}/refresh-analytics`);
      
      // Then fetch ALL updated data sources
      await fetchAnalytics(overstockMultiplier);
      await fetchUploadHistory();
      
      toast.success("All data refreshed successfully!");
    } catch (error) {
      console.error("Error refreshing analytics:", error);
      toast.error("Failed to refresh data");
    } finally {
      setLoading(false);
    }
  };

  // Handle demand forecast export
  const handleExportDemandList = async () => {
    try {
      const response = await axios.get(`${API}/export-demand-list`, {
        responseType: 'blob',
      });
      
      // Create blob link to download
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      
      // Get filename from response headers or use default
      const contentDisposition = response.headers['content-disposition'];
      const filename = contentDisposition 
        ? contentDisposition.split('filename=')[1].replace(/"/g, '')
        : `liquor_demand_forecast_${new Date().toISOString().split('T')[0]}.xlsx`;
      
      link.setAttribute('download', filename);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
      
      toast.success("Demand forecast exported successfully!");
    } catch (error) {
      console.error("Error exporting demand forecast:", error);
      toast.error("Failed to export demand forecast");
    }
  };

  // Module 1: Brand Management handlers
  const handleAddBrand = async (e) => {
    e.preventDefault();
    
    try {
      setLoading(true);
      
      const response = await axios.post(`${API}/brands/add`, {
        index_number: parseInt(brandFormData.index_number),
        brand_name: brandFormData.brand_name,
        wholesale_rate: parseFloat(brandFormData.wholesale_rate),
        selling_rate: parseFloat(brandFormData.selling_rate),
        initial_stock_qty: parseInt(brandFormData.initial_stock_qty) || 0
      });
      
      toast.success(response.data.message);
      setShowBrandModal(false);
      
      // Reset form
      setBrandFormData({
        index_number: '',
        brand_name: '',
        wholesale_rate: '',
        selling_rate: '',
        initial_stock_qty: 0
      });
      
      // Refresh analytics if data exists
      if (hasData) {
        await fetchAnalytics(overstockMultiplier);
      }
      
    } catch (error) {
      console.error("Error adding brand:", error);
      const errorMessage = error.response?.data?.detail || "Failed to add brand";
      toast.error(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  const handleUpdateRates = async (e) => {
    e.preventDefault();
    
    if (!ratesFile) {
      toast.error("Please select an Excel file");
      return;
    }
    
    try {
      setLoading(true);
      
      const formData = new FormData();
      formData.append("file", ratesFile);
      
      const response = await axios.post(`${API}/brands/update-rates`, formData, {
        headers: {
          "Content-Type": "multipart/form-data",
        },
      });
      
      const result = response.data;
      
      if (result.updated_count > 0) {
        toast.success(`Successfully updated ${result.updated_count} brand(s)`);
      }
      
      if (result.not_found_count > 0) {
        toast.warning(`${result.not_found_count} brand(s) not found: ${result.not_found_brands.slice(0, 3).join(', ')}${result.not_found_brands.length > 3 ? '...' : ''}`);
      }
      
      setShowRatesModal(false);
      setRatesFile(null);
      
      // Refresh analytics
      if (hasData) {
        await fetchAnalytics(overstockMultiplier);
      }
      
    } catch (error) {
      console.error("Error updating rates:", error);
      const errorMessage = error.response?.data?.detail || "Failed to update rates";
      toast.error(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  // Module 3: Stock Reset & Backup handlers
  const fetchBackups = async () => {
    try {
      const response = await axios.get(`${API}/stock/backups`);
      setBackupsList(response.data);
    } catch (error) {
      console.error("Error fetching backups:", error);
      toast.error("Failed to fetch backups");
    }
  };

  const handleStockReset = async () => {
    try {
      setResetting(true);
      
      const response = await axios.post(`${API}/stock/reset`);
      
      toast.success(`Stock reset successful! ${response.data.records_deleted} records deleted. Backup ID: ${response.data.backup_id}`);
      
      setShowResetDialog(false);
      setHasData(false);
      
      // Refresh backups list
      await fetchBackups();
      
    } catch (error) {
      console.error("Error resetting stock:", error);
      const errorMessage = error.response?.data?.detail || "Failed to reset stock";
      toast.error(errorMessage);
    } finally {
      setResetting(false);
    }
  };

  const handleDownloadBackup = async (backupId, timestamp) => {
    try {
      const response = await axios.get(`${API}/stock/backup/${backupId}/download`, {
        responseType: 'blob',
      });
      
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      
      const filename = `stock_backup_${new Date(timestamp).toISOString().split('T')[0]}.xlsx`;
      link.setAttribute('download', filename);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
      
      toast.success("Backup downloaded successfully!");
    } catch (error) {
      console.error("Error downloading backup:", error);
      toast.error("Failed to download backup");
    }
  };

  const handleCreateBackup = async () => {
    try {
      setLoading(true);
      
      const response = await axios.post(`${API}/stock/backup?reason=manual_backup`);
      
      toast.success(`Backup created! ${response.data.total_records} records backed up.`);
      
      await fetchBackups();
      
    } catch (error) {
      console.error("Error creating backup:", error);
      const errorMessage = error.response?.data?.detail || "Failed to create backup";
      toast.error(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteBackup = async (backupId, backupReason) => {
    if (!window.confirm(`Are you sure you want to delete this backup?\n\nReason: ${backupReason}\n\nThis action cannot be undone.`)) {
      return;
    }
    
    try {
      setLoading(true);
      
      await axios.delete(`${API}/stock/backup/${backupId}`);
      
      toast.success("Backup deleted successfully!");
      
      await fetchBackups();
      
    } catch (error) {
      console.error("Error deleting backup:", error);
      const errorMessage = error.response?.data?.detail || "Failed to delete backup";
      toast.error(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  // Module 4: Report Generation Handlers
  const handleGenerateExcelReport = async () => {
    try {
      setGeneratingReport(true);
      
      const response = await axios.post(`${API}/reports/generate-excel`, {}, {
        responseType: 'blob'
      });
      
      // Create download link
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      
      // Extract filename from response headers
      const contentDisposition = response.headers['content-disposition'];
      let filename = 'monthly_report.xlsx';
      if (contentDisposition) {
        const filenameMatch = contentDisposition.match(/filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/);
        if (filenameMatch && filenameMatch[1]) {
          filename = filenameMatch[1].replace(/['"]/g, '');
        }
      }
      
      link.setAttribute('download', filename);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
      
      toast.success("Excel report generated successfully!");
      
    } catch (error) {
      console.error("Error generating Excel report:", error);
      const errorMessage = error.response?.data?.detail || "Failed to generate Excel report";
      toast.error(errorMessage);
    } finally {
      setGeneratingReport(false);
    }
  };

  const handleGeneratePDFReport = async () => {
    try {
      setGeneratingReport(true);
      
      const response = await axios.post(`${API}/reports/generate-pdf`, reportParameters, {
        responseType: 'blob'
      });
      
      // Create download link
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      
      // Extract filename from response headers
      const contentDisposition = response.headers['content-disposition'];
      let filename = 'monthly_report.pdf';
      if (contentDisposition) {
        const filenameMatch = contentDisposition.match(/filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/);
        if (filenameMatch && filenameMatch[1]) {
          filename = filenameMatch[1].replace(/['"]/g, '');
        }
      }
      
      link.setAttribute('download', filename);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
      
      toast.success("PDF report generated successfully!");
      setShowReportModal(false);
      
    } catch (error) {
      console.error("Error generating PDF report:", error);
      const errorMessage = error.response?.data?.detail || "Failed to generate PDF report";
      toast.error(errorMessage);
    } finally {
      setGeneratingReport(false);
    }
  };

  const handleReportParameterChange = (key, value) => {
    setReportParameters(prev => ({
      ...prev,
      [key]: value
    }));
  };

  // Format currency
  const formatCurrency = (amount) => {
    return new Intl.NumberFormat("en-IN", {
      style: "currency",
      currency: "INR",
      maximumFractionDigits: 0,
    }).format(amount);
  };

  // Format number
  const formatNumber = (number) => {
    return new Intl.NumberFormat("en-IN").format(number);
  };

  // Format date
  const formatDate = (dateString) => {
    try {
      const date = new Date(dateString);
      return date.toLocaleString("en-IN", {
        year: "numeric",
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
        timeZone: "Asia/Kolkata"
      });
    } catch {
      return dateString;
    }
  };

  // Format file size
  const formatFileSize = (bytes) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  // Chart colors
  const CHART_COLORS = [
    '#3B82F6', '#EF4444', '#10B981', '#F59E0B', '#8B5CF6',
    '#F97316', '#06B6D4', '#84CC16', '#EC4899', '#6366F1'
  ];

  // Onboarding content
  const onboardingSteps = [
    {
      title: "Welcome to Liquor Sales Analytics! 🎯",
      content: (
        <div className="space-y-4">
          <p className="text-gray-600 leading-relaxed">
            This dashboard helps you analyze your liquor sales patterns and identify overstocking issues. 
            Let's take a quick tour to get you started!
          </p>
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
            <h4 className="font-semibold text-blue-900 mb-2">What you can do:</h4>
            <ul className="text-blue-800 space-y-1 text-sm">
              <li>• Upload Excel/CSV files with sales data</li>
              <li>• Track daily sales trends across all brands</li>
              <li>• Identify overstocked items automatically</li>
              <li>• Compare brand performance rankings</li>
              <li>• Configure overstock thresholds (3x rule by default)</li>
            </ul>
          </div>
        </div>
      )
    },
    {
      title: "Step 1: Upload Your Data 📊",
      content: (
        <div className="space-y-4">
          <p className="text-gray-600">
            Start by uploading your liquor sales Excel file. The system supports .xlsx, .xls, and .csv formats.
          </p>
          <div className="bg-green-50 border border-green-200 rounded-lg p-4">
            <h4 className="font-semibold text-green-900 mb-2">Required columns in your file:</h4>
            <ul className="text-green-800 space-y-1 text-sm">
              <li>• <strong>Brand Name</strong> - Name of the liquor brand</li>
              <li>• <strong>Rate</strong> - Price per unit</li>
              <li>• <strong>Date columns</strong> - Daily sales quantities (e.g., 25-Aug-25, 26-Aug-25)</li>
              <li>• <strong>Monthly Sale value (a)</strong> - Total monthly sales value</li>
              <li>• <strong>Stock value Today</strong> - Current stock value</li>
            </ul>
          </div>
          <div className="flex items-center space-x-2 text-sm text-gray-600">
            <FileSpreadsheet className="w-4 h-4" />
            <span>Click the "Upload Data" button in the top-right corner</span>
          </div>
        </div>
      )
    },
    {
      title: "Step 2: Configure Overstock Settings ⚙️",
      content: (
        <div className="space-y-4">
          <p className="text-gray-600">
            Set your overstock multiplier to define what constitutes overstocking. The default is 3x monthly average.
          </p>
          <div className="bg-orange-50 border border-orange-200 rounded-lg p-4">
            <h4 className="font-semibold text-orange-900 mb-2">How it works:</h4>
            <div className="text-orange-800 space-y-2 text-sm">
              <p>• <strong>3x multiplier</strong>: Items with stock &gt; 3× monthly sales = overstocked</p>
              <p>• <strong>2x multiplier</strong>: Items with stock &gt; 2× monthly sales = overstocked</p>
              <p>• Lower multipliers = more brands flagged as overstocked</p>
            </div>
          </div>
          <div className="flex items-center space-x-2 text-sm text-gray-600">
            <AlertTriangle className="w-4 h-4" />
            <span>Adjust the multiplier in the header and click "Update"</span>
          </div>
        </div>
      )
    },
    {
      title: "Step 3: Analyze Your Data 📈",
      content: (
        <div className="space-y-4">
          <p className="text-gray-600">
            Explore three main sections to analyze your liquor business:
          </p>
          <div className="grid gap-4">
            <div className="bg-blue-50 border border-blue-200 rounded-lg p-3">
              <div className="flex items-center space-x-2 mb-2">
                <TrendingUp className="w-4 h-4 text-blue-600" />
                <strong className="text-blue-900">Sales Trends</strong>
              </div>
              <p className="text-blue-800 text-sm">View daily sales performance across all brands over time</p>
            </div>
            <div className="bg-orange-50 border border-orange-200 rounded-lg p-3">
              <div className="flex items-center space-x-2 mb-2">
                <AlertTriangle className="w-4 h-4 text-orange-600" />
                <strong className="text-orange-900">Overstocking Alerts</strong>
              </div>
              <p className="text-orange-800 text-sm">Identify brands with excessive stock and calculate overstock values</p>
            </div>
            <div className="bg-green-50 border border-green-200 rounded-lg p-3">
              <div className="flex items-center space-x-2 mb-2">
                <BarChart3 className="w-4 h-4 text-green-600" />
                <strong className="text-green-900">Brand Performance</strong>
              </div>
              <p className="text-green-800 text-sm">Compare top-performing brands by sales value and stock ratios</p>
            </div>
          </div>
        </div>
      )
    },
    {
      title: "Ready to Get Started! 🚀",
      content: (
        <div className="space-y-4">
          <p className="text-gray-600">
            You're all set! Here's a quick checklist to get the most out of your dashboard:
          </p>
          <div className="space-y-3">
            <div className="flex items-center space-x-3">
              <CheckCircle className="w-5 h-5 text-green-600" />
              <span className="text-gray-800">Upload your Excel file with liquor sales data</span>
            </div>
            <div className="flex items-center space-x-3">
              <CheckCircle className="w-5 h-5 text-green-600" />
              <span className="text-gray-800">Review key metrics in the top dashboard cards</span>
            </div>
            <div className="flex items-center space-x-3">
              <CheckCircle className="w-5 h-5 text-green-600" />
              <span className="text-gray-800">Check overstocking alerts to optimize inventory</span>
            </div>
            <div className="flex items-center space-x-3">
              <CheckCircle className="w-5 h-5 text-green-600" />
              <span className="text-gray-800">Analyze brand performance to focus on winners</span>
            </div>
            <div className="flex items-center space-x-3">
              <CheckCircle className="w-5 h-5 text-green-600" />
              <span className="text-gray-800">Adjust overstock multiplier as needed</span>
            </div>
          </div>
          <div className="bg-gradient-to-r from-indigo-50 to-purple-50 border border-indigo-200 rounded-lg p-4 mt-6">
            <p className="text-indigo-800 text-center font-medium">
              💡 Pro Tip: Start with the default 3x multiplier and adjust based on your business needs!
            </p>
          </div>
        </div>
      )
    }
  ];

  // Initialize
  useEffect(() => {
    fetchAnalytics();
    fetchUploadHistory();
  }, []);

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 via-indigo-50 to-purple-50">
      <Toaster position="top-right" />
      
      {/* Header */}
      <div className="bg-white border-b shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <div className="p-2 bg-indigo-100 rounded-lg">
                <BarChart3 className="h-8 w-8 text-indigo-600" />
              </div>
              <div>
                <h1 className="text-2xl font-bold text-gray-900">Liquor Sales Analytics</h1>
                <div className="flex items-center space-x-4">
                  <p className="text-sm text-gray-600">D1=First Date Column | DL=Last Date Column | CORRECTED Calculations</p>
                  {currentDateRange && (
                    <div className="flex items-center space-x-2 px-3 py-1 bg-blue-50 border border-blue-200 rounded-lg">
                      <Calendar className="w-4 h-4 text-blue-600" />
                      <span className="text-xs font-medium text-blue-800">
                        Current: D1={currentDateRange.d1_date} | DL={currentDateRange.dl_date}
                      </span>
                    </div>
                  )}
                </div>
              </div>
            </div>
            
            <div className="flex flex-col lg:flex-row items-end lg:items-center space-y-3 lg:space-y-0 lg:space-x-4">
              <div className="flex items-center space-x-2">
                {/* Refresh Button */}
                <Button
                  onClick={handleManualRefresh}
                  variant="outline"
                  size="sm"
                  className="bg-white hover:bg-gray-50 text-xs"
                  disabled={loading}
                  data-testid="refresh-analytics-btn"
                >
                  <RefreshCw className={`w-3 h-3 mr-1 ${loading ? 'animate-spin' : ''}`} />
                  {loading ? 'Refreshing...' : 'Refresh'}
                </Button>
                
                {/* Help Guide */}
                <Dialog open={showOnboarding} onOpenChange={setShowOnboarding}>
                  <DialogTrigger asChild>
                    <Button 
                      variant="outline" 
                      size="sm"
                      className="bg-white hover:bg-gray-50 text-xs"
                      data-testid="help-guide-btn"
                    >
                      <HelpCircle className="w-3 h-3 mr-1" />
                      Help
                    </Button>
                  </DialogTrigger>
                <DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto">
                  <DialogHeader>
                    <DialogTitle className="flex items-center space-x-2">
                      <Play className="w-5 h-5 text-indigo-600" />
                      <span>{onboardingSteps[onboardingStep].title}</span>
                    </DialogTitle>
                    <DialogDescription>
                      Step {onboardingStep + 1} of {onboardingSteps.length}
                    </DialogDescription>
                  </DialogHeader>
                  
                  <div className="mt-6">
                    {onboardingSteps[onboardingStep].content}
                  </div>
                  
                  <div className="flex items-center justify-between mt-8">
                    <div className="flex space-x-1">
                      {onboardingSteps.map((_, index) => (
                        <div
                          key={index}
                          className={`w-2 h-2 rounded-full transition-colors ${
                            index <= onboardingStep ? 'bg-indigo-600' : 'bg-gray-300'
                          }`}
                        />
                      ))}
                    </div>
                    
                    <div className="flex space-x-2">
                      {onboardingStep > 0 && (
                        <Button
                          variant="outline"
                          onClick={() => setOnboardingStep(onboardingStep - 1)}
                          size="sm"
                        >
                          Previous
                        </Button>
                      )}
                      
                      {onboardingStep < onboardingSteps.length - 1 ? (
                        <Button
                          onClick={() => setOnboardingStep(onboardingStep + 1)}
                          size="sm"
                          className="bg-indigo-600 hover:bg-indigo-700"
                        >
                          Next
                          <ArrowRight className="w-4 h-4 ml-1" />
                        </Button>
                      ) : (
                        <Button
                          onClick={() => {
                            setShowOnboarding(false);
                            setOnboardingStep(0);
                          }}
                          size="sm"
                          className="bg-green-600 hover:bg-green-700"
                        >
                          <CheckCircle className="w-4 h-4 mr-1" />
                          Get Started!
                        </Button>
                      )}
                    </div>
                  </div>
                </DialogContent>
              </Dialog>

                {/* Upload History Button */}
                <Dialog open={showUploadHistory} onOpenChange={setShowUploadHistory}>
                  <DialogTrigger asChild>
                    <Button 
                      variant="outline" 
                      size="sm"
                      className="bg-white hover:bg-gray-50 text-xs"
                      data-testid="upload-history-btn"
                    >
                      <History className="w-3 h-3 mr-1" />
                      History
                    </Button>
                  </DialogTrigger>
                  <DialogContent className="max-w-4xl max-h-[80vh] overflow-y-auto">
                    <DialogHeader>
                      <DialogTitle className="flex items-center space-x-2">
                        <History className="w-5 h-5 text-indigo-600" />
                        <span>Upload History</span>
                      </DialogTitle>
                      <DialogDescription>
                        Track all uploaded Excel files and data changes
                      </DialogDescription>
                    </DialogHeader>
                    
                    <div className="mt-6">
                      {uploadHistory.length > 0 ? (
                        <div className="space-y-4">
                          {uploadHistory.map((upload, index) => (
                            <div key={index} className="border border-gray-200 rounded-lg p-4 hover:bg-gray-50">
                              <div className="flex items-center justify-between mb-2">
                                <div className="flex items-center space-x-3">
                                  <div className={`p-2 rounded-lg ${
                                    upload.upload_type === 'full_monthly' 
                                      ? 'bg-green-100 text-green-600'
                                      : 'bg-orange-100 text-orange-600'
                                  }`}>
                                    {upload.upload_type === 'full_monthly' ? <Database className="w-4 h-4" /> : <RefreshCw className="w-4 h-4" />}
                                  </div>
                                  <div>
                                    <h4 className="font-semibold text-gray-900">{upload.filename}</h4>
                                    <p className="text-sm text-gray-600">
                                      {upload.upload_type === 'full_monthly' ? 'Full Monthly Data' : "Today's Data Update"}
                                    </p>
                                  </div>
                                </div>
                                <Badge variant={upload.upload_type === 'full_monthly' ? 'default' : 'secondary'}>
                                  {upload.records_count} records
                                </Badge>
                              </div>
                              <div className="grid grid-cols-3 gap-4 text-sm text-gray-600">
                                <div>
                                  <span className="font-medium">Uploaded:</span>
                                  <div>{formatDate(upload.upload_timestamp)}</div>
                                </div>
                                <div>
                                  <span className="font-medium">File Size:</span>
                                  <div>{formatFileSize(upload.file_size)}</div>
                                </div>
                                <div>
                                  <span className="font-medium">Uploaded By:</span>
                                  <div>{upload.uploaded_by}</div>
                                </div>
                              </div>
                            </div>
                          ))}
                        </div>
                      ) : (
                        <div className="text-center py-8">
                          <FileSpreadsheet className="w-12 h-12 text-gray-400 mx-auto mb-4" />
                          <h3 className="text-lg font-semibold text-gray-900 mb-2">No Upload History</h3>
                          <p className="text-gray-600">Upload your first Excel file to see history</p>
                        </div>
                      )}
                    </div>
                  </DialogContent>
                </Dialog>

                {/* Duplicate Date Error Dialog */}
                <Dialog open={showDuplicateDialog} onOpenChange={setShowDuplicateDialog}>
                  <DialogContent className="max-w-md">
                    <DialogHeader>
                      <DialogTitle className="flex items-center space-x-2 text-orange-600">
                        <AlertTriangle className="w-5 h-5" />
                        <span>Duplicate Date Detected</span>
                      </DialogTitle>
                      <DialogDescription>
                        The uploaded file contains dates that already exist in your database
                      </DialogDescription>
                    </DialogHeader>
                    
                    {duplicateError && (
                      <div className="mt-4 space-y-4">
                        <div className="p-4 bg-orange-50 border border-orange-200 rounded-lg">
                          <h4 className="font-semibold text-orange-900 mb-2">📅 Duplicate Dates Found:</h4>
                          <div className="text-sm text-orange-800">
                            <div className="font-medium">File: {duplicateError.filename}</div>
                            <div className="mt-1">Dates: <span className="font-mono bg-white px-1 rounded">{duplicateError.duplicateDates.join(', ')}</span></div>
                            {duplicateError.existing_dates_found && (
                              <div className="mt-2">
                                <div className="font-medium">Found in database:</div>
                                <ul className="mt-1 ml-4 text-xs">
                                  {duplicateError.existing_dates_found.map((date, idx) => (
                                    <li key={idx} className="font-mono">• {date}</li>
                                  ))}
                                </ul>
                              </div>
                            )}
                          </div>
                        </div>
                        
                        <div className="p-4 bg-blue-50 border border-blue-200 rounded-lg">
                          <h4 className="font-semibold text-blue-900 mb-2">💡 Solutions:</h4>
                          <ul className="text-sm text-blue-800 space-y-1">
                            <li>• Upload data for a <strong>new date</strong> instead</li>
                            <li>• Use <strong>"Full Monthly Data"</strong> to replace all existing data</li>
                            <li>• Check your Excel file has the correct date columns</li>
                          </ul>
                        </div>
                        
                        <div className="flex justify-end space-x-2 pt-4">
                          <Button
                            variant="outline"
                            onClick={() => {
                              setShowDuplicateDialog(false);
                              setDuplicateError(null);
                            }}
                            data-testid="duplicate-dialog-ok-btn"
                          >
                            Got it
                          </Button>
                        </div>
                      </div>
                    )}
                  </DialogContent>
                </Dialog>
              </div>

              <div className="flex flex-col lg:flex-row items-end lg:items-center space-y-2 lg:space-y-0 lg:space-x-4">
                {/* Overstock Multiplier Configuration */}
                <div className="flex items-center space-x-2">
                  <Label htmlFor="multiplier" className="text-xs font-medium text-gray-700">
                    Overstock Multiplier:
                  </Label>
                  <Input
                    id="multiplier"
                    type="number"
                    step="0.1"
                    min="1"
                    max="10"
                    value={overstockMultiplier}
                    onChange={(e) => setOverstockMultiplier(parseFloat(e.target.value) || 3.0)}
                    className="w-16 text-xs"
                    data-testid="overstock-multiplier-input"
                  />
                  <Button
                    onClick={handleMultiplierChange}
                    size="sm"
                    variant="outline"
                    disabled={!hasData || loading}
                    data-testid="update-multiplier-btn"
                    className="text-xs"
                  >
                    Update
                  </Button>
                </div>

                {/* Action Buttons - Two Rows Layout */}
                <div className="flex flex-col space-y-2">
                  {/* First Row: Upload & Management Buttons */}
                  <div className="flex items-center space-x-2">
                    {/* Full Monthly Data Upload */}
                    <Button 
                      variant="default" 
                      size="sm"
                      className="bg-green-600 hover:bg-green-700 cursor-pointer transition-all duration-200 text-xs"
                      disabled={loading}
                      data-testid="upload-full-monthly-btn"
                      onClick={() => {
                        const fileInput = document.getElementById('full-monthly-upload');
                        if (fileInput) {
                          fileInput.click();
                        }
                      }}
                    >
                      <Database className="w-3 h-3 mr-1" />
                      {loading ? 'Processing...' : 'Full Monthly'}
                    </Button>
                    <Input
                      id="full-monthly-upload"
                      type="file"
                      accept=".xlsx,.xls,.csv"
                      onChange={handleFullMonthlyUpload}
                      className="hidden"
                      data-testid="full-monthly-file-input"
                    />

                    {/* Today's Data Upload */}
                    <Button 
                      variant="outline" 
                      size="sm"
                      className="bg-orange-50 hover:bg-orange-100 border-orange-200 text-orange-700 cursor-pointer transition-all duration-200 text-xs"
                      disabled={loading}
                      data-testid="upload-todays-btn"
                      onClick={() => {
                        const fileInput = document.getElementById('todays-data-upload');
                        if (fileInput) {
                          fileInput.click();
                        }
                      }}
                    >
                      <RefreshCw className="w-3 h-3 mr-1" />
                      {loading ? 'Processing...' : "Today's Data"}
                    </Button>
                    <Input
                      id="todays-data-upload"
                      type="file"
                      accept=".xlsx,.xls,.csv"
                      onChange={handleTodaysDataUpload}
                      className="hidden"
                      data-testid="todays-data-file-input"
                    />

                    {/* Module 1: Brand Management Buttons */}
                    <Button 
                      variant="outline" 
                      size="sm"
                      onClick={() => setShowBrandModal(true)}
                      disabled={loading}
                      data-testid="add-brand-btn"
                      className="border-green-600 text-green-600 hover:bg-green-50 text-xs"
                    >
                      <Package className="w-3 h-3 mr-1" />
                      Add Brand
                    </Button>
                    <Button 
                      variant="outline" 
                      size="sm"
                      onClick={() => setShowRatesModal(true)}
                      disabled={loading}
                      data-testid="update-rates-btn"
                      className="border-blue-600 text-blue-600 hover:bg-blue-50 text-xs"
                    >
                      <DollarSign className="w-3 h-3 mr-1" />
                      Update Rates
                    </Button>
                  </div>

                  {/* Second Row: Backup & Reset Buttons */}
                  <div className="flex items-center space-x-2">
                    {/* Module 3: Stock Reset & Backup Buttons */}
                    <Button 
                      variant="outline" 
                      size="sm"
                      onClick={() => {
                        fetchBackups();
                        setShowBackupsDialog(true);
                      }}
                      disabled={loading}
                      data-testid="backups-btn"
                      className="border-purple-600 text-purple-600 hover:bg-purple-50 text-xs"
                    >
                      <Database className="w-3 h-3 mr-1" />
                      Backups
                    </Button>
                    <Button 
                      variant="outline" 
                      size="sm"
                      onClick={() => setShowResetDialog(true)}
                      disabled={loading || !hasData}
                      data-testid="reset-stock-btn"
                      className="border-red-600 text-red-600 hover:bg-red-50 text-xs"
                    >
                      <RefreshCw className="w-3 h-3 mr-1" />
                      Reset Stock
                    </Button>
                  </div>
                </div>
              </div>
            </div>
          </div>
          
          {/* Upload Progress */}
          {uploadProgress > 0 && (
            <div className="mt-4">
              <div className="flex items-center space-x-2">
                <FileSpreadsheet className="w-4 h-4 text-indigo-600" />
                <span className="text-sm text-gray-600">Uploading...</span>
              </div>
              <Progress value={uploadProgress} className="mt-2" data-testid="upload-progress" />
            </div>
          )}
        </div>
      </div>

      {/* Main Content */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {!hasData && !loading ? (
          <div className="text-center py-12">
            <div className="p-6 bg-white rounded-lg shadow-sm border-2 border-dashed border-gray-300">
              <FileSpreadsheet className="w-16 h-16 text-gray-400 mx-auto mb-4" />
              <h3 className="text-lg font-semibold text-gray-900 mb-2">No Data Available</h3>
              <p className="text-gray-600 mb-4">Upload your liquor sales Excel file to start analyzing data</p>
              <div className="text-sm text-gray-500 mb-4">
                <p>Supported formats: .xlsx, .xls, .csv</p>
              </div>
              <Button
                onClick={() => setShowOnboarding(true)}
                variant="outline"
                className="mt-2"
                data-testid="get-started-btn"
              >
                <Play className="w-4 h-4 mr-2" />
                Get Started Guide
              </Button>
            </div>
          </div>
        ) : loading && !analyticsData ? (
          <div className="flex items-center justify-center py-12">
            <div className="text-center">
              <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-600 mx-auto"></div>
              <p className="mt-4 text-gray-600">Loading analytics...</p>
            </div>
          </div>
        ) : analyticsData ? (
          <div className="space-y-8">
            {/* Key Metrics Cards */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
              <Card data-testid="total-brands-card">
                <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                  <CardTitle className="text-sm font-medium text-gray-600">Total Brands</CardTitle>
                  <Package className="h-4 w-4 text-indigo-600" />
                </CardHeader>
                <CardContent>
                  <div className="text-2xl font-bold text-gray-900">{analyticsData.total_brands}</div>
                </CardContent>
              </Card>

              <Card data-testid="total-stock-value-card">
                <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                  <CardTitle className="text-sm font-medium text-gray-600">Total Stock Value</CardTitle>
                  <DollarSign className="h-4 w-4 text-green-600" />
                </CardHeader>
                <CardContent>
                  <div className="text-2xl font-bold text-gray-900">{formatCurrency(analyticsData.total_stock_value)}</div>
                </CardContent>
              </Card>

              <Card data-testid="overstocked-brands-card">
                <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                  <CardTitle className="text-sm font-medium text-gray-600">Overstocked Brands</CardTitle>
                  <AlertTriangle className="h-4 w-4 text-orange-600" />
                </CardHeader>
                <CardContent>
                  <div className="text-2xl font-bold text-gray-900">{analyticsData.overstocked_brands}</div>
                  <Badge variant="secondary" className="mt-1 text-xs">
                    {overstockMultiplier}x rule
                  </Badge>
                </CardContent>
              </Card>

              <Card data-testid="overstocked-value-card">
                <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                  <CardTitle className="text-sm font-medium text-gray-600">Overstocked Value</CardTitle>
                  <TrendingUp className="h-4 w-4 text-red-600" />
                </CardHeader>
                <CardContent>
                  <div className="text-2xl font-bold text-red-600">{formatCurrency(analyticsData.total_overstocked_value)}</div>
                </CardContent>
              </Card>
            </div>

            {/* Main Dashboard Tabs */}
            <Tabs defaultValue="performance-charts" className="w-full">
              <TabsList className="grid w-full grid-cols-7 gap-2 p-2 bg-gradient-to-r from-blue-50 to-indigo-50 border-2 border-blue-100 rounded-xl shadow-lg">
                <TabsTrigger 
                  value="performance-charts" 
                  data-testid="performance-charts-tab"
                  className="flex items-center space-x-2 px-4 py-3 rounded-lg font-medium text-sm transition-all duration-300 hover:scale-105 data-[state=active]:bg-gradient-to-r data-[state=active]:from-blue-500 data-[state=active]:to-blue-600 data-[state=active]:text-white data-[state=active]:shadow-lg data-[state=active]:transform data-[state=active]:scale-105 bg-blue-100 text-blue-700 hover:bg-blue-200 border border-blue-200 data-[state=active]:border-blue-300"
                >
                  <BarChart3 className="w-4 h-4" />
                  <span>Charts</span>
                </TabsTrigger>
                <TabsTrigger 
                  value="sales-trends" 
                  data-testid="sales-trends-tab"
                  className="flex items-center space-x-2 px-4 py-3 rounded-lg font-medium text-sm transition-all duration-300 hover:scale-105 data-[state=active]:bg-gradient-to-r data-[state=active]:from-green-500 data-[state=active]:to-green-600 data-[state=active]:text-white data-[state=active]:shadow-lg data-[state=active]:transform data-[state=active]:scale-105 bg-green-100 text-green-700 hover:bg-green-200 border border-green-200 data-[state=active]:border-green-300"
                >
                  <TrendingUp className="w-4 h-4" />
                  <span>Trends</span>
                </TabsTrigger>
                <TabsTrigger 
                  value="overstocking" 
                  data-testid="overstocking-tab"
                  className="flex items-center space-x-2 px-4 py-3 rounded-lg font-medium text-sm transition-all duration-300 hover:scale-105 data-[state=active]:bg-gradient-to-r data-[state=active]:from-orange-500 data-[state=active]:to-orange-600 data-[state=active]:text-white data-[state=active]:shadow-lg data-[state=active]:transform data-[state=active]:scale-105 bg-orange-100 text-orange-700 hover:bg-orange-200 border border-orange-200 data-[state=active]:border-orange-300"
                >
                  <AlertTriangle className="w-4 h-4" />
                  <span>Alerts</span>
                </TabsTrigger>
                <TabsTrigger 
                  value="brand-performance" 
                  data-testid="brand-performance-tab"
                  className="flex items-center space-x-2 px-4 py-3 rounded-lg font-medium text-sm transition-all duration-300 hover:scale-105 data-[state=active]:bg-gradient-to-r data-[state=active]:from-purple-500 data-[state=active]:to-purple-600 data-[state=active]:text-white data-[state=active]:shadow-lg data-[state=active]:transform data-[state=active]:scale-105 bg-purple-100 text-purple-700 hover:bg-purple-200 border border-purple-200 data-[state=active]:border-purple-300"
                >
                  <Crown className="w-4 h-4" />
                  <span>Top Brands</span>
                </TabsTrigger>
                <TabsTrigger 
                  value="recommendations" 
                  data-testid="recommendations-tab"
                  className="flex items-center space-x-2 px-4 py-3 rounded-lg font-medium text-sm transition-all duration-300 hover:scale-105 data-[state=active]:bg-gradient-to-r data-[state=active]:from-indigo-500 data-[state=active]:to-indigo-600 data-[state=active]:text-white data-[state=active]:shadow-lg data-[state=active]:transform data-[state=active]:scale-105 bg-indigo-100 text-indigo-700 hover:bg-indigo-200 border border-indigo-200 data-[state=active]:border-indigo-300"
                >
                  <Target className="w-4 h-4" />
                  <span>Forecast</span>
                </TabsTrigger>
                <TabsTrigger 
                  value="calculations" 
                  data-testid="calculations-tab"
                  className="flex items-center space-x-2 px-4 py-3 rounded-lg font-medium text-sm transition-all duration-300 hover:scale-105 data-[state=active]:bg-gradient-to-r data-[state=active]:from-teal-500 data-[state=active]:to-teal-600 data-[state=active]:text-white data-[state=active]:shadow-lg data-[state=active]:transform data-[state=active]:scale-105 bg-teal-100 text-teal-700 hover:bg-teal-200 border border-teal-200 data-[state=active]:border-teal-300"
                >
                  <CheckCircle className="w-4 h-4" />
                  <span>Verify</span>
                </TabsTrigger>
                <TabsTrigger 
                  value="database-view" 
                  data-testid="database-view-tab"
                  className="flex items-center space-x-2 px-4 py-3 rounded-lg font-medium text-sm transition-all duration-300 hover:scale-105 data-[state=active]:bg-gradient-to-r data-[state=active]:from-gray-600 data-[state=active]:to-gray-700 data-[state=active]:text-white data-[state=active]:shadow-lg data-[state=active]:transform data-[state=active]:scale-105 bg-gray-200 text-gray-700 hover:bg-gray-300 border border-gray-300 data-[state=active]:border-gray-400"
                >
                  <Database className="w-4 h-4" />
                  <span>Database</span>
                </TabsTrigger>
              </TabsList>

              {/* Performance Charts Tab */}
              <TabsContent value="performance-charts" className="space-y-6">
                {chartsData && (
                  <div className="grid gap-6">
                    {/* Volume Leaders Chart */}
                    <Card data-testid="volume-leaders-chart">
                      <CardHeader>
                        <CardTitle className="flex items-center space-x-2">
                          <BarChart3 className="h-5 w-5 text-blue-600" />
                          <span>Volume Leaders - Stock Quantities</span>
                        </CardTitle>
                        <CardDescription>Brands with highest current stock quantities</CardDescription>
                      </CardHeader>
                      <CardContent>
                        <div className="h-80 w-full">
                          <ResponsiveContainer width="100%" height="100%">
                            <BarChart data={chartsData.volume_leaders}>
                              <CartesianGrid strokeDasharray="3 3" />
                              <XAxis 
                                dataKey="name" 
                                angle={-45}
                                textAnchor="end"
                                height={100}
                                interval={0}
                              />
                              <YAxis />
                              <Tooltip formatter={(value) => [formatNumber(value), "Quantity in Stock"]} />
                              <Bar dataKey="value" fill="#3B82F6" />
                            </BarChart>
                          </ResponsiveContainer>
                        </div>
                      </CardContent>
                    </Card>

                    {/* Revenue Leaders and Fastest Moving */}
                    <div className="grid md:grid-cols-2 gap-6">
                      <Card data-testid="revenue-leaders-chart">
                        <CardHeader>
                          <CardTitle className="flex items-center space-x-2">
                            <DollarSign className="h-5 w-5 text-green-600" />
                            <span>Revenue Leaders</span>
                          </CardTitle>
                          <CardDescription>Top brands by estimated sales revenue</CardDescription>
                        </CardHeader>
                        <CardContent>
                          <div className="h-64 w-full">
                            <ResponsiveContainer width="100%" height="100%">
                              <BarChart data={chartsData.revenue_leaders.slice(0, 6)}>
                                <CartesianGrid strokeDasharray="3 3" />
                                <XAxis 
                                  dataKey="name" 
                                  angle={-45}
                                  textAnchor="end"
                                  height={80}
                                  interval={0}
                                />
                                <YAxis />
                                <Tooltip formatter={(value) => [formatCurrency(value), "Revenue"]} />
                                <Bar dataKey="value" fill="#10B981" />
                              </BarChart>
                            </ResponsiveContainer>
                          </div>
                        </CardContent>
                      </Card>

                      <Card data-testid="velocity-leaders-chart">
                        <CardHeader>
                          <CardTitle className="flex items-center space-x-2">
                            <Zap className="h-5 w-5 text-yellow-600" />
                            <span>Fastest Moving Brands</span>
                          </CardTitle>
                          <CardDescription>Brands with highest sales velocity</CardDescription>
                        </CardHeader>
                        <CardContent>
                          <div className="space-y-3">
                            {chartsData.velocity_leaders.slice(0, 5).map((brand, index) => (
                              <div key={index} className="flex items-center justify-between p-3 bg-yellow-50 rounded-lg">
                                <div>
                                  <div className="font-medium text-gray-900">{brand.name}</div>
                                  <div className="text-sm text-gray-600">{brand.days_of_stock.toFixed(1)} days stock</div>
                                </div>
                                <div className="text-right">
                                  <div className="text-lg font-semibold text-yellow-600">
                                    {brand.velocity}x
                                  </div>
                                  <div className="text-xs text-gray-500">velocity</div>
                                </div>
                              </div>
                            ))}
                          </div>
                        </CardContent>
                      </Card>
                    </div>

                    {/* Revenue Proportion Pie Chart */}
                    <Card data-testid="revenue-proportion-chart">
                      <CardHeader>
                        <CardTitle className="flex items-center space-x-2">
                          <Crown className="h-5 w-5 text-purple-600" />
                          <span>Revenue Share Distribution</span>
                        </CardTitle>
                        <CardDescription>Each brand's contribution to total estimated sales</CardDescription>
                      </CardHeader>
                      <CardContent>
                        <div className="h-80 w-full">
                          <ResponsiveContainer width="100%" height="100%">
                            <PieChart>
                              <Pie
                                data={chartsData.revenue_proportion.slice(0, 8)}
                                cx="50%"
                                cy="50%"
                                innerRadius={60}
                                outerRadius={120}
                                paddingAngle={5}
                                dataKey="percentage"
                                label={({ name, percentage }) => `${name.substring(0, 15)}...: ${percentage}%`}
                              >
                                {chartsData.revenue_proportion.slice(0, 8).map((entry, index) => (
                                  <Cell key={`cell-${index}`} fill={CHART_COLORS[index % CHART_COLORS.length]} />
                                ))}
                              </Pie>
                              <Tooltip formatter={(value) => [`${value}%`, "Revenue Share"]} />
                            </PieChart>
                          </ResponsiveContainer>
                        </div>
                      </CardContent>
                    </Card>
                  </div>
                )}
              </TabsContent>

              {/* Sales Trends Tab */}
              <TabsContent value="sales-trends" className="space-y-6">
                <Card data-testid="sales-trends-card">
                  <CardHeader>
                    <CardTitle className="flex items-center space-x-2">
                      <TrendingUp className="h-5 w-5 text-indigo-600" />
                      <span>Stock Analysis Overview</span>
                    </CardTitle>
                    <CardDescription>Current stock positions and estimated performance</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-4">
                      {analyticsData && Object.entries(analyticsData.sales_trends).length > 0 ? (
                        <>
                          <div className="h-80 w-full mb-6">
                            <ResponsiveContainer width="100%" height="100%">
                              <LineChart
                                data={Object.entries(analyticsData.sales_trends)
                                  .filter(([date]) => !date.includes('Monthly') && !date.includes('Stock'))
                                  .map(([date, sales]) => ({
                                    date: date.length > 10 ? date.substring(0, 10) : date,
                                    sales: sales || 0,
                                    displayDate: date
                                  }))
                                }
                              >
                                <CartesianGrid strokeDasharray="3 3" />
                                <XAxis 
                                  dataKey="date" 
                                  angle={-45}
                                  textAnchor="end"
                                  height={80}
                                />
                                <YAxis />
                                <Tooltip 
                                  formatter={(value) => [formatNumber(value || 0), "Daily Stock"]}
                                  labelFormatter={(label) => `Date: ${label}`}
                                />
                                <Line 
                                  type="monotone" 
                                  dataKey="sales" 
                                  stroke="#3B82F6" 
                                  strokeWidth={3}
                                  dot={{ fill: '#3B82F6', strokeWidth: 2, r: 4 }}
                                />
                              </LineChart>
                            </ResponsiveContainer>
                          </div>
                          
                          <div className="grid gap-4">
                            <h4 className="font-medium text-gray-900">Recent Stock Trends</h4>
                            {Object.entries(analyticsData.sales_trends)
                              .filter(([date]) => !date.includes('Monthly') && !date.includes('Stock'))
                              .map(([date, sales]) => (
                                <div key={date} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                                  <div className="flex items-center space-x-3">
                                    <Calendar className="h-4 w-4 text-gray-500" />
                                    <span className="font-medium text-gray-900">{date}</span>
                                  </div>
                                  <div className="text-right">
                                    <div className="text-lg font-semibold text-indigo-600">{formatNumber(sales || 0)}</div>
                                    <div className="text-xs text-gray-500">total stock units</div>
                                  </div>
                                </div>
                              ))}
                          </div>
                        </>
                      ) : (
                        <div className="text-center py-8">
                          <TrendingUp className="h-12 w-12 text-gray-400 mx-auto mb-4" />
                          <h3 className="text-lg font-semibold text-gray-900 mb-2">Stock Analysis Ready</h3>
                          <p className="text-gray-600">Upload your new liquor data to view detailed stock analysis</p>
                        </div>
                      )}
                    </div>
                  </CardContent>
                </Card>
              </TabsContent>

              {/* Overstocking Tab */}
              <TabsContent value="overstocking" className="space-y-6">
                <Card data-testid="overstocking-card">
                  <CardHeader>
                    <CardTitle className="flex items-center space-x-2">
                      <AlertTriangle className="h-5 w-5 text-orange-600" />
                      <span>Overstocked Items</span>
                    </CardTitle>
                    <CardDescription>
                      Items with stock value exceeding {overstockMultiplier}x their monthly average sales
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    {analyticsData.overstocked_items.length > 0 ? (
                      <div className="space-y-4">
                        {analyticsData.overstocked_items.map((item, index) => (
                          <Alert key={index} className="border-orange-200 bg-orange-50" data-testid={`overstock-item-${index}`}>
                            <AlertTriangle className="h-4 w-4 text-orange-600" />
                            <AlertDescription>
                              <div className="space-y-2">
                                <div className="flex justify-between items-start">
                                  <h4 className="font-semibold text-gray-900">{item.brand_name}</h4>
                                  <Badge variant="destructive">
                                    Overstock: {formatCurrency(item.overstock_value)}
                                  </Badge>
                                </div>
                                <div className="grid grid-cols-2 gap-4 text-sm">
                                  <div>
                                    <span className="text-gray-600">Current Stock:</span>
                                    <span className="ml-2 font-medium">{formatCurrency(item.current_stock_value)}</span>
                                  </div>
                                  <div>
                                    <span className="text-gray-600">Monthly Avg:</span>
                                    <span className="ml-2 font-medium">{formatCurrency(item.monthly_avg_sale)}</span>
                                  </div>
                                  <div>
                                    <span className="text-gray-600">Threshold ({overstockMultiplier}x):</span>
                                    <span className="ml-2 font-medium">{formatCurrency(item.threshold)}</span>
                                  </div>
                                  <div>
                                    <span className="text-gray-600">Stock Ratio:</span>
                                    <span className="ml-2 font-medium">{item.stock_ratio.toFixed(2)}</span>
                                  </div>
                                </div>
                              </div>
                            </AlertDescription>
                          </Alert>
                        ))}
                      </div>
                    ) : (
                      <div className="text-center py-8">
                        <Package className="h-12 w-12 text-green-500 mx-auto mb-4" />
                        <h3 className="text-lg font-semibold text-gray-900 mb-2">No Overstocking Issues</h3>
                        <p className="text-gray-600">All brands are within optimal stock levels</p>
                      </div>
                    )}
                  </CardContent>
                </Card>
              </TabsContent>

              {/* Brand Performance Tab */}
              <TabsContent value="brand-performance" className="space-y-6">
                <Card data-testid="brand-performance-card">
                  <CardHeader>
                    <CardTitle className="flex items-center space-x-2">
                      <BarChart3 className="h-5 w-5 text-indigo-600" />
                      <span>Top Performing Brands</span>
                    </CardTitle>
                    <CardDescription>Ranked by estimated sales performance</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-4">
                      {analyticsData && analyticsData.top_selling_brands.map((brand, index) => (
                        <div 
                          key={index} 
                          className="flex items-center justify-between p-4 bg-gray-50 rounded-lg hover:bg-gray-100 transition-colors"
                          data-testid={`top-brand-${index}`}
                        >
                          <div className="flex items-center space-x-4">
                            <div className="flex items-center justify-center w-8 h-8 bg-indigo-100 text-indigo-600 font-bold text-sm rounded-full">
                              {index + 1}
                            </div>
                            <div>
                              <h4 className="font-semibold text-gray-900">{brand.brand_name}</h4>
                              <p className="text-sm text-gray-600">Stock Ratio: {brand.stock_ratio.toFixed(2)}</p>
                            </div>
                          </div>
                          <div className="text-right">
                            <div className="text-lg font-semibold text-indigo-600">
                              {formatCurrency(brand.monthly_sale_value)}
                            </div>
                            <div className="text-sm text-gray-500">
                              Stock: {formatCurrency(brand.stock_value_today)}
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              </TabsContent>

              {/* Demand Forecast Tab */}
              <TabsContent value="recommendations" className="space-y-6">
                <div className="flex justify-between items-center">
                  <div>
                    <h2 className="text-2xl font-bold text-gray-900">Smart Demand Forecast</h2>
                    <p className="text-gray-600">AI-powered recommendations with wholesale rates and quantities</p>
                  </div>
                  <Button
                    onClick={handleExportDemandList}
                    className="bg-green-600 hover:bg-green-700"
                    data-testid="export-demand-btn"
                  >
                    <Download className="w-4 h-4 mr-2" />
                    Export Excel
                  </Button>
                </div>

                {demandData && demandData.length > 0 ? (
                  <div className="space-y-4">
                    {/* Urgency Level Summary */}
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                      <Card className="border-red-200 bg-red-50">
                        <CardContent className="p-4">
                          <div className="flex items-center space-x-2">
                            <AlertTriangle className="h-5 w-5 text-red-600" />
                            <div>
                              <div className="text-2xl font-bold text-red-600">
                                {demandData.filter(item => item.urgency_level === 'HIGH').length}
                              </div>
                              <div className="text-sm text-red-800">High Priority</div>
                            </div>
                          </div>
                        </CardContent>
                      </Card>
                      
                      <Card className="border-yellow-200 bg-yellow-50">
                        <CardContent className="p-4">
                          <div className="flex items-center space-x-2">
                            <Package className="h-5 w-5 text-yellow-600" />
                            <div>
                              <div className="text-2xl font-bold text-yellow-600">
                                {demandData.filter(item => item.urgency_level === 'MEDIUM').length}
                              </div>
                              <div className="text-sm text-yellow-800">Medium Priority</div>
                            </div>
                          </div>
                        </CardContent>
                      </Card>
                      
                      <Card className="border-blue-200 bg-blue-50">
                        <CardContent className="p-4">
                          <div className="flex items-center space-x-2">
                            <Target className="h-5 w-5 text-blue-600" />
                            <div>
                              <div className="text-2xl font-bold text-blue-600">
                                {demandData.filter(item => item.urgency_level === 'LOW').length}
                              </div>
                              <div className="text-sm text-blue-800">Low Priority</div>
                            </div>
                          </div>
                        </CardContent>
                      </Card>
                    </div>

                    {/* Recommendations List */}
                    <Card data-testid="recommendations-list">
                      <CardHeader>
                        <CardTitle className="flex items-center space-x-2">
                          <Target className="h-5 w-5 text-indigo-600" />
                          <span>Recommended Orders</span>
                        </CardTitle>
                        <CardDescription>
                          Optimized ordering recommendations with wholesale rates (10% lower than selling price)
                        </CardDescription>
                      </CardHeader>
                      <CardContent>
                        <div className="space-y-4">
                          {demandData.map((rec, index) => {
                            const urgencyColors = {
                              HIGH: 'border-red-200 bg-red-50',
                              MEDIUM: 'border-yellow-200 bg-yellow-50',
                              LOW: 'border-blue-200 bg-blue-50'
                            };
                            
                            const urgencyBadgeColors = {
                              HIGH: 'bg-red-600 text-white',
                              MEDIUM: 'bg-yellow-600 text-white',
                              LOW: 'bg-blue-600 text-white'
                            };

                            return (
                              <div 
                                key={index} 
                                className={`p-4 rounded-lg border ${urgencyColors[rec.urgency_level]}`}
                                data-testid={`recommendation-${index}`}
                              >
                                <div className="flex justify-between items-start mb-3">
                                  <div>
                                    <h4 className="font-semibold text-gray-900">{rec.brand_name}</h4>
                                    <p className="text-sm text-gray-600">
                                      Current Stock: {rec.current_stock_qty} units
                                    </p>
                                  </div>
                                  <Badge className={urgencyBadgeColors[rec.urgency_level]}>
                                    {rec.urgency_level} PRIORITY
                                  </Badge>
                                </div>
                                
                                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                                  <div>
                                    <span className="text-gray-600">Selling Rate:</span>
                                    <div className="font-medium">{formatCurrency(rec.selling_rate)}</div>
                                  </div>
                                  <div>
                                    <span className="text-gray-600">Wholesale Rate:</span>
                                    <div className="font-medium text-green-600">{formatCurrency(rec.wholesale_rate)}</div>
                                  </div>
                                  <div>
                                    <span className="text-gray-600">Current Stock:</span>
                                    <div className="font-medium">{rec.current_stock_qty} units</div>
                                  </div>
                                  <div>
                                    <span className="text-gray-600">Recommended Order:</span>
                                    <div className="font-medium text-indigo-600 text-lg">
                                      {rec.recommended_qty} units
                                    </div>
                                  </div>
                                </div>
                              </div>
                            );
                          })}
                        </div>
                      </CardContent>
                    </Card>
                  </div>
                ) : (
                  <div className="text-center py-12">
                    <Target className="h-12 w-12 text-gray-400 mx-auto mb-4" />
                    <h3 className="text-lg font-semibold text-gray-900 mb-2">No Recommendations Available</h3>
                    <p className="text-gray-600">Upload liquor data to generate smart demand forecasts</p>
                  </div>
                )}
              </TabsContent>

              {/* Calculation Verification Tab */}
              <TabsContent value="calculations" className="space-y-6">
                <div className="flex justify-between items-center">
                  <div>
                    <h2 className="text-2xl font-bold text-gray-900">Calculation Verification</h2>
                    <p className="text-gray-600">Compare dashboard calculations with your manual calculations</p>
                  </div>
                  <Button
                    onClick={() => {
                      if (calculationData && calculationData.length > 0) {
                        // Export calculation data as CSV for easy comparison
                        const csvContent = [
                          // Header row
                          'Index,Brand Name,D1 Stock,DL Stock,D1 Date,DL Date,Wholesale Rate,Selling Rate,Total Sales Qty,Avg Daily Sales,Monthly Sale Value,Current Stock Value,Multiplier Value,Days Analyzed,Stock Available Days',
                          // Data rows
                          ...calculationData.map(row => [
                            row.index,
                            `"${row.brand_name}"`,
                            row.D1_stock,
                            row.DL_stock,
                            row.D1_date,
                            row.DL_date,
                            row.calculated_wholesale_rate,
                            row.selling_rate,
                            row.total_sales_qty.toFixed(2),
                            row.avg_daily_sales_qty.toFixed(3),
                            row.calculated_avg_monthly_sale.toFixed(2),
                            row.calculated_current_stock_value.toFixed(2),
                            row.calculated_multiplier_value,
                            row.days_analyzed,
                            row.stock_available_days.toFixed(1)
                          ].join(','))
                        ].join('\n');
                        
                        const blob = new Blob([csvContent], { type: 'text/csv' });
                        const url = window.URL.createObjectURL(blob);
                        const link = document.createElement('a');
                        link.href = url;
                        link.download = `calculation_verification_${new Date().toISOString().split('T')[0]}.csv`;
                        link.click();
                        window.URL.revokeObjectURL(url);
                        toast.success("Calculation data exported to CSV!");
                      }
                    }}
                    variant="outline"
                    disabled={!calculationData || calculationData.length === 0}
                    data-testid="export-calculations-btn"
                  >
                    <Download className="w-4 h-4 mr-2" />
                    Export CSV
                  </Button>
                </div>

                {calculationData && calculationData.length > 0 ? (
                  <Card data-testid="calculation-table">
                    <CardHeader>
                      <CardTitle>Detailed Calculations for All Brands</CardTitle>
                      <CardDescription>
                        Verify these calculations against your manual Excel calculations. 
                        Multiplier Value = Current Stock Value ÷ Monthly Sales Value
                      </CardDescription>
                    </CardHeader>
                    <CardContent>
                      <div className="overflow-x-auto">
                        <table className="w-full text-sm">
                          <thead>
                            <tr className="border-b bg-gray-50">
                              <th className="text-left p-3 font-semibold">Index</th>
                              <th className="text-left p-3 font-semibold">Brand Name</th>
                              <th className="text-left p-3 font-semibold">D1 Stock</th>
                              <th className="text-left p-3 font-semibold">DL Stock</th>
                              <th className="text-left p-3 font-semibold">Wholesale Rate</th>
                              <th className="text-left p-3 font-semibold">Selling Rate</th>
                              <th className="text-left p-3 font-semibold">Monthly Sale Value</th>
                              <th className="text-left p-3 font-semibold">Current Stock Value</th>
                              <th className="text-left p-3 font-semibold">Multiplier Value</th>
                              <th className="text-left p-3 font-semibold">Status</th>
                            </tr>
                          </thead>
                          <tbody>
                            {calculationData.map((row, index) => (
                              <tr key={index} className="border-b hover:bg-gray-50" data-testid={`calc-row-${index}`}>
                                <td className="p-3 font-medium">{row.index}</td>
                                <td className="p-3 max-w-xs truncate" title={row.brand_name}>{row.brand_name}</td>
                                <td className="p-3 font-medium text-indigo-600">{row.D1_stock}</td>
                                <td className="p-3 font-medium text-orange-600">{row.DL_stock}</td>
                                <td className="p-3">{formatCurrency(row.calculated_wholesale_rate)}</td>
                                <td className="p-3">{formatCurrency(row.selling_rate)}</td>
                                <td className="p-3 font-medium text-blue-600">
                                  {formatCurrency(row.calculated_avg_monthly_sale)}
                                </td>
                                <td className="p-3 font-medium text-green-600">
                                  {formatCurrency(row.calculated_current_stock_value)}
                                </td>
                                <td className="p-3 font-bold text-purple-600">{row.calculated_multiplier_value}</td>
                                <td className="p-3">
                                  {row.calculated_multiplier_value > overstockMultiplier ? (
                                    <Badge variant="destructive">Overstocked</Badge>
                                  ) : row.calculated_multiplier_value > overstockMultiplier * 0.7 ? (
                                    <Badge className="bg-yellow-500 text-white">Warning</Badge>
                                  ) : (
                                    <Badge className="bg-green-500 text-white">Healthy</Badge>
                                  )}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>

                      {/* Calculation Details Breakdown */}
                      <div className="mt-8 grid gap-4">
                        <h4 className="text-lg font-semibold text-gray-900">Calculation Formula Breakdown</h4>
                        <div className="grid md:grid-cols-2 gap-4 text-sm">
                          <div className="p-4 bg-blue-50 rounded-lg">
                            <h5 className="font-semibold text-blue-900 mb-2">Monthly Sales Calculation</h5>
                            <ol className="text-blue-800 space-y-1">
                              <li>1. Total Sales = D1 Stock - DL Stock</li>
                              <li>2. Average Daily Sales = Total Sales ÷ Days Between D1 & DL</li>
                              <li>3. Monthly Sales Qty = Average Daily Sales × 24</li>
                              <li>4. Monthly Sales Value = Monthly Sales Qty × Selling Rate</li>
                            </ol>
                          </div>
                          <div className="p-4 bg-purple-50 rounded-lg">
                            <h5 className="font-semibold text-purple-900 mb-2">Overstocking Analysis</h5>
                            <ol className="text-purple-800 space-y-1">
                              <li>1. Current Stock Value = DL Stock × Selling Rate</li>
                              <li>2. Multiplier Value = Stock Value ÷ Monthly Sales Value</li>
                              <li>3. Overstocked if Multiplier > {overstockMultiplier}x</li>
                              <li>4. Warning if Multiplier > {(overstockMultiplier * 0.7).toFixed(1)}x</li>
                            </ol>
                          </div>
                        </div>

                        {/* Detailed calculation for Black Dog Centenary as example */}
                        {calculationData.length > 0 && (() => {
                          // Find Black Dog Centenary in the data
                          const blackDogExample = calculationData.find(item => 
                            item.brand_name.toLowerCase().includes('black dog') && 
                            item.brand_name.toLowerCase().includes('centenary')
                          ) || calculationData[0]; // Fallback to first item if Black Dog Centenary not found
                          
                          return (
                            <div className="mt-4 p-4 bg-gray-50 rounded-lg">
                              <h5 className="font-semibold text-gray-900 mb-2">
                                Example Calculation ({blackDogExample.brand_name})
                                {blackDogExample !== calculationData[0] && (
                                  <span className="ml-2 text-sm text-green-600 font-normal">✓ Found Black Dog Centenary</span>
                                )}:
                              </h5>
                              <div className="text-sm text-gray-700 space-y-1">
                                <p><strong>Index:</strong> {blackDogExample.index}</p>
                                <p>• <strong>D1 Stock</strong> ({blackDogExample.D1_date}): <span className="text-indigo-600 font-medium">{blackDogExample.D1_stock} units</span></p>
                                <p>• <strong>DL Stock</strong> ({blackDogExample.DL_date}): <span className="text-orange-600 font-medium">{blackDogExample.DL_stock} units</span></p>
                                <p>• <strong>Total Sales:</strong> {blackDogExample.D1_stock} - {blackDogExample.DL_stock} = <span className="text-red-600 font-medium">{blackDogExample.total_sales_qty} units</span></p>
                                <p>• <strong>Days Analyzed:</strong> {blackDogExample.days_analyzed} days</p>
                                <p>• <strong>Average Daily Sales:</strong> {blackDogExample.total_sales_qty} ÷ {blackDogExample.days_analyzed} = <span className="text-blue-600 font-medium">{blackDogExample.avg_daily_sales_qty.toFixed(3)} units/day</span></p>
                                <p>• <strong>Monthly Sales Value:</strong> {blackDogExample.avg_daily_sales_qty.toFixed(3)} × 24 × ₹{blackDogExample.selling_rate} = <span className="text-blue-600 font-medium">{formatCurrency(blackDogExample.calculated_avg_monthly_sale)}</span></p>
                                <p>• <strong>Current Stock Value:</strong> {blackDogExample.DL_stock} × ₹{blackDogExample.selling_rate} = <span className="text-green-600 font-medium">{formatCurrency(blackDogExample.calculated_current_stock_value)}</span></p>
                                <p>• <strong>Multiplier:</strong> {formatCurrency(blackDogExample.calculated_current_stock_value)} ÷ {formatCurrency(blackDogExample.calculated_avg_monthly_sale)} = <strong className="text-purple-600 text-lg">{blackDogExample.calculated_multiplier_value}</strong></p>
                                <p>• <strong>Stock Status:</strong> 
                                  {blackDogExample.calculated_multiplier_value > 3 ? (
                                    <span className="text-red-600 font-medium"> Overstocked (>{overstockMultiplier}x)</span>
                                  ) : blackDogExample.calculated_multiplier_value > 2.1 ? (
                                    <span className="text-yellow-600 font-medium"> Warning (>2.1x)</span>
                                  ) : (
                                    <span className="text-green-600 font-medium"> Healthy Stock Level</span>
                                  )}
                                </p>
                              </div>
                            </div>
                          );
                        })()}
                      </div>
                    </CardContent>
                  </Card>
                ) : (
                  <div className="text-center py-12">
                    <BarChart3 className="h-12 w-12 text-gray-400 mx-auto mb-4" />
                    <h3 className="text-lg font-semibold text-gray-900 mb-2">No Calculation Data</h3>
                    <p className="text-gray-600">Upload liquor data to see detailed calculations</p>
                  </div>
                )}
              </TabsContent>

              {/* Database View Tab */}
              <TabsContent value="database-view" className="space-y-6">
                <div className="flex justify-between items-center">
                  <div>
                    <h2 className="text-2xl font-bold text-gray-900">Database View</h2>
                    <p className="text-gray-600">Complete view of raw database data for debugging and transparency</p>
                  </div>
                  {databaseView && databaseView.data && (
                    <Button
                      onClick={() => {
                        // Export database view as JSON
                        const dataStr = JSON.stringify(databaseView.data, null, 2);
                        const dataBlob = new Blob([dataStr], { type: 'application/json' });
                        const url = URL.createObjectURL(dataBlob);
                        const link = document.createElement('a');
                        link.href = url;
                        link.download = `database_export_${new Date().toISOString().split('T')[0]}.json`;
                        link.click();
                        URL.revokeObjectURL(url);
                        toast.success("Database exported as JSON file!");
                      }}
                      variant="outline"
                      data-testid="export-database-btn"
                    >
                      <Download className="w-4 h-4 mr-2" />
                      Export JSON
                    </Button>
                  )}
                </div>

                {databaseView ? (
                  <div className="space-y-6">
                    {/* Database Summary */}
                    <Card data-testid="database-summary">
                      <CardHeader>
                        <CardTitle className="flex items-center space-x-2">
                          <Database className="w-5 h-5 text-blue-600" />
                          <span>Database Summary</span>
                        </CardTitle>
                      </CardHeader>
                      <CardContent>
                        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                          <div className="text-center p-4 bg-blue-50 rounded-lg">
                            <div className="text-2xl font-bold text-blue-600">{databaseView.total_records}</div>
                            <div className="text-sm text-blue-800">Total Records</div>
                          </div>
                          <div className="text-center p-4 bg-green-50 rounded-lg">
                            <div className="text-2xl font-bold text-green-600">{databaseView.summary?.unique_d1_dates?.length || 0}</div>
                            <div className="text-sm text-green-800">D1 Dates</div>
                          </div>
                          <div className="text-center p-4 bg-purple-50 rounded-lg">
                            <div className="text-2xl font-bold text-purple-600">{databaseView.summary?.unique_dl_dates?.length || 0}</div>
                            <div className="text-sm text-purple-800">DL Dates</div>
                          </div>
                          <div className="text-center p-4 bg-orange-50 rounded-lg">
                            <div className="text-2xl font-bold text-orange-600">{databaseView.summary?.unique_daily_sales_dates?.length || 0}</div>
                            <div className="text-sm text-orange-800">Daily Sales Dates</div>
                          </div>
                        </div>

                        {databaseView.summary && (
                          <div className="mt-6 grid md:grid-cols-2 gap-6">
                            <div className="p-4 bg-gray-50 rounded-lg">
                              <h4 className="font-semibold text-gray-900 mb-2">Date Information</h4>
                              <div className="text-sm space-y-1">
                                {databaseView.summary.unique_d1_dates && (
                                  <div>
                                    <span className="font-medium text-blue-600">D1 Dates:</span>
                                    <span className="ml-2">{databaseView.summary.unique_d1_dates.join(', ')}</span>
                                  </div>
                                )}
                                {databaseView.summary.unique_dl_dates && (
                                  <div>
                                    <span className="font-medium text-purple-600">DL Dates:</span>
                                    <span className="ml-2">{databaseView.summary.unique_dl_dates.join(', ')}</span>
                                  </div>
                                )}
                                {databaseView.summary.date_range && (
                                  <div>
                                    <span className="font-medium text-gray-600">Date Range:</span>
                                    <span className="ml-2">{databaseView.summary.date_range}</span>
                                  </div>
                                )}
                              </div>
                            </div>

                            <div className="p-4 bg-gray-50 rounded-lg">
                              <h4 className="font-semibold text-gray-900 mb-2">Record Fields</h4>
                              <div className="text-xs text-gray-600">
                                {databaseView.summary.sample_record_fields && databaseView.summary.sample_record_fields.length > 0 ? (
                                  <div className="flex flex-wrap gap-1">
                                    {databaseView.summary.sample_record_fields.map((field, idx) => (
                                      <span key={idx} className="bg-white px-2 py-1 rounded border text-xs">
                                        {field}
                                      </span>
                                    ))}
                                  </div>
                                ) : (
                                  "No fields available"
                                )}
                              </div>
                            </div>
                          </div>
                        )}
                      </CardContent>
                    </Card>

                    {/* Raw Data Table */}
                    {databaseView.data && databaseView.data.length > 0 ? (
                      <Card data-testid="raw-database-table">
                        <CardHeader>
                          <CardTitle>Raw Database Records</CardTitle>
                          <CardDescription>
                            Showing all {databaseView.total_records} records from the database
                          </CardDescription>
                        </CardHeader>
                        <CardContent>
                          <div className="overflow-x-auto">
                            <table className="w-full text-sm">
                              <thead>
                                <tr className="border-b bg-gray-50">
                                  <th className="text-left p-2 font-semibold">Index</th>
                                  <th className="text-left p-2 font-semibold">Brand Name</th>
                                  <th className="text-left p-2 font-semibold">D1 Date</th>
                                  <th className="text-left p-2 font-semibold">D1 Stock</th>
                                  <th className="text-left p-2 font-semibold">DL Date</th>
                                  <th className="text-left p-2 font-semibold">DL Stock</th>
                                  <th className="text-left p-2 font-semibold">Days Analyzed</th>
                                  <th className="text-left p-2 font-semibold">Selling Rate</th>
                                  <th className="text-left p-2 font-semibold">Monthly Sale Value</th>
                                  <th className="text-left p-2 font-semibold">Current Stock Value</th>
                                  <th className="text-left p-2 font-semibold">Actions</th>
                                </tr>
                              </thead>
                              <tbody>
                                {databaseView.data.map((record, index) => (
                                  <tr key={index} className="border-b hover:bg-gray-50" data-testid={`db-row-${index}`}>
                                    <td className="p-2 font-medium">{record.index_number || 'N/A'}</td>
                                    <td className="p-2 max-w-xs truncate" title={record.brand_name}>{record.brand_name}</td>
                                    <td className="p-2 text-blue-600 text-xs">{record.D1_date || 'N/A'}</td>
                                    <td className="p-2 font-medium text-indigo-600">{record.D1_stock || 0}</td>
                                    <td className="p-2 text-purple-600 text-xs">{record.DL_date || 'N/A'}</td>
                                    <td className="p-2 font-medium text-orange-600">{record.DL_stock || 0}</td>
                                    <td className="p-2 font-medium text-green-600">{record.days_analyzed || 'N/A'}</td>
                                    <td className="p-2">{record.selling_rate ? formatCurrency(record.selling_rate) : 'N/A'}</td>
                                    <td className="p-2 font-medium text-blue-600">{record.monthly_sale_value ? formatCurrency(record.monthly_sale_value) : 'N/A'}</td>
                                    <td className="p-2 font-medium text-green-600">{record.stock_value_today ? formatCurrency(record.stock_value_today) : 'N/A'}</td>
                                    <td className="p-2">
                                      <Button
                                        variant="outline"
                                        size="sm"
                                        onClick={() => {
                                          // Show detailed record in JSON format
                                          const detailStr = JSON.stringify(record, null, 2);
                                          navigator.clipboard.writeText(detailStr);
                                          toast.success(`${record.brand_name} record copied to clipboard!`);
                                        }}
                                        className="text-xs"
                                      >
                                        Copy JSON
                                      </Button>
                                    </td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>

                          {databaseView.data.length > 10 && (
                            <div className="mt-4 text-center text-sm text-gray-600">
                              Showing all {databaseView.data.length} records
                            </div>
                          )}
                        </CardContent>
                      </Card>
                    ) : (
                      <div className="text-center py-12">
                        <Database className="h-12 w-12 text-gray-400 mx-auto mb-4" />
                        <h3 className="text-lg font-semibold text-gray-900 mb-2">No Database Records</h3>
                        <p className="text-gray-600">Upload liquor data to populate the database</p>
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="text-center py-12">
                    <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-600 mx-auto mb-4"></div>
                    <p className="text-gray-600">Loading database view...</p>
                  </div>
                )}
              </TabsContent>

            </Tabs>
          </div>
        ) : null}
      </div>

      {/* Module 1: Add Brand Modal */}
      <Dialog open={showBrandModal} onOpenChange={setShowBrandModal}>
        <DialogContent className="sm:max-w-[500px]" data-testid="add-brand-modal">
          <DialogHeader>
            <DialogTitle>Add New Brand</DialogTitle>
            <DialogDescription>
              Enter the details for the new liquor brand you want to add to your inventory.
            </DialogDescription>
          </DialogHeader>
          <form onSubmit={handleAddBrand} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="index_number">Index Number *</Label>
              <Input
                id="index_number"
                type="number"
                required
                value={brandFormData.index_number}
                onChange={(e) => setBrandFormData({...brandFormData, index_number: e.target.value})}
                placeholder="e.g., 63"
                data-testid="brand-index-input"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="brand_name">Brand Name *</Label>
              <Input
                id="brand_name"
                type="text"
                required
                value={brandFormData.brand_name}
                onChange={(e) => setBrandFormData({...brandFormData, brand_name: e.target.value})}
                placeholder="e.g., Johnnie Walker Black Label"
                data-testid="brand-name-input"
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="wholesale_rate">Wholesale Rate *</Label>
                <Input
                  id="wholesale_rate"
                  type="number"
                  step="0.01"
                  required
                  value={brandFormData.wholesale_rate}
                  onChange={(e) => setBrandFormData({...brandFormData, wholesale_rate: e.target.value})}
                  placeholder="e.g., 2500"
                  data-testid="brand-wholesale-input"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="selling_rate">Retail Rate *</Label>
                <Input
                  id="selling_rate"
                  type="number"
                  step="0.01"
                  required
                  value={brandFormData.selling_rate}
                  onChange={(e) => setBrandFormData({...brandFormData, selling_rate: e.target.value})}
                  placeholder="e.g., 2800"
                  data-testid="brand-retail-input"
                />
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="initial_stock_qty">Initial Stock Quantity</Label>
              <Input
                id="initial_stock_qty"
                type="number"
                value={brandFormData.initial_stock_qty}
                onChange={(e) => setBrandFormData({...brandFormData, initial_stock_qty: e.target.value})}
                placeholder="e.g., 50 (optional)"
                data-testid="brand-stock-input"
              />
              <p className="text-xs text-gray-500">Leave as 0 if you don't have stock yet</p>
            </div>
            <div className="flex justify-end gap-3 pt-4">
              <Button
                type="button"
                variant="outline"
                onClick={() => setShowBrandModal(false)}
                disabled={loading}
              >
                Cancel
              </Button>
              <Button
                type="submit"
                disabled={loading}
                data-testid="brand-submit-btn"
                className="bg-green-600 hover:bg-green-700"
              >
                {loading ? 'Adding...' : 'Add Brand'}
              </Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>

      {/* Module 1: Update Rates Modal */}
      <Dialog open={showRatesModal} onOpenChange={setShowRatesModal}>
        <DialogContent className="sm:max-w-[500px]" data-testid="update-rates-modal">
          <DialogHeader>
            <DialogTitle>Update Brand Rates</DialogTitle>
            <DialogDescription>
              Upload an Excel file to update wholesale and retail rates for existing brands.
              <br />
              <span className="text-sm font-medium mt-2 block">Required columns:</span>
              <span className="text-xs text-gray-600">Index, Brand Name, Wholesale Rate, Retail Rate</span>
            </DialogDescription>
          </DialogHeader>
          <form onSubmit={handleUpdateRates} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="rates-file">Select Excel File *</Label>
              <Input
                id="rates-file"
                type="file"
                accept=".xlsx,.xls,.csv"
                required
                onChange={(e) => setRatesFile(e.target.files[0])}
                data-testid="rates-file-input"
              />
              <p className="text-xs text-gray-500">
                File should contain: Index, Brand Name, Wholesale Rate, Retail Rate
              </p>
            </div>
            {ratesFile && (
              <Alert>
                <AlertDescription className="flex items-center">
                  <FileSpreadsheet className="w-4 h-4 mr-2" />
                  Selected: {ratesFile.name}
                </AlertDescription>
              </Alert>
            )}
            <div className="flex justify-end gap-3 pt-4">
              <Button
                type="button"
                variant="outline"
                onClick={() => {
                  setShowRatesModal(false);
                  setRatesFile(null);
                }}
                disabled={loading}
              >
                Cancel
              </Button>
              <Button
                type="submit"
                disabled={loading || !ratesFile}
                data-testid="rates-submit-btn"
                className="bg-blue-600 hover:bg-blue-700"
              >
                {loading ? 'Updating...' : 'Update Rates'}
              </Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>

      {/* Module 3: Stock Reset Dialog */}
      <Dialog open={showResetDialog} onOpenChange={setShowResetDialog}>
        <DialogContent className="sm:max-w-[500px]" data-testid="reset-stock-dialog">
          <DialogHeader>
            <DialogTitle className="flex items-center space-x-2 text-red-600">
              <AlertTriangle className="w-5 h-5" />
              <span>Reset Stock Data</span>
            </DialogTitle>
            <DialogDescription>
              This action will delete all current stock data. A backup will be created automatically before reset.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <Alert className="border-orange-200 bg-orange-50">
              <AlertTriangle className="h-4 w-4 text-orange-600" />
              <AlertDescription className="text-orange-800">
                <strong>Warning:</strong> This action cannot be undone. All date-wise stock data will be permanently deleted.
              </AlertDescription>
            </Alert>

            <div className="p-4 bg-blue-50 border border-blue-200 rounded-lg">
              <h4 className="font-semibold text-blue-900 mb-2">What happens during reset:</h4>
              <ul className="text-sm text-blue-800 space-y-1">
                <li>✅ Automatic backup is created</li>
                <li>✅ All stock records are deleted</li>
                <li>✅ Next upload becomes the new D1 (first date)</li>
                <li>✅ Fresh start for new cycle</li>
              </ul>
            </div>

            <div className="p-4 bg-green-50 border border-green-200 rounded-lg">
              <h4 className="font-semibold text-green-900 mb-2">Safety measures:</h4>
              <ul className="text-sm text-green-800 space-y-1">
                <li>🛡️ Backup created before deletion</li>
                <li>🛡️ Download backup anytime from "Backups" button</li>
                <li>🛡️ Backup includes all data for recovery</li>
              </ul>
            </div>

            <div className="flex justify-end gap-3 pt-4">
              <Button
                type="button"
                variant="outline"
                onClick={() => setShowResetDialog(false)}
                disabled={resetting}
              >
                Cancel
              </Button>
              <Button
                onClick={handleStockReset}
                disabled={resetting}
                data-testid="confirm-reset-btn"
                className="bg-red-600 hover:bg-red-700"
              >
                {resetting ? 'Resetting...' : 'Confirm Reset'}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* Module 3: Backups List Dialog */}
      <Dialog open={showBackupsDialog} onOpenChange={setShowBackupsDialog}>
        <DialogContent className="sm:max-w-[700px] max-h-[80vh] overflow-y-auto" data-testid="backups-dialog">
          <DialogHeader>
            <DialogTitle className="flex items-center space-x-2">
              <Database className="w-5 h-5 text-purple-600" />
              <span>Stock Backups</span>
            </DialogTitle>
            <DialogDescription>
              View and download stock data backups
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4">
            <div className="flex justify-between items-center">
              <p className="text-sm text-gray-600">Total backups: {backupsList.length}</p>
              <Button
                onClick={handleCreateBackup}
                size="sm"
                disabled={loading || !hasData}
                data-testid="create-backup-btn"
                className="bg-purple-600 hover:bg-purple-700"
              >
                <Database className="w-4 h-4 mr-2" />
                Create Backup
              </Button>
            </div>

            {backupsList.length > 0 ? (
              <div className="space-y-3">
                {backupsList.map((backup, index) => (
                  <div 
                    key={backup.id} 
                    className="p-4 border border-gray-200 rounded-lg hover:bg-gray-50"
                    data-testid={`backup-item-${index}`}
                  >
                    <div className="flex justify-between items-start mb-2">
                      <div>
                        <h4 className="font-semibold text-gray-900">
                          {backup.backup_reason === 'pre_reset_backup' ? '🔄 Pre-Reset Backup' : '💾 Manual Backup'}
                        </h4>
                        <p className="text-sm text-gray-600">
                          {formatDate(backup.backup_timestamp)}
                        </p>
                      </div>
                      <Badge variant="secondary">
                        {backup.total_records} records
                      </Badge>
                    </div>
                    <div className="flex justify-between items-center">
                      <div className="text-xs text-gray-500">
                        Created by: {backup.created_by}
                      </div>
                      <div className="flex gap-2">
                        <Button
                          onClick={() => handleDownloadBackup(backup.id, backup.backup_timestamp)}
                          size="sm"
                          variant="outline"
                          data-testid={`download-backup-${index}`}
                          className="border-blue-600 text-blue-600 hover:bg-blue-50"
                        >
                          <Download className="w-4 h-4 mr-1" />
                          Download
                        </Button>
                        <Button
                          onClick={() => handleDeleteBackup(backup.id, backup.backup_reason)}
                          size="sm"
                          variant="outline"
                          data-testid={`delete-backup-${index}`}
                          className="border-red-600 text-red-600 hover:bg-red-50"
                          disabled={loading}
                        >
                          <AlertTriangle className="w-4 h-4 mr-1" />
                          Delete
                        </Button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-center py-8">
                <Database className="w-12 h-12 text-gray-400 mx-auto mb-4" />
                <h3 className="text-lg font-semibold text-gray-900 mb-2">No Backups Yet</h3>
                <p className="text-gray-600">Create a backup to safely store your stock data</p>
              </div>
            )}
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}

export default App;