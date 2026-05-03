from fastapi import APIRouter
from app.db.mongo import collections

router = APIRouter(prefix='/api', tags=['analytics'])

@router.get('/analytics')
async def get_analytics(overstock_multiplier: float = 3.0):
    rows = await collections.liquor_data.find({}, {'_id': 0}).to_list(5000)
    total_stock_value = sum(float(row.get('stock_value_today', 0) or 0) for row in rows)
    overstocked = []
    for row in rows:
        avg_daily = float(row.get('avg_daily_sales_qty', 0) or 0)
        current_stock = float(row.get('current_stock_qty', 0) or 0)
        stock_days = current_stock / avg_daily if avg_daily else 0
        if avg_daily and stock_days > overstock_multiplier:
            overstocked.append({
                'brand_name': row.get('brand_name'),
                'stock_days': round(stock_days, 2),
                'stock_value_today': float(row.get('stock_value_today', 0) or 0),
            })
    top_selling = sorted(rows, key=lambda x: float(x.get('monthly_sale_value', 0) or 0), reverse=True)[:10]
    return {
        'total_brands': len(rows),
        'total_stock_value': round(total_stock_value, 2),
        'total_overstocked_value': round(sum(x['stock_value_today'] for x in overstocked), 2),
        'overstocked_brands': len(overstocked),
        'top_selling_brands': top_selling,
        'overstocked_items': overstocked,
        'sales_trends': {'calculation_basis': 'stock_difference_estimate'},
    }
