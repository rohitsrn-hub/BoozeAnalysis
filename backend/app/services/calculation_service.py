from typing import Dict, List, Optional
from app.utils.date_utils import parse_date_value


def _safe_number(value, default=None):
    if value in ('', None):
        return default
    try:
        return float(value)
    except Exception:
        return default


def choose_boundary_stock(sorted_snapshots: List[Dict], boundary: str) -> Optional[float]:
    if not sorted_snapshots:
        return None
    if boundary == 'first':
        return _safe_number(sorted_snapshots[0].get('stock'), None)
    return _safe_number(sorted_snapshots[-1].get('stock'), None)


def detect_replenishment(sorted_snapshots: List[Dict]) -> bool:
    previous = None
    for item in sorted_snapshots:
        current = _safe_number(item.get('stock'), None)
        if current is None:
            continue
        if previous is not None and current > previous:
            return True
        previous = current
    return False


def calculate_sales_metrics(brand_name: str, rate: float, date_stock_map: Dict[str, float]) -> Dict:
    normalized = []
    for raw_date, stock in date_stock_map.items():
        parsed = parse_date_value(raw_date)
        if not parsed:
            continue
        normalized.append({
            'raw_date': raw_date,
            'iso_date': parsed.strftime('%Y-%m-%d'),
            'parsed_date': parsed,
            'stock': _safe_number(stock, None),
        })
    normalized.sort(key=lambda x: x['parsed_date'])
    if not normalized:
        return {
            'brand_name': brand_name,
            'selling_rate': rate or 0.0,
            'd1_date': None,
            'd1_stock': None,
            'dl_date': None,
            'dl_stock': None,
            'total_sales_qty': 0.0,
            'avg_daily_sales_qty': 0.0,
            'days_analyzed': 0,
            'current_stock_qty': 0.0,
            'monthly_sale_value': 0.0,
            'calculation_method': 'no_valid_dates',
            'replenishment_detected': False,
        }
    d1 = choose_boundary_stock(normalized, 'first')
    dl = choose_boundary_stock(normalized, 'last')
    replenishment = detect_replenishment(normalized)
    days = max(1, len(normalized) - 1)
    estimated_sales = max(0.0, (d1 or 0.0) - (dl or 0.0)) if d1 is not None and dl is not None else 0.0
    avg_daily = estimated_sales / days if days else 0.0
    current_stock = dl or 0.0
    return {
        'brand_name': brand_name,
        'selling_rate': rate or 0.0,
        'd1_date': normalized[0]['iso_date'],
        'd1_stock': d1,
        'dl_date': normalized[-1]['iso_date'],
        'dl_stock': dl,
        'total_sales_qty': round(estimated_sales, 2),
        'avg_daily_sales_qty': round(avg_daily, 2),
        'days_analyzed': days,
        'current_stock_qty': current_stock,
        'monthly_sale_value': round(estimated_sales * (rate or 0.0), 2),
        'calculation_method': 'stock_difference_estimate',
        'replenishment_detected': replenishment,
    }
