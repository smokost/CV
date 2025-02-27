from typing import Any

from sqlalchemy import UnaryExpression, asc, desc


def parse_order_by_string(order_by: str) -> list[UnaryExpression[Any]]:
    items = (item.strip().lower() for item in order_by.split(','))
    return [desc(item[1:]) if item.startswith('-') else asc(item) for item in items]
