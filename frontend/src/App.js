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
import { Upload, TrendingUp, AlertTriangle, BarChart3, Package, DollarSign, Calendar, FileSpreadsheet, HelpCircle, Play, CheckCircle, ArrowRight } from "lucide-react";
import { toast } from "sonner";
import { Toaster } from "@/components/ui/sonner";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

function App() {
  const [analyticsData, setAnalyticsData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [overstockMultiplier, setOverstockMultiplier] = useState(3.0);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [hasData, setHasData] = useState(false);

  // Fetch analytics data
  const fetchAnalytics = async (multiplier = 3.0) => {
    try {
      setLoading(true);
      const response = await axios.get(`${API}/analytics?overstock_multiplier=${multiplier}`);
      setAnalyticsData(response.data);
      setHasData(true);
      toast.success("Analytics updated successfully");
    } catch (error) {
      console.error("Error fetching analytics:", error);
      if (error.response?.status === 404) {
        setHasData(false);
        toast.error("No data found. Please upload liquor data first.");
      } else {
        toast.error("Failed to fetch analytics data");
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
              <div className="text-sm text-gray-500">
                <p>Supported formats: .xlsx, .xls, .csv</p>
              </div>
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
              <TabsList className="grid w-full grid-cols-3">
                <TabsTrigger value="sales-trends" data-testid="sales-trends-tab">Sales Trends</TabsTrigger>
                <TabsTrigger value="overstocking" data-testid="overstocking-tab">Overstocking Alerts</TabsTrigger>
                <TabsTrigger value="brand-performance" data-testid="brand-performance-tab">Brand Performance</TabsTrigger>
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
                        <div className="grid gap-4">
                          {Object.entries(analyticsData.sales_trends)
                            .slice(-10) // Show last 10 days
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
                      ) : (
                        <p className="text-gray-500 text-center py-8">No sales trend data available</p>
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
            </Tabs>
          </div>
        ) : null}
      </div>
    </div>
  );
}

export default App;