from io import BytesIO
from typing import Dict, List
import pandas as pd
from app.services.calculation_service import calculate_sales_metrics
from app.utils.date_utils import to_iso_date, parse_date_value

REQUIRED_BRAND_COLUMNS = ['brand', 'brand_name', 'item', 'name']
RATE_COLUMNS = ['rate', 'selling_rate', 'mrp']
WHOLESALE_COLUMNS = ['wholesale_rate', 'purchase_rate', 'cost_rate']


def _read_dataframe(file_content: bytes, filename: str = 'upload.xlsx') -> pd.DataFrame:
    lower = filename.lower()
    if lower.endswith('.csv'):
        return pd.read_csv(BytesIO(file_content))
    return pd.read_excel(BytesIO(file_content))


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(col).strip() for col in df.columns]
    return df


def _find_first_column(df: pd.DataFrame, candidates: List[str]):
    lowered = {str(col).strip().lower(): col for col in df.columns}
    for candidate in candidates:
        if candidate in lowered:
            return lowered[candidate]
    for col in df.columns:
        col_lower = str(col).lower()
        if any(candidate in col_lower for candidate in candidates):
            return col
    return None


def _extract_date_columns(df: pd.DataFrame) -> List[str]:
    date_cols = []
    for col in df.columns:
        if parse_date_value(col):
            date_cols.append(col)
    return date_cols


def parse_inventory_file(file_content: bytes, filename: str) -> List[Dict]:
    df = _read_dataframe(file_content, filename)
    df = _normalize_columns(df)

    brand_col = _find_first_column(df, REQUIRED_BRAND_COLUMNS)
    rate_col = _find_first_column(df, RATE_COLUMNS)
    wholesale_col = _find_first_column(df, WHOLESALE_COLUMNS)
    date_cols = _extract_date_columns(df)

    if not brand_col or not date_cols:
        raise ValueError('File must contain a brand column and at least one date column')

    records = []
    for index, row in df.iterrows():
        brand_name = str(row.get(brand_col, '')).strip()
        if not brand_name or brand_name.lower() == 'nan':
            continue
        date_stock_map = {to_iso_date(col): row.get(col) for col in date_cols if to_iso_date(col)}
        rate = float(row.get(rate_col, 0) or 0) if rate_col else 0.0
        wholesale_rate = float(row.get(wholesale_col, 0) or 0) if wholesale_col else 0.0
        metrics = calculate_sales_metrics(brand_name=brand_name, rate=rate, date_stock_map=date_stock_map)
        record = {
            'index_number': index + 1,
            'brand_name': brand_name,
            'rate': rate,
            'selling_rate': rate,
            'wholesale_rate': wholesale_rate,
            'daily_sales': date_stock_map,
            'monthly_sale_qty': metrics['total_sales_qty'],
            'avg_daily_sale': metrics['avg_daily_sales_qty'],
            'stock_available_days': round((metrics['current_stock_qty'] / metrics['avg_daily_sales_qty']), 2) if metrics['avg_daily_sales_qty'] else 0.0,
            'stock_value_before': (metrics['d1_stock'] or 0.0) * rate,
            'stock_value_today': metrics['current_stock_qty'] * rate,
            'stock_ratio': round((metrics['current_stock_qty'] / metrics['avg_daily_sales_qty']), 2) if metrics['avg_daily_sales_qty'] else 0.0,
            **metrics,
        }
        records.append(record)
    return records
