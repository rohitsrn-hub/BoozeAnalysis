from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4
from pydantic import BaseModel, Field

class LiquorRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    brand_name: str
    rate: float = 0.0
    daily_sales: Dict[str, float] = Field(default_factory=dict)
    monthly_sale_qty: float = 0.0
    monthly_sale_value: float = 0.0
    avg_daily_sale: float = 0.0
    stock_available_days: float = 0.0
    stock_value_before: float = 0.0
    stock_value_today: float = 0.0
    stock_ratio: float = 0.0
    index_number: int = 0
    wholesale_rate: float = 0.0
    selling_rate: float = 0.0
    d1_date: Optional[str] = None
    d1_stock: Optional[float] = None
    dl_date: Optional[str] = None
    dl_stock: Optional[float] = None
    total_sales_qty: float = 0.0
    avg_daily_sales_qty: float = 0.0
    days_analyzed: int = 0
    current_stock_qty: float = 0.0
    upload_timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    calculation_method: str = 'stock_difference_estimate'
    replenishment_detected: bool = False

class UploadHistory(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    filename: str
    upload_type: str
    upload_timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    records_count: int
    file_size: int
    uploaded_by: str = 'dashboard_user'
    can_undo: bool = True
    undone_at: Optional[datetime] = None
    changes_snapshot: Optional[Dict[str, Any]] = None

class StockBackup(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    total_records: int
    data_snapshot: List[Dict[str, Any]]
    backup_reason: str

class AnalyticsSummary(BaseModel):
    total_brands: int
    total_stock_value: float
    total_overstocked_value: float
    overstocked_brands: int
    top_selling_brands: List[Dict[str, Any]]
    overstocked_items: List[Dict[str, Any]]
    sales_trends: Dict[str, Any]
