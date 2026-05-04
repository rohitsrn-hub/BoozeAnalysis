from datetime import datetime, timezone
from typing import Any, Dict, List
from fastapi import HTTPException
from app.db.mongo import collections
from app.services.parser_service import parse_inventory_file
from app.services.calculation_service import calculate_sales_metrics
from app.utils.date_utils import to_iso_date


async def upload_todays_inventory(file_content: bytes, filename: str) -> Dict[str, Any]:
    parsed_rows = parse_inventory_file(file_content, filename)
    if not parsed_rows:
        raise HTTPException(status_code=400, detail='No valid brand data found in today\'s file')

    date_candidates = []
    for row in parsed_rows:
        date_candidates.extend(list((row.get('daily_sales') or {}).keys()))
    if not date_candidates:
        raise HTTPException(status_code=400, detail='No valid date column found in today\'s file')

    new_date = sorted(set([d for d in date_candidates if d]))[-1]
    existing_records = await collections.liquor_data.find({}, {'daily_sales': 1, 'dl_date': 1}).to_list(5000)
    existing_dates = set()
    for record in existing_records:
        if record.get('dl_date'):
            existing_dates.add(to_iso_date(record.get('dl_date')) or str(record.get('dl_date')))
        for key in (record.get('daily_sales') or {}).keys():
            existing_dates.add(to_iso_date(key) or str(key))
    if new_date in existing_dates:
        raise HTTPException(status_code=409, detail=f'Date {new_date} already exists in database')

    brands_updated = {}
    brands_added = []
    updated_count = 0
    new_brands_count = 0

    for row in parsed_rows:
        brand_name = row['brand_name']
        new_stock_qty = float(row.get('current_stock_qty', 0) or 0)
        existing_brand = await collections.liquor_data.find_one({'brand_name': brand_name})

        if existing_brand:
            brands_updated[existing_brand['id']] = {
                'dl_date': existing_brand.get('dl_date'),
                'dl_stock': existing_brand.get('dl_stock'),
                'current_stock_qty': existing_brand.get('current_stock_qty'),
                'total_sales_qty': existing_brand.get('total_sales_qty'),
                'avg_daily_sales_qty': existing_brand.get('avg_daily_sales_qty'),
                'days_analyzed': existing_brand.get('days_analyzed'),
                'monthly_sale_value': existing_brand.get('monthly_sale_value'),
                'avg_daily_sale': existing_brand.get('avg_daily_sale'),
                'stock_value_today': existing_brand.get('stock_value_today'),
                'stock_available_days': existing_brand.get('stock_available_days'),
                'stock_ratio': existing_brand.get('stock_ratio'),
            }

            daily_sales = existing_brand.get('daily_sales', {}) or {}
            daily_sales[new_date] = new_stock_qty

            metrics = calculate_sales_metrics(
                brand_name=brand_name,
                rate=float(existing_brand.get('selling_rate', existing_brand.get('rate', 0)) or 0),
                date_stock_map=daily_sales,
            )

            selling_rate = float(existing_brand.get('selling_rate', existing_brand.get('rate', 0)) or 0)
            avg_daily = float(metrics['avg_daily_sales_qty'] or 0)
            current_stock = float(metrics['current_stock_qty'] or 0)

            update_data = {
                'daily_sales': daily_sales,
                'dl_date': metrics['dl_date'],
                'dl_stock': metrics['dl_stock'],
                'current_stock_qty': current_stock,
                'total_sales_qty': metrics['total_sales_qty'],
                'avg_daily_sales_qty': avg_daily,
                'days_analyzed': metrics['days_analyzed'],
                'monthly_sale_value': metrics['monthly_sale_value'],
                'avg_daily_sale': avg_daily,
                'stock_value_today': current_stock * selling_rate,
                'stock_available_days': round(current_stock / avg_daily, 2) if avg_daily else 0,
                'stock_ratio': round(current_stock / avg_daily, 2) if avg_daily else 0,
                'calculation_method': metrics['calculation_method'],
                'replenishment_detected': metrics['replenishment_detected'],
            }

            await collections.liquor_data.update_one({'id': existing_brand['id']}, {'$set': update_data})
            updated_count += 1
        else:
            row['daily_sales'] = {new_date: new_stock_qty}
            row['d1_date'] = new_date
            row['dl_date'] = new_date
            row['d1_stock'] = new_stock_qty
            row['dl_stock'] = new_stock_qty
            row['days_analyzed'] = 0
            row['total_sales_qty'] = 0
            row['avg_daily_sales_qty'] = 0
            row['monthly_sale_value'] = 0
            row['avg_daily_sale'] = 0
            row['stock_value_today'] = new_stock_qty * float(row.get('selling_rate', row.get('rate', 0)) or 0)
            row['stock_available_days'] = 0
            row['stock_ratio'] = 0
            row['upload_timestamp'] = datetime.now(timezone.utc)

            await collections.liquor_data.insert_one(row)
            brands_added.append(row['id'])
            new_brands_count += 1

    upload_history = {
        'id': f'daily-{datetime.now(timezone.utc).timestamp()}',
        'filename': filename,
        'upload_type': 'daily_update',
        'upload_timestamp': datetime.now(timezone.utc),
        'records_count': updated_count + new_brands_count,
        'file_size': len(file_content),
        'uploaded_by': 'dashboard_user',
        'can_undo': True,
        'changes_snapshot': {
            'brands_updated': brands_updated,
            'brands_added': brands_added,
            'date_added': new_date,
        },
    }

    await collections.upload_history.insert_one(upload_history)

    return {
        'success': True,
        'new_date_column': new_date,
        'updated_count': updated_count,
        'new_brands_count': new_brands_count,
    }
