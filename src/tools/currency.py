from __future__ import annotations
from langchain.tools import tool
import requests

FRANKFURTER_RATES_URL = "https://api.frankfurter.dev/v2/rates"

@tool
def convert_currency(amount: float, source_currency: str, target_currency: str) -> dict:
    '''Converts an amount between currencies using current exchange rates'''
    source_currency = source_currency.upper()
    target_currency = target_currency.upper()

    response = requests.get(
        FRANKFURTER_RATES_URL,
        params={"base": source_currency, "quotes": target_currency},
        timeout=10,
    )
    response.raise_for_status()
    rows = response.json()

    if not isinstance(rows, list) or not rows:
        raise ValueError(f"Unsupported currency pair: {source_currency} -> {target_currency}")

    match = next((row for row in rows if row.get("quote") == target_currency), None)
    if not match or "rate" not in match:
        raise ValueError(f"Unsupported currency pair: {source_currency} -> {target_currency}")

    rate = float(match["rate"])
    converted_amount = amount * rate

    return {
        "amount": amount,
        "source_currency": source_currency,
        "target_currency": target_currency,
        "exchange_rate": round(rate, 6),
        "converted_amount": round(converted_amount, 2),
        "date": match.get("date"),
    }
