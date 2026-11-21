from __future__ import annotations
from langchain.tools import tool
from collections import defaultdict
from typing import Iterable


@tool
def organize_by_category(expenses: Iterable[dict]) -> dict:
    '''Group travel expenses by category and compute per-category subtotals'''
    grouped = defaultdict(lambda: {"items": [], "subtotal": 0.0})

    for expense in expenses:
        category = expense.get("category", "uncategorized")
        amount = expense.get("amount", 0)
        grouped[category]["items"].append(expense)
        grouped[category]["subtotal"] += amount

    for category_data in grouped.values():
        category_data["subtotal"] = round(category_data["subtotal"], 2)

    return dict(grouped)

@tool
def calculate_total_cost(expenses: Iterable[dict]) -> float:
    '''Calculate the total estimated cost across all travel expenses'''
    total = sum(expense.get("amount", 0) for expense in expenses)
    return round(total, 2)
