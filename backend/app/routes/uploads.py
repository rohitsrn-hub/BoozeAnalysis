from fastapi import APIRouter, File, HTTPException, UploadFile
from app.repositories.liquor_repository import liquor_repository
from app.schemas.liquor import StockBackup, UploadHistory
from app.db.mongo import collections
from app.services.parser_service import parse_inventory_file

router = APIRouter(prefix='/api', tags=['uploads'])

@router.post('/upload-full-monthly-data')
async def upload_full_monthly_data(file: UploadFile = File(...)):
    if not file.filename or not file.filename.endswith(('.xlsx', '.xls', '.csv')):
        raise HTTPException(status_code=400, detail='Only Excel and CSV files are supported')

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail='Empty file uploaded')

    try:
        parsed_data = parse_inventory_file(content, file.filename)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f'Failed to parse file: {exc}') from exc

    if not parsed_data:
        raise HTTPException(status_code=400, detail='No valid records found in the file')

    existing_records = await liquor_repository.list_all()
    if existing_records:
        backup = StockBackup(
            total_records=len(existing_records),
            data_snapshot=existing_records,
            backup_reason='pre_full_monthly_upload',
        )
        await collections.stock_backups.insert_one(backup.model_dump())

    existing_rates = await liquor_repository.get_existing_rates()
    for record in parsed_data:
        previous = existing_rates.get(record['brand_name'])
        if not previous:
            continue
        if not record.get('wholesale_rate'):
            record['wholesale_rate'] = previous['wholesale_rate']
        if not record.get('selling_rate'):
            record['selling_rate'] = previous['selling_rate']
            record['rate'] = previous['selling_rate']
            record['stock_value_today'] = record['current_stock_qty'] * record['selling_rate']
            record['monthly_sale_value'] = record['total_sales_qty'] * record['selling_rate']

    inserted_count = await liquor_repository.replace_all(parsed_data)
    history = UploadHistory(
        filename=file.filename,
        upload_type='full_monthly',
        records_count=inserted_count,
        file_size=len(content),
        changes_snapshot={'replaced_all_records': True},
    )
    await collections.upload_history.insert_one(history.model_dump())

    return {
        'success': True,
        'message': 'Full monthly data uploaded successfully',
        'records_count': inserted_count,
        'warnings': [
            'Sales values are stock-difference estimates and may be affected by replenishment.',
        ],
    }
