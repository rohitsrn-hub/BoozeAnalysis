from datetime import datetime, timezone
from io import BytesIO
from typing import Any, Dict, List
from fastapi import HTTPException
from fastapi.responses import StreamingResponse
import json
from app.db.mongo import collections


async def create_stock_backup(reason: str = 'manual_backup') -> Dict[str, Any]:
    rows = await collections.liquor_data.find({}, {'_id': 0}).to_list(5000)
    backup_id = f'backup-{datetime.now(timezone.utc).timestamp()}'
    payload = {
        'id': backup_id,
        'created_at': datetime.now(timezone.utc),
        'total_records': len(rows),
        'data_snapshot': rows,
        'backup_reason': reason,
    }
    await collections.stock_backups.insert_one(payload)
    return {'success': True, 'backup_id': backup_id, 'total_records': len(rows)}


async def list_stock_backups() -> List[Dict[str, Any]]:
    rows = await collections.stock_backups.find({}, {'_id': 0}).sort('created_at', -1).to_list(1000)
    for row in rows:
        created_at = row.get('created_at')
        if created_at and hasattr(created_at, 'isoformat'):
            row['created_at'] = created_at.isoformat()
        row.pop('data_snapshot', None)
    return rows


async def download_stock_backup(backup_id: str):
    backup = await collections.stock_backups.find_one({'id': backup_id}, {'_id': 0})
    if not backup:
        raise HTTPException(status_code=404, detail='Backup not found')
    payload = json.dumps(backup, default=str, indent=2).encode('utf-8')
    return StreamingResponse(
        BytesIO(payload),
        media_type='application/json',
        headers={'Content-Disposition': f'attachment; filename={backup_id}.json'}
    )


async def restore_stock_backup(backup_id: str) -> Dict[str, Any]:
    backup = await collections.stock_backups.find_one({'id': backup_id}, {'_id': 0})
    if not backup:
        raise HTTPException(status_code=404, detail='Backup not found')
    rows = backup.get('data_snapshot', [])
    await collections.liquor_data.delete_many({})
    if rows:
        await collections.liquor_data.insert_many(rows)
    return {'success': True, 'restored_records': len(rows), 'backup_id': backup_id}


async def delete_stock_backup(backup_id: str) -> Dict[str, Any]:
    result = await collections.stock_backups.delete_one({'id': backup_id})
    if not result.deleted_count:
        raise HTTPException(status_code=404, detail='Backup not found')
    return {'success': True, 'backup_id': backup_id}


async def reset_stock_data() -> Dict[str, Any]:
    result = await collections.liquor_data.delete_many({})
    return {'success': True, 'deleted_records': result.deleted_count}
