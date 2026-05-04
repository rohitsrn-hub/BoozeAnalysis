from collections import defaultdict
from typing import Any, Dict, List
from app.db.mongo import collections


async def get_historical_periods() -> List[Dict[str, Any]]:
    rows = await collections.upload_history.find(
        {'upload_type': 'full_monthly'},
        {'_id': 0}
    ).sort('upload_timestamp', -1).to_list(500)

    result = []
    for row in rows:
        ts = row.get('upload_timestamp')
        result.append({
            'id': row.get('id'),
            'filename': row.get('filename'),
            'upload_timestamp': ts.isoformat() if hasattr(ts, 'isoformat') else str(ts),
            'records_count': row.get('records_count', 0),
        })
    return result


async def get_historical_data_view(period_ids: List[str]) -> List[Dict[str, Any]]:
    if not period_ids:
        return []
    rows = await collections.stock_backups.find({'id': {'$in': period_ids}}, {'_id': 0}).to_list(500)
    return rows


async def get_historical_analysis(period_ids: List[str]) -> List[Dict[str, Any]]:
    backups = await get_historical_data_view(period_ids)
    aggregated = defaultdict(lambda: {
        'brand_name': '',
        'total_sales_qty': 0.0,
        'monthly_sale_value': 0.0,
        'period_count': 0
    })

    for backup in backups:
        for row in backup.get('data_snapshot', []):
            brand = row.get('brand_name')
            if not brand:
                continue
            aggregated[brand]['brand_name'] = brand
            aggregated[brand]['total_sales_qty'] += float(row.get('total_sales_qty', 0) or 0)
            aggregated[brand]['monthly_sale_value'] += float(row.get('monthly_sale_value', 0) or 0)
            aggregated[brand]['period_count'] += 1

    result = []
    for brand, values in aggregated.items():
        periods = values['period_count'] or 1
        result.append({
            'brand_name': brand,
            'avg_sales_qty': round(values['total_sales_qty'] / periods, 2),
            'avg_sales_value': round(values['monthly_sale_value'] / periods, 2),
            'period_count': periods,
        })

    result.sort(key=lambda x: x['avg_sales_value'], reverse=True)
    return result


async def get_historical_averages(month: str | None = None) -> List[Dict[str, Any]]:
    rows = await collections.brands_master.find({}, {'_id': 0}).sort('brand_name', 1).to_list(5000)
    if month:
        return [row for row in rows if row.get('month') == month]
    return rows


async def calculate_historical_averages() -> Dict[str, Any]:
    backups = await collections.stock_backups.find({}, {'_id': 0}).to_list(1000)
    aggregated = defaultdict(lambda: {'brand_name': '', 'total_sales_qty': 0.0, 'period_count': 0})

    for backup in backups:
        for row in backup.get('data_snapshot', []):
            brand = row.get('brand_name')
            if not brand:
                continue
            aggregated[brand]['brand_name'] = brand
            aggregated[brand]['total_sales_qty'] += float(row.get('total_sales_qty', 0) or 0)
            aggregated[brand]['period_count'] += 1

    await collections.brands_master.delete_many({})
    output = []

    for brand, values in aggregated.items():
        periods = values['period_count'] or 1
        doc = {
            'brand_name': brand,
            'avg_sales_qty': round(values['total_sales_qty'] / periods, 2),
            'period_count': periods,
        }
        output.append(doc)

    if output:
        await collections.brands_master.insert_many(output)

    return {'success': True, 'calculated_records': len(output)}
