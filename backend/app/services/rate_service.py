from typing import Any, Dict, List
from fastapi import HTTPException
from app.db.mongo import collections


async def get_brand_rates() -> List[Dict[str, Any]]:
    rows = await collections.liquor_data.find(
        {},
        {'_id': 0, 'brand_name': 1, 'rate': 1, 'selling_rate': 1, 'wholesale_rate': 1}
    ).sort('brand_name', 1).to_list(5000)
    return rows


async def add_brand(payload: Dict[str, Any]) -> Dict[str, Any]:
    brand_name = str(payload.get('brand_name', '')).strip()
    if not brand_name:
        raise HTTPException(status_code=400, detail='brand_name is required')

    existing = await collections.liquor_data.find_one({'brand_name': brand_name})
    if existing:
        raise HTTPException(status_code=400, detail='Brand already exists')

    record = {
        'brand_name': brand_name,
        'rate': float(payload.get('selling_rate', payload.get('rate', 0)) or 0),
        'selling_rate': float(payload.get('selling_rate', payload.get('rate', 0)) or 0),
        'wholesale_rate': float(payload.get('wholesale_rate', 0) or 0),
        'daily_sales': {},
        'monthly_sale_qty': 0,
        'monthly_sale_value': 0,
        'avg_daily_sale': 0,
        'stock_available_days': 0,
        'stock_value_before': 0,
        'stock_value_today': 0,
        'stock_ratio': 0,
        'index_number': int(payload.get('index_number', 0) or 0),
        'd1_date': None,
        'd1_stock': None,
        'dl_date': None,
        'dl_stock': None,
        'total_sales_qty': 0,
        'avg_daily_sales_qty': 0,
        'days_analyzed': 0,
        'current_stock_qty': 0,
        'calculation_method': 'manual_brand_entry',
        'replenishment_detected': False,
    }

    await collections.liquor_data.insert_one(record)
    return {'success': True, 'brand_name': brand_name}


async def update_brand_rates(updates: List[Dict[str, Any]]) -> Dict[str, Any]:
    updated = 0

    for item in updates:
        brand_name = item.get('brand_name')
        if not brand_name:
            continue

        selling_rate = float(item.get('selling_rate', item.get('rate', 0)) or 0)
        wholesale_rate = float(item.get('wholesale_rate', 0) or 0)

        result = await collections.liquor_data.update_one(
            {'brand_name': brand_name},
            {'$set': {'rate': selling_rate, 'selling_rate': selling_rate, 'wholesale_rate': wholesale_rate}}
        )
        updated += result.modified_count

    return {'success': True, 'updated_count': updated}
