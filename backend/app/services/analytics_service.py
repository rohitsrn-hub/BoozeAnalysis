from collections import defaultdict
from typing import Any, Dict, List
from app.db.mongo import collections


async def get_chart_data() -> Dict[str, List[Dict[str, Any]]]:
    rows = await collections.liquor_data.find({}, {'_id': 0}).to_list(5000)
    if not rows:
        return {
            'volume_leaders': [],
            'velocity_leaders': [],
            'revenue_leaders': [],
            'revenue_proportion': [],
        }

    volume_leaders = sorted(rows, key=lambda x: float(x.get('total_sales_qty', 0) or 0), reverse=True)[:10]
    velocity_leaders = sorted(rows, key=lambda x: float(x.get('avg_daily_sales_qty', 0) or 0), reverse=True)[:10]
    revenue_leaders = sorted(rows, key=lambda x: float(x.get('monthly_sale_value', 0) or 0), reverse=True)[:10]
    total_revenue = sum(float(x.get('monthly_sale_value', 0) or 0) for x in rows) or 1.0

    revenue_proportion = [
        {
            'brand_name': row.get('brand_name'),
            'monthly_sale_value': float(row.get('monthly_sale_value', 0) or 0),
            'percentage': round((float(row.get('monthly_sale_value', 0) or 0) / total_revenue) * 100, 2),
        }
        for row in revenue_leaders
    ]

    return {
        'volume_leaders': volume_leaders,
        'velocity_leaders': velocity_leaders,
        'revenue_leaders': revenue_leaders,
        'revenue_proportion': revenue_proportion,
    }


async def get_demand_recommendations() -> List[Dict[str, Any]]:
    rows = await collections.liquor_data.find({}, {'_id': 0}).to_list(5000)
    recommendations = []

    for row in rows:
        avg_daily = float(row.get('avg_daily_sales_qty', 0) or 0)
        current_stock = float(row.get('current_stock_qty', 0) or 0)
        target_days = 30
        recommended_qty = max(0.0, round((avg_daily * target_days) - current_stock, 2))
        urgency = 'low'

        if avg_daily > 0:
            stock_days = current_stock / avg_daily if avg_daily else 0
            if stock_days <= 7:
                urgency = 'high'
            elif stock_days <= 15:
                urgency = 'medium'

        if recommended_qty > 0:
            recommendations.append({
                'brand_name': row.get('brand_name'),
                'selling_rate': float(row.get('selling_rate', row.get('rate', 0)) or 0),
                'wholesale_rate': float(row.get('wholesale_rate', 0) or 0),
                'current_stock_qty': current_stock,
                'recommended_qty': recommended_qty,
                'urgency_level': urgency,
            })

    recommendations.sort(key=lambda x: ({'high': 0, 'medium': 1, 'low': 2}[x['urgency_level']], -x['recommended_qty']))
    return recommendations


async def get_database_view() -> List[Dict[str, Any]]:
    return await collections.liquor_data.find({}, {'_id': 0}).sort('brand_name', 1).to_list(5000)


async def get_sales_trends() -> List[Dict[str, Any]]:
    rows = await collections.liquor_data.find({}, {'_id': 0}).to_list(5000)
    bucket = defaultdict(float)

    for row in rows:
        bucket['current_period_sales_value'] += float(row.get('monthly_sale_value', 0) or 0)
        bucket['current_period_sales_qty'] += float(row.get('total_sales_qty', 0) or 0)

    return [{'period': key, 'value': round(value, 2)} for key, value in bucket.items()]


async def get_calculation_details() -> List[Dict[str, Any]]:
    rows = await collections.liquor_data.find({}, {'_id': 0}).to_list(5000)
    details = []

    for row in rows:
        details.append({
            'brand_name': row.get('brand_name'),
            'd1_date': row.get('d1_date'),
            'd1_stock': row.get('d1_stock'),
            'dl_date': row.get('dl_date'),
            'dl_stock': row.get('dl_stock'),
            'days_analyzed': row.get('days_analyzed', 0),
            'total_sales_qty': row.get('total_sales_qty', 0),
            'avg_daily_sales_qty': row.get('avg_daily_sales_qty', 0),
            'calculation_method': row.get('calculation_method', 'stock_difference_estimate'),
            'replenishment_detected': row.get('replenishment_detected', False),
        })

    return details
