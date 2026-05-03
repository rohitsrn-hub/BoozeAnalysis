from datetime import datetime, timedelta
from typing import Optional
import math
import pandas as pd

DATE_FORMATS = [
    '%d/%m/%Y', '%d-%m-%Y', '%Y-%m-%d', '%d/%m/%y', '%d-%m-%y',
    '%d/%m', '%d-%m', '%m/%d/%Y', '%m-%d-%Y'
]


def parse_excel_serial(value: float) -> Optional[datetime]:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    try:
        base = datetime(1899, 12, 30)
        return base + timedelta(days=float(value))
    except Exception:
        return None


def parse_date_value(value) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if hasattr(value, 'to_pydatetime'):
        return value.to_pydatetime()
    if isinstance(value, (int, float)):
        parsed = parse_excel_serial(value)
        if parsed:
            return parsed
    text = str(value).strip()
    if not text:
        return None
    for fmt in DATE_FORMATS:
        try:
            parsed = datetime.strptime(text, fmt)
            if fmt in {'%d/%m', '%d-%m'}:
                parsed = parsed.replace(year=datetime.utcnow().year)
            return parsed
        except ValueError:
            continue
    try:
        parsed = pd.to_datetime(text, dayfirst=True, errors='coerce')
        if pd.isna(parsed):
            return None
        return parsed.to_pydatetime()
    except Exception:
        return None


def to_iso_date(value) -> Optional[str]:
    parsed = parse_date_value(value)
    return parsed.strftime('%Y-%m-%d') if parsed else None
