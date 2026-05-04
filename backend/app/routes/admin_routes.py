from fastapi import APIRouter, Body, File, UploadFile
from app.db.mongo import collections
from app.services.daily_upload_service import upload_todays_inventory
from app.services.backup_service import (
    create_stock_backup,
    list_stock_backups,
    download_stock_backup,
    restore_stock_backup,
    delete_stock_backup,
    reset_stock_data,
)
from app.services.historical_service import (
    get_historical_periods,
    get_historical_data_view,
    get_historical_analysis,
    get_historical_averages,
    calculate_historical_averages,
)
from app.services.report_service import get_report_data, generate_excel_report, generate_pdf_report

router = APIRouter(prefix='/api', tags=['admin'])


@router.post('/upload-todays-data')
async def upload_todays_data(file: UploadFile = File(...)):
    content = await file.read()
    return await upload_todays_inventory(content, file.filename or 'todays-upload.xlsx')


@router.delete('/clear-data')
async def clear_data():
    result = await collections.liquor_data.delete_many({})
    return {'success': True, 'deleted_records': result.deleted_count}


@router.post('/refresh-analytics')
async def refresh_analytics():
    return {'success': True, 'message': 'Analytics are derived live from database records'}


@router.post('/stock/backup')
async def stock_backup():
    return await create_stock_backup()


@router.get('/stock/backups')
async def stock_backups():
    return await list_stock_backups()


@router.get('/stock/backup/{backup_id}/download')
async def stock_backup_download(backup_id: str):
    return await download_stock_backup(backup_id)


@router.post('/stock/backup/{backup_id}/restore')
async def stock_backup_restore(backup_id: str):
    return await restore_stock_backup(backup_id)


@router.delete('/stock/backup/{backup_id}')
async def stock_backup_delete(backup_id: str):
    return await delete_stock_backup(backup_id)


@router.post('/stock/reset')
async def stock_reset():
    return await reset_stock_data()


@router.get('/historical-periods')
async def historical_periods():
    return await get_historical_periods()


@router.post('/historical-data-view')
async def historical_data_view(payload: dict = Body(...)):
    return await get_historical_data_view(payload.get('period_ids', []))


@router.post('/historical-analysis')
async def historical_analysis(payload: dict = Body(...)):
    return await get_historical_analysis(payload.get('period_ids', []))


@router.get('/historical-averages')
async def historical_averages(month: str | None = None):
    return await get_historical_averages(month)


@router.post('/calculate-historical-averages')
async def calculate_historical_avg():
    return await calculate_historical_averages()


@router.get('/analytics-source')
async def analytics_source():
    return {'source': 'live_database', 'calculation_basis': 'stock_difference_estimate'}


@router.get('/reports/data')
async def reports_data():
    return await get_report_data()


@router.post('/reports/generate-excel')
async def reports_excel():
    return await generate_excel_report()


@router.post('/reports/generate-pdf')
async def reports_pdf():
    return await generate_pdf_report()


@router.post('/clear-all-data')
async def clear_all_data():
    liquor = await collections.liquor_data.delete_many({})
    history = await collections.upload_history.delete_many({})
    backups = await collections.stock_backups.delete_many({})
    return {
        'success': True,
        'liquor_deleted': liquor.deleted_count,
        'history_deleted': history.deleted_count,
        'backups_deleted': backups.deleted_count
    }
