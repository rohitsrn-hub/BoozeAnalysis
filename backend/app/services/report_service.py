from io import BytesIO
from typing import Any, Dict, List
from fastapi.responses import StreamingResponse
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle
from app.db.mongo import collections


async def get_report_data() -> List[Dict[str, Any]]:
    return await collections.liquor_data.find({}, {'_id': 0}).sort('monthly_sale_value', -1).to_list(5000)


async def generate_excel_report():
    rows = await get_report_data()
    df = pd.DataFrame(rows)
    output = BytesIO()

    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Monthly Report')

    output.seek(0)
    return StreamingResponse(
        output,
        media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        headers={'Content-Disposition': 'attachment; filename=monthly_report.xlsx'}
    )


async def generate_pdf_report():
    rows = await get_report_data()
    output = BytesIO()
    doc = SimpleDocTemplate(output, pagesize=A4)

    table_data = [['Brand', 'Sale Qty', 'Sale Value', 'Current Stock']]
    for row in rows[:50]:
        table_data.append([
            str(row.get('brand_name', '')),
            str(row.get('total_sales_qty', 0)),
            str(row.get('monthly_sale_value', 0)),
            str(row.get('current_stock_qty', 0)),
        ])

    table = Table(table_data)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
    ]))

    doc.build([table])
    output.seek(0)

    return StreamingResponse(
        output,
        media_type='application/pdf',
        headers={'Content-Disposition': 'attachment; filename=monthly_report.pdf'}
    )
