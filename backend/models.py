from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
import uuid
from datetime import datetime, timezone

class LiquorData(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    brand_name: str = Field(default="Unknown Brand")
    rate: float = Field(default=0.0)
    daily_sales: Dict[str, float] = Field(default_factory=dict)
    monthly_sale_qty: int = Field(default=0)
    monthly_sale_value: float = Field(default=0.0)
    avg_daily_sale: float = Field(default=0.0)
    stock_available_days: float = Field(default=0.0)
    stock_value_before: float = Field(default=0.0)
    stock_value_today: float = Field(default=0.0)
    stock_ratio: float = Field(default=0.0)
    index_number: int = Field(default=0)
    wholesale_rate: float = Field(default=0.0)
    selling_rate: float = Field(default=0.0)
    D1_date: str = Field(default="N/A")
    D1_stock: float = Field(default=0.0)
    DL_date: str = Field(default="N/A")
    DL_stock: float = Field(default=0.0)
    total_sales_qty: float = Field(default=0.0)
    avg_daily_sales_qty: float = Field(default=0.0)
    days_analyzed: int = Field(default=0)
    current_stock_qty: int = Field(default=0)
    upload_timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class UploadHistory(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    filename: str
    upload_type: str  # "full_monthly", "daily_update", or "rate_update"
    upload_timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    records_count: int
    file_size: int
    uploaded_by: str = Field(default="dashboard_user")
    can_undo: bool = Field(default=True)
    undone_at: Optional[datetime] = None
    changes_snapshot: Optional[Dict[str, Any]] = None

class OverstockConfig(BaseModel):
    multiplier: float = 3.0

class StockBackup(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    backup_timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    total_records: int
    backup_reason: str = Field(default="manual_backup")
    created_by: str = Field(default="dashboard_user")
    data_snapshot: List[Dict[str, Any]]

class BrandMaster(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    brand_name: str
    wholesale_rate: float = Field(default=0.0)
    selling_rate: float = Field(default=0.0)
    index_number: int = Field(default=0)
    last_updated: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

# --- Response & Utility Models ---

class AnalyticsResponse(BaseModel):
    total_brands: int
    total_stock_value: float
    total_overstocked_value: float
    overstocked_brands: int
    top_selling_brands: List[Dict[str, Any]]
    overstocked_items: List[Dict[str, Any]]
    sales_trends: Dict[str, Any]

class ChartsResponse(BaseModel):
    volume_leaders: List[Dict[str, Any]]
    velocity_leaders: List[Dict[str, Any]]
    revenue_leaders: List[Dict[str, Any]]
    revenue_proportion: List[Dict[str, Any]]

class DemandRecommendation(BaseModel):
    brand_name: str
    selling_rate: float
    wholesale_rate: float
    current_stock_qty: int
    recommended_qty: float
    urgency_level: str

class AddBrandRequest(BaseModel):
    index_number: int
    brand_name: str
    wholesale_rate: float
    selling_rate: float
    initial_stock_qty: int = Field(default=0)

class BrandRateInfo(BaseModel):
    id: str
    index_number: int
    brand_name: str
    wholesale_rate: float
    selling_rate: float
    current_stock_qty: int
    stock_value_today: float
    last_updated: datetime

class UpdateRatesResponse(BaseModel):
    updated_count: int
    not_found_count: int
    updated_brands: List[str]
    not_found_brands: List[str]

class BackupListResponse(BaseModel):
    id: str
    backup_timestamp: datetime
    total_records: int
    backup_reason: str
    created_by: str

class ReportParameters(BaseModel):
    include_executive_summary: bool = True
    include_top_sellers: bool = True
    include_slow_sellers: bool = True
    include_capital_blockers: bool = True
    include_revenue_analysis: bool = True
    include_demand_forecast: bool = True
    include_profit_analysis: bool = True
    include_recommendations: bool = True
    include_datewise_analysis: bool = False
    report_title: str = "Monthly Sales Analytics Report"
    report_period: str = ""
    selected_periods: list = []

class HistoricalSalesAverage(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    brand_name: str
    month_year: str
    average_daily_sales_qty: float
    average_daily_sales_value: float
    total_sales_quantity: float
    total_sales_value: float
    total_sales_days: int
    wholesale_rate: float = Field(default=0.0)
    selling_rate: float = Field(default=0.0)
    calculation_date: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class AnalyticsSourceInfo(BaseModel):
    data_source: str
    days_of_data: int
    using_month: str
    transition_threshold: int = 5
    is_transitioning: bool
    confidence_level: str

class TopSeller(BaseModel):
    brand_name: str
    revenue: float
    volume: float
    profit: float
    profit_margin: float

class SlowSeller(BaseModel):
    brand_name: str
    revenue: float
    volume: float
    stock_days: float
    stock_value: float

class CapitalBlocker(BaseModel):
    brand_name: str
    stock_value: float
    stock_quantity: float
    stock_days: float
    overstocked_ratio: float

class DemandForecastItem(BaseModel):
    brand_name: str
    current_stock: float
    recommended_qty: float
    wholesale_rate: float
    total_cost: float
    urgency_level: str

class ProfitAnalysis(BaseModel):
    total_revenue: float
    total_cost: float
    total_profit: float
    average_profit_margin: float
    top_profit_brands: List[Dict[str, Any]]

class MonthlyReportData(BaseModel):
    report_period: str
    total_brands: int
    executive_summary: Dict[str, Any]
    top_sellers_revenue: List[TopSeller]
    top_sellers_volume: List[TopSeller]
    slow_sellers: List[SlowSeller]
    capital_blockers: List[CapitalBlocker]
    revenue_analysis: Dict[str, Any]
    demand_forecast: List[DemandForecastItem]
    profit_analysis: ProfitAnalysis
    recommendations: List[str]
    datewise_analysis: Optional[List[Dict[str, Any]]] = None
