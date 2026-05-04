from fastapi import APIRouter, Body
from app.services.history_service import get_upload_history_records, undo_upload_by_id
from app.services.analytics_service import (
    get_chart_data,
    get_demand_recommendations,
    get_database_view,
    get_sales_trends,
    get_calculation_details,
)
from app.services.rate_service import get_brand_rates, add_brand, update_brand_rates

router = APIRouter(prefix='/api', tags=['extra'])


@router.get('/upload-history')
async def upload_history():
    return await get_upload_history_records()


@router.post('/upload-history/{upload_id}/undo')
async def undo_upload(upload_id: str):
    return await undo_upload_by_id(upload_id)


@router.get('/charts')
async def charts():
    return await get_chart_data()


@router.get('/demand-recommendations')
async def demand_recommendations():
    return await get_demand_recommendations()


@router.get('/database-view')
async def database_view():
    return await get_database_view()


@router.get('/sales-trends')
async def sales_trends(period: str = 'quarterly', sales_month: str | None = None):
    return await get_sales_trends()


@router.get('/calculation-details')
async def calculation_details():
    return await get_calculation_details()


@router.get('/brands/rates')
async def brand_rates():
    return await get_brand_rates()


@router.post('/brands/add')
async def create_brand(payload: dict = Body(...)):
    return await add_brand(payload)


@router.post('/brands/update-rates')
async def update_rates(payload: list = Body(...)):
    return await update_brand_rates(payload)
