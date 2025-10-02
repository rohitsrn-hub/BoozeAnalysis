import { useState, useEffect } from "react";
import "@/App.css";
import axios from "axios";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Progress } from "@/components/ui/progress";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Upload, TrendingUp, AlertTriangle, BarChart3, Package, DollarSign, Calendar, FileSpreadsheet, HelpCircle, Play, CheckCircle, ArrowRight, Download, Zap, Target, Crown } from "lucide-react";
import { toast } from "sonner";
import { Toaster } from "@/components/ui/sonner";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell, LineChart, Line } from "recharts";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

function App() {
  const [analyticsData, setAnalyticsData] = useState(null);
  const [chartsData, setChartsData] = useState(null);
  const [demandData, setDemandData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [overstockMultiplier, setOverstockMultiplier] = useState(3.0);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [hasData, setHasData] = useState(false);
  const [showOnboarding, setShowOnboarding] = useState(false);
  const [onboardingStep, setOnboardingStep] = useState(0);

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
      
      setHasData(true);
      toast.success("Analytics updated successfully");
    } catch (error) {
      console.error("Error fetching data:", error);
      if (error.response?.status === 404) {
        setHasData(false);
        toast.error("No data found. Please upload liquor data first.");
      } else {
        toast.error("Failed to fetch data");
      }
    } finally {
      setLoading(false);
    }
  };

  // Handle file upload
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
      
      // Fetch analytics after successful upload
      await fetchAnalytics(overstockMultiplier);
      
    } catch (error) {
      console.error("Error uploading file:", error);
      toast.error(error.response?.data?.detail || "Failed to upload file");
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

  // Handle demand list export
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
        : `liquor_demand_recommendations_${new Date().toISOString().split('T')[0]}.xlsx`;
      
      link.setAttribute('download', filename);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
      
      toast.success("Demand list exported successfully!");
    } catch (error) {
      console.error("Error exporting demand list:", error);
      toast.error("Failed to export demand list");
    }
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
                <p className="text-sm text-gray-600">Comprehensive sales analysis and inventory management</p>
              </div>
            </div>
            
            <div className="flex items-center space-x-4">
              {/* Help Guide */}
              <Dialog open={showOnboarding} onOpenChange={setShowOnboarding}>
                <DialogTrigger asChild>
                  <Button 
                    variant="outline" 
                    size="sm"
                    className="bg-white hover:bg-gray-50"
                    data-testid="help-guide-btn"
                  >
                    <HelpCircle className="w-4 h-4 mr-2" />
                    Help Guide
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

              {/* Overstock Multiplier Configuration */}
              <div className="flex items-center space-x-2">
                <Label htmlFor="multiplier" className="text-sm font-medium text-gray-700">
                  Overstock Multiplier:
                </Label>
                <div className="flex items-center space-x-2">
                  <Input
                    id="multiplier"
                    type="number"
                    step="0.1"
                    min="1"
                    max="10"
                    value={overstockMultiplier}
                    onChange={(e) => setOverstockMultiplier(parseFloat(e.target.value) || 3.0)}
                    className="w-20"
                    data-testid="overstock-multiplier-input"
                  />
                  <Button
                    onClick={handleMultiplierChange}
                    size="sm"
                    variant="outline"
                    disabled={!hasData || loading}
                    data-testid="update-multiplier-btn"
                  >
                    Update
                  </Button>
                </div>
              </div>

              {/* File Upload */}
              <div className="relative">
                <Label htmlFor="file-upload" className="cursor-pointer">
                  <Button 
                    variant="default" 
                    className="bg-indigo-600 hover:bg-indigo-700"
                    disabled={loading}
                    data-testid="upload-btn"
                  >
                    <Upload className="w-4 h-4 mr-2" />
                    Upload Data
                  </Button>
                </Label>
                <Input
                  id="file-upload"
                  type="file"
                  accept=".xlsx,.xls,.csv"
                  onChange={handleFileUpload}
                  className="hidden"
                  data-testid="file-input"
                />
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
            <Tabs defaultValue="sales-trends" className="w-full">
              <TabsList className="grid w-full grid-cols-5">
                <TabsTrigger value="sales-trends" data-testid="sales-trends-tab">Sales Trends</TabsTrigger>
                <TabsTrigger value="performance-charts" data-testid="performance-charts-tab">Performance Charts</TabsTrigger>
                <TabsTrigger value="overstocking" data-testid="overstocking-tab">Overstocking Alerts</TabsTrigger>
                <TabsTrigger value="brand-performance" data-testid="brand-performance-tab">Top Brands</TabsTrigger>
                <TabsTrigger value="recommendations" data-testid="recommendations-tab">Recommendations</TabsTrigger>
              </TabsList>

              {/* Sales Trends Tab */}
              <TabsContent value="sales-trends" className="space-y-6">
                <Card data-testid="sales-trends-card">
                  <CardHeader>
                    <CardTitle className="flex items-center space-x-2">
                      <TrendingUp className="h-5 w-5 text-indigo-600" />
                      <span>Daily Sales Trends</span>
                    </CardTitle>
                    <CardDescription>Sales performance across all brands over time</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-4">
                      {Object.entries(analyticsData.sales_trends).length > 0 ? (
                        <>
                          <div className="h-80 w-full">
                            <ResponsiveContainer width="100%" height="100%">
                              <LineChart
                                data={Object.entries(analyticsData.sales_trends)
                                  .filter(([date]) => !date.includes('Monthly') && !date.includes('Stock'))
                                  .map(([date, sales]) => ({
                                    date: date,
                                    sales: sales
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
                                  formatter={(value) => [formatNumber(value), "Units Sold"]}
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
                          
                          <div className="grid gap-4 mt-6">
                            <h4 className="font-medium text-gray-900">Daily Sales Summary</h4>
                            {Object.entries(analyticsData.sales_trends)
                              .filter(([date]) => !date.includes('Monthly') && !date.includes('Stock'))
                              .slice(-7)
                              .map(([date, sales]) => (
                                <div key={date} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                                  <div className="flex items-center space-x-3">
                                    <Calendar className="h-4 w-4 text-gray-500" />
                                    <span className="font-medium text-gray-900">{date}</span>
                                  </div>
                                  <div className="text-right">
                                    <div className="text-lg font-semibold text-indigo-600">{formatNumber(sales)}</div>
                                    <div className="text-xs text-gray-500">units sold</div>
                                  </div>
                                </div>
                              ))}
                          </div>
                        </>
                      ) : (
                        <p className="text-gray-500 text-center py-8">No sales trend data available</p>
                      )}
                    </div>
                  </CardContent>
                </Card>
              </TabsContent>

              {/* Performance Charts Tab */}
              <TabsContent value="performance-charts" className="space-y-6">
                {chartsData && (
                  <div className="grid gap-6">
                    {/* Volume Leaders Chart */}
                    <Card data-testid="volume-leaders-chart">
                      <CardHeader>
                        <CardTitle className="flex items-center space-x-2">
                          <BarChart3 className="h-5 w-5 text-blue-600" />
                          <span>Volume Leaders</span>
                        </CardTitle>
                        <CardDescription>Top brands by quantity sold</CardDescription>
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
                              <Tooltip formatter={(value) => [formatNumber(value), "Quantity Sold"]} />
                              <Bar dataKey="value" fill="#3B82F6" />
                            </BarChart>
                          </ResponsiveContainer>
                        </div>
                      </CardContent>
                    </Card>

                    {/* Revenue Leaders Chart */}
                    <Card data-testid="revenue-leaders-chart">
                      <CardHeader>
                        <CardTitle className="flex items-center space-x-2">
                          <DollarSign className="h-5 w-5 text-green-600" />
                          <span>Revenue Leaders</span>
                        </CardTitle>
                        <CardDescription>Top brands by sales revenue</CardDescription>
                      </CardHeader>
                      <CardContent>
                        <div className="h-80 w-full">
                          <ResponsiveContainer width="100%" height="100%">
                            <BarChart data={chartsData.revenue_leaders}>
                              <CartesianGrid strokeDasharray="3 3" />
                              <XAxis 
                                dataKey="name" 
                                angle={-45}
                                textAnchor="end"
                                height={100}
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

                    {/* Velocity Leaders and Revenue Proportion */}
                    <div className="grid md:grid-cols-2 gap-6">
                      <Card data-testid="velocity-leaders-chart">
                        <CardHeader>
                          <CardTitle className="flex items-center space-x-2">
                            <Zap className="h-5 w-5 text-yellow-600" />
                            <span>Fastest Moving</span>
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

                      <Card data-testid="revenue-proportion-chart">
                        <CardHeader>
                          <CardTitle className="flex items-center space-x-2">
                            <Crown className="h-5 w-5 text-purple-600" />
                            <span>Revenue Share</span>
                          </CardTitle>
                          <CardDescription>Contribution to total sales</CardDescription>
                        </CardHeader>
                        <CardContent>
                          <div className="h-64 w-full">
                            <ResponsiveContainer width="100%" height="100%">
                              <PieChart>
                                <Pie
                                  data={chartsData.revenue_proportion.slice(0, 6)}
                                  cx="50%"
                                  cy="50%"
                                  innerRadius={40}
                                  outerRadius={80}
                                  paddingAngle={5}
                                  dataKey="percentage"
                                  label={({ name, percentage }) => `${name}: ${percentage}%`}
                                >
                                  {chartsData.revenue_proportion.slice(0, 6).map((entry, index) => (
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
                  </div>
                )}
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
                    <CardDescription>Ranked by monthly sales value</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-4">
                      {analyticsData.top_selling_brands.map((brand, index) => (
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

              {/* Recommendations Tab */}
              <TabsContent value="recommendations" className="space-y-6">
                <div className="flex justify-between items-center">
                  <div>
                    <h2 className="text-2xl font-bold text-gray-900">Smart Demand Recommendations</h2>
                    <p className="text-gray-600">AI-powered insights for optimal inventory management</p>
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
                          Optimized ordering recommendations based on sales velocity and current stock levels
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
                                      {rec.days_of_stock.toFixed(1)} days of stock remaining
                                    </p>
                                  </div>
                                  <Badge className={urgencyBadgeColors[rec.urgency_level]}>
                                    {rec.urgency_level} PRIORITY
                                  </Badge>
                                </div>
                                
                                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                                  <div>
                                    <span className="text-gray-600">Current Stock:</span>
                                    <div className="font-medium">{formatCurrency(rec.current_stock)}</div>
                                  </div>
                                  <div>
                                    <span className="text-gray-600">Monthly Avg Sales:</span>
                                    <div className="font-medium">{formatCurrency(rec.avg_monthly_sales)}</div>
                                  </div>
                                  <div>
                                    <span className="text-gray-600">Recommended Order:</span>
                                    <div className="font-medium text-indigo-600">
                                      {formatCurrency(rec.recommended_quantity)}
                                    </div>
                                  </div>
                                  <div>
                                    <span className="text-gray-600">Target:</span>
                                    <div className="font-medium">45 days stock</div>
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
                    <p className="text-gray-600">Upload sales data to generate smart demand recommendations</p>
                  </div>
                )}
              </TabsContent>
            </Tabs>
          </div>
        ) : null}
      </div>
    </div>
  );
}

export default App;