from fastapi import APIRouter, File, UploadFile
from app.routes.uploads import upload_full_monthly_data
from app.services.maintenance_service import (
    export_demand_list_file,
    delete_upload_history_item,
    cleanup_upload_history,
    fix_database_integrity,
    cleanup_historical_averages,
)

router = APIRouter(prefix='/api', tags=['final'])


@router.post('/upload-data')
async def upload_data(file: UploadFile = File(...)):
    return await upload_full_monthly_data(file)


@router.get('/export-demand-list')
async def export_demand_list():
    return await export_demand_list_file()


@router.delete('/upload-history/{upload_id}')
async def delete_upload_history(upload_id: str):
    return await delete_upload_history_item(upload_id)


@router.delete('/upload-history/cleanup')
async def upload_history_cleanup():
    return await cleanup_upload_history()


@router.post('/admin/fix-database-integrity')
async def admin_fix_database_integrity():
    return await fix_database_integrity()


@router.delete('/historical-averages/cleanup')
async def historical_averages_cleanup():
    return await cleanup_historical_averages()
