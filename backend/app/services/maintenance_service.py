from io import BytesIO
from math import ceil
from typing import Any, Dict, List
from fastapi import HTTPException
from fastapi.responses import StreamingResponse
import pandas as pd
from app.db.mongo import collections
from app.services.analytics_service import get_demand_recommendations


async def export_demand_list_file():
    recommendations = await get_demand_recommendations()
    if not recommendations:
        raise HTTPException(status_code=404, detail='No recommendations to export')

    liquor_records = await collections.liquor_data.find({}, {'_id': 0}).to_list(5000)
    brand_lookup = {row.get('brand_name'): row for row in liquor_records}

    df_rows = []
    for rec in recommendations:
        brand_name = rec.get('brand_name')
        brand_row = brand_lookup.get(brand_name, {})
        recommended_qty = float(rec.get('recommended_qty', 0) or 0)
        wholesale_rate = float(rec.get('wholesale_rate', 0) or 0)
        current_stock_qty = float(rec.get('current_stock_qty', 0) or 0)
        projected_monthly_sale_qty = float(brand_row.get('monthly_sales_qty', brand_row.get('monthly_sale_qty', 0)) or 0)
        cases_needed = ceil(recommended_qty / 12) if recommended_qty > 0 else 0

        df_rows.append({
            'Index': brand_row.get('index_number', 'N/A'),
            'Brand Name': brand_name,
            'Current Stock Qty': current_stock_qty,
            'Recommended Qty': recommended_qty,
            'Cases Needed': cases_needed,
            'Projected Monthly Sale Qty': projected_monthly_sale_qty,
            'Wholesale Rate': wholesale_rate,
            'Projected Purchase Value': round(recommended_qty * wholesale_rate, 2),
            'Urgency': rec.get('urgency_level', 'low'),
        })

    df = pd.DataFrame(df_rows)
    output = BytesIO()

    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Demand List')

    output.seek(0)
    return StreamingResponse(
        output,
        media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        headers={'Content-Disposition': 'attachment; filename=demand_list.xlsx'}
    )


async def delete_upload_history_item(upload_id: str) -> Dict[str, Any]:
    result = await collections.upload_history.delete_one({'id': upload_id})
    if not result.deleted_count:
        raise HTTPException(status_code=404, detail='Upload history not found')
    return {'success': True, 'upload_id': upload_id}


async def cleanup_upload_history() -> Dict[str, Any]:
    result = await collections.upload_history.delete_many({'undone_at': {'$ne': None}})
    return {'success': True, 'deleted_count': result.deleted_count}


async def fix_database_integrity() -> Dict[str, Any]:
    rows = await collections.liquor_data.find({}, {'_id': 0}).to_list(5000)
    updated = 0
    seen = set()

    for row in rows:
        brand_name = row.get('brand_name')
        if not brand_name or brand_name in seen:
            continue
        seen.add(brand_name)

        update_data = {}
        if 'selling_rate' not in row and 'rate' in row:
            update_data['selling_rate'] = row.get('rate', 0)
        if 'rate' not in row and 'selling_rate' in row:
            update_data['rate'] = row.get('selling_rate', 0)
        if 'daily_sales' not in row:
            update_data['daily_sales'] = {}

        if update_data:
            await collections.liquor_data.update_one({'id': row.get('id')}, {'$set': update_data})
            updated += 1

    return {'success': True, 'updated_records': updated}


async def cleanup_historical_averages() -> Dict[str, Any]:
    result = await collections.brands_master.delete_many({})
    return {'success': True, 'deleted_count': result.deleted_count}
