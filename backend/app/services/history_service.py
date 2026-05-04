from datetime import datetime, timezone
from typing import Any, Dict, List
from fastapi import HTTPException
from app.db.mongo import collections


def _serialize_datetime(value):
    if value and hasattr(value, 'isoformat'):
        return value.isoformat()
    return value


async def get_upload_history_records() -> List[Dict[str, Any]]:
    rows = await collections.upload_history.find().sort('upload_timestamp', -1).to_list(1000)
    result = []
    for row in rows:
        result.append({
            'id': row.get('id'),
            'filename': row.get('filename', 'Unknown'),
            'upload_type': row.get('upload_type', 'unknown'),
            'upload_timestamp': _serialize_datetime(row.get('upload_timestamp')) or datetime.now(timezone.utc).isoformat(),
            'records_count': row.get('records_count', 0),
            'file_size': row.get('file_size', 0),
            'uploaded_by': row.get('uploaded_by', 'dashboard_user'),
            'can_undo': row.get('can_undo', False),
            'undone_at': _serialize_datetime(row.get('undone_at')),
        })
    return result


async def undo_upload_by_id(upload_id: str) -> Dict[str, Any]:
    upload_record = await collections.upload_history.find_one({'id': upload_id})
    if not upload_record:
        raise HTTPException(status_code=404, detail='Upload history not found')
    if upload_record.get('undone_at'):
        raise HTTPException(status_code=400, detail='This upload has already been undone')
    if not upload_record.get('can_undo', False):
        raise HTTPException(status_code=400, detail='This upload cannot be undone')

    changes_snapshot = upload_record.get('changes_snapshot', {})
    upload_type = upload_record.get('upload_type')
    brands_reverted = 0
    brands_deleted = 0

    if upload_type == 'full_monthly':
        backup_id = changes_snapshot.get('backup_id')
        if not backup_id:
            raise HTTPException(status_code=400, detail='No backup available for this upload')
        backup_record = await collections.stock_backups.find_one({'$or': [{'id': backup_id}, {'backup_id': backup_id}]})
        if not backup_record:
            raise HTTPException(status_code=404, detail='Backup not found')
        restored_data = backup_record.get('data_snapshot', [])
        await collections.liquor_data.delete_many({})
        if restored_data:
            await collections.liquor_data.insert_many(restored_data)
        brands_reverted = len(restored_data)
    elif upload_type == 'daily_update':
        brands_updated = changes_snapshot.get('brands_updated', {})
        brands_added = changes_snapshot.get('brands_added', [])
        date_added = changes_snapshot.get('date_added')
        for brand_id, previous_state in brands_updated.items():
            brand_record = await collections.liquor_data.find_one({'id': brand_id})
            if not brand_record:
                continue
            current_daily_sales = brand_record.get('daily_sales', {})
            if date_added and date_added in current_daily_sales:
                del current_daily_sales[date_added]
            await collections.liquor_data.update_one(
                {'id': brand_id},
                {'$set': {
                    'daily_sales': current_daily_sales,
                    'dl_date': previous_state.get('DL_date') or previous_state.get('dl_date'),
                    'dl_stock': previous_state.get('DL_stock') or previous_state.get('dl_stock'),
                    'current_stock_qty': previous_state.get('current_stock_qty'),
                    'total_sales_qty': previous_state.get('total_sales_qty'),
                    'avg_daily_sales_qty': previous_state.get('avg_daily_sales_qty'),
                    'days_analyzed': previous_state.get('days_analyzed'),
                    'monthly_sale_value': previous_state.get('monthly_sale_value'),
                    'avg_daily_sale': previous_state.get('avg_daily_sale'),
                    'stock_value_today': previous_state.get('stock_value_today'),
                    'stock_available_days': previous_state.get('stock_available_days'),
                    'stock_ratio': previous_state.get('stock_ratio'),
                }}
            )
            brands_reverted += 1
        if brands_added:
            result = await collections.liquor_data.delete_many({'id': {'$in': brands_added}})
            brands_deleted = result.deleted_count
    else:
        raise HTTPException(status_code=400, detail=f'Undo not supported for upload type: {upload_type}')

    await collections.upload_history.update_one({'id': upload_id}, {'$set': {'undone_at': datetime.now(timezone.utc)}})
    return {
        'success': True,
        'upload_id': upload_id,
        'upload_type': upload_type,
        'brands_reverted': brands_reverted,
        'brands_deleted': brands_deleted,
    }
