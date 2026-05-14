from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any


def parse_date(text: str, end_of_day: bool = False) -> str:
    text = text.strip()
    fmts = ["%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d"]
    for fmt in fmts:
        try:
            dt = datetime.strptime(text, fmt)
            if end_of_day:
                return dt.strftime("%Y-%m-%d 23:59:59")
            return dt.strftime("%Y-%m-%d 00:00:00")
        except ValueError:
            pass
    raise ValueError(f"Không parse được ngày: {text}")


def localize_iso(value: Any) -> Any:
    if not isinstance(value, str) or not value:
        return value
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return dt.astimezone().strftime("%Y-%m-%d %H:%M:%S %z")
    except Exception:
        return value


def display_date(value: Any) -> str:
    if value in (None, ""):
        return ""
    if isinstance(value, datetime):
        return value.astimezone().strftime("%d/%m/%Y") if value.tzinfo else value.strftime("%d/%m/%Y")
    text = str(value).strip()
    if not text:
        return ""
    try:
        iso_dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if iso_dt.tzinfo:
            return iso_dt.astimezone().strftime("%d/%m/%Y")
        return iso_dt.strftime("%d/%m/%Y")
    except Exception:
        pass
    fmts = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
        "%d/%m/%Y",
    ]
    for fmt in fmts:
        try:
            return datetime.strptime(text, fmt).strftime("%d/%m/%Y")
        except ValueError:
            pass
    return text


def display_number(value: Any) -> Any:
    if value in (None, ""):
        return ""
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value) if value.is_integer() else value
    try:
        number = Decimal(str(value).replace(",", "").strip())
    except (InvalidOperation, ValueError):
        return value
    if number == number.to_integral_value():
        return int(number)
    return float(number)


def lookup_label(value: Any, mapping: dict[str, str]) -> Any:
    if value in (None, ""):
        return ""
    return mapping.get(str(value), value)
